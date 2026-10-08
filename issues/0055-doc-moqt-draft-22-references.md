# MOQT の仕様参照を draft-ietf-moq-transport-22 の節番号に揃える

- Created: 2026-10-08
- Completed:
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
