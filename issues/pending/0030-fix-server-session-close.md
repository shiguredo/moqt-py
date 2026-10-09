# Server が MOQT セッション終了時に WebTransport session を閉じられない

- Created: 2026-09-16
- Completed:
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
