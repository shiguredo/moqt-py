# テスト向けの低レベル API を公開する

- Created: 2026-10-08
- Completed:
- Branch: feature/add-low-level-apis
- Polished:

## 目的

CODEBASE.md の「テストから実装の細部を扱えるよう、低レベルな API を積極的に公開する」方針に
従い、`moqt.moq` から状態機械・全イベント・生のストリーム操作を扱えるようにする。
moqt-py は他プロジェクトの E2E テストから使われるため、高水準 API で隠れている部分を
テストから制御・観測できることが必要である。

## 現状

- `Client` は `_require_runtime()` でランタイムを隠しており、テストは `Runtime` の
  `receive_stream` / `receive_datagram` / `receive_stream_closed` / `tick` といった
  プリミティブを直接呼べない
- 種類ごとのコールバック (`on_publish_done` / `on_goaway` など) は受信イベントしか運ばず、
  `send_request` / `send_on_stream` / `reset_request_stream` / `stop_sending_request_stream`
  のような送信系のイベントをテストから観測できない
- `TransportOps` が private であり、ストリームの開設・生バイト列の送信・reset /
  STOP_SENDING・生のデータグラム送信をテストから行えない
- `Runtime` / `NativeEvent` / `MOQTError` は `moqt.moq._runtime` からしか import できず、
  低レベル API が返す型を利用側が参照しづらい (moqt-py 自身のテストも private から
  import している)

## 設計方針

- `Runtime.session` / `Client.runtime` / `Client.session` でランタイムと native の状態機械を
  公開する。`Client.runtime` は接続前は `MOQTError` とする
- `Client.on_event` / `Server.on_event` ですべてのイベントを組み込みの処理より先に渡す
  - server は 1 つのコールバックで複数接続を扱うため、イベントはランタイムと組にして渡す
- `Client.open_stream` / `Client.send_stream_data` / `Client.reset_stream` /
  `Client.stop_sending_stream` / `Client.send_datagram` で生の操作を公開する
  - `Runtime.stop_sending(request_id)` が既にあるため、ストリーム単位の STOP_SENDING は
    `stop_sending_stream` とする
- `MOQTError` / `NativeEvent` / `Runtime` を `moqt.moq` から公開する
- 状態機械やストリームを直接操作するとランタイムの簿記と食い違うため、doc に注意を明記する
- 低レベル API のテストは `tests/test_low_level.py` に置く

## 完了条件

- 低レベル API のテストが追加され、`uv run pytest` が全件通ること
- `ruff` / `ty` / `cargo fmt` / `cargo clippy` が通ること
- README の低レベル API の節に使い方が記載されていること
