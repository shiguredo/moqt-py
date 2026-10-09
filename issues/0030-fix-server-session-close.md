# Server が MOQT セッション終了時に WebTransport session を閉じられない

- Created: 2026-09-16
- Completed: 2026-10-09
- Branch: feature/fix-server-session-close
- Polished:

## 目的

MOQT セッションが終了したことを peer が検知できるようにする。

状態機械がプロトコル違反でセッションを閉じても、WebTransport session が開いたままだと
peer は失敗に気づけない。相手側は期限まで待ち続けることになる。

## 現状

`moq.moq.testing.server.Server` の転送操作で、状態機械からの close 要求は WT-H3 では
統一 API の `Session.reset_stream(session_id, 0)` に繋がっている。これは CONNECT
ストリームを reset するだけであり、WebTransport session を終了コードと理由付きで
閉じてはいない。終了コードと理由も捨てている。

`moq.moq.Client` は `transport.close()` を呼ぶため WebTransport session は閉じるが、
こちらも終了コードと理由は渡していない。

webtransport-py の統一 API には WT-H3 の WebTransport session を閉じる API が無い
(`webtransport.Server` の WT-H3 経路が公開するのは `close_stream` / `reset_stream` /
`stop` のみ)。`webtransport.Client.close()` もコードと理由を受け取らない。

WT-H2 経路は統一 API の `Session.close_session(error_code, error_message)` でコードと
理由を渡せており、moqt-py もそれを使っている。h3 と quic だけができない状態である。

## 設計方針

webtransport-py にサーバー側のセッション終了 API が追加されたら、`Server` の close 経路を
それに繋ぎ、MOQT の終了コードと理由を渡す。クライアント側も同じくコードと理由を渡せる
API が用意されたら合わせる。

## 完了条件

- MOQT セッションが終了したとき、peer が WebTransport session の終了として検知できること
- 終了コードと理由が peer へ伝わること

## pending にする理由

webtransport-py にサーバー側の WebTransport session 終了 API が無く、moqt-py だけでは
実装できない。クライアント側も終了コードと理由を渡す API が無い。

webtransport-py ではこの不足が 0257 (h3 層で WebTransport セッションを終了コードと
理由付きで閉じられるようにする) と 0258 (quic 層でサーバーがストリームを中断し接続を
終了コードと理由付きで閉じられるようにする) として起票されており、実装はこれらを待つ。
どちらも 2026-10-08 時点では open である。

- h3 層: 統一 API の WT-H3 経路に session 終了 API が無く、`webtransport.Client.close()`
  は終了コードと理由を受け取らない。低レベル `webtransport_ext.h3.Session.close_session`
  は既に `error_code` と `error_message` を受け取れるため、高レベル層への露出が 0257 の
  対象である
- quic 層: `quic.Client.close()` は終了コードと理由を受け取らない (0258)
- h2 層: 統一 API の `Session.close_session(error_code, error_message)` が既にあるため、
  moqt-py は WT-H2 経路では既に終了コードと理由を渡せている。残るのは h3 / quic との
  非対称である

webtransport-py の 0257 / 0258 がリリースされた時点で reopened にして対応する。

## reopened にする理由

webtransport-py 2026.1.0.dev25 で 0257 と 0258 がリリースされ、実装できるようになった。

- 0257: 統一 API の `Session` に `close_session(error_code, error_message)` と
  `stop_sending(stream_id, error_code)` が入り、WT-H3 でも終了コードと理由付きで
  WebTransport session を閉じられるようになった。`Client.close(error_code, error_message)` も
  引数を受け取る
- 0258: `quic.Server` に `shutdown_stream` / `reset_stream` / `stop_sending` / `close` と
  `on_stream_reset` が入り、QUIC 直接接続の server でも同じ経路を作れるようになった

あわせて、実測で次の 2 点を確認した。

