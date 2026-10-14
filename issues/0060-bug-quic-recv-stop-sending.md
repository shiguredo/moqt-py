# QUIC 直接接続で受信した STOP_SENDING を状態機械へ通知していない

- Created: 2026-10-14
- Completed:
- Branch: feature/fix-quic-recv-stop-sending
- Polished:

## 目的

QUIC 直接接続でも、peer が自側の送信ストリームへ STOP_SENDING を送ったことを状態機械へ
通知する。moqt-py の直近の修正で WT-H2 は通知するようになったが、QUIC 直接接続は
webtransport-py が同じコールバックを公開しているのに登録していない。

## 現状

- `python/moqt/moq/client.py` の `Client.__init__` は、`isinstance(self._transport,
  quic.Client)` の分岐で `on_stream_data` / `on_connection_closed` / `on_datagram` だけを
  登録しており、受信 STOP_SENDING を登録していない
- `python/moqt/moq/testing/server.py` の QUIC 分岐も `on_stream_data` / `on_datagram` /
  `on_stream_reset` / `on_connection_closed` だけを登録しており、同じく登録していない
- webtransport-py は ngtcp2 / nghttp3 / nghttp2 を `webtransport_ext` で束ね、その上に
  asyncio の高レベル層を提供する。受信 STOP_SENDING は QUIC 直接接続では
  `webtransport.quic.Client.on_stop_sending` (ngtcp2 の `EventType.STOP_SENDING` を
  そのまま通知する) と `webtransport.quic.Server.on_stop_sending(stream_id, error_code,
  addr)` として公開されている
- 受信 STOP_SENDING を公開していないのは WT-H3 だけである。ngtcp2 は
  `EventType.STOP_SENDING` を上げているが、webtransport-py の h3 ラッパー
  (`webtransport._h3_client` / `_h3_server`) はアプリへ渡すコールバックを持たず、
  nghttp3 への送出要求として処理している
- 送信側は変更不要である。`webtransport.quic.Client.shutdown_stream` は
  `ngtcp2_conn_shutdown_stream` を呼び、リモート単方向ストリーム (moqt-py が受信して
  いる subgroup stream) では read 側だけ、つまり STOP_SENDING のみを送出する

### 直近の修正の記述の訂正

先の修正では「WT-H3 と QUIC 直接接続は webtransport-py が受信 STOP_SENDING を公開して
いない」と記載したが、これは QUIC 直接接続について誤りである。QUIC 直接接続は公開して
おり、moqt-py 側の登録漏れが残っている。あわせて「QUIC は reset で代替している」と
記載したが、実際には `shutdown_stream` が STOP_SENDING を送出している。

## 設計方針

- `Client.__init__` の QUIC 分岐に `quic.Client.on_stop_sending` を登録し、既存の
  `Client._on_stop_sending` から `Runtime.receive_stop_sending` へ渡す
  (WT-H2 と同じ経路)
- `Server.__init__` の QUIC 分岐に `quic.Server.on_stop_sending` を登録し、`addr` から
  `_quic_context` で接続を引いて `Runtime.receive_stop_sending` へ渡す
- WT-H3 は対象外のままとし、「受信 STOP_SENDING を公開していないのは WT-H3 だけ」と
  コメントを訂正する。QUIC の送信側コメントも実態 (`shutdown_stream` が STOP_SENDING を
  送出する) に合わせる
- `tests/test_e2e.py` の WT-H2 向け実通信テスト 2 件を WT-H2 / QUIC の 2 接続方式で
  実行する

## 完了条件

- QUIC 直接接続で購読者がデータストリームへ STOP_SENDING を送ると、publisher の状態機械が
  再オープン禁止を記録すること
- QUIC 直接接続で購読者が fetch stream へ STOP_SENDING を送ると、publisher の fetch が
  終端すること
- WT-H2 の既存テストが引き続き通ること
- `uv run pytest` が全件通ること
