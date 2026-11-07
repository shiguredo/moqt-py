"""QUIC / QMux / WebTransport を利用する MOQT server。"""

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from types import TracebackType
from typing import TYPE_CHECKING

from moqt import moqt
from moqt.moq._io import ServerSession as IoServerSession
from moqt.moq._io import ServerTransport
from moqt.moq._runtime import (
    TICK_INTERVAL,
    MessageBody,
    MOQTError,
    NativeEvent,
    Runtime,
    RuntimeEvents,
    TransportOps,
)
from moqt.moq.client import PeerGoaway
from moqt.moq.publisher import Publication
from moqt.moq.transport import Transport

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

# 接続を識別する context。`RuntimeEvents.bind` がコールバックの第 1 引数に渡す。
#
# I/O 層が接続ごとに振る ID を使う。WebTransport の session ID は接続方式によっては
# 存在しないため、識別子には使わない。
ConnectionContext = int

# QUIC 直接接続に WebTransport session が無いことを示す session ID。
QUIC_SESSION_ID = 0


@dataclass(frozen=True, slots=True)
class ServerSession:
    """確立した MOQT server session。"""

    session_id: int
    """WebTransport session の ID。QUIC 直接接続では `QUIC_SESSION_ID` (0)。"""

    address: tuple[str, int]
    """peer のアドレス。"""

    runtime: Runtime
    """この session のランタイム。"""

    async def goaway(self, timeout: int = 0, new_session_uri: bytes = b"") -> None:
        """GOAWAY を送り、セッションの終了を予告する。

        `timeout` は peer が残りの request を終えるまで待つ猶予時間 (ms) である。
        GOAWAY の送信後、peer は新しい request を開始しない。

        `new_session_uri` は移行先のセッション URI である。Server はこれで移行先を
        通知でき、Client は空の URI しか送れない。`MAX_NEW_SESSION_URI_LENGTH` を
        超える値は送信せずに `MOQTError` になる
        (draft-ietf-moq-transport-23 §9.2 (GOAWAY))。
        """
        await self.runtime.send_goaway(timeout, new_session_uri)

    @property
    def peer_max_auth_token_cache_size(self) -> int:
        """peer が SETUP で宣言した MAX_AUTH_TOKEN_CACHE_SIZE を返す。

        宣言が無い場合は 0 である
        (draft-ietf-moq-transport-23 §9.1.3 (MAX_AUTH_TOKEN_CACHE_SIZE))。
        """
        return self.runtime.peer_max_auth_token_cache_size

    @property
    def peer_alias_retention_ms(self) -> int:
        """キャンセル済み peer publisher alias の保持期間 (ms) を返す。

        draft-ietf-moq-transport-23 §3.1.3 (Track Alias) の SHOULD に対応する
        保持期間である。
        """
        return self.runtime.peer_alias_retention_ms

    def set_peer_alias_retention_ms(self, retention_ms: int) -> None:
        """キャンセル済み peer publisher alias の保持期間 (ms) を設定する。

        0 を設定すると保持は実質無効になる。既に登録済みの保持期限は変わらない。
        """
        self.runtime.set_peer_alias_retention_ms(retention_ms)

    @property
    def goaway_drain_ready(self) -> bool:
        """GOAWAY の drain が完了しているかを返す。

        GOAWAY を送った後、購読や fetch の終了を待ってからセッションを閉じる
        判断に使う
        (draft-ietf-moq-transport-23 §6.6.1 (Graceful Session Migration))。
        """
        return self.runtime.goaway_drain_ready

    def goaway_drain_snapshot(self) -> dict[str, list[int]]:
        """GOAWAY の drain を妨げている Request ID を返す。

        キーは `blocking_subscription_request_ids` / `blocking_fetch_request_ids` /
        `blocking_track_status_request_ids` である
        (draft-ietf-moq-transport-23 §6.6.1 (Graceful Session Migration) /
        §9.2 (GOAWAY))。
        """
        return self.runtime.goaway_drain_snapshot()

    def subscription_state(self, request_id: int) -> dict[str, object] | None:
        """指定 Request ID の subscription の状態を返す。

        保持していない Request ID の場合は `None` である。全件は
        `subscriptions()` で取得する。値は状態機械のスナップショットであり、
        参照しても状態は変化しない。
        """
        return self.runtime.subscription_state(request_id)

    def subscriptions(self) -> dict[int, dict[str, object]]:
        """自側が保持する全 subscription の状態を Request ID をキーにして返す。

        値は状態機械のスナップショットであり、参照しても状態は変化しない。
        """
        return self.runtime.subscriptions()

    def fetch_state(self, request_id: int) -> dict[str, object] | None:
        """指定 Request ID の fetch の状態を返す。

        保持していない Request ID の場合は `None` である。全件は `fetches()` で
        取得する。名前は `Client.fetch_state` と揃えている。値は状態機械の
        スナップショットであり、参照しても状態は変化しない。
        """
        return self.runtime.fetch_state(request_id)

    def fetches(self) -> dict[int, dict[str, object]]:
        """自側が保持する全 fetch の状態を Request ID をキーにして返す。

        値は状態機械のスナップショットであり、参照しても状態は変化しない。
        """
        return self.runtime.fetches()

    def track_status_state(self, request_id: int) -> dict[str, object] | None:
        """指定 Request ID の TRACK_STATUS の状態を返す。

        保持していない Request ID の場合は `None` である。全件は
        `track_status_requests()` で取得する。値は状態機械のスナップショットであり、
        参照しても状態は変化しない。
        """
        return self.runtime.track_status_state(request_id)

    def track_status_requests(self) -> dict[int, dict[str, object]]:
        """自側が保持する全 TRACK_STATUS の状態を Request ID をキーにして返す。

        値は状態機械のスナップショットであり、参照しても状態は変化しない。
        """
        return self.runtime.track_status_requests()


