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

`Cargo.lock` の `shiguredo_moqt` を `28977d6` から `d7a7b13` へ更新した。公開 API の
差分はなく、`uv run pytest` は 416 件すべて通った。`python/moqt/_native.pyi` の再生成
結果にも差分がないことを確認した。

`uv run ty check` が次の 2 件を検出したため、あわせて修正した。どちらも moqt-rs の
追従とは独立の型の絞り込み漏れである。

- `python/moqt/moq/_runtime.py` の `_finish_request_stream` が
  `request_id` (`int | None`) を `dict.pop` のキーに渡していたため、`None` でないことを
  条件に加えた
- `tests/test_e2e.py` の
  `test_fetch_response_carries_properties_and_datagram_origin` が
  `MOQTObject.properties` (`bytes | None`) をそのまま `ObjectProperties.decode` へ
  渡していたため、`None` でないことを明示してから渡すようにした

`cargo fmt` / `cargo clippy` / `ruff` / `ty` と `prek run --all-files` が通ることを
確認した。
