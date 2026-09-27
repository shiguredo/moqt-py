# 開発

```bash
# 依存の同期と Rust 拡張の開発ビルド (型スタブも生成する)
uv sync
uv run maturin develop --generate-stubs

# テスト
uv run pytest
```

Git フックは prek で管理しています。`prek.toml` のフック (cargo fmt / cargo clippy / ruff / ty / tombi / pytest / cargo test) をコミット時とプッシュ時に実行します。

```bash
prek install --prepare-hooks
prek run --all-files
```

moqt-rs は公開リポジトリの `develop` ブランチを追従します。実際にビルドしたコミットは `Cargo.lock` が固定します。最新へ更新するときは次を実行します。

```bash
cargo update -p shiguredo_moqt
```

## 実サーバーへの接続テスト

`tests/test_connect.py` は環境変数 `TEST_MOQT_URI` が指す MOQT サーバーへ接続するテストです。未設定の場合は skip します。GitHub Actions の `e2e-test` ワークフローでは repository secrets の `TEST_MOQT_URI` を環境変数として渡します。

```bash
TEST_MOQT_URI=moqt://<host>/ uv run pytest tests/test_connect.py
```
