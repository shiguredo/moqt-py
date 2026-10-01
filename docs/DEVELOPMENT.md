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

## 実 relay への E2E テスト

`tests/test_connect.py` は環境変数 `TEST_MOQT_URI` が指す MOQT サーバーへ接続するテストです。`tests/test_relay.py` は同じ接続先へ publisher と subscriber の 2 つの client を張り、relay を挟んだ object の配送を確認します。映像と音声は実コーデックで符号化せず、LOC のプロパティを付けた固定のダミーペイロードを使います。

いずれも `TEST_MOQT_URI` が未設定の場合は skip します。GitHub Actions の `e2e-test` ワークフローでは repository secrets の `TEST_MOQT_URI` を環境変数として渡します。

```bash
TEST_MOQT_URI=moqt://<host>/ uv run pytest tests/test_connect.py tests/test_relay.py
```

開発用の relay は自己署名証明書を使うため、その場合は証明書の検証を切ります。既定は検証します。

```bash
TEST_MOQT_URI=moqt://127.0.0.1:4433/ TEST_MOQT_VERIFY_PEER=0 uv run pytest tests/test_relay.py
```

`tests/test_relay.py` が確認する経路は次のとおりです。

- 映像の subgroup stream 配送と LOC の TIMESTAMP / TIMESCALE / VIDEO_FRAME_MARKING
- 音声の subgroup stream 配送と LOC の TIMESTAMP / TIMESCALE / AUDIO_LEVEL
- 音声のデータグラム配送 (データグラムは再送されないため、複数件のうち 1 件の到達を確認する)
- MSF カタログの購読と FETCH による取得
