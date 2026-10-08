# 使い方

moqt-py の使い方をモジュールごとに示す。API の一覧、引数、定数、注意点は
[skills/moqt-py/SKILL.md](../skills/moqt-py/SKILL.md) にまとめている。

低レベル API はバイト列を入出力するだけで、ソケットにもイベントループにも依存しない。

## moqt.moqt

MOQT の codec と sans I/O セッション状態機械。ストリームの実体には触れず、呼び出し側が
peer とのバイト列の受け渡しを行う。

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

peer から受け取ったバイト列は `Session.receive_control` / `receive_request_stream` /
`receive_data_stream` / `receive_datagram` へ渡し、戻り値の `Event` に従って
`Session.send_*` が返すバイト列を送出する。SETUP の交換は次のように書ける。

```python
from moqt.moqt import Session

client = Session.client("my-client")
server = Session.server("my-server")

client_setup = client.start()
server_setup = server.start()
server.receive_control(client_setup)
client.receive_control(server_setup)
print(client.established, server.established)
```

## moqt.loc

LOC (Low Overhead Media Container) のプロパティ codec。プロパティ ID の偶奇で値の型が決まり、
偶数 ID は vi64、奇数 ID は長さ付きバイト列である。

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

## moqt.msf

MSF (MOQT Streaming Format) のカタログとタイムラインの codec。カタログは draft の MUST に
照らして検証され、違反は `ValueError` になる。

```python
from moqt import msf

catalog = msf.Catalog.parse(
    '{"version":"draft-01","tracks":[{"name":"video","packaging":"loc","isLive":true}]}'
)
print(catalog.tracks)

# delta 更新を適用する
catalog.apply_delta('{"deltaUpdate":[{"op":"remove","tracks":[{"name":"video"}]}]}')
print(catalog.encode())
```

Track 識別子 (`namespace--track`) の相互変換 (`parse_name` / `serialize_name`)、
メディアタイムラインとイベントタイムライン、JSON 文字列を経由しないカタログの組み立てにも
対応する。詳細は [SKILL.md](../skills/moqt-py/SKILL.md) を参照。

## moqt.c4m

C4M (Common Access Token for MoQ) のトークンと DPoP proof の codec。署名と検証には
aws-lc-rs を使う。CBOR / COSE / JWK / JWS compact の低レベル API も公開している。

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
assert token.claims.authorize(c4m.MoqtAction.PUBLISH, (b"example.com",), b"video-hd")
```

付録 A のテストベクタは `tests/test_c4m.py` で固定している。

## moqt.moq

WebTransport (WT-H3 / WT-H2) と QUIC 直接接続で MOQT セッションを張る client。接続方式は
`Transport` で選ぶ (省略時は WT-H3)。

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

Track を配信する場合は `Client.publish` が返す `Publication` からオブジェクトを送る。

```python
publication = await client.publish([b"moqt-py", b"test"], b"video", 1)
await publication.send_object(0, 0, b"payload")
await publication.close()
```

`moqt.moq` は低レベル API も隠さない。`Client.runtime` と `Client.session` で接続が駆動して
いるランタイムと状態機械を直接扱え、`Client.on_event` ですべてのイベントを到着順に観測できる。
生のストリーム操作とデータグラム送信も公開している。

## moqt.moq.testing

E2E テスト向けの server と pytest fixture。`moqt.moq` は client だけを公開するため、
client の相手役はこのパッケージに置いている。

pytest の rootdir の `conftest.py` で宣言する。

```python
pytest_plugins = ["moqt.moq.testing"]
```

fixture は `moq_certificates` / `moq_transport` / `moq_server` / `moq_client_factory` /
`moq_pair` の 5 つである。`moq_transport` を上書きすると suite 全体の接続方式を変えられる。

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

`Server` を直接起動することもできる。`certfile` と `keyfile` には WebTransport のサーバー
証明書を指定し、開発用の自己署名証明書は `generate_certificates` が書き出す。

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

非同期 fixture を使うため `pytest-asyncio` が必要である。`asyncio_mode` は `auto` でも
`strict` でも動作する。

```bash
uv add "moqt-py[testing]"
```
