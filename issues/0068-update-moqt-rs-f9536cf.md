# moqt-rs の develop を b5310c7 へ更新し、未対応 request の検証と QMux の transport 通知に追随する

- Created: 2026-10-18
- Completed:
- Branch: feature/update-moqt-rs-b5310c7
- Polished:

## 目的

`Cargo.toml` が追従すると定めている moqt-rs の `develop` ブランチの最新へ `Cargo.lock` を
更新し、moqt-py が固定しているコミットとの差を埋める。差には、セッション状態機械が
未対応 request (PUBLISH_NAMESPACE / SUBSCRIBE_NAMESPACE / SUBSCRIBE_TRACKS) の本体を
解析してパラメータのスコープと AUTHORIZATION_TOKEN を検証する変更、REGISTER を
GOAWAY 拒否でも token cache へ適用する変更、`Transport::Qmux` の追加が含まれる。
後者 2 つは moqt-py が状態機械へ渡す接続方式と Python 境界のテストに影響する。

## 現状

- `Cargo.lock` は moqt-rs の `3c63f49b3aedddfaa323b8d92cb25af35a655ee9` (2026-10-14) を
  固定している
- 現行 `develop` の最新は `b5310c7acd4a2f6e91893f14488d0f4f679a8509` (2026-10-17) であり、
  `3c63f49` は現行 `develop` の祖先である。差は 97 コミット、`src/` は 10 ファイル
  (1225 行追加 / 257 行削除) に及ぶ
- `src/` の差のうち `playout` と音声の再生制御 (0282-0299) は、E2E テスト向け MOQT
  client / server ライブラリである moqt-py の責務外である。moqt-py の公開 API に影響する
  差は次の 2 つである
  1. `Transport::Qmux` が増えた。QMux は WebTransport ではないため、AUTHORITY / PATH の
     送信可否は native QUIC と同じ扱いになる (draft-ietf-moq-transport-22 §9.1.1
     (AUTHORITY) / §9.1.2 (PATH))。moqt-py は現状 `"qmux"` を `Transport::Quic` に写して
     おり、状態機械へ接続方式を正しく伝えていない
  2. `Session::recv_request` が未対応 request の本体を解析するようになった。本体の
     フレーミング違反・許可外パラメータ・REGISTER 適用の失敗は
     `PROTOCOL_VIOLATION` / `KEY_VALUE_FORMATTING_ERROR` / `AUTH_TOKEN_CACHE_OVERFLOW` /
     `DUPLICATE_AUTH_TOKEN_ALIAS` でセッションを閉じ、不正な AUTHORIZATION_TOKEN は
     REQUEST_ERROR (MALFORMED_AUTH_TOKEN) でメッセージ単位に拒否してセッションを維持する
     (draft-ietf-moq-transport-22 §1.6 (Modularity) / §8.9 (Authorization Token
     Compression) / §9.20.1 (Parameter Scope))。REGISTER は GOING_AWAY で拒否する場合も
     token cache へ適用する (MUST)
- moqt-py 側で追随が必要な箇所は次である
  - `src/core.rs` の `transport_from_python` が `"qmux"` を `Transport::Quic` に写している
  - `tests/test_moqt.py` の
    `test_defined_but_unimplemented_request_is_rejected_with_not_supported` は Request ID
    だけの本体 (Request ID + Track Namespace Prefix + パラメータが揃っていない) を送って
    おり、新しい状態機械では本体の解析に失敗して `PROTOCOL_VIOLATION` でセッションを
    閉じるため失敗する
  - `tests/test_moqt.py` の
    `test_defined_but_unimplemented_response_message_closes_the_session` は終了理由の
    文言 `response-only control message` を期待しており、新しい文言
    `control message type cannot start a request stream` と一致しないため失敗する
  - 上記 2 件以外に、未対応 request の新しい検証経路を固定するテストが無い

## 設計方針

- `cargo update -p shiguredo_moqt` で `Cargo.lock` を最新へ更新する
- `transport_from_python` は `"qmux"` を `Transport::Qmux` へ写すようにする。QMux では
  AUTHORITY / PATH を送れるため、既存の高水準 API の挙動は変わらない
- 未対応 request の新しい検証を Python 境界のテストで固定する
  - Request ID + Track Namespace Prefix + パラメータが揃った本体は従来どおり
    REQUEST_ERROR (NOT_SUPPORTED) で拒否され、セッションは維持されること
  - 本体が途中で切れている場合は `PROTOCOL_VIOLATION` でセッションを閉じること
  - PUBLISH_NAMESPACE に許可されないパラメータが入る場合は `PROTOCOL_VIOLATION` で
    セッションを閉じること
  - パラメータの値の直列化が壊れている場合は `KEY_VALUE_FORMATTING_ERROR` で
    セッションを閉じること
  - AUTHORIZATION_TOKEN の (Token Type, Token Value) が重複する場合は
    REQUEST_ERROR (MALFORMED_AUTH_TOKEN) でメッセージ単位に拒否し、セッションを
    維持すること
  - REGISTER が MAX_AUTH_TOKEN_CACHE_SIZE を超える場合は
    `AUTH_TOKEN_CACHE_OVERFLOW` でセッションを閉じること
  - GOAWAY 送信済みのときは NOT_SUPPORTED より GOING_AWAY を優先すること
- 応答専用メッセージが request stream の先頭に届く場合の期待メッセージを新しい文言へ更新する
- `playout` / 音声の再生制御は公開 API に載せない
- 生成物である `python/moqt/_native.pyi` を再生成し、diff が出ないことを確認する
- 実装の挙動は未対応 request の検証と `Transport::Qmux` の通知以外は変えない

## 完了条件

- `cargo update -p shiguredo_moqt` 後の `Cargo.lock` で `uv run pytest` が全件通ること
- 上記の未対応 request の検証経路を固定するテストが追加されていること
- `cargo fmt` / `cargo clippy` / `cargo test` / `ruff` / `ty` が通ること
- `prek run --all-files` (pre-commit ステージと pre-push ステージ) が通ること
- `python/moqt/_native.pyi` がビルドから再生成した内容と一致すること
