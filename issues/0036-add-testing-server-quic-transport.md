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
