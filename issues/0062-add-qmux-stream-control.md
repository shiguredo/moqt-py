# QMux でストリームの reset / STOP_SENDING とデータグラムを送れない

- Created: 2026-10-14
- Completed:
- Branch: feature/add-qmux-stream-control
- Polished:

## 目的

QMux 接続でも MOQT のキャンセル (RESET_STREAM / STOP_SENDING) とオブジェクト
データグラムを送れるようにする。QMux 経路は未対応の操作を理由の分かる `MOQTError` で
失敗させるようにしてあり、接続方式によって使える機能が非対称なままになっている。

## 現状

- `Transport.Qmux` は実装済みであり、SETUP の交換、購読と配信、fetch は動く
- ただし `Client._transport_ops()` と `Server._qmux_transport_ops()` が組み立てる
  `TransportOps` の `reset_stream` / `stop_sending` / `send_datagram` は `MOQTError` を
  送出する。QMux では次の操作が失敗する
  - データストリームの受信を止める `stop_sending` (subgroup stream のキャンセル)
  - ストリームの reset (`Publication.reset_subgroup` などの経路)
  - オブジェクトデータグラムの送信 (`Publication.send_datagram` など)
- webtransport-py の `webtransport.qmux` は `open_stream` / `send_stream_data` / `close`
  だけを公開しており、reset / STOP_SENDING を送る API とデータグラムの送受信 API が無い。
  受信側の `on_stream_reset` / `on_stop_sending` はあるため、moqt-py は受信は通知できる
- QMux 側ではそれぞれ拡張にあたり、webtransport-py が未実装である
  (draft-ietf-quic-qmux-02 §9.2 (Stream Resets with Partial Delivery Extension) /
  §9.1 (Unreliable Datagram Extension))
- この制約のため `moq_transport` fixture に QMux を加えておらず、既存の E2E テストを
  QMux で回せていない (reset / STOP_SENDING / データグラムを使うテストが多数あるため)

## 設計方針

webtransport-py の qmux が API を公開したら、次を行う。

- `Client._transport_ops()` と `Server._qmux_transport_ops()` の `reset_stream` /
  `stop_sending` / `send_datagram` を QMux の API へ写す
- `MOQTError` を送出する実装と、それを確認しているテスト
  (`tests/test_client.py` の `test_qmux_reports_unsupported_transport_operations`) を
  置き換える
- `moq_transport` fixture に QMux を加え、既存の E2E テストを QMux でも回せるか検討する。
  接続方式によって意味が変わるテスト (Origin 検査など) は対象外にする

## 完了条件

- QMux で `reset_stream` / `stop_sending` が送れること
- QMux でオブジェクトデータグラムが送受信できること (QMux のデータグラム拡張が
  使えるようになった場合)
- QMux でデータストリームのタイムアウトが動くこと (`data_stream_timeout` の経路)
- `uv run pytest` が全件通ること

## pending にする理由

webtransport-py の qmux がストリームの reset / STOP_SENDING の送出 API と、データグラム
の API を公開しておらず、moqt-py だけでは実装できない。QMux の仕様では両者とも拡張
(draft-ietf-quic-qmux-02 §9.1 / §9.2) であり、webtransport-py 側の実装を待つ必要がある。
回避する方法は無い (低レベル `webtransport_ext.qmux.Connection` にも該当する API が
無いことを確認済み)。

webtransport-py が対応した版がリリースされた時点で reopened にして対応する。
