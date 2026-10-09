# testing Server を QUIC 直接接続に対応させる

- Created: 2026-09-21
- Completed:
- Branch: feature/add-testing-server-quic-transport
- Polished:

## 目的

QUIC 直接接続でも E2E テストを実行できるようにする。

`moqt.moq.Client` は `Transport.Quic` に対応済みであるが、テストの相手役となる
server が QUIC に対応していないため、E2E テストで検証できていない。

## 現状

`moqt.moq.testing.server.Server` は `Transport.WebTransportOverHTTP2` と
`Transport.WebTransportOverHTTP3` にだけ対応しており、`Transport.Quic` を渡すと
`ValueError` になる。

webtransport-py の `quic.Server` には次の API が無く、MOQT の server 役を
完全には実装できない。

- ストリームの reset (`quic.Client` の `shutdown_stream` に相当するもの)
- STOP_SENDING の送信
- ピアの RESET_STREAM の通知 (client の `wait_for_stream_reset` に相当するもの)
- 接続の close (MOQT の終了コードと理由を渡す口)

`open_stream` / `send_stream_data` / `send_datagram` と受信コールバックは揃っている。

## 設計方針

webtransport-py の `quic.Server` に不足している API が追加されたら、`Server` に
`Transport.Quic` を実装する。QUIC には WebTransport session が無いため、接続は
session ID ではなく address 単位になり、`_Connection` と `TransportOps` の組み立てを
QUIC 用に分岐させる。

moqt-py 自身の suite も `moq_transport` fixture の上書きで QUIC を回せるようにする。

## 完了条件

- QUIC 直接接続で E2E テスト (SETUP / SUBSCRIBE / オブジェクト送受信 / データグラム) が通ること

## pending にする理由

webtransport-py の `quic.Server` にストリームの reset / STOP_SENDING / 接続 close を
送る API が無く、moqt-py だけでは MOQT の server 役を実装できない。

webtransport-py ではこの不足が 0220 (層間に欠けている公開 API を追加する) と
0258 (quic 層でサーバーがストリームを中断し接続を終了コードと理由付きで閉じられるように
する) として起票されている。0220 は `shutdown_stream` と `close` を、0258 は
`stop_sending` / `reset_stream` / `on_stream_reset` を対象にしており、両方の実装を待つ。
どちらも 2026-10-08 時点では open である。

- 低レベル `webtransport_ext.quic.Connection` には `close_stream` / `stop_sending` /
  `reset_stream` / `close(error_code, reason)` が既にあり、高レベル `quic.Server` に
  露出していないのが原因である
- `quic.Client` には `shutdown_stream` と `wait_for_stream_reset` があるため、client 側の
  不足は `close()` が終了コードと理由を受け取らない点だけである
- 統一 API (`webtransport.Server` / `Session`) は QUIC 直接接続を扱わないため、
  QUIC 対応は `quic.Server` の API 追加を待つ必要がある

webtransport-py の 0220 / 0258 がリリースされた時点で reopened にして対応する。

## reopened にする理由

webtransport-py 2026.1.0.dev25 で 0258 がリリースされ、`quic.Server` に必要な API が揃った。

- `shutdown_stream` / `reset_stream` / `stop_sending` / `close(error_code, reason)` が
  追加され、MOQT の server 役に必要な送信操作が揃った
- `on_stream_reset` が追加され、ピアの RESET_STREAM を状態機械へ通知できるようになった
- 0220 は引き続き open であるが、この issue が必要としていた `quic.Server` の
  `shutdown_stream` と `close` は 0258 に含まれている

実測では、`Transport.Quic` を `Server` へ渡すと `ValueError` になり、E2E テストで
QUIC 直接接続を検証できない状態だった。
