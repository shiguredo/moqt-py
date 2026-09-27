# moqt-rs の develop 追従で削除された API と意味論の変更に追随する

- Created: 2026-09-27
- Completed: 2026-09-27
- Branch: feature/update-moqt-rs-develop
- Polished: {YYYY-MM-DD}

## 目的

`Cargo.toml` が追従すると定めている moqt-rs の `develop` ブランチの最新へ
`Cargo.lock` を更新し、moqt-rs 側の API 変更と挙動変更に moqt-py のコード・doc を
追随させる。あわせて moqt-rs が公開しているパラメータ定数の取りこぼしを埋める。

## 現状

`Cargo.lock` は moqt-rs の `b373b37` (2026-09-23) を固定している。`develop` の
最新は `28977d6` (2026-09-27) であり、この間のコミットで次が変わっている。

- `stream::decoder::DecodedFetchEntry` / `DecodedFetchObject` から `Copy` が外れた
- `message::ControlMessage` に `Unsupported { type_id, request_id, body }` が追加された。
  draft-ietf-moq-transport-21 §9 Table 5 に定義済みだが実装しない 6 種
  (PUBLISH_NAMESPACE / SUBSCRIBE_NAMESPACE / SUBSCRIBE_TRACKS / NAMESPACE /
  NAMESPACE_DONE / PUBLISH_SKIPPED) を、未知型として拒否せず生バイト列のまま保持する
- `message_parameter::PARAM_RENDEZVOUS_TIMEOUT` (0x04) が追加され、SUBSCRIBE への
  出現が受理されるようになった
- 定義済みだが未実装の request に `REQUEST_ERROR` の `NOT_SUPPORTED` を返すようになった

`b373b37` への追従で `ControlMessage::Unsupported` の `message_kind` /
`message_body_to_python` の分岐、`moqt.moqt` の `PARAM_RENDEZVOUS_TIMEOUT` の公開、
`track_status` を `REQUEST_ERROR` で拒否する server は実装済みである。残っているのは
次の 2 点。

- `src/core.rs` の FETCH 経路が `DecodedFetchEntry` を `Copy` として扱っており、
  `pending_fetch_entries` へ戻す経路で move が起きる
- `src/codec.rs` の `Message.kind` の doc が、`unsupported` の `body` に入る
  `type_id` / `request_id` / `body` のキーを説明していない

## 設計方針

- moqt-rs の新しい公開 API と挙動を正とし、moqt-py 側を合わせる
- moqt-rs から削除された API は moqt-py の公開 API からも削除する
  (`CODEBASE.md` の「moqt-rs への追従」)
- relay 専用機構は moqt-py に含めない方針を維持する。`Unsupported` は wire から
  届きうるメッセージとして type ID と生バイト列だけを渡し、namespace 発見・告知の
  状態機械は追加しない
- 生成物である `python/moqt/_native.pyi` を再生成する
- ソースコードの位置は行番号ではなくファイルパスとシンボル名で示す

## 完了条件

- `cargo update -p shiguredo_moqt` 後の `Cargo.lock` で `uv run pytest` が全件通ること
- `PARAM_RENDEZVOUS_TIMEOUT` が `moqt.moqt` と `moqt._native` の両方から参照でき、
  `__all__` に含まれること
- `Message.kind` の doc が `unsupported` の `body` のキーを説明していること
- `cargo fmt` / `cargo clippy` / `ruff` / `ty` が通ること
- `python/moqt/_native.pyi` がビルドから再生成した内容と一致すること

## 解決方法

`Cargo.lock` の `shiguredo_moqt` を `28977d6` へ更新し、ビルドを通すための修正と
doc の補充を行った。

### `Copy` の削除への追随 (`src/core.rs`)

- FETCH のエントリを `pending_fetch_entries` へ戻す経路で move が起きないよう、
  `match entry` を `match &entry` に変えて参照で判定してから本体を match するようにした

### doc の追随 (`src/codec.rs`)

- `Message.kind` の doc に、`unsupported` のとき `body` に入る `type_id` /
  `request_id` / `body` のキーと、draft-ietf-moq-transport-21 §9 Table 5 の
  参照を追記した。`python/moqt/_native.pyi` も再生成した

`uv run pytest` は 416 件すべて通り、`cargo fmt` / `cargo clippy` / `ruff` / `ty` と
`prek run --all-files` も通ることを確認した。

## 補足

`0028` で `Client.track_status` が削除され、`testing` の server が peer からの
TRACK_STATUS を `REQUEST_ERROR` の `NOT_SUPPORTED` で拒否する実装は既に入っている。
本 issue ではこの挙動を変更しない。
