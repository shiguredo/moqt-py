# moqt-rs の develop を cc3e5fe へ更新する

- Created: 2026-09-27
- Completed: 2026-09-27
- Branch: feature/update-moqt-rs-develop
- Polished: {YYYY-MM-DD}

## 目的

`Cargo.toml` が追従すると定めている moqt-rs の `develop` ブランチの最新へ
`Cargo.lock` を更新し、moqt-py が固定しているコミットとの差を埋める。

## 現状

`Cargo.lock` は moqt-rs の `d7a7b13` を固定している。`develop` の最新は `cc3e5fe`
であり、この差に含まれるコミットは `0169` / `0171` / `0162` / `0176` の 4 件である。
いずれも issue ファイルのみの更新であり、`src/` の変更を含まない。

## 設計方針

- `cargo update -p shiguredo_moqt` で最新へ更新し、`uv run pytest` で挙動の差を検出する
- 差が出た場合は moqt-rs の新しい挙動を正として moqt-py のコード・テスト・doc を合わせる
- 生成物である `python/moqt/_native.pyi` を再生成する

## 完了条件

- `cargo update -p shiguredo_moqt` 後の `Cargo.lock` で `uv run pytest` が全件通ること
- `cargo fmt` / `cargo clippy` / `ruff` / `ty` が通ること
- `python/moqt/_native.pyi` がビルドから再生成した内容と一致すること

## 解決方法

`Cargo.lock` の `shiguredo_moqt` を `d7a7b13` から `cc3e5fe` へ更新した。

`d7a7b13` との差は issue ファイルの更新だけで `src/` に変更が無いため、公開 API と
挙動の差分はない。`uv run pytest` は 416 件すべて通り、`python/moqt/_native.pyi` の
再生成結果にも差分が無いことを確認した。
