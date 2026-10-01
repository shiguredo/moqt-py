# Transport.Quic で接続すると AUTHORITY の検証で失敗する

- Created: 2026-10-01
- Completed:
- Branch: feature/fix-quic-transport-setup
- Polished: {YYYY-MM-DD}

## 目的

`moqt.moq.Client` の `Transport.Quic` (QUIC 直接接続) を接続できるようにする。

README は `Transport.Quic` を「QUIC 直接接続。URI の authority、path、query を SETUP の
AUTHORITY と PATH で通知し、ALPN は `moqt-21`」と説明しているが、実際には接続できない。

## 現状

`Transport.Quic` を指定して接続すると、SETUP の交換で失敗する。

```python
from moqt.moq import Client, Transport

client = Client(url="moqt://127.0.0.1:4433/live", transport=Transport.Quic, verify_peer=False)
await client.connect()
# RuntimeError: session error 0x19: AUTHORITY MUST NOT be used with WebTransport
```

原因は、状態機械へ通知する transport が `WebTransport` に固定されている一方、I/O 層は
QUIC のときに AUTHORITY と PATH を載せていることである。

- `src/core.rs` の `CoreSession::new` が `Session::new_client(Transport::WebTransport, ...)` と
  `Session::new_server(Transport::WebTransport, ...)` を渡しており、Python 側から transport を
  指定する手段が無い
- `python/moqt/moq/client.py` は `Transport.Quic` のとき SETUP に AUTHORITY と PATH を載せる
  (draft-ietf-moq-transport-21 §6.2.2 (Native QUIC))
- moqt-rs は QUIC の SETUP に AUTHORITY と PATH を要求し (§9.1.1 (AUTHORITY) /
  §9.1.2 (PATH))、WebTransport の SETUP では AUTHORITY を拒否する (§6.2.1 (WebTransport))。
  そのため transport が `WebTransport` のまま AUTHORITY を送ると INVALID_AUTHORITY (0x19) に
  なる

`tests/test_client.py` は transport オブジェクトと SETUP のオプションだけを検証しており、
接続しないためこの不整合を検出できていない。実 relay へ接続する `tests/test_relay.py` は
既定の WebTransport over HTTP/3 だけを使う。

## 設計方針

- Python 側から transport を指定できるようにし、`Client` が選んだ接続方式を状態機械へ
  渡す。`moqt.moq.testing` の server も同じ経路を使う
- QUIC では AUTHORITY と PATH を送り、WebTransport では送らないという現在の I/O 層の分岐を
  維持する
- relay を用意しなくても検証できるよう、低レベル API (`moqt.moqt` の `Session`) の
  SETUP に対してテストを書く

## 完了条件

- `Transport.Quic` で `Client.connect` が成功し、SETUP の交換が完了すること
- WebTransport の SETUP に AUTHORITY を載せると失敗し、QUIC では成功することをテストで
  固定すること
- `uv run pytest` / `cargo clippy` / `ruff` / `ty` と `prek run --all-files` が通ること

## 補足

`Transport.Quic` を使う E2E テストは `moqt.moq.testing` の server が QUIC に対応してから
追加する。QUIC に対応していない理由と経過は `0036` にある。
