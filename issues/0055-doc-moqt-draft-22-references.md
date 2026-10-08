# MOQT の仕様参照を draft-ietf-moq-transport-22 の節番号に揃える

- Created: 2026-10-08
- Completed: 2026-10-08
- Branch: feature/doc-moqt-draft-22-references
- Polished:

## 目的

コードとテストのコメントは「なぜこの実装なのか」の根拠として draft の節番号を引用している。
引用が古い draft のままだと一次資料で根拠を確認できず、引用を付けた意味が失われる。

moqt-py は moqt-rs が実装する draft-ietf-moq-transport-22 に追従しており、ALPN も `moqt-22`
であるが、引用は draft-ietf-moq-transport-21 のまま 514 箇所残っている。draft-22 では節番号が
変わっているため、単純な置換では直らない。

## 現状

引用の数 (2026-10-08 時点、`python/` / `src/` / `tests/`):

- `draft-ietf-moq-transport-21`: 514
- `draft-ietf-moq-transport-22`: 29

draft-22 と突き合わせて確認したずれ (引用 → draft-22 の実際):

- Object Status: §11.1.2 → §11.1.1 (§11.1.2 は Object Properties)
- Object Properties: §11.1.3 → §11.1.2
- 終了コード: §16.11.1 / §16.11.2 / §16.11.3 / §16.11.4 → §12.2 (Session Termination Codes) /
  §12.3 (Request Error Codes) / §12.4 (Publish Done Codes) / §12.5 (Stream Reset Error Codes)
- Track Alias: §3.1.2 → §3.1.3 (§3.1.2 は Subscription State Management)
- SUBSCRIBER_PRIORITY: §9.20.6 → §9.20.7
- GROUP ORDER: §9.20.9 → §9.20.8
- SETUP の Setup Option: §16.4 → §6.3 (Session initialization)
- Properties の表: §16.8 (Table 14) → §8.4 (Track and Object Properties)
- Mandatory to Understand Track Properties: §3.6 → §3.7 (§3.6 は Subscribing to Tracks by Prefix)
- MSF のカタログ Track 名: draft-ietf-moq-msf-01 §4.1 → §5 (Catalog) (§4.1 は LOC packaging)

draft-22 と一致している引用もあるため、一括置換はできない (§6.1 / §6.2.1 / §6.2.2 / §8.8 /
§9.1 / §9.1.1 / §9.2 / §9.20 / §11.2.1 / §11.3.1 / §11.4.1 / §13 / LOC の §2.3.x)。

一次資料は moqt-py のリポジトリに無く、moqt-rs の `refs/moq/draft-ietf-moq-transport-22.txt`
(および `draft-ietf-moq-loc-04.txt` / `draft-ietf-moq-msf-01.txt` / `draft-ietf-moq-c4m-01.txt`)
にある。

## 設計方針

- 引用を 1 件ずつ draft-22 の本文と突き合わせ、節番号と節名を直す。正規表現による一括置換はしない
- 引用先の内容が draft-22 で移動・統合・削除されている場合は、正しい節を選ぶか、引用を外して
  理由そのものを書く (issue 番号や行番号ではなく、仕様の記述内容を根拠にする)
- 一次資料に裏付けがあるのに引用が無い箇所は、この機会に引用を追加する
- 対象は `python/` / `src/` / `tests/` のコメントと docstring とする
  - `python/moqt/_native.pyi` は maturin の生成物であるため、生成元の `src/core.rs` を直して
    `uv run maturin develop --generate-stubs` で再生成する
- LOC / MSF / C4M の引用も同時に突き合わせる (draft-ietf-moq-loc-04 / draft-ietf-moq-msf-01 /
  draft-ietf-moq-c4m-01 / draft-nandakumar-moq-generic-dpop-proof-00)
- 挙動は変えない。コメントと docstring だけを直し、テストが通ることを確認する

## 完了条件

- `draft-ietf-moq-transport-21` の引用が残っていないこと (draft-21 との差を説明する記述を除く)
- 各引用の節番号と節名が一次資料の本文と一致すること
- `cargo fmt` / `cargo clippy` / `cargo test` / `ruff` / `ty` / `uv run pytest` が通ること
- `python/moqt/_native.pyi` がビルドから再生成した内容と一致すること

