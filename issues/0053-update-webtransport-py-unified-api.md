# webtransport-py の統一 Client / Server へ追従する

- Created: 2026-10-08
- Completed: 2026-10-08
- Branch: feature/update-webtransport-py-unified-api
- Polished:

## 目的

webtransport-py が高レベル API を統一し、WebTransport のクライアント / サーバーが
`HTTPVersion` で HTTP/3 と HTTP/2 を選ぶ形になった。`webtransport.h3` / `webtransport.h2`
は Sans-IO 専用になり、moqt-py が使っている `webtransport.h3.Client` /
`webtransport.h3.Server` / `webtransport.h2.Client` / `webtransport.h2.Server` は
存在しなくなっている。

moqt-py は `webtransport-py>=2026.1.0.dev18,<2026.2` を指定し `uv.lock` で dev18 を
固定しているため、この変更を追従しない限り依存を上げられない。追従により、dev18 に
固定している間に webtransport-py へ入った修正 (h3 の DATAGRAM 配送、層ごとの例外階層)
も取り込める。

## 現状

依存:

- `pyproject.toml` は `webtransport-py>=2026.1.0.dev18,<2026.2` を指定し、`uv.lock` は
  `2026.1.0.dev18` を固定している
- PyPI の最新は `2026.1.0.dev24` であり、統一 API (`webtransport.Client` /
  `webtransport.Server` / `HTTPVersion` / `Session`) は dev24 に含まれる
- dev24 では `webtransport.h2` / `webtransport.h3` が Sans-IO 専用の `Session` だけを
  公開し、asyncio の高レベル実装は `webtransport._h2_client` / `webtransport._h3_client`
  などの内部モジュールへ移っている

client (`python/moqt/moq/client.py`):

- `_create_transport` が `webtransport.h3.Client` / `webtransport.h2.Client` /
  `webtransport.quic.Client` を作り分けている
- `Client.__init__` と `Client._transport_ops` は `isinstance(..., quic.Client)` /
  `isinstance(..., h2.Client)` でプロトコルを判定している
- 統一 API では `webtransport.Client(url, http_version=HTTPVersion.HTTP3/HTTP2, ...)` を
  1 つ作り、プロトコル固有の操作 (`stop_sending` / `migrate` など) は `client.h3` /
  `client.h2` のハンドルから呼ぶ。`webtransport.Client` の `connect()` は `-> None` で
  失敗時に例外を送出し、`webtransport.quic.Client` は `connect() -> bool` のままである

testing server (`python/moqt/moq/testing/server.py`):

- `webtransport.h2.Server` / `webtransport.h3.Server` を作り分け、コールバックを
  層ごとに登録している
- WT-H3 のコールバックは `(session_id, ..., addr)`、WT-H2 のコールバックは
  `SessionWriter` を受け取り、`ConnectionContext` を `(address, session_id)` と
  `SessionWriter` の union にしている
- 統一 API のコールバックは両方ともセッションハンドル `webtransport.Session` を
  第 1 引数で受け取る (`on_stream_data(session, stream_id, data)` など)
- `Session` ハンドルはコールバックのたびに作られるため、接続の識別に同一性は使えない
- `Session` は `open_stream` / `send_stream_data` / `send_datagram` / `reset_stream` を
  持ち、WT-H2 だけが `stop_sending` / `close_session` を持つ。WT-H3 のセッション終了
  (終了コードと理由) と WT-H3 の STOP_SENDING 送出はまだ無い

テスト:

- `tests/test_client.py` が `webtransport.h2` / `webtransport.h3` を import し、
  `isinstance(transport, h3.Client)` で接続方式を確認している

## 設計方針

- `pyproject.toml` を `webtransport-py>=2026.1.0.dev24,<2026.2` に上げ、
  `uv lock --upgrade-package webtransport-py` で `uv.lock` を更新する
- WebTransport の client は `webtransport.Client(url, http_version=..., ...)` を作る。
  `HTTPVersion.HTTP2` では `ca_file` を受け取らないため、moqt-py 側の明示的な拒否は
  そのまま残す
- QUIC 直接接続は `webtransport.quic.Client` のままにする (ALPN に `moqt-22` を
  指定する必要があるため)