@dataclass(slots=True)
class SubscriptionRequest:
    """peer から届いた SUBSCRIBE。"""

    request_id: int
    """SUBSCRIBE の Request ID。"""

    namespace: tuple[bytes, ...]
    """Track Namespace。"""

    track_name: bytes
    """Track 名。"""

    parameters: dict[int, object]
    """購読パラメータ。"""

    runtime: Runtime
    """応答に使うランタイム。"""

    async def subscribe_ok(
        self,
        track_alias: int,
        parameters: dict[int, object] | None = None,
        track_properties: dict[int, object] | None = None,
    ) -> Publication:
        """SUBSCRIBE_OK を返して配信を開始する。

        返る `Publication` は送った SUBSCRIBE_OK のパラメータと Track Properties を
        保持する。publisher が購読条件を確定する値 (EXPIRES / LARGEST_OBJECT /
        GROUP_ORDER / DEFAULT_PUBLISHER_PRIORITY) はここで通知した値である
        (draft-ietf-moq-transport-23 §9.19 (Control Message Parameters))。
        """
        await self.runtime.send_subscribe_ok(
            self.request_id, track_alias, parameters, track_properties
        )
        return Publication(
            request_id=self.request_id,
            track_alias=track_alias,
            namespace=self.namespace,
            track_name=self.track_name,
            runtime=self.runtime,
            parameters=dict(parameters or {}),
            track_properties=dict(track_properties or {}),
        )

    async def reject(self, error_code: int, reason: str) -> None:
        """REQUEST_ERROR を返して購読を拒否する。"""
        await self.runtime.send_request_error(self.request_id, error_code, reason)


@dataclass(slots=True)
class FetchRequest:
    """peer から届いた FETCH。"""

    request_id: int
    """FETCH の Request ID。"""

    namespace: tuple[bytes, ...]
    """Track Namespace。"""

    track_name: bytes
    """Track 名。"""

    parameters: dict[int, object]
    """取得条件のパラメータ。"""

    runtime: Runtime
    """応答に使うランタイム。"""

    async def respond(
        self,
        *,
        parameters: dict[int, object] | None = None,
        track_properties: dict[int, object] | None = None,
    ) -> FetchResponse:
        """FETCH_OK を返して応答ストリームを開く。

        draft-23 では応答範囲の終端は状態機械が要求と LARGEST_OBJECT から確定する。
        `parameters` には EXPIRES / LARGEST_OBJECT などを指定する
        (draft-ietf-moq-transport-23 §9.3 (REQUEST_OK) / §3.2 (Fetch))。
        """
        await self.runtime.send_fetch_ok(
            self.request_id,
            parameters=parameters,
            track_properties=track_properties,
        )
        stream_id = await self.runtime.open_fetch_stream(self.request_id)
        return FetchResponse(
            request_id=self.request_id,
            stream_id=stream_id,
            runtime=self.runtime,
        )

    async def reject(self, error_code: int, reason: str) -> None:
        """REQUEST_ERROR を返して取得を拒否する。"""
        await self.runtime.send_request_error(self.request_id, error_code, reason)


