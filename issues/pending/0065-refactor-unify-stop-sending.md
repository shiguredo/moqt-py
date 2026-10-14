# 統一 Server.on_stop_sending へ寄せる

- Created: 2026-10-15
- Completed:
- Branch: feature/refactor-unify-stop-sending
- Polished:

## 目的

ピアの STOP_SENDING の受信を、テスト用サーバーでも統一 API から登録する。
webtransport-py 2026.1.0.dev29 で 0287 がリリースされ、統一 `Server.on_stop_sending` が
HTTP/2 と HTTP/3 の両方に対応した。moqt-py は WT-H3 だけ h3 ハンドル経由で登録しており、
ハンドラも 2 本に分かれている。

## 現状

- `python/moqt/moq/testing/server.py` は、WT-H2 では統一 API の
  `Server.on_stop_sending` を、WT-H3 では `transport.h3.on_stop_sending` を登録している。
  そのためハンドラが `_on_stop_sending(session, stream_id, error_code)` と
  `_on_h3_stop_sending(session_id, stream_id, error_code, addr)` の 2 本ある
- 統一 `Server.on_stop_sending` のコールバックは `(session, stream_id, error_code)` で
  あり、`error_code` は HTTP/3 では WT_APPLICATION_ERROR レンジ外のとき `None` になる
- クライアント側 (`Client`) の STOP_SENDING は、統一 `Client` に `on_stop_sending` と
  `stop_sending` が無いため、引き続き h2 / h3 ハンドル経由である。本 issue の対象外とし、
  別 issue で扱う

## 設計方針

- `Server.__init__` の登録を統一 API の `Server.on_stop_sending` 1 本に戻す
- `_on_h3_stop_sending` を削除し、`_on_stop_sending` の `error_code` を `int | None` に
  する。WT-H3 はレンジ外のコードを `None` で通知する
  (draft-ietf-webtrans-http3-16 §4.4 (Resetting Data Streams))
- `tests/test_e2e.py` の実通信テスト 2 件 (WT-H2 / WT-H3 / QUIC の 6 件) が引き続き
  通ることを確認する

## 完了条件

- testing server の STOP_SENDING の登録が統一 API の 1 本になり、ハンドラが 1 本になる
- WT-H2 / WT-H3 / QUIC の STOP_SENDING の実通信テストが全件通る
- `uv run pytest` が全件通る

## pending にした理由

統一 `Server.on_stop_sending` の HTTP/3 対応は webtransport-py の develop にのみ入っており
(0287)、まだリリースされていなかった。統一 `Client` の `on_stop_sending` と
`stop_sending` は webtransport-py 側で未起票・未実装である。

## reopened にした理由

webtransport-py 2026.1.0.dev29 で 0287 がリリースされ、統一 `Server.on_stop_sending` が
HTTP/2 と HTTP/3 の両方で `(session, stream_id, error_code)` を通知するようになった。
サーバー側を保留していた理由が解消したため reopened にする。統一 `Client` の
`on_stop_sending` と `stop_sending` は dev29 にも入っておらず引き続き保留であるため、
クライアント側は本 issue の対象から外し、別 issue で扱う。
