# moqt-rs の develop を d7a7b13 へ更新する

- Created: 2026-09-27
- Completed: 2026-09-27
- Branch: feature/update-moqt-rs-develop
- Polished: {YYYY-MM-DD}

## 目的

`Cargo.toml` が追従すると定めている moqt-rs の `develop` ブランチの最新へ
`Cargo.lock` を更新し、moqt-py が固定しているコミットとの差を埋める。

## 現状

`Cargo.lock` は moqt-rs の `28977d6` を固定している。`develop` の最新は `d7a7b13`
であり、この差に含まれる変更は MSF の codec 検証、MSF URI の percent-encoding、
WebTransport over H3 のエラー処理、URL の authority 解釈である。moqt-py が使う
`shiguredo_moqt` の公開 API と、`moqt.msf` が使う MSF codec の挙動に影響しうる。

## 設計方針

- `cargo update -p shiguredo_moqt` で最新へ更新し、`uv run pytest` で挙動の差を検出する
- 差が出た場合は moqt-rs の新しい挙動を正として moqt-py のコード・テスト・doc を合わせる
- 生成物である `python/moqt/_native.pyi` を再生成する

## 完了条件

- `cargo update -p shiguredo_moqt` 後の `Cargo.lock` で `uv run pytest` が全件通ること
- `cargo fmt` / `cargo clippy` / `ruff` / `ty` が通ること
- `python/moqt/_native.pyi` がビルドから再生成した内容と一致すること

## 解決方法

`Cargo.lock` の `shiguredo_moqt` を `28977d6` から `d7a7b13` へ更新した。

公開 API の差分はなく、`uv run pytest` は 416 件すべて通った。`cargo fmt` /
`cargo clippy` / `ruff` / `ty` と `python/moqt/_native.pyi` の再生成結果も差分がない
ことを確認した。
