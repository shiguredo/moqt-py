# moqt-rs の C4M (CAT) を moqt.c4m として公開する

- Created: 2026-09-27
- Completed:
- Branch: feature/add-c4m-support
- Polished:

## 目的

moqt-rs が実装した C4M (draft-ietf-moq-c4m-01) の認可トークン (CAT) を moqt-py からも
使えるようにする。他プロジェクトの E2E テストから、トークンの発行・検証・認可判定と
DPoP proof の発行・検証を Python で組み立てられるようにする。

## 現状

- `Cargo.lock` の `shiguredo_moqt` は c4m 追加前の `cc3e5fe` を固定している
- moqt-py の公開モジュールは `moqt.moqt` / `moqt.loc` / `moqt.msf` の 3 つであり、
  c4m の公開 API を写したモジュールが無い
- moqt-rs の c4m は `CoseCrypto` trait で暗号実装を分離し、aws-lc-rs 実装は
  optional feature `aws-lc-rs` で提供する

moqt-rs の c4m が公開するもの (moqt-rs の `src/c4m.rs` と `src/c4m/`):

- `c4m`: `MoqtAction` / `Match` / `NamespaceMatch` / `MoqtScope` / `MoqtClaim` / `CatDpop`
- `c4m::cbor`: `Value` と `encode` / `decode` / `decode_partial`
- `c4m::cose`: `Algorithm` / `Header` / `CoseSign1` / `CoseMac0` / `CoseMessage` /
  `CoseEncodingOptions`
- `c4m::crypto`: `CoseKey` / `EcCurve` / `OkpCurve` / `DigestAlgorithm` と署名・検証・ハッシュ
- `c4m::cat`: `CatToken` / `CatClaims` / `Confirmation` / `CatTokenBuilder` と検証オプション
- `c4m::jwk` / `c4m::jwt` / `c4m::dpop`: JWK / JWS compact / DPoP proof

## 設計方針

- `Cargo.lock` を moqt-rs の develop 最新 (`0dc8214`) へ更新し、`Cargo.toml` で
  `shiguredo_moqt` の `aws-lc-rs` feature を有効にする
- 暗号実装は aws-lc-rs に固定する。`CoseCrypto` trait は Python へ公開せず、署名・検証・
  ハッシュは `moqt.c4m` の関数 (`sign` / `verify` / `digest`) として提供する
- Rust 側のラッパは `src/c4m.rs` と `src/c4m/` 配下に置き、`moqt._native` へ公開する。
  Python 側の `python/moqt/c4m.py` が公開 API を組み立てる
- Rust の enum のうち値が整数であるもの (`MoqtAction` / `Algorithm` / `EcCurve` /
  `OkpCurve`) は Python 側の `enum.IntEnum` で表現する。native 側は整数を受け渡しする。
  `TokenFormat` などの値が文字列であるものは Python 側の `enum.Enum` にする
- Track Namespace は既存 API と同じ `tuple[bytes, ...]`、Track Name は `bytes` で扱う
- デコード・検証の失敗は `ValueError` にする (既存の codec 層と同じ)
- 付録 A のテストベクタで、トークン構造・認可判定・検証・DPoP を Python から固定する

## 完了条件

- `moqt.c4m` から c4m の公開 API (クレーム、CBOR、COSE、鍵、CAT、JWK、JWT、DPoP) を
  参照できること
- 付録 A のベクタでトークンのデコード・認可判定・署名検証が一致すること
- `CatTokenBuilder` で compact / COSE 形式のトークンを発行し、`CatToken.verify` と
  `CatClaims.validate` / `authorize` で検証できること
- `DpopProofBuilder` で proof を発行し、`DpopProof.verify_against_cat_token` で
  検証できること
- `cargo fmt` / `cargo clippy` / `ruff` / `ty` / `uv run pytest` が通ること
- `python/moqt/_native.pyi` がビルドから再生成した内容と一致すること

## 解決方法