- `moq.moq._runtime.Runtime._handle_close` はアプリへの通知だけで終わり、トランスポートを
  閉じていない。`Runtime.close` の経路だけが `TransportOps.close` を呼んでいる。このため、
  状態機械がプロトコル違反でセッションを閉じても peer は WebTransport session の終了を
  観測できない。実測では、WT-H3 / WT-H2 のどちらでもサーバーの状態機械が閉じた後も
  クライアントの `established` が真のままだった
- peer のトランスポート層は終了コードと理由を保持するが、統一 API の `Client` は
  ピアの WT_CLOSE_SESSION の終了コードと理由を公開していない。WT-H2 の client は
  受信ループの終端例外としてのみ観測できる

完了条件に状態機械起点の経路を明記する。

## 完了条件 (reopened 時点)

- 状態機械がセッションを閉じたとき、peer が WebTransport session の終了として検知できること
- 終了コードと理由が peer へ伝わること

## 解決方法

`pyproject.toml` と `uv.lock` の webtransport-py を 2026.1.0.dev25 へ上げ、0257 / 0258 で
入った API に接続した。

### 状態機械が閉じたセッションをトランスポートへ伝える

- `moq.moq._runtime.Runtime._handle_close` で、状態機械の終了通知をアプリへ流したあとに
  `TransportOps.close(code, reason)` を呼ぶようにした。プロトコル違反などで状態機械が
  セッションを閉じた場合も peer が終了コードと理由を観測できる
  (draft-ietf-moq-transport-22 §12.2 (Session Termination Codes))。`Runtime.close` からの
  経路は `_closed` で先に閉じるため二重に送出しない
- `moq.moq.testing.server.Server._transport_ops` の WT-H3 分岐を無くし、接続方式によらず
  統一 API の `Session.stop_sending` と `Session.close_session(code, reason)` を使うように
  した。WT-H3 でも CONNECT ストリームの reset ではなく WT_CLOSE_SESSION で終了する
- `moq.moq.Client._close_transport` が MOQT の終了コードと理由をトランスポートへ渡すように
  した。QUIC 直接接続は `close(error_code, reason)`、WebTransport は
  `close(error_code, error_message)` である
- `moq.moq.Client._on_session_closed` は SETUP 完了後の終了を
  `Runtime.receive_session_closed()` で MOQT セッションの終了として反映するようにした。
  終了コードと理由は接続方式によってはトランスポート層にしか無いため、この経路では
  0 と空文字で通知する。`Runtime.established` はセッション終了後は偽になる

### テスト

`tests/test_e2e.py` に `test_state_machine_session_close_reaches_the_peer` を追加した
(WT-H2 / WT-H3 の両方で実行)。

- クライアントが解釈できない stream type を送り、サーバーの状態機械をプロトコル違反で
  終了させる
- サーバー側が終了コード (`SESSION_PROTOCOL_VIOLATION`) と理由を観測すること
- peer が MOQT セッションの終了として観測し (`established` が偽)、トランスポートの
  終端例外が同じ終了コードを保持すること
- WT-H2 では終端例外の理由が状態機械の理由と一致すること。WT-H3 の理由は
  webtransport-py が CONNECT ストリームの終了として生成する説明文になる

### 残る制約

統一 API の `Client` はピアの WT_CLOSE_SESSION の終了コードと理由を公開していないため、
WT-H2 で peer 起点の終了を観測した場合だけ理由を moqt-py から伝えられない
(`_on_session_closed` の経路で 0 と空文字になる)。WT-H3 は状態機械が CONNECT ストリームの
終了から終了コードを受け取るため、状態機械の終了通知がそのまま使われる。

### 確認

- `uv run pytest` は 547 件通過、7 件 skip
- `prek run --all-files` (pre-commit ステージ) が通る
- `cargo clippy --all-targets --all-features -- -D warnings` / `cargo fmt --check` /
  `cargo test` / `ruff check` / `ruff format --check` / `ty` が通る
