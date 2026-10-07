# native QUIC で relay へ接続できず E2E テストが失敗する

- Created: 2026-10-08
- Completed:
- Branch: feature/fix-native-quic-alpn
- Polished:

## 目的

repository secrets の `TEST_MOQT_URI` が指す relay を使う e2e-test ワークフローが、native
QUIC の接続テストだけで失敗し続けている。ALPN が relay の要求する値と食い違っているため
であり、draft-ietf-moq-transport-22 に合わせて解消する。

## 現状

- e2e-test ワークフローは `tests/test_relay.py` の
  `test_relay_accepts_a_native_quic_connection` が
  `ConnectionError: failed to establish a QUIC connection` で失敗する
- 同じジョブの `tests/test_connect.py` と WT-H2 / WT-H3 の relay テストは成功している。
  relay 自体には到達できており、native QUIC の経路だけが失敗している
- `python/moqt/moq/transport.py` の `MOQT_PROTOCOL` が `moqt-21` のままである。
  `python/moqt/moq/client.py` の `_create_transport` は `Transport.Quic` のときこれを
  `alpn_protocols` に渡すため、native QUIC のハンドシェイクは ALPN `moqt-21` を提示する
- moqt-rs の `develop` は draft-22 に合わせて `moqt-22` を広告しており
  (`examples/tokio-moq/src/lib.rs` の `MOQT_PROTOCOL`)、同じ `TEST_MOQT_URI` の relay へ
  native QUIC で接続する moqt-rs の E2E Test ワークフローは成功している
- 失敗は moqt-rs を `6c3ab63` へ更新した 0048 の push (2026-10-05) から始まっており、
  それ以前の 0047 の push (2026-10-02) では成功していた
- moqt-py は draft-22 を対象にしており (issue 0048 で `message_parameters.rs` などを
  draft-22 の符号化へ追随させている)、`moqt-21` は取り残された値である

## 設計方針

- `MOQT_PROTOCOL` を `moqt-22` にし、参照している draft の節番号を
  draft-ietf-moq-transport-22 §6.2 (Session establishment) に合わせる
- 値を説明している README とテストの doc を追随させる
- ALPN の値以外の挙動は変えない。WT-H2 / WT-H3 の経路は現状のまま維持する
- 検証は `TEST_MOQT_URI` を設定した `uv run pytest tests/test_connect.py tests/test_relay.py`
  で行う。ローカルに relay が無い場合は e2e-test ワークフローで確認する

## 完了条件

- native QUIC の接続テスト (`test_relay_accepts_a_native_quic_connection`) が成功すること
- `uv run pytest` / `cargo fmt` / `cargo clippy` / `ruff` / `ty` が通ること
