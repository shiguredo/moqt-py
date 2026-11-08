# TLS の PEM 読み込みとルート証明書を現在の crate へ移行する

- Created: 2026-11-08
- Completed:
- Branch: feature/tls-modern-crates
- Polished:

## 目的

`rustls-pemfile` は rustls-pki-types に PEM 読み込み機能が移され、今後の API 拡張が
行われない。`webpki-roots` は静的な Mozilla ルート証明書で、OS の証明書ストアや
失効確認を使えない。どちらも現在の推奨構成へ移行する。

## 現状

`Cargo.toml` で `rustls-pemfile = "2"` と `webpki-roots = "1"` を直接依存している。
`src/io/tls.rs` は次の用途で使っている。

- サーバーの証明書と鍵の PEM 読み込み
- クライアントの `ca_file` の PEM 読み込み
- クライアントの既定ルート証明書

## 設計方針

- PEM の読み込みは `rustls-pki-types` の `PemObject` API を使う
  - 証明書は `CertificateDer::pem_file_iter`
  - 秘密鍵は `PrivateKeyDer::from_pem_file`
- 証明書検証には `rustls-platform-verifier` の `Verifier` を使う
  - OS の証明書ストアと失効確認を使う
  - `ca_file` は `Verifier::new_with_extra_roots` で追加のルート証明書として渡す
- `verify_peer=False` の検証無効化は既存の `InsecureVerifier` を維持する
- 暗号プロバイダは既存どおり aws-lc-rs を使う

## 作業項目

- [x] `rustls-pemfile` と `webpki-roots` を依存から削除する
- [x] `rustls-pki-types` (std) と `rustls-platform-verifier` を追加する
- [x] 証明書・鍵・CA ファイルの読み込みを `rustls-pki-types` へ移行する
- [x] クライアントの検証を `rustls-platform-verifier` へ移行する
- [x] `ca_file` を使った接続テストを追加する
- [x] Rust と Python のテストを通す

## テスト

- `cargo check` / `cargo clippy --all-targets -- -D warnings` / `cargo test`
- `prek run --all-files`
- Python 3.14 / 3.15 / 3.15t の全テスト

### 結果

- `cargo check`: 成功
- `cargo clippy --all-targets -- -D warnings`: 成功
- `cargo test`: 成功
- `prek run --all-files`: 成功
- `ca_file` を使った接続テスト: 3 接続方式で成功
- Python 3.14 / 3.15 / 3.15t: 672 passed
