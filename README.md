# moqt-py

[![PyPI](https://img.shields.io/pypi/v/moqt-py)](https://pypi.org/project/moqt-py/)
[![image](https://img.shields.io/pypi/pyversions/moqt-py.svg)](https://pypi.python.org/pypi/moqt-py)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Actions status](https://github.com/shiguredo/moqt-py/workflows/CI/badge.svg)](https://github.com/shiguredo/moqt-py/actions)

## About Shiguredo's open source software

We will not respond to PRs or issues that have not been discussed on Discord. Also, Discord is only available in Japanese.

Please read <https://github.com/shiguredo/oss/blob/master/README.en.md> before use.

## 時雨堂のオープンソースソフトウェアについて

利用前に <https://github.com/shiguredo/oss> をお読みください。

## moqt-py について

moqt-py は Media over QUIC Transport (MOQT) のクライアントライブラリです。本体は MOQT / LOC / MSF / C4M の codec と sans I/O セッション状態機械です。

- `moqt.moqt` / `moqt.loc` / `moqt.msf`: MOQT / LOC / MSF の codec と sans I/O セッション状態機械
- `moqt.c4m`: C4M (CAT) の認可トークンと DPoP proof の codec
- `moqt.moq`: QUIC、WebTransport over HTTP/2 (WT-H2)、WebTransport over HTTP/3 (WT-H3) で接続する MOQT クライアント
- `moqt.moq.testing`: server と pytest fixture

実装には次のライブラリを利用しています。

- MOQT の codec とセッション状態機械、LOC / MSF / C4M の codec に [moqt-rs](https://github.com/shiguredo/moqt-rs) を PyO3 経由で利用しています
- C4M の署名と検証に [aws-lc-rs](https://github.com/aws/aws-lc-rs) を利用しています
- QUIC / WT-H2 / WT-H3 の I/O に [webtransport-py](https://pypi.org/project/webtransport-py/) を利用しています

## 対応仕様

- Media over QUIC Transport: [draft-ietf-moq-transport-21](https://datatracker.ietf.org/doc/html/draft-ietf-moq-transport-21)
- Low Overhead Media Container: [draft-ietf-moq-loc-04](https://datatracker.ietf.org/doc/html/draft-ietf-moq-loc-04)
- MOQT Streaming Format: [draft-ietf-moq-msf-01](https://datatracker.ietf.org/doc/html/draft-ietf-moq-msf-01)
- Authorization scheme for MOQT using Common Access Tokens: [draft-ietf-moq-c4m-01](https://datatracker.ietf.org/doc/html/draft-ietf-moq-c4m-01)
- CBOR / COSE / CWT: [RFC 8949](https://www.rfc-editor.org/rfc/rfc8949) / [RFC 9052](https://www.rfc-editor.org/rfc/rfc9052) / [RFC 8392](https://www.rfc-editor.org/rfc/rfc8392)
- Application-Agnostic Demonstrating Proof-of-Possession: [draft-nandakumar-moq-generic-dpop-proof-00](https://datatracker.ietf.org/doc/draft-nandakumar-moq-generic-dpop-proof/)

いずれも draft 由来であり、将来の改訂で変更される可能性があります。対応仕様は moqt-rs に追従します。

## 対応プラットフォーム

wheel は配布しておらず、Rust 1.93 以降の toolchain を使ってソースからビルドします。GitHub Actions の CI で確認している環境は次のとおりです。

- macOS 26 arm64
- Ubuntu 26.04 x86_64
- Ubuntu 26.04 arm64
- Ubuntu 24.04 x86_64
- Ubuntu 24.04 arm64

## 対応 Python

- 3.14
- 3.14t (Free-Threading)

## インストール

```bash
uv add moqt-py
```

## 使い方 (高レベル API)

`moqt.moq` が提供する client API です。

- `moqt.moq.Client` で MOQT セッションを張ります
- 低レベル API は [moqt.moqt](#moqtmoqt) / [moqt.loc](#moqtloc) / [moqt.msf](#moqtmsf) を参照してください

### client

接続先は MOQT の URI (`moqt://host:port/path`) であり、接続方式は `transport` で選びます (draft-ietf-moq-transport-21 §6.1 (MOQT URI Scheme))。

- `Transport.Quic`: QUIC 直接接続。URI の authority、path、query を SETUP の AUTHORITY と PATH で通知し、ALPN は `moqt-21` (§6.2.2 (Native QUIC))
- `Transport.WebTransportOverHTTP3` (省略時) / `Transport.WebTransportOverHTTP2`: WebTransport。URI のスキームを `https` に置き換えて extended CONNECT を送る (§6.2.1 (WebTransport))

```python
from moqt.moq import Client, Transport

# QUIC 直接接続
client = Client(url="moqt://127.0.0.1:4433/live", transport=Transport.Quic, verify_peer=False)

# WebTransport over HTTP/3 (省略時)
client = Client(url="moqt://127.0.0.1:4433/live", verify_peer=False)

# WebTransport over HTTP/2
client = Client(
    url="moqt://127.0.0.1:4433/live",
    transport=Transport.WebTransportOverHTTP2,
    verify_peer=False,
)
```

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

Track を配信する場合は `Client.publish` で `Publication` を作ります。

```python
publication = await client.publish([b"moqt-py", b"test"], b"video", 1)
await publication.send_object(0, 0, b"payload")
await publication.close()
```

送信の詳細は [オブジェクトの送信](#オブジェクトの送信) を参照してください。

### オブジェクトの送信

`Client.publish` や `moqt.moq.testing` の `subscribe_ok` が返す `Publication` からオブジェクトを送ります。`Publication.send_object` は subgroup ストリームで、`Publication.send_datagram` はデータグラムで送ります。Subgroup ID のモードは Group ごとに固定されるため、モードを変えるときは Group を分けます (draft-ietf-moq-transport-21 §11.3.1)。

```python
from moqt import moqt
from moqt.moq import SUBGROUP_ID_MODE_EXPLICIT, SUBGROUP_ID_MODE_FIRST_OBJECT_ID

# subgroup ストリームで送る。subgroup_id / publisher_priority / end_of_group も指定できる
await publication.send_object(1, 0, b"payload")

# Subgroup ID を明示する
await publication.send_object(
    2,
    0,
    b"payload",
    subgroup_id=3,
    subgroup_id_mode=SUBGROUP_ID_MODE_EXPLICIT,
)

# Subgroup ID を最初の Object ID にする。Subgroup ID を明示するモードと比べて
# Subgroup ID フィールドの分だけ wire が短くなる
await publication.send_object(3, 0, b"payload", subgroup_id_mode=SUBGROUP_ID_MODE_FIRST_OBJECT_ID)

# End of Group を通知する。このとき payload は空でなければならない
await publication.send_object(4, 0, b"", status=moqt.OBJECT_STATUS_END_OF_GROUP)

# データグラムで送る
await publication.send_datagram(5, 0, b"datagram payload")
```

同じ Location のオブジェクトは subgroup とデータグラムのどちらか一方しか届きません。データグラムで送るオブジェクトには、subgroup で送ったオブジェクトと重複しない Location を選んでください。

受信側では、Subgroup ID を最初の Object ID として決めるモードでも、最初のオブジェクトを受信した時点で `MOQTObject.subgroup_id` に値が入ります (draft-ietf-moq-transport-21 §11.3.1)。

> [!WARNING]
>
> - データグラムは経路 MTU を超えると通知なく破棄され、送信側からは検知できません (draft-ietf-moq-transport-21 §11.2.1)。`moqt.moqt.MAX_DATAGRAM_SIZE` を超えるデータグラムを送ると警告を記録します。大きいオブジェクトは subgroup ストリームで送ってください

### moqt.moq.testing

pytest の rootdir に置いた `conftest.py` で宣言すると、client と server の組を用意する fixture が使えます。

```python
pytest_plugins = ["moqt.moq.testing"]
```

接続方式は `moq_transport` fixture で選べます (既定は WebTransport over HTTP/3)。上書きすると suite 全体を別の接続方式で実行できます。

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

fixture を使わずに `Server` を直接起動することもできます。

```python
import asyncio

from moqt.moq.testing import Server, SubscriptionRequest


async def main() -> None:
    server = Server(
        host="127.0.0.1",
        port=4433,
        certfile="cert.pem",
        keyfile="key.pem",
    )

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

`certfile` と `keyfile` には WebTransport のサーバー証明書を指定します。開発用の自己署名証明書は `generate_certificates` が `cert.pem` と `key.pem` を書き出します。

`moqt.moq.testing` は `pytest` / `pytest-asyncio` / `cryptography` を使います。非同期のテストを実行するため、`pyproject.toml` で `asyncio_mode = "auto"` を設定するか、テストに `@pytest.mark.asyncio` を付けます。

```bash
uv add "moqt-py[testing]"
```

## 使い方 (低レベル API)

### moqt.moqt

MOQT の codec と sans I/O セッション状態機械です。ストリームの実体には触れず、呼び出し側がバイト列をやり取りします。

```python
from moqt.moqt import Session, decode_message

# 自側の制御ストリームの先頭バイト列を作る
client = Session.client("my-implementation")
data = client.start()
# 先頭 2 バイトは制御ストリームの stream type (0x2F00)
print(data[:2])

# 制御メッセージを 1 件デコードする
message, consumed = decode_message(data[2:])
print(message.kind, hex(message.type_id), message.body)
```

### moqt.loc

LOC (Low Overhead Media Container) のプロパティ codec です。

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

### moqt.msf

MSF (MOQT Streaming Format) のカタログとタイムラインの codec です。カタログは draft の MUST に照らして検証されます。

```python
from moqt import msf

catalog = msf.Catalog.parse(
    '{"version":"draft-01","tracks":[{"name":"video","packaging":"loc","isLive":true}]}'
)
print(catalog.tracks)

# delta 更新を適用する
catalog.apply_delta('{"deltaUpdate":[{"op":"remove","tracks":[{"name":"video"}]}]}')
print(catalog.encode())

# JSON 文字列を経由せずにカタログと delta 更新を組み立てる
built = msf.Catalog()
built.add_track(msf.Track("video", "loc", True))
delta = msf.DeltaUpdate()
delta.add_tracks([msf.Track("audio", "loc", True)])
delta.clone_tracks([msf.CloneTrack("video-low", "video")])
built.apply_delta_update(delta)
print(built.encode())

# タイムラインは gzip 圧縮にも対応する
timeline = msf.MediaTimeline()
timeline.add(1000, 1, 2, 0)
print(msf.MediaTimeline.decode(timeline.encode(gzip=True)).entries)
```

### moqt.c4m

C4M (Common Access Token for MoQ) のトークンと DPoP proof の codec です。署名と検証には aws-lc-rs を使います。Track Namespace は `tuple[bytes, ...]`、Track Name は `bytes` で扱います。

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

CBOR / COSE / JWK / JWS compact の低レベル API も公開しています。付録 A のテストベクタは `tests/test_c4m.py` で固定しています。

## ライセンス

Apache License 2.0

```text
Copyright 2026 Shiguredo Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```
