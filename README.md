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

moqt-py は Media over QUIC Transport (MOQT) の codec と sans I/O セッション状態機械を提供する Python ライブラリです。I/O を一切持たず、バイト列を入れてイベントを取り出す形なので、任意のイベントループ、スレッド、テストから呼び出せます。

- `moqt.moqt`: MOQT の codec と sans I/O セッション状態機械
- `moqt.loc`: LOC (Low Overhead Media Container) のプロパティ codec
- `moqt.msf`: MSF (MOQT Streaming Format) のカタログとタイムラインの codec
- `moqt.c4m`: C4M (Common Access Token for MoQ) のトークンと DPoP proof の codec

`moqt.moq` はこれらの上に載る WebTransport / QUIC の client で、おまけです。E2E テスト向けの server と pytest fixture は `moqt.moq.testing` にあります。

実装には次のライブラリを利用しています。

- MOQT の codec とセッション状態機械、LOC / MSF / C4M の codec に [moqt-rs](https://github.com/shiguredo/moqt-rs) を PyO3 経由で利用しています
- C4M の署名と検証に [aws-lc-rs](https://github.com/aws/aws-lc-rs) を利用しています
- `moqt.moq` の QUIC / WT-H2 / WT-H3 の I/O に [webtransport-py](https://pypi.org/project/webtransport-py/) を利用しています

API 一覧と使い方の詳細は [skills/moqt-py/SKILL.md](skills/moqt-py/SKILL.md) にまとめています。

## 対応仕様

- Media over QUIC Transport: [draft-ietf-moq-transport-22](https://datatracker.ietf.org/doc/html/draft-ietf-moq-transport-22)
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

## 使い方

低レベル API はバイト列を入出力するだけで、ソケットにもイベントループにも依存しません。

### moqt.moqt

MOQT の codec と sans I/O セッション状態機械です。ストリームの実体には触れず、呼び出し側が peer とのバイト列の受け渡しを行います。

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

peer から受け取ったバイト列は `Session.receive_control` / `receive_request_stream` / `receive_data_stream` / `receive_datagram` へ渡し、戻り値の `Event` に従って `Session.send_*` が返すバイト列を送出します。

### moqt.loc

LOC のプロパティ codec です。

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

MSF のカタログとタイムラインの codec です。カタログは draft の MUST に照らして検証されます。

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

### moqt.c4m

C4M のトークンと DPoP proof の codec です。署名と検証には aws-lc-rs を使います。

```python
from moqt import c4m

# CAT トークンを compact 形式で発行する
claim = c4m.MoqtClaim()
scope = c4m.MoqtScope([c4m.MoqtAction.PUBLISH])
scope.namespace_match(c4m.NamespaceMatch.match(c4m.Match.exact(b"example.com")))
scope.track = c4m.Match.prefix(b"video-")
claim.scope(scope)

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

### おまけ: moqt.moq

WebTransport (WT-H3 / WT-H2) と QUIC 直接接続で MOQT セッションを張る client です。接続方式は `Transport` で選びます。

```python
import asyncio

from moqt.moq import Client


async def main() -> None:
    # verify_peer=False は自己署名証明書を使う開発時の設定
    client = Client(url="moqt://127.0.0.1:4433/webtransport", verify_peer=False)
    await client.connect()

    subscription = await client.subscribe([b"moqt-py", b"test"], b"video")
    async for obj in subscription.objects():
        print(obj.group_id, obj.object_id, len(obj.payload), obj.status)

    await client.close()


asyncio.run(main())
```

Track を配信する場合は `Client.publish` が返す `Publication` からオブジェクトを送ります。E2E テストで client の相手役が要る場合は `moqt.moq.testing` の `Server` と pytest fixture を使います。

`moqt.moq` は低レベル API も隠しません。`Client.runtime` と `Client.session` で接続が駆動しているランタイムと状態機械を直接扱え、`Client.on_event` ですべてのイベントを到着順に観測できます。

## 開発

開発手順は [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) を参照してください。

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