@dataclass(slots=True)
class FetchResponse:
    """配信中の fetch 応答。"""

    request_id: int
    """FETCH の Request ID。"""

    stream_id: int
    """応答に使う fetch stream の ID。"""

    runtime: Runtime
    """送信に使うランタイム。"""

    async def send_object(
        self,
        group_id: int,
        object_id: int,
        payload: bytes,
        *,
        publisher_priority: int = 128,
        subgroup_id: int = 0,
        properties_data: bytes | None = None,
        datagram_origin: bool = False,
    ) -> None:
        """fetch stream へオブジェクトを書き込む。

        オブジェクトは `GROUP_ORDER` で要求された向きの順に送る。逆向きの Group を
        送ろうとすると `MOQTError` になる
        (draft-ietf-moq-transport-23 §9.19.8 (GROUP ORDER Parameter))。

        `properties_data` には `moqt.moqt.ObjectProperties` の encode 結果を渡す。
        `Properties Length` を含む生バイト列であり、宣言長と実データ長が一致しない
        場合は `MOQTError` になる
        (draft-ietf-moq-transport-23 §11.1.2 (Object Properties))。

        `datagram_origin` を真にすると、もともとデータグラムで届いたオブジェクトで
        あることを示す。この場合 Subgroup ID は wire に載らず、受信側では 0 として
        解決される (draft-ietf-moq-transport-23 §11.4.1.1 (Flags))。
        """
        await self.runtime.send_fetch_stream_object(
            self.stream_id,
            group_id,
            object_id,
            payload,
            publisher_priority=publisher_priority,
            subgroup_id=subgroup_id,
            properties_data=properties_data,
            datagram_origin=datagram_origin,
        )

    async def send_end_of_non_existent_range(self, group_id: int, object_id: int) -> None:
        """要求された範囲にオブジェクトが存在しないことを通知する。

        `group_id` と `object_id` は存在しない範囲の終端である。
        (draft-ietf-moq-transport-23 §11.4.2 (End of Range))
        """
        await self.runtime.send_fetch_end_of_range(
            self.stream_id, "end_of_non_existent_range", group_id, object_id
        )

    async def send_end_of_unknown_range(self, group_id: int, object_id: int) -> None:
        """要求された範囲のオブジェクトが不明であることを通知する。

        `group_id` と `object_id` は不明な範囲の終端である。
        (draft-ietf-moq-transport-23 §11.4.2 (End of Range))
        """
        await self.runtime.send_fetch_end_of_range(
            self.stream_id, "end_of_unknown_range", group_id, object_id
        )

    async def send_end_of_gone_range(self, group_id: int, object_id: int) -> None:
        """要求された範囲のオブジェクトが Gone であることを通知する。

        `group_id` と `object_id` は Gone の範囲の終端である。
        (draft-ietf-moq-transport-23 §11.4.2 (End of Range))
        """
        await self.runtime.send_fetch_end_of_range(
            self.stream_id, "end_of_gone_range", group_id, object_id
        )

    async def send_end_of_timed_out_range(self, group_id: int, object_id: int) -> None:
        """要求された範囲のオブジェクトが期限切れで取得できなかったことを通知する。

        `group_id` と `object_id` は期限切れの範囲の終端である。
        (draft-ietf-moq-transport-23 §11.4.1 (Fetch Header) Table 8)
        """
        await self.runtime.send_fetch_end_of_range(
            self.stream_id, "end_of_timed_out_range", group_id, object_id
        )

    async def send_end_of_group(self) -> None:
        """直前のオブジェクトが Group の最終オブジェクトであることを通知する。

        (draft-ietf-moq-transport-23 §11.4.2.2 (Prior Object Fields))
        """
        await self.runtime.send_fetch_end_marker(self.stream_id, "end_of_group")

    async def send_end_of_track(self) -> None:
        """直前のオブジェクトが Track の最終オブジェクトであることを通知する。

        (draft-ietf-moq-transport-23 §11.4.2.2 (Prior Object Fields))
        """
        await self.runtime.send_fetch_end_marker(self.stream_id, "end_of_track")

    async def close(self) -> None:
        """fetch stream を終了する。"""
        await self.runtime.close_fetch_stream(self.stream_id)


