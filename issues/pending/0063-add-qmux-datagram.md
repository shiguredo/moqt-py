# QMux でオブジェクトデータグラムを送受信できない

- Created: 2026-10-14
- Completed:
- Branch: feature/add-qmux-datagram
- Polished:

## 目的

QMux 接続でも MOQT のオブジェクトデータグラムを送受信できるようにする。QMux は
draft-ietf-quic-qmux-02 §9.1 (Unreliable Datagram Extension) で DATAGRAM フレームを
規定しており、transport parameter で折衝すれば運べる。moqt-py は接続方式によって
使える機能が非対称なままになっている。

## 現状

- `Transport.Qmux` は実装済みであり、SETUP の交換、購読と配信、fetch は動く
- ただし `Client._transport_ops()` と `Server._qmux_transport_ops()` が組み立てる
  `TransportOps` の `send_datagram` は `MOQTError` を送出する。受信の経路も無い
  (webtransport-py の `webtransport.qmux` に `on_datagram` が無いため、moqt-py は
  データグラムのコールバックを登録していない)
- QMux の仕様 (§9.1 (Unreliable Datagram Extension)) は DATAGRAM フレームを次のように
  規定している
  - 符号化と意味は QUIC の Unreliable Datagram Extension のままで、使用は transport
    parameter で折衝する
  - 最大長は `max_datagram_frame_size` と `max_record_size` の両方で制限される。QUIC では
    コンテナが packet だが QMux では QMux Record であるためである。既定の
    `max_record_size` 16382 では、ペイロードは最大 16381 バイトになる
  - 送信側は flow control / congestion control で詰まっているときにフレームを drop できる
- ただし QMux の仕様 (§1.1 (Trade-offs Between QMux and QUIC Version 1)) は、QMux の
  DATAGRAM が QUIC と意味が異なることも明記している
  - 信頼できる順序どおりの配送になり、同じヘッドオブラインブロッキングを受ける
  - 一度書いたデータグラムは捨てられない (送信側にできるのは「送らない」選択だけである)
  - §6 (Forward Progress and Flow Control) は、アプリへ速やかに渡せない場合に受信側が
    drop することを MAY で許容している
- MOQT over QMux の draft はデータグラムのマッピングを定義しておらず、§6
  (Trade-offs and Limitations) で「不確実なデータグラムが要るアプリは native QUIC を
  使え」としている。ただし QMux で運ぶこと自体を禁じてはいない
- 未実装の層は dwnx である。公開ヘッダ `dwnx.h` にデータグラムの API が無い。
  webtransport-py の 0279 (closed) も「DATAGRAM (Unreliable Datagram Extension) は
  dwnx が未実装のため対応していない。CODEBASE.md の『ngtcp2 / nghttp3 / nghttp2 を
  フォークしない』方針に従い、上流の対応を待つ」としている
- 影響: `Publication.send_datagram` と、データグラムで届くオブジェクトの受信が QMux では
  使えない。`moq_transport` fixture に QMux を加えられない理由の 1 つでもある

## 設計方針

dwnx が §9.1 を実装し、webtransport-py が API を公開したら、次を行う。

- `send_datagram` を QMux の API へ写す
- 受信のコールバック (`on_datagram` 相当) を登録し、`Runtime.receive_datagram` へ渡す
  (QMux には接続単位のセッションハンドルがあるため、server 側はセッションで識別する)
- `MOQTError` を送出する実装と、それを確認しているテスト
  (`tests/test_client.py` の `test_qmux_reports_unsupported_transport_operations`) を
  置き換える
- 上限の扱いを決める。MOQT のオブジェクトデータグラムは 1 オブジェクト 1 データグラムで
  あり、`max_record_size` を超えるオブジェクトは送れない。QUIC の
  `max_datagram_frame_size` と同じく、上限を超えた場合は送信しない判断をする
- QMux では不確実配送にならないこと (§1.1) を docstring と SKILL に明記する

## 完了条件

- QMux でオブジェクトデータグラムを送受信できること
- `max_record_size` を超えるデータグラムの扱いが決まっていること
- QMux では不確実配送にならないことがドキュメントに書かれていること
- `uv run pytest` が全件通ること

## pending にする理由

QMux の仕様 (§9.1) はデータグラムを規定しているが、dwnx が未実装であり、webtransport-py
も moqt-py も実装できない。webtransport-py の CODEBASE.md は ngtcp2 / nghttp3 / nghttp2 を
フォークしない方針であり、上流の対応を待つ以外に方法が無い。

dwnx が対応し webtransport-py が版をリリースした時点で reopened にして対応する。