- プロトコル固有の操作は選択したハンドルから呼ぶ。WT-H2 の `stop_sending` は
  `client.h2.stop_sending`、WT-H3 の STOP_SENDING は API が無いため従来どおり
  `reset_stream` で代替する
- testing server は `webtransport.Server(host, port, http_version=..., certfile=...,
  keyfile=..., allowed_origins=...)` を 1 つ作り、コールバックは `Session` を
  受け取る形へ統一する
- 接続の識別は `(peer address, session ID)` に統一する。`Session.addr` が不定の
  場合は `("", 0)` にする。WT-H2 のコールバックは `SessionWriter` しか渡さない
  現状の制約が無くなるため、`on_session_request` で address を控える必要も消える
- WT-H2 だけが持つ `stop_sending` / `close_session` は `Session.http_version` で
  判定して呼ぶ。型検査のために moqt-py 側で必要なメソッドを持つ Protocol を定義し、
  `typing.cast` で絞る
- WT-H3 のセッション終了 API が無いため、server の `TransportOps.close` は
  従来どおり CONNECT ストリームの `reset_stream` にする
- 統一 API にもピアの FIN を通知する `on_stream_end` は無いため、`_runtime.py` の
  FIN に関するコメントを現状の API 名に合わせて書き換える
- `issues/pending/0030-fix-server-session-close.md` と
  `issues/pending/0036-add-testing-server-quic-transport.md` の参照を統一 API の
  名前に合わせ、待っている API がまだ無いことを確認して pending のまま残す

## 完了条件

- `uv run pytest` が全件通ること (relay が要るテストの skip を除く)
- `prek run --all-files` (pre-commit ステージ) が通ること
- WT-H2 と WT-H3 の両方で E2E テストが通ること
- `tests/test_client.py` が統一 API の型と `HTTPVersion` で接続方式を確認していること

## 解決方法

webtransport-py を 2026.1.0.dev24 へ上げ、統一 API へ追従した。

- `pyproject.toml` の依存を `webtransport-py>=2026.1.0.dev24,<2026.2` にし、
  `uv lock --upgrade-package webtransport-py` で `uv.lock` を更新した
- `moqt.moq.Client` は `webtransport.Client` に `HTTPVersion` を渡して作るようにした。
  プロトコル固有の操作は選択したハンドルから呼び、WT-H2 の STOP_SENDING は
  `client.h2.stop_sending`、WT-H3 は API が無いため従来どおり `reset_stream` で
  代替する。QUIC 直接接続は `webtransport.quic.Client` のままである
- `moqt.moq.testing.Server` は `webtransport.Server` を `HTTPVersion` で選び、
  コールバックを `Session` ハンドルを受け取る形へ統一した。接続の識別は
  `(peer address, session ID)` に統一し、`on_session_request` で address を控える
  必要を無くした
- WT-H2 だけが持つ `stop_sending` / `close_session` は `Session.http_version` で
  判定し、moqt-py 側で定義した Protocol へ `typing.cast` で絞って呼ぶ
- WT-H3 のセッション終了 API がまだ無いため、server の close は CONNECT ストリームの
  `reset_stream` のままにした
- 統一 API にもピアの FIN を通知するコールバックは無いため、`_runtime.py` の FIN に
  関するコメントを現状の API に合わせて書き換えた
- pending の 0030 / 0036 の参照を統一 API の名前へ更新した。待っている webtransport-py
  の 0257 (h3 のセッション終了 API) / 0258 (quic のストリーム中断と接続 close) /
  0220 (層間に欠けている公開 API) は 2026-10-08 時点でも open であり、pending のまま
  残している

### 確認

- `uv run pytest` は 541 件通過、7 件 skip (TEST_MOQT_URI が必要な relay / connect)
- `prek run --all-files` (pre-commit ステージ) が通る
- E2E テストは conftest の `moq_transport` が WT-H2 と WT-H3 の両方を回り、どちらも通る
- テストは WT-H2 (STOP_SENDING と `close_session`) と WT-H3 (`reset_stream` による代替)
  の両方の `TransportOps` を通る