@dataclass(slots=True)
class PublisherRequest:
    """peer から届いた PUBLISH。"""

    request_id: int
    """PUBLISH の Request ID。"""

    namespace: tuple[bytes, ...]
    """Track Namespace。"""

    track_name: bytes
    """Track 名。"""

    track_alias: int
    """peer が通知した Track Alias。"""

    parameters: dict[int, object]
    """PUBLISH のパラメータ。"""

    runtime: Runtime
    """応答に使うランタイム。"""

    async def accept(
        self,
        parameters: dict[int, object] | None = None,
        track_properties: dict[int, object] | None = None,
    ) -> Publication:
        """REQUEST_OK を返して配信を受け入れる。

        PUBLISH の応答は REQUEST_OK であり、SUBSCRIBE_OK とは異なり Track Alias を
        運ばない。peer が通知した Track Alias をそのまま使う
        (draft-ietf-moq-transport-23 §9.3 (REQUEST_OK))。

        返る `Publication` は送った REQUEST_OK のパラメータと Track Properties を
        保持する。
        """
        await self.runtime.send_request_ok(self.request_id, parameters, track_properties)
        return Publication(
            request_id=self.request_id,
            track_alias=self.track_alias,
            namespace=self.namespace,
            track_name=self.track_name,
            runtime=self.runtime,
            parameters=dict(parameters or {}),
            track_properties=dict(track_properties or {}),
        )

    async def reject(self, error_code: int, reason: str) -> None:
        """REQUEST_ERROR を返して配信を拒否する。"""
        await self.runtime.send_request_error(self.request_id, error_code, reason)


@dataclass(slots=True)
class _Connection:
    """1 本の接続に対応する MOQT の内部状態。"""

    runtime: Runtime
    address: tuple[str, int]
    session_id: int


