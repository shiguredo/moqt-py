# moqt-rs の develop を 3c63f49 へ更新する

- Created: 2026-10-14
- Completed: 2026-10-14
- Branch: feature/update-moqt-rs-3c63f49
- Polished:

## 目的

`Cargo.toml` が追従すると定めている moqt-rs の `develop` ブランチの最新へ `Cargo.lock` を
更新し、moqt-py が固定しているコミットとの差を埋める。

## 現状

- `Cargo.lock` は `162e5da0be5035ba68e1b50ef98b975f6737f597` (2026-10-14T09:06Z) を固定
  している
- 現行 `develop` の最新は `3c63f49b3a` (2026-10-14T09:21Z) であり、差は 7 コミットである
- この差で `src/` が受けた変更は `src/playout/splice_fade.rs` の追加のみであり、
  moqt-py が公開している API (`src/core.rs` 経由の状態機械) には影響しない
- moqt-py 側で追随が必要な API 変更・挙動変更は無い

## 設計方針

- `cargo update -p shiguredo_moqt` で `Cargo.lock` を最新へ更新する
- 生成物である `python/moqt/_native.pyi` を再生成し、差分が出ないことを確認する
- 公開 API に載せない方針の `playout` の変更は追随しない

## 完了条件

- `cargo update -p shiguredo_moqt` 後の `Cargo.lock` で `uv run pytest` が全件通ること
- `cargo fmt` / `cargo clippy` / `cargo test` / `ruff` / `ty` が通ること
- `python/moqt/_native.pyi` がビルドから再生成した内容と一致すること

## 解決方法

`cargo update -p shiguredo_moqt` で `Cargo.lock` の `shiguredo_moqt` を `162e5da0` から
`3c63f49b` へ更新した。moqt-py 側のコード変更は生じていない。

`src/` の変更は `src/playout/splice_fade.rs` のみであり、`python/moqt/_native.pyi` を
再生成しても差分が出ないことを確認した。

### 確認

`uv run pytest` は 626 件すべて通る (relay が要る 7 件は skip)。`cargo fmt` /
`cargo clippy` / `cargo test` / `ruff` / `ty` と `prek run --all-files` (pre-commit
ステージ) も通ることを確認した。
