# QMux 上の MOQT に対応する

- Created: 2026-10-14
- Completed:
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
