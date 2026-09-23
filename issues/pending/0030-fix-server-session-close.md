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

`moq.moq.Server` の転送操作で、状態機械からの close 要求は
`transport.close_stream(address, session_id, 0)` に繋がっている。これはストリームを閉じる
だけであり、WebTransport session は閉じない。終了コードと理由も捨てている。

`moq.moq.Client` は `transport.close()` を呼ぶため WebTransport session は閉じるが、
こちらも終了コードと理由は渡していない。

webtransport-py の `h3.Server` には WebTransport session を閉じる API が無い
(`close_stream` / `reset_stream` / `stop` のみ)。`h3.Client.close()` もコードと理由を
受け取らない。

WT-H2 経路は `h2.SessionWriter.close_session(error_code, error_message)` でコードと理由を
渡せており、moqt-py もそれを使っている。h3 と quic だけができない状態である。

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

- h3 層: `h3.Server` に session 終了 API が無く、`h3.Client.close()` は終了コードと
  理由を受け取らない。低レベル `webtransport_ext.h3.Session.close_session` は既に
  `error_code` と `error_message` を受け取れるため、高レベル層への露出が 0257 の対象である
- quic 層: `quic.Client.close()` は終了コードと理由を受け取らない (0258)
- h2 層: `h2.SessionWriter.close_session(error_code, error_message)` が既にあるため、
  moqt-py は WT-H2 経路では既に終了コードと理由を渡せている。残るのは h3 / quic との
  非対称である

webtransport-py の 0257 / 0258 がリリースされた時点で reopened にして対応する。
