# QMux 上の MOQT に対応する

- Created: 2026-10-14
- Completed: 2026-10-14
- Branch: feature/add-qmux-transport
- Polished:

## 目的

UDP が使えない、または不安定な環境でも MOQT を動かせるようにする。QMux は
TCP/TLS のような双方向バイトストリーム上で QUIC v1 相当のストリーム多重化を提供する
プロトコルであり、MOQT を QMux 上で動かす仕様が起票されている
(draft-nandakumar-moq-qmux-moqt-00)。moqt-py は現在 UDP (QUIC 直接接続) と
WebTransport (WT-H2 / WT-H3) だけに対応しており、TCP しか通らない環境では接続できない。

## 現状

- `python/moqt/moq/transport.py` の `Transport` は `Quic` / `WebTransportOverHTTP2` /
  `WebTransportOverHTTP3` の 3 つであり、QMux が無い
- `python/moqt/moq/client.py` の `_create_transport` は統一 `webtransport.Client` と
  `webtransport.quic.Client` を作り分ける。QMux の経路は無い
- `python/moqt/moq/testing/server.py` の `Server` も QMux に対応していない
- webtransport-py の `webtransport.qmux` が次を提供する
  - `Client(host, port, *, config, ssl, alpn_protocols, close_reason)` と
    `Server(host, port, *, config, ssl, alpn_protocols)`。TLS を使う場合は
    `alpn_protocols` が必須である (draft-ietf-quic-qmux-02 §8.1 (Protocol Negotiation))
  - `open_stream(unidirectional)` / `send_stream_data(stream_id, data, fin)` / `close()` と、
    `on_connected` / `on_closed` / `on_stream_data` / `on_stream_reset` / `on_stop_sending`
    (server は `on_session_ready` / `on_session_closed` とセッションハンドル `Session`)
- MOQT over QMux の ALPN は native QUIC と同じ `moqt-XX` であり、専用の値は定義されない
  (draft-nandakumar-moq-qmux-moqt-00 §3.2 (ALPN Identification))。MOQT のストリームは
  QMux のストリームへそのまま対応し、オブジェクトは単方向ストリームで運ばれる
  (§4.1 (Stream Mapping) / §4.3 (Object Delivery))
- webtransport-py の qmux はストリームの reset / STOP_SENDING の送出 API と、
  データグラムの API を公開していない。QMux 側ではそれぞれ
  draft-ietf-quic-qmux-02 §9.2 (Stream Resets with Partial Delivery Extension) と
  §9.1 (Unreliable Datagram Extension) の拡張にあたり、未実装である
- draft-nandakumar-moq-qmux-moqt-00 §4.2 は制御ストリームを「双方向ストリーム 0」と
  しているが、MOQT 自身の制御ストリームは単方向であり
  (draft-ietf-moq-transport-22 §6.4.1 (Unidirectional Streams))、moqt-py の状態機械も
  ストリーム ID の向きで種別を判定するため、native QUIC と同じ単方向ストリームで扱う

## 設計方針

- `Transport.Qmux = "qmux"` を追加する
- `moqt.moq.Client` に QMux の経路を追加する
  - TLS の `SSLContext` は `verify_peer` / `ca_file` から作り、ALPN に `MOQT_PROTOCOL` を
    提示する
  - `TransportOps` は `open_stream` / `send_stream_data` / `close` を QMux へ写す。
    reset / STOP_SENDING / データグラムは QMux が公開していないため、呼ばれたら理由の
    分かる `MOQTError` を送出する (黙って捨てない)
  - `on_stream_data` (FIN を運ぶ) / `on_stream_reset` / `on_stop_sending` を登録する
- `moqt.moq.testing.Server` に QMux の経路を追加する
  - `certfile` / `keyfile` からサーバー側の `SSLContext` を作る
  - 接続はセッションハンドルで識別し、既存の QUIC と同じく接続ごとのランタイムを作る
- E2E テストは QMux 専用のものを追加する。既存の `moq_transport` fixture には加えない。
  reset / STOP_SENDING / データグラムを使うテストが多数あり、QMux では未対応のため

## 完了条件

- QMux で SETUP 交換が完了し、SUBSCRIBE / PUBLISH とオブジェクトの送受信が動くこと
- QMux で FETCH と fetch 応答が動くこと
- QMux で未対応の操作 (reset / STOP_SENDING / データグラム) が理由の分かる
  `MOQTError` になること
- `uv run pytest` が全件通ること

## 解決方法

`python/moqt/moq/transport.py` に `Transport.Qmux` (`"qmux"`) を追加した。

`python/moqt/moq/client.py` では `_create_transport` に QMux の経路を追加し、URI の
authority へ TCP 接続して TLS を張る `webtransport.qmux.Client` を作るようにした。
`SSLContext` は `verify_peer` と `ca_file` から作り、ALPN に `MOQT_PROTOCOL` を提示する。
`TransportOps` は `open_stream` / `send_stream_data` / `close` を QMux へ写し、reset /
STOP_SENDING / データグラムは webtransport-py の qmux が公開していないため、呼ばれたら
理由の分かる `MOQTError` を送出する。AUTHORITY と PATH は HTTP 層を持たない接続として
QMux でも送る。

`python/moqt/moq/testing/server.py` では `Transport.Qmux` の経路を追加し、`certfile` と
`keyfile` からサーバー側の `SSLContext` を作って `webtransport.qmux.Server` を動かす。
接続はセッションハンドル単位のコールバックで扱い、`peer_address` とサーバーが振る
`session_id` の組で識別する。

`src/core.rs` の `transport_from_python` は `"qmux"` を native QUIC と同じ扱いにする。
QMux は WebTransport ではないため、状態機械から見た Setup Option の制約が QUIC と同じに
なる (draft-nandakumar-moq-qmux-moqt-00 §4.1 (Stream Mapping))。

QMux ではサーバーが接続の確立と同時に制御ストリームへ SETUP を書くため、クライアントの
`connect()` が返る前にデータが届く。ランタイムができる前に届いたストリームデータと
データグラムは保持し、`Runtime.start()` の後に状態機械へ渡すようにした。自側の SETUP より
先に peer の SETUP を渡すと、状態機械が初期状態のまま制御メッセージを受けたとして拒否する
ためである。

### 確認

- `tests/test_client.py`: 接続先の authority、ALPN、AUTHORITY / PATH、未対応操作の
  `MOQTError` を確認する 4 件を追加した
- `tests/test_e2e.py`: QMux で SETUP と SUBSCRIBE とオブジェクトの配送を確認する
  `test_qmux_delivers_objects_to_the_subscriber` と、FETCH と fetch 応答を確認する
  `test_qmux_fetches_objects` を追加した
- `uv run pytest` は 634 件すべて通る (relay が要る 7 件は skip)。`prek run --all-files`
  (ruff-format / ruff-check / ty / tombi / cargo fmt / cargo clippy / cargo test) も通る

### 残る制約

ストリームの reset / STOP_SENDING とデータグラムは QMux では使えない。QMux 側では
それぞれ draft-ietf-quic-qmux-02 §9.2 / §9.1 の拡張にあたり、webtransport-py の qmux が
未実装である。既存の `moq_transport` fixture には QMux を加えていない。これらの操作を
使うテストが多数あるためである。
