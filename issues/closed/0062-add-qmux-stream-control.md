# QMux でストリームの reset / STOP_SENDING を送れない

- Created: 2026-10-14
- Completed: 2026-10-15
- Branch: feature/add-qmux-stream-control
- Polished:

## 目的

QMux 接続でも MOQT のキャンセル (RESET_STREAM / STOP_SENDING) を送れるようにする。
QMux 経路は未対応の操作を理由の分かる `MOQTError` で失敗させるようにしてあり、接続方式に
よって使える機能が非対称なままになっている。

## 現状

- `Transport.Qmux` は実装済みであり、SETUP の交換、購読と配信、fetch は動く
- ただし `Client._transport_ops()` と `Server._qmux_transport_ops()` が組み立てる
  `TransportOps` の `reset_stream` / `stop_sending` は `MOQTError` を送出する。QMux では
  次の操作が失敗する
  - データストリームの受信を止める `stop_sending` (subgroup stream のキャンセル)
  - ストリームの reset (`Publication.reset_subgroup` などの経路)
  - データストリームのタイムアウト時の停止要求 (`data_stream_timeout` の経路)
- 受信側は通知できる。webtransport-py の `webtransport.qmux` は `on_stream_reset` と
  `on_stop_sending` を持ち、moqt-py はそれを状態機械へ渡している
- 送信側が使えない原因は webtransport-py にある。QMux は RESET_STREAM と STOP_SENDING を
  QUIC のフレームとして扱い、dwnx (ngtcp2 プロジェクトの QMux 実装) は
  `dwnx_conn_shutdown_stream` / `dwnx_conn_shutdown_stream_write` /
  `dwnx_conn_shutdown_stream_read` を公開ヘッダで提供している。しかし webtransport-py の
  `src/bindings/qmux.cpp` の `QmuxConnection` は `open_stream` / `send_stream_data` /
  `close` だけを公開しており、`webtransport.qmux` の `Client` / `Session` も同じである
- webtransport-py の 0279 (closed) は、設計方針で `Connection` に `reset_stream` /
  `stop_sending` / `close_stream` を持たせるとしていたが、解決方法で実装されたのは
  `open_stream` / `send_stream_data` / `close` だけである。露出漏れとして残っている
- webtransport-py の open issue に、QMux の reset / STOP_SENDING の露出を扱うものは無い

## 設計方針

webtransport-py の qmux が API を公開したら、次を行う。

- `Client._transport_ops()` と `Server._qmux_transport_ops()` の `reset_stream` /
  `stop_sending` を QMux の API へ写す
- `MOQTError` を送出する実装と、それを確認しているテスト
  (`tests/test_client.py` の `test_qmux_reports_unsupported_transport_operations`) を
  置き換える
- `moq_transport` fixture に QMux を加え、既存の E2E テストを QMux でも回せるか検討する。
  接続方式によって意味が変わるテスト (Origin 検査など) は対象外にする

## 完了条件

- QMux で `reset_stream` / `stop_sending` が送れること
- QMux でデータストリームのタイムアウトが動くこと (`data_stream_timeout` の経路)
- QMux で subgroup stream のキャンセルが動くこと
- `uv run pytest` が全件通ること

## pending にする理由

webtransport-py がストリームの reset / STOP_SENDING の送出 API を公開しておらず、
moqt-py だけでは実装できない。上流の dwnx は該当する API を持っているため、待っているのは
webtransport-py の露出である。moqt-py から回避する方法は無い (低レベル
`webtransport_ext.qmux.Connection` にも該当する API が無いことを確認済み)。

webtransport-py が対応した版がリリースされた時点で reopened にして対応する。

## reopened にした理由

webtransport-py 2026.1.0.dev29 で 0285 (QMux のローカル発ストリーム終了 API) が
リリースされ、`webtransport.qmux.Client` と `qmux.Server` の `Session` に
`reset_stream(stream_id, error_code=0)` / `stop_sending(stream_id, error_code=0)` /
`close_stream(stream_id, error_code=0)` が追加された。pending にした理由 (webtransport-py
が送出 API を公開していない) が解消したため、reopened にして対応する。

## 解決方法

`pyproject.toml` の webtransport-py の下限を 2026.1.0.dev29 へ上げ、`uv lock` と `uv sync`
で追随した。

`python/moqt/moq/client.py` の `Client._transport_ops()` で、QMux の `reset_stream` と
`stop_sending` を `webtransport.qmux.Client` のメソッドへ配線した。データグラムは dwnx が
実装していないため、引き続き理由の分かる `MOQTError` を送出する。

`python/moqt/moq/testing/server.py` の `Server._qmux_transport_ops()` も同じく
`webtransport.qmux.Session` の `reset_stream` / `stop_sending` へ配線した。

webtransport-py 2026.1.0.dev29 の変更により統一 `Server.on_stop_sending` のコールバックの
`error_code` が `int | None` になったため、`Server._on_stop_sending` の型もあわせた。

### 確認

- `tests/test_client.py`: `test_qmux_wires_stream_reset_and_stop_sending` で配線を確認し、
  `test_qmux_reports_unsupported_datagram` をデータグラムだけの確認に絞った
- `tests/test_e2e.py`: 実通信テスト 2 件のパラメータに QMux を追加し、WT-H2 / WT-H3 /
  QUIC / QMux の 4 接続方式で回すようにした (8 件)。QMux でデータストリームのタイムアウトが
  STOP_SENDING を送ることを確認する `test_qmux_data_stream_timeout_sends_stop_sending` を
  追加した
- `skills/moqt-py/SKILL.md` の QMux の制約をデータグラムだけに直した
- `uv run pytest` は 640 件すべて通る (relay が要る 7 件は skip)。`prek run --all-files`
  (ruff-format / ruff-check / ty / tombi / cargo fmt / cargo clippy / cargo test) も通る
