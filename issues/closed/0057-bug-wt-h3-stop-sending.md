# WT-H3 で STOP_SENDING の代わりに RESET_STREAM を送出している

- Created: 2026-10-14
- Completed: 2026-10-14
- Branch: feature/fix-wt-h3-stop-sending
- Polished:

## 目的

MOQT が STOP_SENDING を送る場面 (購読や fetch の cancel、DATA_STREAM_TIMEOUT による
受信ストリームの停止) で、WT-H3 だけが RESET_STREAM を送っている。RESET_STREAM は
ストリームの破棄、STOP_SENDING は送信の停止要求であり、peer が観測する操作と以後の
挙動が異なる。送出できる公開 API があるのに使っていない状態を解消し、接続方式に
よらず状態機械の要求どおりの操作を送る。

## 現状

`python/moqt/moq/client.py` の `Client._transport_ops` は、WT-H3 の分岐で
`transport.reset_stream(...)` を `stop_sending` として返し、「WT-H3 には STOP_SENDING
だけを送る API が無いため、ストリームを reset して受信を終わらせる」とコメントして
いる。

webtransport-py は `webtransport._h3_client.Client.stop_sending` を持っており、
統一 API の `webtransport.Client` が公開する `h3` ハンドルから呼べる。同じ
`_transport_ops` の WT-H2 の分岐は、`h2` ハンドルの `stop_sending` を同じ形で使って
おり、WT-H3 の分岐だけが取り残されている。

`TransportOps.stop_sending` を呼ぶのは `Runtime.stop_sending_stream` と、状態機械が
生成する `stop_sending_request_stream` (購読 / fetch の cancel) および
`stop_sending_data_stream` (`DATA_STREAM_TIMEOUT` による受信ストリームの停止) である。

`webtransport.quic.Client` には STOP_SENDING だけを送る API が無いため、QUIC 直接接続の
回避策 (`shutdown_stream` による reset) は現状のままとする。

## 設計方針

- WT-H3 の分岐で `transport.h3` の `stop_sending` を使う。WT-H2 の分岐と同じ形にそろえる
- QUIC 直接接続の分岐とコメントは変更しない
- `TransportOps.stop_sending` が h3 ハンドルの `stop_sending` を指し、`reset_stream` では
  ないことをテストで固定する
- 生きたコメントだけを残す (事実と異なる「API が無いため」のコメントを削除する)

## 完了条件

- WT-H3 で `TransportOps.stop_sending` が STOP_SENDING を送出すること
- `uv run pytest` が全件通ること

## 解決方法

`python/moqt/moq/client.py` の `Client._transport_ops` の WT-H3 分岐で、`reset_stream` に
よる代替をやめて `transport.h3` の `stop_sending` を使うようにした。WT-H2 の分岐と
同じ形であり、統一 API の `webtransport.Client` がプロトコル固有の操作を持たないため
ハンドルから呼ぶ。事実と異なっていた「WT-H3 には STOP_SENDING だけを送る API が無い」
というコメントも削除した。

`tests/test_client.py` に
`test_webtransport_over_http3_sends_stop_sending_from_the_h3_handle` を追加し、
`TransportOps.stop_sending` が h3 ハンドルの `stop_sending` を指し、`reset_stream` では
ないことを固定した。

`webtransport.quic.Client` には STOP_SENDING だけを送る API が無いため、QUIC 直接接続の
回避策 (`shutdown_stream` による reset) は現状のままとした。

### 確認

`uv run pytest` は 624 件すべて通る (relay が要る 7 件は skip)。`prek run --all-files`
(ruff-format / ruff-check / ty / tombi / cargo fmt / cargo clippy) も通ることを確認した。
