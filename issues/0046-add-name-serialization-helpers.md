# Track Namespace と Track 名の正規シリアライズ関数を公開する

- Created: 2026-10-02
- Completed: 2026-10-02
- Branch: feature/add-name-serialization-helpers
- Polished: {YYYY-MM-DD}

## 目的

`moqt.c4m` の `AuthorizationContext` が要求する `tns` / `tn` は draft-ietf-moq-transport-21
§8.8 (Representing Namespace and Track Names) の正規シリアライズ表現であり、リテラル
(`a-z` / `A-Z` / `0-9` / `_`) でないバイトは `.` と 16 進 2 桁へエスケープされる。この変換を
行う関数が moqt-py に無いため、利用者は `example.com` を `example.2ecom`、`video-hd` を
`video.2dhd` と手で書く必要がある。間違えても `verify_target` の
`actx.tns or actx.tn does not match the target` まで気づけない。

## 現状

- moqt-rs は `name::serialize_namespace` / `name::serialize_track_name` /
  `name::parse_namespace` / `name::parse_track_name` を `pub fn` として公開しており、
  `Cargo.lock` が固定している `1105e61` に含まれる
- moqt-py が公開しているのは `moqt.msf` の `parse_name` / `serialize_name` の 2 つだけである。
  どちらも `namespace--track` の全体形を扱うため、namespace と Track 名を個別に変換できない。
  `serialize_track_name` に相当する処理を `serialize_name` から取り出すこともできない
- `moqt.c4m.AuthorizationContext` の `tns` / `tn` はこの正規表現を前提にする
- `tests/test_c4m.py` は `example.2ecom` のようなエスケープ済みの文字列を直接書いており、
  変換規則がテストのリテラルに散っている

## 設計方針

- `moqt.msf` に `parse_namespace` / `serialize_namespace` / `parse_track_name` /
  `serialize_track_name` を追加する。既存の `parse_name` / `serialize_name` と同じ場所に置き、
  `-` と `.` の規則を 1 か所で扱う
- 変換は moqt-rs の関数をそのまま呼ぶ。moqt-rs 側の変更は不要である
- 失敗は `ValueError` にし、メッセージには moqt-rs の `NameParseError` の `Display` 表現を
  そのまま使う (既存の `parse_name` と同じ)
- 0 フィールドの namespace は空文字列、Track 名の `-` は `.2d` へエスケープされる (§8.8)
- `AuthorizationContext` の doc に、`tns` / `tn` へ渡す関数を明記する
- 生成物である `python/moqt/_native.pyi` を再生成する
- ソースコードの位置は行番号ではなくファイルパスとシンボル名で示す

## 完了条件

- `moqt.msf` から 4 関数が参照でき、`__all__` に含まれること
- `.` と `-` のエスケープ、0 フィールドの namespace、ラウンドトリップがテストで固定されること
- `moqt.msf` の変換結果を `AuthorizationContext` の `tns` / `tn` へ渡すと `verify_target` が
  通ること
- `uv run pytest` / `cargo fmt` / `cargo clippy` / `ruff` / `ty` と `prek run --all-files` が
  通ること
- `python/moqt/_native.pyi` がビルドから再生成した内容と一致すること

## 解決方法

`moqt.msf` に 4 関数を追加し、`AuthorizationContext` の doc から参照させた。

### `moqt.msf` の追加 (`src/msf.rs` / `src/lib.rs`)

- `serialize_namespace(namespace)` は moqt-rs の `name::serialize_namespace` を呼ぶ。0
  フィールドは空文字列になる
- `parse_namespace(text)` は `name::parse_namespace` を呼び、`ValueError` のメッセージに
  失敗した規則の説明を載せる
- `serialize_track_name(track_name)` は `name::serialize_track_name` を呼ぶ。`-` は `.2d` へ
  エスケープされる
- `parse_track_name(text)` は `name::parse_track_name` を呼ぶ
- `src/lib.rs` の `#[pymodule_export]` に 4 つを追加し、`python/moqt/msf.py` の再輸出と
  `__all__` を追随させた

### doc (`src/c4m/dpop.rs`)

`AuthorizationContext` の doc に、`tns` には `moqt.msf.serialize_namespace`、`tn` には
`moqt.msf.serialize_track_name` の結果を渡すことと、生の名前を渡すと `verify_target` で
一致しないことを追記した。

### テスト

- `tests/test_msf.py` に、`.` と `-` のエスケープ、0 フィールドの namespace、空のフィールドの
  拒否、生の `-` の拒否、大文字 16 進の拒否を追加した
- `tests/test_c4m.py` に、`moqt.msf` の変換結果を `AuthorizationContext` の `tns` / `tn` へ
  渡すと `verify_target` が通り、生の名前では一致しないことを追加した

### 確認

`uv run pytest` は 519 件すべて通る (6 件を追加した)。`cargo fmt` / `cargo clippy` /
`cargo test` / `ruff` / `ty` と `prek run --all-files` (pre-commit / pre-push の両ステージ) も
通ることを確認した。`python/moqt/_native.pyi` は再生成した内容と一致する。
