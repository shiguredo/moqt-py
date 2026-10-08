# パッケージの description を実態に合わせる

- Created: 2026-10-08
- Completed:
- Branch: feature/change-package-description
- Polished:

## 目的

PyPI と GitHub に出る一行説明が実態と合っておらず、初めて見る人に誤った姿を伝えている。
README で「本体は codec と sans I/O セッション状態機械、`moqt.moq` はその上に載る client」と
位置づけ直したので、description もそれに合わせる。

## 現状

`pyproject.toml` / `Cargo.toml` / GitHub の repository description は同じ文字列である。

```
Python client and server library for Media over QUIC over WebTransport
```

実態と合っていない点:

- `client and server library` と書いているが、公開 API は client だけである。server は
  `moqt.moq.testing` の E2E テスト専用であり、利用者向けの server ライブラリではない
  (CODEBASE.md の「`moqt.moq` が公開するのは client のみとする」)
- `over WebTransport` と書いているが、接続方式は QUIC 直接接続 / WT-H3 / WT-H2 であり、
  本体は I/O を持たない sans I/O なので WebTransport に閉じていない
- MOQT 層しか書いておらず、`moqt.loc` / `moqt.msf` / `moqt.c4m` の codec が抜けている
- 姉妹プロジェクトの書きぶりと揃っていない (moqt-rs は
  `Sans-I/O Rust library for Media over QUIC Transport (MoQT)`、webtransport-py は
  `webtransport-py is a Sans-IO WebTransport/HTTP3/HTTP2/QUIC/QMux library using ngtcp2, nghttp3, nghttp2 and dwnx.`)

## 設計方針

- webtransport-py の形 (`{name} is a Sans-IO {扱う層} library using {依存}.`) に合わせ、
  扱う層に codec を、依存に moqt-rs を書く
- クライアントを強調するため、client を文の要素として明記する
- 3 か所 (pyproject.toml / Cargo.toml / GitHub) を同じ文字列にする
- 文面は
  `moqt-py is a Sans-IO MOQT/LOC/MSF/C4M library with a WebTransport/QUIC client, using moqt-rs.`
  とする

## 完了条件

- `pyproject.toml` / `Cargo.toml` / GitHub の description が同じ新しい文字列になっていること
- `prek run --all-files` (pre-commit ステージ) が通ること
- `uv lock --check` が通ること (description の変更がロックに影響しないことの確認)
