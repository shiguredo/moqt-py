# クライアントの STOP_SENDING を統一 API に寄せる

- Created: 2026-10-15
- Completed:
- Branch: feature/refactor-unify-client-stop-sending
- Polished:

## 目的

ピアの STOP_SENDING の受信と、STOP_SENDING の送出を、クライアントでも統一 API に寄せる。
統一 `webtransport.Client` には `on_stop_sending` と `stop_sending` が無く、moqt-py は
WT-H2 と WT-H3 でプロトコル固有のハンドルを直接使っている。統一 `Server` は 0287 で
HTTP/2 と HTTP/3 の両方に対応しており、非対称が残っている。

## 現状

- `python/moqt/moq/client.py` の `Client.__init__` は、WT-H2 では
  `transport.h2.on_stop_sending` を、WT-H3 では `transport.h3.on_stop_sending` を登録して
  いる。統一 `Client` に `on_stop_sending` が無いためである
- `Client._transport_ops()` も、WT-H2 では `h2_client.stop_sending`、WT-H3 では
  `h3_client.stop_sending` を使う。統一 `Client` には `stop_sending` が無い
  (`reset_stream` と `send_datagram` は統一 API にある)
- webtransport-py の 0287 は統一 `Server.on_stop_sending` の HTTP/3 対応であり、統一
  `Client` の `on_stop_sending` は対象外とされている
- webtransport-py 2026.1.0.dev29 にも統一 `Client` の `on_stop_sending` と `stop_sending` は
  入っていない。webtransport-py 側に該当する issue は起票されていない

## 設計方針

- webtransport-py の統一 `Client` に `on_stop_sending` と `stop_sending` が入った版が
  リリースされたら、`pyproject.toml` の下限を上げて次を行う
  - `Client.__init__` の受信登録を統一 API の 1 本にする
  - `Client._transport_ops()` の `stop_sending` を統一 API から取る
- 受信と送出の両方を寄せた後、`_transport_ops()` が `http_version` で WT-H2 / WT-H3 に
  分かれている理由が無くなるかを確認し、分岐を減らせるなら減らす
- WT-H2 / WT-H3 / QUIC の STOP_SENDING の実通信テストが引き続き通ることを確認する

## 完了条件

- `Client` の STOP_SENDING の受信登録が統一 API の 1 本になる
- `Client._transport_ops()` が STOP_SENDING の送出にプロトコル固有のハンドルを使わなくなる
- WT-H2 / WT-H3 / QUIC の STOP_SENDING の実通信テストが全件通る
- `uv run pytest` が全件通る

## pending にする理由

統一 `webtransport.Client` に `on_stop_sending` と `stop_sending` が無く、webtransport-py
側でも未起票・未実装である。moqt-py から回避する方法は無く (現在のハンドル経由が回避策で
ある)、webtransport-py が統一 `Client` へ配線した版をリリースした時点で reopened にして
対応する。

## reopened にした理由

webtransport-py 2026.1.0.dev30 で 0288 がリリースされ、統一 `Client` に
`on_stop_sending(callback(stream_id, error_code: int | None))` と
`stop_sending(stream_id, error_code=0)` が追加された。`_impl()` が選択した HTTP/2 と
HTTP/3 の実装へ委譲するため、どちらの接続方式でも使える。pending にした理由が解消したため
reopened にする。
