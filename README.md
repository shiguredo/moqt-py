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
- `moqt.moq`: これらの上に載る WebTransport / QUIC の client (おまけ)
- `moqt.moq.testing`: E2E テスト向けの server と pytest fixture

実装には [moqt-rs](https://github.com/shiguredo/moqt-rs) を PyO3 経由で、署名と検証に [aws-lc-rs](https://github.com/aws/aws-lc-rs) を、`moqt.moq` の I/O に [webtransport-py](https://pypi.org/project/webtransport-py/) を利用しています。

## 対応仕様

- Media over QUIC Transport: [draft-ietf-moq-transport-22](https://datatracker.ietf.org/doc/html/draft-ietf-moq-transport-22)
- Low Overhead Media Container: [draft-ietf-moq-loc-04](https://datatracker.ietf.org/doc/html/draft-ietf-moq-loc-04)
- MOQT Streaming Format: [draft-ietf-moq-msf-01](https://datatracker.ietf.org/doc/html/draft-ietf-moq-msf-01)
- Authorization scheme for MOQT using Common Access Tokens: [draft-ietf-moq-c4m-01](https://datatracker.ietf.org/doc/html/draft-ietf-moq-c4m-01)
- CBOR / COSE / CWT: [RFC 8949](https://www.rfc-editor.org/rfc/rfc8949) / [RFC 9052](https://www.rfc-editor.org/rfc/rfc9052) / [RFC 8392](https://www.rfc-editor.org/rfc/rfc8392)
- Application-Agnostic Demonstrating Proof-of-Possession: [draft-nandakumar-moq-generic-dpop-proof-00](https://datatracker.ietf.org/doc/draft-nandakumar-moq-generic-dpop-proof/)

いずれも draft 由来であり、将来の改訂で変更される可能性があります。対応仕様は moqt-rs に追従します。

## 対応プラットフォーム

wheel は配布しておらず、Rust 1.93 以降の toolchain を使ってソースからビルドします。

- macOS 26 arm64
- Ubuntu 26.04 / 24.04 の x86_64 と arm64

## 対応 Python

- 3.14
- 3.14t (Free-Threading)

## インストール

```bash
uv add moqt-py
```

```python
from moqt.moqt import Session, decode_message

# I/O は呼び出し側が持ち、このライブラリはバイト列だけを扱う
session = Session.client("my-implementation")
message, consumed = decode_message(session.start()[2:])
print(message.kind, message.body)
```

## ドキュメント

- [使い方](docs/USAGE.md): 各モジュールの使い方と例
- [開発](docs/DEVELOPMENT.md): ビルド、テスト、実 relay への E2E テスト
- [利用リファレンス](skills/moqt-py/SKILL.md): API の一覧、引数、定数、注意点

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
