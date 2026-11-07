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

`cargo` が PATH に無い環境では、maturin がコンパイラを見つけられるよう PATH を追加してから実行します。

```bash
PATH=$HOME/.cargo/bin:$PATH uv run maturin develop --generate-stubs
```

moqt-rs は公開リポジトリの `develop` ブランチを追従します。実際にビルドしたコミットは `Cargo.lock` が固定します。最新へ更新するときは次を実行します。

```bash
cargo update -p shiguredo_moqt
```

`moqt.moq` の I/O は Rust 側で実装しています。接続方式ごとのライブラリは次のとおりです。

- QUIC 直接接続: tobi-quic
- WebTransport over HTTP/3: tobi-quic / tobi-webtransport (http3-rs を含む)
- WebTransport over HTTP/2: http2-rs (`shiguredo_http2` の Sans I/O 状態機械を独自に駆動する)
- QMux: qmux-rs

tobi-quic と qmux-rs は git の `.git` を指す依存であり、`Cargo.lock` が実際のコミットを固定します。上流の更新を取り込むときは次を実行します。

```bash
cargo update -p tobi_quic -p tobi_webtransport -p shiguredo_tokio_qmux
```

## Python 3.15

`requires-python` は `>=3.14` で、3.14 / 3.14t / 3.15 / 3.15t をサポートします。
デフォルトの `.python-version` は 3.14 です。3.15 系は CI でも検証しており、
ローカルでは Python ごとに独立した環境を作って実行します。

```bash
# Python 3.15
UV_PROJECT_ENVIRONMENT=.venv-315 uv sync --python 3.15
UV_PROJECT_ENVIRONMENT=.venv-315 uv run --python 3.15 pytest

# Python 3.15t (Free-Threading)
UV_PROJECT_ENVIRONMENT=.venv-315t uv sync --python 3.15t
UV_PROJECT_ENVIRONMENT=.venv-315t uv run --python 3.15t pytest
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
