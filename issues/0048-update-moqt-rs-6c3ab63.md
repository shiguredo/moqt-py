# moqt-rs の develop を 6c3ab63 へ更新し、LOCATION_FILTER の符号化変更に追随する

- Created: 2026-10-05
- Completed: 2026-10-05
- Branch: feature/update-moqt-rs-6c3ab63
- Polished: {YYYY-MM-DD}

## 目的

`Cargo.toml` が追従すると定めている moqt-rs の `develop` ブランチの最新へ `Cargo.lock` を
更新し、moqt-py が固定しているコミットとの差を埋める。`develop` は履歴が作り直されており、
moqt-py が固定している `056cf19` は現行 `develop` の祖先ではない。

## 現状

- `Cargo.lock` は moqt-rs の `056cf19a75ce22e28b2638c21fdff9df52096b28` (2026-10-01) を
  固定している
- 現行 `develop` の最新は `6c3ab63e89f7c196d269deaee51881dfd9d71730` (2026-10-04) であり、
  この差で LOCATION_FILTER の符号化が Length-prefixed から Type-prefixed に変わった
  (draft-ietf-moq-transport-22 §9.20.9)
  - `LocationFilter` に `NoFilter` (Type 0x00) が増えた
  - `MessageParameters::location_filter` (生バイト) が削除され、`location_filter_typed` と
    `location_filter_update` に一本化された
  - 値は `MessageParameterValue::LocationFilter` として持つようになった
- moqt-py は旧符号化を前提としており、`src/message_parameters.rs` の `LocationFilter` に
  `none` kind がなく、`src/core.rs` の `parameter_value_to_python` が
  `MessageParameterValue::LocationFilter` を処理しないためコンパイルできない
- `src/core.rs` の `parameter_from_python` は型付きフィルタを `LengthPrefixed` に詰めており、
  新しい符号化と一致しない

## 設計方針

- `cargo update -p shiguredo_moqt` で `Cargo.lock` を最新へ更新する
- LOCATION_FILTER は Type-prefixed な値として扱い、次を追随する
  - `LocationFilter` に `none` kind を追加する
  - `MessageParameterValue::LocationFilter` を Python 側の `LocationFilter` へ変換する
  - 生バイト列は値域全体が 1 つのフィルタであることを検証し、余剰バイトと未知の Type を
    拒否する
- 生成物の `python/moqt/_native.pyi` を再生成し、テストを新しい符号化に合わせる
- 実装の挙動は LOCATION_FILTER の符号化以外は変えない

## 完了条件

- `cargo update -p shiguredo_moqt` 後の `Cargo.lock` で `uv run pytest` が全件通ること
- `cargo fmt` / `cargo clippy` / `cargo test` / `ruff` / `ty` が通ること
- `python/moqt/_native.pyi` がビルドから再生成した内容と一致すること

## 解決方法

- `Cargo.lock` の `shiguredo_moqt` を `056cf19` から `6c3ab63` へ更新した
- `src/message_parameters.rs` の `LocationFilter` に `none` kind と `NoFilter` の処理を
  追加し、`location_filter` は `location_filter_update` からフィルタ本体を返すようにした
- `src/core.rs` の `parameter_from_python` は型付きフィルタを
  `MessageParameterValue::LocationFilter` として渡し、`parameter_value_to_python` は
  `LocationFilter` を Python 側の値へ変換するようにした。生バイト列は
  `LocationFilter::decode` で値域全体を検証する
- `python/moqt/_native.pyi` を再生成し、テストの wire 期待値を新しい符号化へ更新した
- 検証: `uv run pytest` は 525 件すべて通る (relay が要る 7 件は skip)。
  `cargo fmt` / `cargo clippy` / `cargo test` / `ruff` / `ty` も通ることを確認した
