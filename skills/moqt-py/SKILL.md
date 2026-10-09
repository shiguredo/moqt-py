---
name: moqt-py
description: Python の MOQT ライブラリ moqt-py (import 名 moqt) の利用リファレンス。MOQT / LOC / MSF / C4M の codec と sans I/O セッション状態機械、WebTransport / QUIC で接続する moqt.moq の client、E2E テスト向けの moqt.moq.testing の使い方に関する質問で使用。
---

# moqt-py

MOQT (Media over QUIC Transport) の codec と sans I/O セッション状態機械を提供する Python ライブラリ。本体は I/O を持たない低レベル API で、WebTransport / QUIC の I/O は `moqt.moq` が [webtransport-py](https://pypi.org/project/webtransport-py/) に委ねる。

人間向けの使い方は `docs/USAGE.md` にある。このファイルは API の一覧と注意点をまとめたリファレンスである。

## インストールと動作環境

```bash
uv add moqt-py
```

- 配布名は `moqt-py`、import 名は `moqt`
- Python 3.14 / 3.14t (Free-Threading)
- wheel は配布しておらず、Rust 1.93 以降の toolchain でソースからビルドする
- 対応プラットフォームは macOS 26 arm64、Ubuntu 26.04 / 24.04 の x86_64 と arm64
- `moqt.moq.testing` を使う場合は `uv add "moqt-py[testing]"` (`pytest` / `pytest-asyncio` / `cryptography` が入る)

## モジュール構成

| やりたいこと | 使うもの |
|---|---|
| MOQT のバイト列を組み立てる / 解析する | `moqt.moqt` |
| MOQT の sans I/O セッション状態機械を回す | `moqt.moqt.Session` |
| LOC のプロパティを encode / decode する | `moqt.loc` |
| MSF のカタログとタイムラインを扱う | `moqt.msf` |
| C4M のトークンと DPoP proof を扱う | `moqt.c4m` |
| WebTransport / QUIC で MOQT セッションを張る | `moqt.moq.Client` |
| E2E テストで client の相手役を立てる | `moqt.moq.testing` |

## moqt.moqt

MOQT の codec と sans I/O セッション状態機械。ストリームの実体には触れず、呼び出し側が peer とのバイト列の受け渡しを行う。

```python
from moqt.moqt import Session, decode_message, decode_varint

# 自側の制御ストリームの先頭バイト列を作る
session = Session.client("my-implementation")
data = session.start()
# 先頭は制御ストリームの stream type (0x2F00) の varint 表現
print(decode_varint(data))

# 制御メッセージを 1 件デコードする
message, consumed = decode_message(data[2:])
print(message.kind, hex(message.type_id), message.body)
```

### Session

`Session.client(implementation="moqt-py", setup_options=None, transport="wt-h3")` と `Session.server(...)` で作る。`transport` は `moqt.moq.Transport` の値であり、QUIC 直接接続では AUTHORITY と PATH を SETUP に載せ、WebTransport では載せない。

回し方は「受信バイト列を `receive_*` へ渡す → 戻り値の `Event` を見る → `send_*` が返すバイト列を送出する」の繰り返しである。SETUP の交換は次のように書ける。

```python
from moqt.moqt import Session

client = Session.client("my-client")
server = Session.server("my-server")

# start() は自側の制御ストリームの先頭バイト列 (SETUP) を返す。
# 自側の start() を呼んでから peer のバイト列を受け取る
client_setup = client.start()
server_setup = server.start()
server.receive_control(client_setup)
client.receive_control(server_setup)
print(client.established, server.established)
```

| 分類 | メソッド |
|---|---|
| 開始 / 終了 | `start()` / `close(code, reason)` |
| 受信 | `receive_control()` / `receive_control_stream_closed()` / `receive_request_stream()` / `receive_request_stream_closed()` / `receive_data_stream()` / `receive_data_stream_closed()` / `receive_datagram()` / `recv_data_stream_stop_sending()` / `report_mid_object_fin()` / `retry_pending_data_streams()` / `drain_pending_events()` |
| 送信 | `send_subscribe()` / `send_publish()` / `send_fetch()` / `send_request_ok()` / `send_request_error()` / `send_subscribe_ok()` / `send_fetch_ok()` / `send_publish_done()` / `send_publish_state_notify()` / `send_goaway()` / `send_object_datagram()` / `send_padding_stream()` / `send_padding_datagram()` |
| ストリーム | `register_local_request_stream()` / `reset_outgoing_data_stream()` / `send_data_stream_closed()` / `send_fetch_header()` / `send_fetch_object()` |
| 状態 | `established` / `role()` / `last_error` / `peer_setup_options()` / `subscriptions()` / `fetches()` / `goaway_drain_ready()` / `goaway_drain_snapshot()` / `next_local_request_id()` |
| 回収 | `forget_subscription()` / `forget_fetch()` / `forget_track_status()` |

全 API は型スタブ `python/moqt/_native.pyi` の `class Session` にある。

### codec 関数

- `encode_varint()` / `decode_varint()` / `decode_varint_prefix()`
- `decode_message()` / `decode_parameter()`
- `classify_data_stream_type()` / `setup_stream_type()` / `is_padding_datagram()`

### パラメータとプロパティ

- `MessageParameters`: draft が定める型と意味でパラメータを読み書きする
- `TrackProperties` / `ObjectProperties`: 偶数型は `int`、奇数型は `bytes` の辞書として扱う
- `LocationFilter` / `LocationFilterUpdate`: `LOCATION_FILTER` の型付き表現。パラメータの辞書の値としてそのまま渡せる

`Event.parameters` と `Message.parameters` は「型番号をキーにしたエンコード済みバイト列の辞書」を返す。同じ形式の辞書が `Session.send_*` と `moqt.moq` の `parameters` 引数に対する入力であり、受信した辞書をそのまま送信経路へ渡せる。

### 定数

- ストリーム種別: `SETUP_STREAM_TYPE` / `FETCH_HEADER_TYPE` / `PADDING_STREAM_TYPE` / `PADDING_DATAGRAM_TYPE`
- SETUP オプション: `SETUP_OPTION_AUTHORITY` / `SETUP_OPTION_PATH` / `SETUP_OPTION_AUTHORIZATION_TOKEN` / `SETUP_OPTION_MAX_AUTH_TOKEN_CACHE_SIZE` / `SETUP_OPTION_MAX_FILTER_RANGES` / `SETUP_OPTION_MOQT_IMPLEMENTATION` / `SETUP_OPTION_MAX_REQUEST_UPDATES`
- パラメータ: `PARAM_*`
- 終了コード: `SESSION_*` / `REQUEST_*` / `PUBLISH_DONE_*` / `STREAM_*`
- Object Status: `OBJECT_STATUS_NORMAL` / `OBJECT_STATUS_END_OF_GROUP` / `OBJECT_STATUS_END_OF_TRACK`
- Subgroup ID モード: `SUBGROUP_ID_MODE_ZERO` / `SUBGROUP_ID_MODE_FIRST_OBJECT_ID` / `SUBGROUP_ID_MODE_EXPLICIT`
- プロパティ型: `PROP_*`
- GREASE: `GREASE_BASE` / `GREASE_INTERVAL` / `GREASE_MAX` と `generate()` / `is_grease()`
- 上限: `MAX_DATAGRAM_SIZE` (1100) / `MAX_NEW_SESSION_URI_LENGTH` / `PUBLISHER_PRIORITY_DEFAULT` / `DEFAULT_SUBSCRIBER_PRIORITY` / `DEFAULT_PEER_ALIAS_RETENTION_MS`

## moqt.loc

LOC (Low Overhead Media Container) のプロパティ codec。プロパティ ID の偶奇で値の型が決まり、偶数 ID は vi64、奇数 ID は長さ付きバイト列である。

```python
from moqt import loc

properties = loc.Properties()
properties.add(loc.TIMESTAMP, 1_234_567)
properties.add(loc.TIMESCALE, 90000)
properties.add(loc.VIDEO_FRAME_MARKING, b"\x80")

encoded = properties.encode()
decoded, consumed = loc.Properties.decode(encoded)
print(decoded.timestamp, decoded.timescale, decoded.video_frame_marking)
```

- プロパティ ID: `TIMESTAMP` / `TIMESCALE` / `VIDEO_FRAME_MARKING` / `AUDIO_LEVEL` / `VIDEO_CONFIG` / `AUDIO_CONFIG`
- LOC Properties は Public と Private に分かれ、Public は MOQT の Object Properties、Private は Object Payload に置く。どちらに置くかはアプリケーション層の責務であり、このモジュールは区別しない

## moqt.msf

MSF (MOQT Streaming Format) のカタログ・メディアタイムライン・イベントタイムライン・URI を扱う。カタログと delta 更新は draft の MUST に照らして検証され、違反は `ValueError` になる。

```python
from moqt import msf

catalog = msf.Catalog.parse(
    '{"version":"draft-01","tracks":[{"name":"video","packaging":"loc","isLive":true}]}'
)
print(catalog.tracks)

# delta 更新を適用する
catalog.apply_delta('{"deltaUpdate":[{"op":"remove","tracks":[{"name":"video"}]}]}')
print(catalog.encode())

# JSON 文字列を経由せずに組み立てる
built = msf.Catalog()
built.add_track(msf.Track("video", "loc", True))
delta = msf.DeltaUpdate()
delta.add_tracks([msf.Track("audio", "loc", True)])
delta.clone_tracks([msf.CloneTrack("video-low", "video")])
built.apply_delta_update(delta)

# タイムラインは gzip 圧縮にも対応する
timeline = msf.MediaTimeline()
timeline.add(1000, 1, 2, 0)
print(msf.MediaTimeline.decode(timeline.encode(gzip=True)).entries)
```

- 型: `Catalog` / `Track` / `CloneTrack` / `RemoveTrack` / `DeltaUpdate` / `MediaTimeline` / `EventTimeline` / `Uri` / `Template` / `InitData` / `Buffers` / `Accessibility` / `AuthInfo`
- 定数: `MSF_VERSION` / `CATALOG_TRACK_NAME` (カタログは `catalog` という Track 名で配信する)
- Track 識別子 (`namespace--track`) の相互変換: `parse_name()` / `serialize_name()`、構成要素は `parse_namespace()` / `serialize_namespace()` / `parse_track_name()` / `serialize_track_name()`。`moqt.c4m.AuthorizationContext` が要求する `tns` / `tn` はこの表現である
- そのほか `parse_msf_fragment()` / `parse_fragment_pairs()` / `resolve_catalog_variables()` / `resolve_timeline_template()`

## moqt.c4m

C4M (Common Access Token for MoQ) のトークンと DPoP proof の codec。CBOR / COSE / CWT / CAT と JWK / JWS compact も公開する。署名と検証は aws-lc-rs を使う。

```python
from moqt import c4m

# `example.com` の `video-` prefix を PUBLISH できるスコープを組み立てる
scope = c4m.MoqtScope([c4m.MoqtAction.PUBLISH])
scope.namespace_match(c4m.NamespaceMatch.match(c4m.Match.exact(b"example.com")))
scope.track = c4m.Match.prefix(b"video-")
claim = c4m.MoqtClaim()
claim.scope(scope)

# CAT トークンを compact 形式で発行する
builder = c4m.CatTokenBuilder()
builder.issuer("https://auth.example.com")
builder.audience("https://relay.example.com")
builder.expiration(1_700_086_400.0)
builder.moqt(claim)
key = c4m.CoseKey.symmetric(bytes(range(32)))
token_text = builder.build_compact(key)

# 検証と認可
token = c4m.CatToken.decode(token_text)
token.verify(key)
token.claims.validate(c4m.ClaimValidationOptions(reference_time_seconds=1_700_000_000.0))
assert token.claims.authorize(c4m.MoqtAction.PUBLISH, (b"example.com",), b"video-hd")
print(token.format, token.claims.issuer)
```

- クレーム: `MoqtAction` / `Match` / `NamespaceMatch` / `MoqtScope` / `MoqtClaim` / `CatDpop`
- CBOR: `CborValue` と `encode_cbor()` / `decode_cbor()` / `decode_cbor_partial()`
- COSE: `CoseHeader` / `CoseMessage` / `CoseEncodingOptions`、鍵と暗号は `CoseKey` / `EcCurve` / `OkpCurve` と `sign()` / `verify()` / `digest()`
- CAT: `CatToken` / `CatClaims` / `Confirmation` / `CatTokenBuilder` / `ClaimValidationOptions` / `VerifyOptions`
- JWK / JWT: `Jwk` / `JwsHeader` / `JwsCompact`
- DPoP: `DpopProof` / `DpopProofBuilder` / `AuthorizationContext` / `DpopReplayCache`
- 整数の識別子を持つ enum (`MoqtAction` / `Algorithm` / `EcCurve` / `OkpCurve`) は `enum.IntEnum` であり、native 側の関数へそのまま渡せる
- Track Namespace は `tuple[bytes, ...]`、Track Name は `bytes` で扱う。デコードと検証の失敗は `ValueError` になる
- クレームとヘッダの定数は `CLAIM_*` / `HEADER_*` / `TAG_*` / `CONFIRMATION_*` / `CAT_*` / `DPOP_*` / `MOQT_*` に分かれている
- 付録 A のテストベクタは `tests/test_c4m.py` で固定している

## moqt.moq

WebTransport (WT-H3 / WT-H2) と QUIC 直接接続で MOQT セッションを張る client。公開 API は client だけで、server は `moqt.moq.testing` に置く。

```python
import asyncio

from moqt.moq import Client


async def main() -> None:
    # verify_peer=False は自己署名証明書を使う開発時の設定
    client = Client(url="moqt://127.0.0.1:4433/webtransport", verify_peer=False)
    await client.connect()
    print(client.established)

    # Track を購読し、届いたオブジェクトを順に処理する
    subscription = await client.subscribe([b"moqt-py", b"test"], b"video")
    async for obj in subscription.objects():
        print(obj.group_id, obj.object_id, len(obj.payload), obj.status)

    await client.close()


asyncio.run(main())
```

### Client

`Client(url, *, transport=None, verify_peer=True, origin="", ca_file=None, implementation="moqt-py", control_message_timeout=None, data_stream_timeout=None, setup_options=None)`

- `url` は MOQT の URI (`moqt://host:port/path`)。`transport` を省略すると WT-H3 になる
- `ca_file` は WT-H3 と QUIC だけで使える。WT-H2 では `ValueError` になる
- `control_message_timeout` と `data_stream_timeout` は peer の停止を検出する期限 (秒)。省略時は期限を設けない
- `setup_options` は SETUP で送る Setup Option。AUTHORITY と PATH は QUIC 直接接続のときだけ指定できる
- 1 接続 = 1 セッションであり、`Client` が接続と MOQT セッションを兼ねる

| メソッド | 内容 |
|---|---|
| `await connect(timeout=10.0)` | 接続し、MOQT SETUP の完了を待つ |
| `await close()` | セッションと接続を閉じる |
| `await subscribe(namespace, track_name, parameters=None)` | SUBSCRIBE を送り `Subscription` を返す |
| `await publish(namespace, track_name, track_alias, parameters=None, track_properties=None)` | PUBLISH を送り `Publication` を返す |
| `await fetch(namespace, track_name, parameters=None)` | FETCH を送り `Fetch` を返す |
| `await goaway(timeout=0, new_session_uri=b"")` | GOAWAY を送りセッションの終了を予告する |
| `established` | MOQT SETUP が完了しているか |
| `peer_setup_options` / `peer_goaway` / `peer_max_auth_token_cache_size` / `peer_alias_retention_ms` | peer が通知した値 |
| `goaway_drain_ready` / `goaway_drain_snapshot()` | GOAWAY の drain の状態 |
| `subscription_state()` / `subscriptions()` / `fetch_state()` / `fetches()` | 状態機械のスナップショット |
| `on_event()` / `on_goaway()` / `on_request_update()` / `on_publish_state_notify()` | コールバック登録 |

### Transport

| 値 | 接続方式 |
|---|---|
| `Transport.WebTransportOverHTTP3` | WT-H3 (省略時) |
| `Transport.WebTransportOverHTTP2` | WT-H2 |
| `Transport.Quic` | QUIC 直接接続。ALPN に `moqt.moq.transport.MOQT_PROTOCOL` (`moqt-22`) を提示する |

### 購読・配信・取得

- `Subscription`: `request_id` / `track_alias` / `namespace` / `track_name` / `parameters` / `track_properties` と、`objects()` (非同期イテレータ) / `close()` / `request_update()`
- `Publication`: `send_object()` (subgroup ストリーム) / `send_datagram()` / `send_publish_state_notify()` / `close()` / `reset_subgroup()` / `reset_subgroup_at()`
- `Fetch`: `objects()` / `ranges()` / `cancel()` と `end_of_track` / `end_location`
- `MOQTObject`: `stream_id` (データグラムは `None`) / `group_id` / `object_id` / `payload` / `status` / `properties` / `publisher_priority` / `subgroup_id`
- `PeerGoaway`: 受信した GOAWAY の `new_session_uri` と `timeout`

### オブジェクトの送信

`Publication.send_object` は subgroup ストリームで、`Publication.send_datagram` はデータグラムで送る。

```python
from moqt import moqt
from moqt.moq import SUBGROUP_ID_MODE_EXPLICIT, SUBGROUP_ID_MODE_FIRST_OBJECT_ID

# subgroup ストリームで送る
await publication.send_object(1, 0, b"payload")

# Subgroup ID を明示する
await publication.send_object(
    2,
    0,
    b"payload",
    subgroup_id=3,
    subgroup_id_mode=SUBGROUP_ID_MODE_EXPLICIT,
)

# Subgroup ID を最初の Object ID にする (Subgroup ID フィールドの分だけ wire が短くなる)
await publication.send_object(3, 0, b"payload", subgroup_id_mode=SUBGROUP_ID_MODE_FIRST_OBJECT_ID)

# End of Group を通知する。このとき payload は空でなければならない
await publication.send_object(4, 0, b"", status=moqt.OBJECT_STATUS_END_OF_GROUP)

# データグラムで送る
await publication.send_datagram(5, 0, b"datagram payload")

# データグラムで Group の終端を宣言する
# (同じ Group ID でこれより大きい Object ID の Object は存在しない)
await publication.send_datagram(6, 0, b"last in group", end_of_group=True)
```

- Subgroup ID のモードは Group ごとに固定されるため、モードを変えるときは Group を分ける
- 同じ Location のオブジェクトは subgroup とデータグラムのどちらか一方しか届かない。データグラムには subgroup と重複しない Location を選ぶ
- データグラムの `end_of_group` は Group の終端を宣言する。受信側は宣言位置を終端として記録し、それより大きい Object ID の Object を Malformed Track として拒否する。`status` との同時指定は無効である (§11.2.1 (Object Datagram) / §12.1 (Malformed Tracks))
- データグラムは経路 MTU を超えると通知なく破棄され、送信側からは検知できない。`moqt.moqt.MAX_DATAGRAM_SIZE` (1100) を超えると警告を記録する。大きいオブジェクトは subgroup ストリームで送る
- 受信側では、Subgroup ID を最初の Object ID として決めるモードでも、最初のオブジェクトを受信した時点で `MOQTObject.subgroup_id` に値が入る

### 低レベル API

`moqt.moq` は低レベル API を隠さない。テストから実装の細部 (ストリームの断片化、到着順、エラー、タイムアウト、状態遷移) を扱える。

```python
from moqt import moqt
from moqt.moq import Client, NativeEvent, Runtime


async def main() -> None:
    client = Client(url="moqt://127.0.0.1:4433/live", verify_peer=False)
    await client.connect()

    # すべてのイベントを到着順に記録する (送信系のイベントも含む)
    events: list[str] = []

    async def on_event(event: NativeEvent) -> None:
        events.append(event.kind)

    client.on_event(on_event)

    # 接続が駆動しているランタイムと native の状態機械を直接観測する
    runtime: Runtime = client.runtime
    print(runtime.session.established, runtime.subscriptions())
    print(client.session.established)

    # 生のストリーム操作とデータグラム送信 (状態機械を介さない)。
    # PADDING ストリームは type の varint とゼロ埋めのペイロードを自分で組み立てる
    padding_stream_id = await client.open_stream()
    await client.send_stream_data(
        padding_stream_id,
        moqt.encode_varint(moqt.PADDING_STREAM_TYPE) + bytes(8),
        fin=True,
    )

    # 用途を登録していないストリームは reset / STOP_SENDING で終端する
    stream_id = await client.open_stream(bidirectional=True)
    await client.reset_stream(stream_id, moqt.STREAM_CANCELLED)
    await client.stop_sending_stream(stream_id, moqt.STREAM_CANCELLED)

    # PADDING データグラム
    await client.send_datagram(moqt.encode_varint(moqt.PADDING_DATAGRAM_TYPE) + bytes(8))
```

生の操作はストリームの用途を登録しないため、peer が解釈できないバイト列を送るとプロトコル違反として扱われる。正常系の送信には `Publication` や `Runtime` の API を使う。

- `Client.runtime` / `Client.session`: 接続前は `MOQTError` になる
- `Client.on_event`: 種類ごとのコールバックと違い、`send_control` / `send_request` / `reset_request_stream` などの送信系も含めて `Runtime` の組み込み処理より先に渡す
- `MOQTError` / `NativeEvent` / `Runtime` は `moqt.moq` から import できる
- 状態機械やストリームを直接操作するとランタイムの簿記と食い違うため、観測と制御を組み合わせて使う

## moqt.moq.testing

E2E テスト向けの server と pytest fixture。`moqt.moq` は client だけを公開し、server 側の型はここに置く。

pytest の rootdir の `conftest.py` で宣言する。

```python
pytest_plugins = ["moqt.moq.testing"]
```

非同期 fixture を含むため `pytest-asyncio` が必要である。`asyncio_mode` は `auto` でも `strict` でも動作する。

| fixture | 内容 |
|---|---|
| `moq_certificates` | localhost 用の自己署名証明書 `(certfile, keyfile)` |
| `moq_transport` | client と server が使う接続方式 (既定は WT-H3)。上書きすると suite 全体の接続方式を変えられる |
| `moq_server` | localhost の空きポートで待ち受ける起動済みの `Server` |
| `moq_client_factory` | `moq_server` へ接続済みの `Client` を作る factory |
| `moq_pair` | 接続済みの client / server と、確立した `ServerSession` |

```python
from moqt.moq import Publication
from moqt.moq.testing import MOQTPair, SubscriptionRequest, collect_objects, wait_until


async def test_objects_are_delivered(moq_pair: MOQTPair) -> None:
    """server が送ったオブジェクトを client が受け取れることを確認する。"""
    published: list[Publication] = []

    async def on_subscribe(request: SubscriptionRequest) -> None:
        published.append(await request.subscribe_ok(1))

    moq_pair.server.on_subscribe(on_subscribe)

    subscription = await moq_pair.client.subscribe([b"ns"], b"video")
    await wait_until(lambda: bool(published))
    await published[0].send_object(1, 0, b"hello")

    received = await collect_objects(subscription.objects(), 1, 5.0)
    assert received[0].payload == b"hello"
```

fixture を使わずに `Server` を直接起動することもできる。

```python
import asyncio

from moqt.moq.testing import Server, SubscriptionRequest


async def main() -> None:
    server = Server(host="127.0.0.1", port=4433, certfile="cert.pem", keyfile="key.pem")

    async def on_subscribe(request: SubscriptionRequest) -> None:
        # SUBSCRIBE_OK を返して配信を開始する
        publication = await request.subscribe_ok(1)
        await publication.send_object(0, 0, b"hello")
        await publication.close()

    server.on_subscribe(on_subscribe)
    await server.start()
    await server.run()


asyncio.run(main())
```

- `Server(host, port, *, certfile, keyfile, transport=Transport.WebTransportOverHTTP3, allowed_origins=None, implementation="moqt-py", control_message_timeout=None, data_stream_timeout=None, setup_options=None)`。`Transport.Quic` は未対応で `ValueError` になる
- コールバックは `on_session_established` / `on_subscribe` / `on_fetch` / `on_publish` / `on_request_update` / `on_goaway` / `on_event` / `on_fill_fetch_stream`
- `ServerSession` は `goaway()` と状態照会、`SubscriptionRequest` は `subscribe_ok()` / `reject()`、`FetchRequest` は `respond()` / `reject()`、`PublisherRequest` は `accept()` / `reject()` を持つ
- 補助 API: `generate_certificates()` / `wait_until()` / `collect_objects()`

## 仕様参照

- MOQT: draft-ietf-moq-transport-22
- LOC: draft-ietf-moq-loc-04
- MSF: draft-ietf-moq-msf-01
- C4M: draft-ietf-moq-c4m-01
- CBOR / COSE / CWT: RFC 8949 / RFC 9052 / RFC 8392
- DPoP: draft-nandakumar-moq-generic-dpop-proof-00

いずれも draft 由来であり、将来の改訂で変更される可能性がある。対応仕様は moqt-rs に追従する。

## 開発

開発手順は `docs/DEVELOPMENT.md` を参照する。要点は次のとおり。

```bash
uv sync
uv run maturin develop --generate-stubs
uv run pytest
```

Git フックは prek で管理しており、`prek install --prepare-hooks` で入る。moqt-rs は `develop` ブランチを追従し、実際にビルドしたコミットは `Cargo.lock` が固定する (`cargo update -p shiguredo_moqt` で更新する)。