class Server:
    """QUIC / QMux / WebTransport 接続上で MOQT を扱う server。"""

    def __init__(
        self,
        host: str,
        port: int,
        *,
        certfile: str,
        keyfile: str,
        transport: Transport = Transport.WebTransportOverHTTP3,
        allowed_origins: list[str] | None = None,
        implementation: str = "moqt-py",
        control_message_timeout: float | None = None,
        data_stream_timeout: float | None = None,
        setup_options: dict[int, object] | None = None,
    ) -> None:
        """server を作成する。

        `transport` は接続方式である。`Transport.Quic` では WebTransport session が無いため、
        接続は address 単位になり、`ServerSession.session_id` は `QUIC_SESSION_ID` (0) に
        なる。`Transport.Qmux` では接続ごとにサーバーが振るセッション ID を使う。
        `allowed_origins` は WebTransport over HTTP/2 の Origin 検査で使う。
        Origin を運ぶ仕組みが無い `Transport.Quic` / `Transport.Qmux` と、Rust の
        WebTransport over HTTP/3 サーバーが Origin ヘッダーを取得できない
        `Transport.WebTransportOverHTTP3` では指定できない。

        `control_message_timeout` と `data_stream_timeout` は peer の停止を検出する
        期限 (秒) である。省略した場合は期限を設けない。設定すると期限切れで
        セッションが終了する
        (draft-ietf-moq-transport-23 §12.2 (Session Termination Codes))。

        `setup_options` は SETUP で送る Setup Option である。キーは Setup Option Type、
        値は偶数型なら `int`、奇数型なら `bytes`、AUTHORIZATION_TOKEN なら Token の
        辞書またはそのリストである。MOQT_IMPLEMENTATION は `implementation` 引数が
        担うため指定できない
        (draft-ietf-moq-transport-23 §16.4 (Setup Options))。
        """
        if transport in {Transport.Quic, Transport.Qmux} and allowed_origins is not None:
            raise ValueError("allowed_origins is not supported for QUIC and QMux")
        if transport is Transport.WebTransportOverHTTP3 and allowed_origins is not None:
            raise ValueError("allowed_origins is not supported for WebTransport over HTTP/3")
        self.transport = transport
        # 接続方式によらず同じトランスポートを使う。証明書の読み込みと ALPN の設定は
        # Rust 側の I/O 層が行う
        self._transport = ServerTransport(
            transport,
            host=host,
            port=port,
            certfile=certfile,
            keyfile=keyfile,
            allowed_origins=allowed_origins,
        )
        self._transport.on_session_ready(self._on_session_ready)
        self._transport.on_session_closed(self._on_session_closed)
        self._transport.on_stream_data(self._on_stream_data)
        self._transport.on_stream_reset(self._on_stream_reset)
        self._transport.on_stop_sending(self._on_stop_sending)
        self._transport.on_datagram(self._on_datagram)
        self._implementation = implementation
        self._control_message_timeout = control_message_timeout
        self._data_stream_timeout = data_stream_timeout
        self._setup_options = dict(setup_options) if setup_options is not None else None
        # 接続を識別する context をキーにした接続
        self._connections: dict[ConnectionContext, _Connection] = {}
        self._on_session_established: Callable[[ServerSession], Awaitable[None]] | None = None
        self._on_subscribe: Callable[[SubscriptionRequest], Awaitable[None]] | None = None
        self._on_fetch: Callable[[FetchRequest], Awaitable[None]] | None = None
        self._publish_callback: Callable[[PublisherRequest], Awaitable[None]] | None = None
        self._request_update_callback: (
            Callable[[Runtime, int, dict[int, object]], Awaitable[None]] | None
        ) = None
        self._fill_fetch_callback: Callable[[Runtime, int, int], Awaitable[None]] | None = None
        self._goaway_callback: Callable[[ServerSession, PeerGoaway], Awaitable[None]] | None = None
        self._event_callback: Callable[[Runtime, NativeEvent], Awaitable[None]] | None = None
        self._tick_task: asyncio.Task[None] | None = None

    # ─── 公開 API ───────────────────────────────────────────

    @property
    def actual_port(self) -> int:
        """実際に待ち受けているポート番号。"""
        return self._transport.actual_port

    def on_session_established(
        self,
        callback: Callable[[ServerSession], Awaitable[None]],
    ) -> None:
        """MOQT SETUP 完了時に呼び出す非同期 callback を設定する。"""
        self._on_session_established = callback

    def on_subscribe(
        self,
        callback: Callable[[SubscriptionRequest], Awaitable[None]],
    ) -> None:
        """peer から SUBSCRIBE が届いたときに呼び出す非同期 callback を設定する。"""
        self._on_subscribe = callback

    def on_fetch(
        self,
        callback: Callable[[FetchRequest], Awaitable[None]],
    ) -> None:
        """peer から FETCH が届いたときに呼び出す非同期 callback を設定する。"""
        self._on_fetch = callback

    def on_publish(
        self,
        callback: Callable[[PublisherRequest], Awaitable[None]],
    ) -> None:
        """peer から PUBLISH が届いたときに呼び出す非同期 callback を設定する。

        コールバックは `PublisherRequest.accept()` で受け入れるか、`reject()` で
        拒否する。未登録の場合は PUBLISH を REQUEST_NOT_SUPPORTED で拒否する。
        """
        self._publish_callback = callback

    def on_request_update(
        self,
        callback: Callable[[Runtime, int, dict[int, object]], Awaitable[None]],
    ) -> None:
        """peer から REQUEST_UPDATE が届いたときに呼び出す非同期 callback を設定する。

        引数はランタイム、request の Request ID、受信パラメータである。コールバックが
        例外を送出すると REQUEST_ERROR で拒否し、それ以外は REQUEST_OK で受け入れる。
        応答はランタイムが送る。未登録の場合は受け入れる。

        request の所有者はランタイムが識別済みである。PUBLISH の応答を返したい場合は
        コールバックで `runtime.send_request_ok(request_id)` を呼ぶ。
        """
        self._request_update_callback = callback

    def on_goaway(
        self,
        callback: Callable[[ServerSession, PeerGoaway], Awaitable[None]],
    ) -> None:
        """peer から GOAWAY が届いたときに呼び出す非同期 callback を設定する。

        引数は GOAWAY を受信した session と、その内容である。GOAWAY の受信後は
        状態機械がその peer への新規 request の送信を拒否する。移行先が通知された
        場合は、アプリが新しいセッションへ接続し直す
        (draft-ietf-moq-transport-23 §9.2 (GOAWAY))。
        """
        self._goaway_callback = callback

    def on_event(
        self,
        callback: Callable[[Runtime, NativeEvent], Awaitable[None]],
    ) -> None:
        """状態機械が生成したすべてのイベントを順序どおりに受け取るコールバックを設定する。

        引数はランタイムとイベントである。種類ごとのコールバックと違い、送信系
        (`send_control` / `send_on_stream` / `reset_request_stream` など) も含めて、
        ランタイムの組み込み処理より先に渡される。到着順やイベント列そのものを
        検証するテストで使う。
        """
        self._event_callback = callback

    def on_fill_fetch_stream(
        self,
        callback: Callable[[Runtime, int, int], Awaitable[None]],
    ) -> None:
        """peer が FILL_PARAMETERS 付きで購読したときに呼ぶコールバックを設定する。

        引数はランタイム、購読の Request ID、開いた fill fetch stream の ID である。
        過去のオブジェクトを補充するには `runtime.send_fetch_stream_object` を使う。
        fill fetch stream は購読の成立に必須ではないため、コールバックが未登録でも
        ストリームは開かれる
        (draft-ietf-moq-transport-23 §3.4 (Fill Semantics))。
        """
        self._fill_fetch_callback = callback

    async def start(self) -> None:
        """WebTransport server を開始する。"""
        await self._transport.start()
        self._tick_task = asyncio.create_task(self._tick_loop())

    async def run(self) -> None:
        """停止されるまで WebTransport server の受信ループを実行する。"""
        await self._transport.run()

    async def stop(self) -> None:
        """全接続と WebTransport server を停止する。"""
        if self._tick_task is not None:
            self._tick_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._tick_task
            self._tick_task = None
        for connection in list(self._connections.values()):
            with contextlib.suppress(Exception):
                await connection.runtime.close()
        self._connections.clear()
        await self._transport.stop()

    # ─── 内部 ───────────────────────────────────────────────

    def _transport_ops(self, session: IoServerSession) -> TransportOps:
        """1 本の session に対応するトランスポート操作を組み立てる。

        WebTransport は server 起点の双方向ストリームを規定していないため、
        双方向ストリームの開設は `MOQTError` にする。QUIC 直接接続と QMux では
        開設できる。
        """

        async def open_bidi_stream() -> int:
            if self.transport in (
                Transport.WebTransportOverHTTP2,
                Transport.WebTransportOverHTTP3,
            ):
                raise MOQTError(
                    "the server cannot open a bidirectional stream; "
                    "server-initiated requests are not available over WebTransport"
                )
            return await session.open_stream(unidirectional=False)

        # STOP_SENDING とセッションの終了は接続方式によらず同じ API で扱う。
        # 終了は MOQT の終了コードと理由をそのまま渡し、peer が失敗を検知できるようにする
        # (draft-ietf-moq-transport-23 §12.2 (Session Termination Codes))。
        return TransportOps(
            open_uni_stream=lambda: session.open_stream(unidirectional=True),
            open_bidi_stream=open_bidi_stream,
            send_stream_data=session.send_stream_data,
            reset_stream=session.reset_stream,
            stop_sending=session.stop_sending,
            send_datagram=session.send_datagram,
            close=lambda code, reason: session.close_session(code, reason),
        )

    def _runtime_events(self, context: ConnectionContext) -> RuntimeEvents:
        """ランタイムのコールバックを組み立てる。

        server は接続ごとにランタイムを作るため、コールバックは接続を
        識別する context を閉じ込めた形で渡す。
        """
        return RuntimeEvents(
            on_event=lambda event: self._on_event(context, event),
            on_established=lambda: self._on_established(context),
            on_request=lambda event: self._on_request(context, event),
            on_request_update=lambda event: self._on_request_update(context, event),
            on_fill_fetch_stream=lambda request_id: self._on_fill_fetch_stream(context, request_id),
            on_goaway=lambda event: self._on_goaway(context, event),
        )

    async def _on_event(self, context: ConnectionContext, event: NativeEvent) -> None:
        """状態機械が生成したすべてのイベントをアプリへ通知する。"""
        callback = self._event_callback
        if callback is None:
            return
        connection = self._connection(context)
        if connection is None:
            return
        await callback(connection.runtime, event)

    async def _on_fill_fetch_stream(self, context: ConnectionContext, request_id: int) -> None:
        """peer が FILL_PARAMETERS 付きで購読したときに fill fetch stream を開く。

        fill は購読の成立に必須ではないため、コールバックが未登録でも
        ストリームは開く。開いたストリーム ID はアプリへ渡す。
        """
        connection = self._connection(context)
        if connection is None:
            return
        stream_id = await connection.runtime.open_fill_fetch_stream(request_id)
        callback = self._fill_fetch_callback
        if callback is not None:
            await callback(connection.runtime, request_id, stream_id)

    async def _on_request_update(self, context: ConnectionContext, event: NativeEvent) -> None:
        """peer からの REQUEST_UPDATE をアプリへ通知する。

        応答 (REQUEST_OK) はランタイムが送る。アプリが例外を送出した場合だけ
        REQUEST_ERROR で拒否される。コールバックが未登録の場合は受け入れる。
        """
        callback = self._request_update_callback
        if callback is None:
            return
        connection = self._connection(context)
        if connection is None:
            return
        await callback(connection.runtime, event.request_id or 0, event.parameters or {})

    async def _on_goaway(self, context: ConnectionContext, event: NativeEvent) -> None:
        """peer からの GOAWAY をアプリへ通知する。

        通知先が未登録の場合も状態機械は GOAWAY を受信済みとして扱う。アプリが
        関心を持つのは移行先と猶予時間だけである。
        """
        callback = self._goaway_callback
        if callback is None:
            return
        connection = self._connection(context)
        if connection is None:
            return
        body = event.message or {}
        new_session_uri = body.get("new_session_uri")
        timeout = body.get("timeout")
        await callback(
            self._server_session(connection),
            PeerGoaway(
                new_session_uri=new_session_uri if isinstance(new_session_uri, bytes) else b"",
                timeout=timeout if isinstance(timeout, int) else 0,
            ),
        )

    def _server_session(self, connection: _Connection) -> ServerSession:
        """接続に対応する `ServerSession` を組み立てる。"""
        return ServerSession(
            session_id=connection.session_id,
            address=connection.address,
            runtime=connection.runtime,
        )

    async def _on_established(self, context: ConnectionContext) -> None:
        """SETUP 完了をアプリケーションへ通知する。"""
        connection = self._connection(context)
        if connection is None:
            return
        if self._on_session_established is not None:
            await self._on_session_established(self._server_session(connection))

    def _connection(self, context: ConnectionContext) -> _Connection | None:
        """コールバックの context から接続を引く。"""
        return self._connections.get(context)

    async def _on_request(self, context: ConnectionContext, event: NativeEvent) -> None:
        """peer からの request を処理する。"""
        connection = self._connection(context)
        if connection is None:
            return
        runtime = connection.runtime
        if event.kind == "fetch":
            if self._on_fetch is None:
                await runtime.send_request_error(
                    event.request_id or 0,
                    0x3,
                    "FETCH is not handled by this server",
                )
                return
            body = event.message
            request = FetchRequest(
                request_id=event.request_id or 0,
                namespace=_body_namespace(body, "track_namespace"),
                track_name=_body_bytes(body, "track_name"),
                parameters=_body_parameters(body),
                runtime=runtime,
            )
            await self._on_fetch(request)
            return
        if event.kind == "publish":
            if self._publish_callback is None:
                await runtime.send_request_error(
                    event.request_id or 0,
                    moqt.REQUEST_NOT_SUPPORTED,
                    "PUBLISH is not handled by this server",
                )
                return
            body = event.message
            request = PublisherRequest(
                request_id=event.request_id or 0,
                namespace=_body_namespace(body, "track_namespace"),
                track_name=_body_bytes(body, "track_name"),
                track_alias=_body_int(body, "track_alias"),
                parameters=_body_parameters(body),
                runtime=runtime,
            )
            await self._publish_callback(request)
            return
        if event.kind != "subscribe":
            # 未対応の request は REQUEST_NOT_SUPPORTED で拒否する。
            # 状態機械が request として受理するのは SUBSCRIBE / PUBLISH / FETCH /
            # TRACK_STATUS であり、それ以外はコールバックへ届かないため、
            # ここで扱うのは SUBSCRIBE のみである
            await runtime.send_request_error(
                event.request_id or 0,
                moqt.REQUEST_NOT_SUPPORTED,
                f"{event.kind} is not supported",
            )
            return
        if self._on_subscribe is None:
            await runtime.send_request_error(
                event.request_id or 0,
                0x3,
                "SUBSCRIBE is not handled by this server",
            )
            return
        body = event.message
        request = SubscriptionRequest(
            request_id=event.request_id or 0,
            namespace=_body_namespace(body, "track_namespace"),
            track_name=_body_bytes(body, "track_name"),
            parameters=_body_parameters(body),
            runtime=runtime,
        )
        await self._on_subscribe(request)

    async def _open_connection(self, session: IoServerSession) -> _Connection:
        """1 本の接続で server role の MOQT Session を開始する。"""
        context = session.connection_id
        if context in self._connections:
            raise RuntimeError(
                f"duplicate connection: id={session.connection_id} from {session.addr}"
            )
        runtime = Runtime(
            client=False,
            implementation=self._implementation,
            ops=self._transport_ops(session),
            events=self._runtime_events(context),
            transport=self.transport,
            control_message_timeout=self._control_message_timeout,
            data_stream_timeout=self._data_stream_timeout,
            setup_options=self._setup_options,
        )
        connection = _Connection(
            runtime=runtime,
            address=session.addr if session.addr is not None else ("", 0),
            session_id=session.session_id,
        )
        self._connections[context] = connection
        await runtime.start()
        return connection

    async def _on_session_ready(self, session: IoServerSession) -> None:
        """接続の確立で MOQT Session を開始する。

        QUIC 直接接続と QMux には WebTransport session が無いが、I/O 層は
        どちらも接続の確立を通知するため、接続方式による分岐は要らない。
        """
        await self._open_connection(session)

    async def _on_session_closed(self, session: IoServerSession) -> None:
        """閉じた接続の MOQT 状態を破棄する。"""
        self._connections.pop(session.connection_id, None)

    async def _on_stream_data(
        self,
        session: IoServerSession,
        stream_id: int,
        data: bytes,
        fin: bool,
    ) -> None:
        """受信データを状態機械へ渡す。

        FIN はリセットではないため `reset=False` で通知する。
        """
        await self._receive_stream(session.connection_id, stream_id, data)
        if not fin:
            return
        connection = self._connections.get(session.connection_id)
        if connection is not None:
            await connection.runtime.receive_stream_closed(stream_id, reset=False, error_code=None)

    async def _on_stream_reset(
        self,
        session: IoServerSession,
        stream_id: int,
        error_code: int | None,
    ) -> None:
        """ストリームリセットを状態機械へ通知する。

        WT-H3 で `error_code` が `None` の場合は「アプリケーションエラーコード無しの
        リセット」である (draft-ietf-webtrans-http3-16 §4.4 (Resetting Data Streams))。
        WT-H2 では WT_RESET_STREAM が MOQT のエラーコードをそのまま運ぶため常に
        コードがある (draft-ietf-moq-transport-23 §12.5 (Stream Reset Error Codes))。
        """
        connection = self._connections.get(session.connection_id)
        if connection is not None:
            await connection.runtime.receive_stream_closed(
                stream_id, reset=True, error_code=error_code
            )

    async def _on_datagram(self, session: IoServerSession, data: bytes) -> None:
        """データグラムを状態機械へ渡す。"""
        connection = self._connections.get(session.connection_id)
        if connection is not None and not connection.runtime.closed:
            await connection.runtime.receive_datagram(data)

    async def _on_stop_sending(
        self,
        session: IoServerSession,
        stream_id: int,
        error_code: int | None,
    ) -> None:
        """ピアからの STOP_SENDING を状態機械へ通知する。

        WT-H2 の WT_STOP_SENDING は MOQT のエラーコードをそのまま運ぶ
        (draft-ietf-moq-transport-23 §12.5 (Stream Reset Error Codes))。WT-H3 では
        WT_APPLICATION_ERROR レンジ外のコードが「アプリケーションエラーコード無し」と
        して `None` で届く (draft-ietf-webtrans-http3-16 §4.4 (Resetting Data Streams))。
        """
        connection = self._connections.get(session.connection_id)
        if connection is not None:
            await connection.runtime.receive_stop_sending(stream_id, error_code)

    async def _receive_stream(
        self,
        context: ConnectionContext,
        stream_id: int,
        data: bytes,
    ) -> None:
        """受信データをストリーム種別に振り分ける。

        状態機械が拒否するデータを peer が送っても server は動き続ける。拒否の理由は
        状態機械が保持し、session の終了は `Runtime.closed` で観測できる。
        client 側の `_on_stream_data` と同じ扱いである。
        """
        connection = self._connections.get(context)
        if connection is None:
            # セッション終了と受信イベントの配送が競合した場合である。接続は
            # 既に無いため、届いたデータは状態機械へ渡さない
            logger.debug("MOQT stream data arrived for a closed connection: %s", context)
            return
        try:
            await connection.runtime.receive_stream(stream_id, data)
        except Exception as error:
            logger.warning(
                "MOQT stream from %s was rejected: session=%s stream=%s error=%s",
                connection.address,
                connection.session_id,
                stream_id,
                error,
            )

    async def _tick_loop(self) -> None:
        """セッションのタイムアウト判定を定期的に実行する。"""
        while True:
            await asyncio.sleep(TICK_INTERVAL)
            for connection in list(self._connections.values()):
                if connection.runtime.closed:
                    continue
                with contextlib.suppress(Exception):
                    await connection.runtime.tick()

    async def __aenter__(self) -> Server:
        await self.start()
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.stop()


def _body_namespace(body: MessageBody | None, key: str) -> tuple[bytes, ...]:
    """メッセージ本体から Track Namespace を取り出す。"""
    if body is None:
        return ()
    value = body.get(key)
    if not isinstance(value, list):
        return ()
    return tuple(field for field in value if isinstance(field, bytes))


def _body_bytes(body: MessageBody | None, key: str) -> bytes:
    """メッセージ本体からバイト列を取り出す。"""
    if body is None:
        return b""
    value = body.get(key)
    return value if isinstance(value, bytes) else b""


def _body_int(body: MessageBody | None, key: str) -> int:
    """メッセージ本体から整数を取り出す。"""
    if body is None:
        return 0
    value = body.get(key)
    return value if isinstance(value, int) else 0


def _body_parameters(body: MessageBody | None) -> dict[int, object]:
    """メッセージ本体からパラメータを取り出す。"""
    if body is None:
        return {}
    value = body.get("parameters")
    if not isinstance(value, dict):
        return {}
    return {key: item for key, item in value.items() if isinstance(key, int)}


__all__ = [
    "FetchRequest",
    "FetchResponse",
    "Publication",
    "PublisherRequest",
    "Server",
    "ServerSession",
    "SubscriptionRequest",
]
