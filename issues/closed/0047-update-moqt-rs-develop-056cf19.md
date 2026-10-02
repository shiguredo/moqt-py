# moqt-rs の develop を 056cf19 へ更新する

- Created: 2026-10-02
- Completed: 2026-10-02
- Branch: feature/update-moqt-rs-develop
- Polished: {YYYY-MM-DD}

## 目的

`Cargo.toml` が追従すると定めている moqt-rs の `develop` ブランチの最新へ `Cargo.lock` を
更新し、moqt-py が固定しているコミットとの差を埋める。

## 現状

`Cargo.lock` は moqt-rs の `1105e61` を固定している。`develop` の最新は `056cf19` であり、
この差に含まれる 5 コミットのうち `src/` を変更するのは `056cf19` だけである。

- `056cf19`: `playout::scheduler` (音声を鳴らす時刻を決めるスケジューラと統計) を追加する。
  `playout` モジュールに `scheduler` が増え、doc の説明も追随する
- 残る 4 コミットはドキュメント・行長・fuzz ターゲットの修正であり `src/` を含まない

moqt-py は `playout` を公開 API に載せていないため、公開 API と挙動の差分はない。

## 設計方針

- `cargo update -p shiguredo_moqt` で最新へ更新し、`uv run pytest` で挙動の差を検出する
- 差が出た場合は moqt-rs の新しい挙動を正として moqt-py のコード・テスト・doc を合わせる
- `playout` はアプリケーションの音声再生処理であり、E2E テスト向けの MOQT client / server
  ライブラリである moqt-py の責務外であるため、公開 API に載せない方針を維持する
- 生成物である `python/moqt/_native.pyi` を再生成する
- ソースコードの位置は行番号ではなくファイルパスとシンボル名で示す

## 完了条件

- `cargo update -p shiguredo_moqt` 後の `Cargo.lock` で `uv run pytest` が全件通ること
- `cargo fmt` / `cargo clippy` / `ruff` / `ty` が通ること
- `python/moqt/_native.pyi` がビルドから再生成した内容と一致すること

## 解決方法

`Cargo.lock` の `shiguredo_moqt` を `1105e61` から `056cf19` へ更新した。

`1105e61` との差は `playout::scheduler` の追加とドキュメントの更新だけであり、moqt-py が
使う `session` / `message` / `codec` / `name` / `parameter` / `msf` / `loc` / `c4m` には
変更がない。`playout` は公開していないため、moqt-py 側のコード・テスト・doc の変更は
不要だった。

### 確認

`uv run pytest` は 523 件すべて通る。`cargo fmt` / `cargo clippy` / `cargo test` / `ruff` /
`ty` と `prek run --all-files` (pre-commit / pre-push の両ステージ) も通ることを確認した。
`python/moqt/_native.pyi` は再生成した内容と一致し、差分が出ないことを確認した。