## 解決方法

`python/` / `src/` / `tests/` の MOQT の引用を draft-ietf-moq-transport-22 の節番号と節名に
揃えた (514 件 → 全 542 件が draft-22)。正規表現による一括置換ではなく、一次資料
(`moqt-rs` の `refs/moq/draft-ietf-moq-transport-22.txt` ほか) の節見出しと突き合わせて
1 件ずつ対応を決めた。

節番号が変わったもの:

- Subscriptions の配下: Track Alias §3.1.2 → §3.1.3、Subscription State Management
  §3.1.1 → §3.1.2、Fetch State Management §3.2.1 → §3.2.4、
  Mandatory Track Properties §3.6 → §3.7 (Mandatory to Understand Track Properties)
- 構造と符号化: Varint Encoding §1.4 → §8.1 (Variable-Length Integers)、Modularity §1.5 → §1.6、
  Object Status §11.1.2 → §11.1.1、Object Properties §11.1.3 → §11.1.2
- ストリームとデータグラム: Subgroup Object §11.3.2 → §11.3.2 (Closing Subgroup Streams)、
  Control Streams §6.4.1 → §6.4.1 (Unidirectional Streams)
- §9.20 のパラメータ: SUBGROUP_DELIVERY_TIMEOUT §9.20.4 → §9.20.3、OBJECT_DELIVERY_TIMEOUT
  §9.20.2 → §9.20.4、FILL TIMEOUT §9.20.6 → §9.20.5、SUBSCRIBER_PRIORITY §9.20.6 → §9.20.7、
  GROUP ORDER §9.20.9 → §9.20.8、FILL PARAMETERS §9.20.16 → §9.20.15、EXPIRES §9.20.17 →
  §9.20.16、LARGEST OBJECT §9.20.18 / §9.20.9 / §9.20.5 → §9.20.17、FORWARD §9.20.19 / §9.20.7 →
  §9.20.18、NEW GROUP REQUEST §9.20.20 → §9.20.19、TRACK_NAMESPACE_PREFIX §9.20.21 → §9.20.20、
  INCLUDE_PROPERTIES §9.20.22 → §9.20.21
- PUBLISHER_PRIORITY は draft-22 でパラメータではなく Track Property になったため
  §9.20.5 → §10.4 (DEFAULT PUBLISHER PRIORITY) とした

節名が変わったもの: Session Termination Error Codes (§16.11.1)、Stream Reset Error Codes
(§16.11.4)、MOQT IMPLEMENTATION (§9.1.5)。

表番号: §6.4.1 Table 3 → Table 2、§11.4.1 Table 7 → Table 8、§16.8 Table 14 → Table 15。

MOQT 以外の draft: MSF のカタログ Track 名 §4.1 → §5 (Catalog)、MSF §5.4 (Catalog variables) →
§5.4 (Variable Substitution)、C4M §2.1 (Authorization Scope) → §2.1 (moqt claim)。

あわせて直したもの:

- 複数行にまたがっていた引用を 1 行にまとめ、ruff の行長制限に合わせて折り返した
- 構造の一覧コメントで Subgroup Object が §11.3.2 を指していたため、draft-22 で
  Subgroup Object のフィールドが定義される §11.3.1 (Subgroup Header) にまとめた
- `python/moqt/_native.pyi` は `uv run maturin develop --generate-stubs` で再生成した

### 確認

- 一次資料と突き合わせる確認スクリプトで、節番号・節名の食い違い 0 件、
  存在しない節への引用 0 件 (MOQT / LOC / MSF / C4M / DPoP / WebTransport)
- `draft-ietf-moq-transport-21` の引用は `python/` / `src/` / `tests/` に 0 件
  (draft-21 との差を説明する `issues/` の記述を除く)
- `cargo fmt --check` / `cargo clippy --all-targets --all-features -- -D warnings` /
  `cargo test` / `ruff check` / `ruff format --check` / `ty` が通る
- `uv run pytest` は 541 件通過、7 件 skip (TEST_MOQT_URI が必要な relay / connect)
- `prek run --all-files` (pre-commit ステージ) が通る
- `python/moqt/_native.pyi` を 2 回再生成して同一の内容になること
- 変更はコメントと docstring だけで、実装の挙動は変えていない
