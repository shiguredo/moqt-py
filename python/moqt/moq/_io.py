"""Rust の I/O 層と asyncio を接続する内部モジュール。

QUIC / WebTransport / QMux の接続・ストリーム・データグラムは ``moqt._native`` の
``IoClient`` / ``IoServer`` が担当する。このモジュールは、その非同期 API を
``moqt.moq`` のトランスポートとして扱える形にまとめ、イベントを登録済みの
コールバックへ配送する。

状態機械の駆動は Python 側に残す。Rust 側はバイト列の送受信と接続の終了だけを
扱い、MOQT のメッセージ境界や要求の状態には関与しない。
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from moqt._native import IoClient, IoEvent, IoServer
from moqt.moq.transport import MOQT_PROTOCOL, Transport

logger = logging.getLogger(__name__)

# ストリームデータを受け取るコールバック。
StreamDataCallback = Callable[[int, bytes, bool], Awaitable[None]]
# ストリームのリセットを受け取るコールバック。
StreamResetCallback = Callable[[int, int | None], Awaitable[None]]
# ピアからの STOP_SENDING を受け取るコールバック。
StopSendingCallback = Callable[[int, int | None], Awaitable[None]]
# データグラムを受け取るコールバック。
DatagramCallback = Callable[[bytes], Awaitable[None]]
# セッションの確立と終了を受け取るコールバック。
SessionReadyCallback = Callable[[int], Awaitable[None]]
SessionClosedCallback = Callable[[], Awaitable[None]]
# サーバー側で接続ごとのイベントを受け取るコールバック。
ServerStreamDataCallback = Callable[["ServerSession", int, bytes, bool], Awaitable[None]]
ServerStreamResetCallback = Callable[["ServerSession", int, int | None], Awaitable[None]]
ServerStopSendingCallback = Callable[["ServerSession", int, int | None], Awaitable[None]]
ServerDatagramCallback = Callable[["ServerSession", bytes], Awaitable[None]]
ServerSessionCallback = Callable[["ServerSession"], Awaitable[None]]


class TransportClosedError(ConnectionError):
    """ピアがトランスポートを終了したことを表す例外。

    ``error_code`` と ``reason`` はピアが通知した終了コードと理由である。
    QUIC では CONNECTION_CLOSE のアプリケーションエラー、WebTransport では
    ``WT_CLOSE_SESSION`` の値、QMux では CONNECTION_CLOSE の値になる。
    """

    def __init__(self, code: int, reason: str) -> None:
        super().__init__(f"transport closed: code={code} reason={reason}")
        self.error_code = code
        """ピアが通知した終了コード。"""
        self.reason = reason
        """ピアが通知した終了理由。"""


def _application_protocols(transport: Transport) -> list[str]:
    """WebTransport の `WT-Available-Protocols` で提示するプロトコルを返す。

    MOQT は WebTransport のサブプロトコルとして MOQT のプロトコル識別子を通知する
    (draft-ietf-moq-transport-23 §6.2 (Session establishment) /
    draft-ietf-webtrans-http3-16 §3.3)。
    """
    if transport in (Transport.WebTransportOverHTTP2, Transport.WebTransportOverHTTP3):
        return [MOQT_PROTOCOL]
    return []


def _alpn_protocols(transport: Transport) -> list[bytes]:
    """接続方式ごとに ALPN へ載せる識別子を返す。

    QUIC 直接接続と QMux は MOQT のプロトコル識別子、WebTransport over HTTP/3 は
    ``h3``、WebTransport over HTTP/2 は ``h2`` を使う
    (draft-ietf-moq-transport-23 §6.2 (Session establishment) /
    draft-ietf-webtrans-http3-16 §3.1 / draft-ietf-webtrans-http2-16 §3.1)。
    """
    if transport in (Transport.Quic, Transport.Qmux):
        return [MOQT_PROTOCOL.encode()]
    if transport is Transport.WebTransportOverHTTP2:
        return [b"h2"]
    return [b"h3"]


class ClientTransport:
    """クライアントのトランスポート。

    ``Client`` の接続を 1 本だけ持ち、ストリームとデータグラムの操作を Rust の
    トランスポートへ委譲する。``connect()`` を呼ぶまで Rust のオブジェクトは
    作らない。イベントループの外で ``Client`` を構築できるようにするためである。
    """

    def __init__(
        self,
        transport: Transport,
        *,
        host: str,
        port: int,
        path: str,
        authority: str,
        verify_peer: bool,
        origin: str,
        ca_file: str | None,
    ) -> None:
        self.transport = transport
        """接続方式。"""
        self.url = f"https://{authority}{path}" if transport in (
            Transport.WebTransportOverHTTP2,
            Transport.WebTransportOverHTTP3,
        ) else f"moqt://{authority}{path}"
        """接続先の URL。"""
        self._host = host
        self._port = port
        self._path = path
        self._authority = authority
        self._verify_peer = verify_peer
        self._origin = origin
        self._ca_file = ca_file
        self._queue: asyncio.Queue[IoEvent] = asyncio.Queue()
        self._io: IoClient | None = None
        self._closing = False
        self._last_close: tuple[int, str] | None = None
        self._on_stream_data: StreamDataCallback | None = None
        self._on_stream_reset: StreamResetCallback | None = None
        self._on_stop_sending: StopSendingCallback | None = None
        self._on_datagram: DatagramCallback | None = None
        self._on_session_ready: SessionReadyCallback | None = None
        self._on_session_closed: SessionClosedCallback | None = None

    # ─── コールバック ───────────────────────────────────────

    def on_stream_data(self, callback: StreamDataCallback) -> None:
        """ストリームデータを受け取るコールバックを登録する。"""
        self._on_stream_data = callback

    def on_stream_reset(self, callback: StreamResetCallback) -> None:
        """ストリームのリセットを受け取るコールバックを登録する。"""
        self._on_stream_reset = callback

    def on_stop_sending(self, callback: StopSendingCallback) -> None:
        """ピアからの STOP_SENDING を受け取るコールバックを登録する。"""
        self._on_stop_sending = callback

    def on_datagram(self, callback: DatagramCallback) -> None:
        """データグラムを受け取るコールバックを登録する。"""
        self._on_datagram = callback

    def on_session_ready(self, callback: SessionReadyCallback) -> None:
        """セッションの確立を受け取るコールバックを登録する。"""
        self._on_session_ready = callback

    def on_session_closed(self, callback: SessionClosedCallback) -> None:
        """セッションの終了を受け取るコールバックを登録する。"""
        self._on_session_closed = callback

    # ─── 接続 ───────────────────────────────────────────────

    async def connect(self, timeout: float = 10.0) -> None:
        """接続を確立する。

        ``timeout`` は接続の確立までの期限 (秒) である。期限を過ぎた場合は
        ``TimeoutError`` になる。
        """
        io = IoClient(
            kind=str(self.transport),
            host=self._host,
            port=self._port,
            path=self._path,
            authority=self._authority,
            server_name=self._host,
            alpn=_alpn_protocols(self.transport),
            protocols=_application_protocols(self.transport),
            verify_peer=self._verify_peer,
            ca_file=self._ca_file,
            origin=self._origin,
            sink=self._queue.put_nowait,
        )
        self._io = io
        await asyncio.wait_for(io.connect(), timeout)

    async def run(self) -> None:
        """イベントを配送し続ける。

        トランスポートが終了すると戻る。ピアが終了コード付きで終了した場合は
        :class:`TransportClosedError` を送出する。
        """
        while True:
            event = await self._queue.get()
            if event.kind == "end":
                break
            await self._dispatch(event)
        # 終了コードはピア起点でも状態機械の判断でも同じように伝える。自側の
        # close() はコード 0 で終了するため、ここで例外になるのは異常終了だけである
        if self._last_close is not None:
            code, reason = self._last_close
            if code != 0:
                raise TransportClosedError(code, reason)

    async def close(self, error_code: int = 0, error_message: str = "") -> None:
        """接続を終了する。

        終了処理は best-effort であり、既に終了している場合は何もしない。
        """
        if self._io is None:
            return
        self._closing = True
        try:
            await self._io.close(error_code=error_code, reason=error_message)
        except (ConnectionError, RuntimeError) as error:
            # ピアが先に終了した場合や、ドライバが既に停止している場合である。
            # 終了処理は完了しているため、利用者へ伝える意味は無い。
            logger.debug("transport is already closed: %s", error)

    # ─── ストリーム操作 ─────────────────────────────────────

    async def open_stream(self, *, bidirectional: bool = False) -> int:
        """ストリームを開設し、ストリーム ID を返す。"""
        io = self._require_io()
        return int(await io.open_stream(bidirectional=bidirectional))

    async def send_stream_data(self, stream_id: int, data: bytes, fin: bool = False) -> None:
        """ストリームへデータを書き込む。"""
        await self._require_io().send_stream_data(stream_id=stream_id, data=data, fin=fin)

    async def reset_stream(self, stream_id: int, error_code: int = 0) -> None:
        """ストリームの送信側をリセットする。"""
        await self._require_io().reset_stream(stream_id=stream_id, error_code=error_code)

    async def stop_sending(self, stream_id: int, error_code: int = 0) -> None:
        """ストリームの受信側へ STOP_SENDING を送る。"""
        await self._require_io().stop_sending(stream_id=stream_id, error_code=error_code)

    async def send_datagram(self, data: bytes) -> None:
        """データグラムを送る。"""
        await self._require_io().send_datagram(data=data)

    # ─── 内部 ───────────────────────────────────────────────

    def _require_io(self) -> IoClient:
        """接続済みの Rust トランスポートを返す。"""
        io = self._io
        if io is None:
            raise RuntimeError("the transport is not connected")
        return io

    async def _dispatch(self, event: IoEvent) -> None:
        """イベントを登録済みのコールバックへ配送する。"""
        kind = event.kind
        if kind == "stream_data":
            callback = self._on_stream_data
            if callback is not None:
                await callback(
                    int(event.stream_id or 0),
                    bytes(event.data or b""),
                    event.fin,
                )
        elif kind == "stream_reset":
            callback = self._on_stream_reset
            if callback is not None:
                await callback(int(event.stream_id or 0), event.error_code)
        elif kind == "stop_sending":
            callback = self._on_stop_sending
            if callback is not None:
                await callback(int(event.stream_id or 0), event.error_code)
        elif kind == "datagram":
            callback = self._on_datagram
            if callback is not None:
                await callback(bytes(event.data or b""))
        elif kind == "session_ready":
            callback = self._on_session_ready
            if callback is not None:
                await callback(event.session_id)
        elif kind == "session_closed":
            self._last_close = (int(event.code or 0), event.reason or "")
            callback = self._on_session_closed
            if callback is not None:
                await callback()
        elif kind == "error":
            logger.warning("transport error: %s", event.message)


class ServerSession:
    """サーバー側の 1 本の接続。

    WebTransport では ``session_id`` がセッション ID になり、QUIC 直接接続では 0、
    QMux では接続ごとに振られる ID になる。
    """

    def __init__(
        self,
        server: IoServer,
        transport: Transport,
        connection_id: int,
        session_id: int,
        address: tuple[str, int] | None,
    ) -> None:
        self._server = server
        self._transport = transport
        self.connection_id = connection_id
        """Rust の I/O 層が接続ごとに振る ID。"""
        self.session_id = session_id
        """WebTransport セッション ID。QUIC 直接接続では 0 である。"""
        self.addr = address
        """ピアのアドレス。取得できなかった場合は ``None`` である。"""

    @property
    def transport(self) -> Transport:
        """接続方式。"""
        return self._transport

    async def open_stream(self, *, unidirectional: bool = True) -> int:
        """ストリームを開設し、ストリーム ID を返す。"""
        return int(
            await self._server.open_stream(
                connection_id=self.connection_id,
                bidirectional=not unidirectional,
            )
        )

    async def send_stream_data(self, stream_id: int, data: bytes, fin: bool = False) -> None:
        """ストリームへデータを書き込む。"""
        await self._server.send_stream_data(
            connection_id=self.connection_id,
            stream_id=stream_id,
            data=data,
            fin=fin,
        )

    async def reset_stream(self, stream_id: int, error_code: int = 0) -> None:
        """ストリームの送信側をリセットする。"""
        await self._server.reset_stream(
            connection_id=self.connection_id,
            stream_id=stream_id,
            error_code=error_code,
        )

    async def stop_sending(self, stream_id: int, error_code: int = 0) -> None:
        """ストリームの受信側へ STOP_SENDING を送る。"""
        await self._server.stop_sending(
            connection_id=self.connection_id,
            stream_id=stream_id,
            error_code=error_code,
        )

    async def send_datagram(self, data: bytes) -> None:
        """データグラムを送る。"""
        await self._server.send_datagram(connection_id=self.connection_id, data=data)

    async def close_session(self, error_code: int = 0, reason: str = "") -> None:
        """接続を終了する。

        終了処理は best-effort であり、ピアが先に終了している場合は何もしない。
        """
        try:
            await self._server.close_session(
                connection_id=self.connection_id,
                error_code=error_code,
                reason=reason,
            )
        except (ConnectionError, RuntimeError) as error:
            # ピアが先に終了した場合や、ドライバが既に停止している場合である。
            # 終了処理は完了しているため、利用者へ伝える意味は無い。
            logger.debug("transport is already closed: %s", error)


class ServerTransport:
    """サーバーのトランスポート。

    ``start()`` で待ち受けを開始し、``run()`` で接続ごとのイベントを配送する。
    ``start()`` を呼ぶまで Rust のオブジェクトは作らない。
    """

    def __init__(
        self,
        transport: Transport,
        *,
        host: str,
        port: int,
        certfile: str,
        keyfile: str,
        allowed_origins: list[str] | None,
    ) -> None:
        self.transport = transport
        """接続方式。"""
        self._host = host
        self._port = port
        self._certfile = certfile
        self._keyfile = keyfile
        self._allowed_origins = allowed_origins
        self._queue: asyncio.Queue[IoEvent] = asyncio.Queue()
        self._io: IoServer | None = None
        self._sessions: dict[int, ServerSession] = {}
        self._on_session_ready: ServerSessionCallback | None = None
        self._on_session_closed: ServerSessionCallback | None = None
        self._on_stream_data: ServerStreamDataCallback | None = None
        self._on_stream_reset: ServerStreamResetCallback | None = None
        self._on_stop_sending: ServerStopSendingCallback | None = None
        self._on_datagram: ServerDatagramCallback | None = None

    @property
    def actual_port(self) -> int:
        """実際に待ち受けているポート番号。開始前は 0 である。"""
        io = self._io
        return 0 if io is None else io.actual_port

    # ─── コールバック ───────────────────────────────────────

    def on_session_ready(self, callback: ServerSessionCallback) -> None:
        """接続の確立を受け取るコールバックを登録する。"""
        self._on_session_ready = callback

    def on_session_closed(self, callback: ServerSessionCallback) -> None:
        """接続の終了を受け取るコールバックを登録する。"""
        self._on_session_closed = callback

    def on_stream_data(self, callback: ServerStreamDataCallback) -> None:
        """ストリームデータを受け取るコールバックを登録する。"""
        self._on_stream_data = callback

    def on_stream_reset(self, callback: ServerStreamResetCallback) -> None:
        """ストリームのリセットを受け取るコールバックを登録する。"""
        self._on_stream_reset = callback

    def on_stop_sending(self, callback: ServerStopSendingCallback) -> None:
        """ピアからの STOP_SENDING を受け取るコールバックを登録する。"""
        self._on_stop_sending = callback

    def on_datagram(self, callback: ServerDatagramCallback) -> None:
        """データグラムを受け取るコールバックを登録する。"""
        self._on_datagram = callback

    # ─── 待ち受け ───────────────────────────────────────────

    async def start(self) -> None:
        """待ち受けを開始する。"""
        io = IoServer(
            kind=str(self.transport),
            host=self._host,
            port=self._port,
            certfile=self._certfile,
            keyfile=self._keyfile,
            alpn=_alpn_protocols(self.transport),
            protocols=_application_protocols(self.transport),
            allowed_origins=self._allowed_origins,
            sink=self._queue.put_nowait,
        )
        self._io = io
        await io.start()

    async def run(self) -> None:
        """停止されるまで接続ごとのイベントを配送する。"""
        while True:
            event = await self._queue.get()
            # 接続ごとの終了はその接続の終端であり、待ち受けは続く。待ち受けの
            # 終了は connection_id が 0 の end で通知される
            if event.kind == "end":
                if event.connection_id == 0:
                    return
                continue
            await self._dispatch(event)

    async def stop(self) -> None:
        """待ち受けを停止する。"""
        io = self._io
        if io is None:
            return
        try:
            await io.stop()
        except (ConnectionError, RuntimeError) as error:
            # 既に停止している場合は送る先が無い。終了処理なので失敗にしない。
            logger.debug("server transport is already stopped: %s", error)
        self._sessions.clear()

    # ─── 内部 ───────────────────────────────────────────────

    def _session(self, event: IoEvent) -> ServerSession | None:
        """イベントが属する接続を返す。"""
        session = self._sessions.get(event.connection_id)
        if session is None:
            logger.warning(
                "received an event for an unknown connection: %d (kind=%s)",
                event.connection_id,
                event.kind,
            )
        return session

    async def _dispatch(self, event: IoEvent) -> None:
        """イベントを登録済みのコールバックへ配送する。"""
        kind = event.kind
        if kind == "session_ready":
            io = self._io
            if io is None:
                return
            session = ServerSession(
                io,
                self.transport,
                event.connection_id,
                event.session_id,
                event.address,
            )
            self._sessions[event.connection_id] = session
            callback = self._on_session_ready
            if callback is not None:
                await callback(session)
            return
        if kind == "session_closed":
            session = self._sessions.pop(event.connection_id, None)
            if session is None:
                return
            callback = self._on_session_closed
            if callback is not None:
                await callback(session)
            return
        session = self._session(event)
        if session is None:
            return
        if kind == "stream_data":
            callback = self._on_stream_data
            if callback is not None:
                await callback(
                    session,
                    int(event.stream_id or 0),
                    bytes(event.data or b""),
                    event.fin,
                )
        elif kind == "stream_reset":
            callback = self._on_stream_reset
            if callback is not None:
                await callback(session, int(event.stream_id or 0), event.error_code)
        elif kind == "stop_sending":
            callback = self._on_stop_sending
            if callback is not None:
                await callback(session, int(event.stream_id or 0), event.error_code)
        elif kind == "datagram":
            callback = self._on_datagram
            if callback is not None:
                await callback(session, bytes(event.data or b""))
        elif kind == "error":
            logger.warning("transport error: %s", event.message)
