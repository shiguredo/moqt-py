# STOP_SENDING の受信を統一 API に寄せる

- Created: 2026-10-15
- Completed:
- Branch: feature/refactor-unify-stop-sending
- Polished:

## 目的

ピアの STOP_SENDING の受信を、プロトコル固有のハンドル経由から統一 API に寄せる。
webtransport-py の develop で統一 `Server.on_stop_sending` が HTTP/3 にも配線され、
WT-H3 でも `(session, stream_id, error_code)` で届くようになった。moqt-py は WT-H3 だけ
h3 ハンドル経由で登録しており、ハンドラも 2 本に分かれている。

## 現状

- `python/moqt/moq/testing/server.py` は、WT-H2 では統一 API の
  `Server.on_stop_sending` を、WT-H3 では `transport.h3.on_stop_sending` を登録している。
  そのためハンドラが `_on_stop_sending(session, stream_id, error_code)` と
  `_on_h3_stop_sending(session_id, stream_id, error_code, addr)` の 2 本ある
- `python/moqt/moq/client.py` は、WT-H2 では `transport.h2.on_stop_sending` を、WT-H3 では
  `transport.h3.on_stop_sending` を登録している。統一 `Client` には `on_stop_sending` が
  無いためである
- STOP_SENDING の送出も、WT-H2 は `h2_client.stop_sending`、WT-H3 は
  `h3_client.stop_sending` を使う。統一 `Client` には `stop_sending` が無い
  (`reset_stream` は統一 API にある)
- webtransport-py の develop では 0287 が closed になり、統一 `Server.on_stop_sending` が
  HTTP/2 と HTTP/3 の両方で `(session, stream_id, error_code: int | None)` を通知するように
  なった。ただし最新リリースは 2026.1.0.dev28 であり、この変更はまだリリースされていない
- 統一 `Client` の `on_stop_sending` は webtransport-py の 0287 で対象外とされており、
  HTTP/2 でも HTTP/3 でもピアの停止要求を統一 API からは観測できない (ハンドル経由では
  観測できる)

## 設計方針

- webtransport-py の次版がリリースされたら、`pyproject.toml` の下限を上げ、
  `Server.__init__` の登録を統一 API の `Server.on_stop_sending` 1 本に戻す。
  `_on_h3_stop_sending` を削除し、`_on_stop_sending` の `error_code` を `int | None` に
  する。WT-H3 はレンジ外のコードを `None` で通知する
  (draft-ietf-webtrans-http3-16 §4.4 (Resetting Data Streams))
- 統一 `Client` に `on_stop_sending` と `stop_sending` が入った版がリリースされたら、
  クライアント側のハンドル経由も統一 API に寄せる。`_transport_ops()` の WT-H2 / WT-H3 の
  分岐も `stop_sending` を統一 API から取れるようになる
- 受信の登録と送出の両方を寄せた後、`_transport_ops()` の WT-H2 / WT-H3 分岐が
  `http_version` で分かれている理由が無くなるかを確認し、分岐を減らせるなら減らす
- `tests/test_e2e.py` の実通信テスト 2 件 (WT-H2 / WT-H3 / QUIC の 6 件) が引き続き
  通ることを確認する

## 完了条件

- testing server の STOP_SENDING の登録が統一 API の 1 本になり、ハンドラが 1 本になる
- 統一 `Client` に対応 API が入った場合は、クライアント側もハンドル経由を使わなくなる
- WT-H2 / WT-H3 / QUIC の STOP_SENDING の実通信テストが全件通る
- `uv run pytest` が全件通る

## pending にする理由

統一 `Server.on_stop_sending` の HTTP/3 対応は webtransport-py の develop にのみ入っており
(0287)、まだリリースされていない。統一 `Client` の `on_stop_sending` と `stop_sending` は
webtransport-py 側で未起票・未実装である。moqt-py から回避する方法は無く
(現在のハンドル経由が回避策である)、webtransport-py の版が出た時点で reopened にして
対応する。
