# moqt-rs の develop を f9536cf へ更新し、未対応 request の検証へ追随する

- Created: 2026-10-18
- Completed: 2026-10-24
- Branch: feature/update-moqt-rs-f9536cf
- Polished:

## 目的

`Cargo.toml` が追従すると定めている moqt-rs の `develop` ブランチの最新へ `Cargo.lock` を
更新し、moqt-py が固定しているコミットとの差を埋める。差には、セッション状態機械が
未対応 request (PUBLISH_NAMESPACE / SUBSCRIBE_NAMESPACE / SUBSCRIBE_TRACKS) の本体を
解析してパラメータのスコープ・予約名前空間・Range Filter・AUTHORIZATION_TOKEN を検証する
変更、REGISTER を拒否時にも token cache へ適用する変更、AUTHORIZATION_TOKEN の alias 解決後
まで含めた一意性検証、`Transport::Qmux` の追加、`SessionEvent::GoawayDrainReady` の追加が
含まれる。後者 2 つは moqt-py が状態機械へ渡す接続方式と Python 境界のイベントに影響する。

## 現状

- `Cargo.lock` は moqt-rs の `3c63f49b3aedddfaa323b8d92cb25af35a655ee9` (2026-10-14) を
  固定していた
- 着手時の現行 `develop` の最新は
  `f9536cf058f7bcc5fdb8d857f34421a8c5bf2fe6` (2026-10-24) であり、`3c63f49` は現行
  `develop` の祖先である。差は 227 コミットである
- issue 作成時は `b5310c7acd4a2f6e91893f14488d0f4f679a8509` (2026-10-17) を対象にしていたが、
  その後に AUTHORIZATION_TOKEN の alias 解決後の一意性検証 (08a8b12)、KVP 宣言長超過の
  KEY_VALUE_FORMATTING_ERROR 化 (210aa0a)、予約名前空間の DOES_NOT_EXIST 拒否 (c912ecc)、
  未対応 request の Range Filter 検証 (f7c1115)、`SessionEvent::GoawayDrainReady` の追加
  (60244e5) が入ったため、対象を `f9536cf` に更新した
- `src/` の差のうち `playout` と音声の再生制御 (0282-0299) は、E2E テスト向け MOQT
  client / server ライブラリである moqt-py の責務外である。moqt-py の公開 API に影響する
  差は次の 4 つである
  1. `Transport::Qmux` が増えた。QMux は WebTransport ではないため、AUTHORITY / PATH の
     送信可否は native QUIC と同じ扱いになる (draft-ietf-moq-transport-22 §9.1.1
     (AUTHORITY) / §9.1.2 (PATH))。moqt-py は現状 `"qmux"` を `Transport::Quic` に写して
     おり、状態機械へ接続方式を正しく伝えていない
  2. `SessionEvent::GoawayDrainReady` が増えた。`SessionEvent` の網羅 match が
     コンパイルエラーになる
  3. `Session::recv_request` が未対応 request の本体を解析するようになった。本体の
     フレーミング違反・許可外パラメータ・REGISTER 適用の失敗は
     `PROTOCOL_VIOLATION` / `KEY_VALUE_FORMATTING_ERROR` /
     `AUTH_TOKEN_CACHE_OVERFLOW` / `DUPLICATE_AUTH_TOKEN_ALIAS` でセッションを閉じ、
     不正な AUTHORIZATION_TOKEN・予約名前空間・不正な Range Filter は REQUEST_ERROR
     (MALFORMED_AUTH_TOKEN / DOES_NOT_EXIST / INVALID_FILTER) でメッセージ単位に拒否して
     セッションを維持する (draft-ietf-moq-transport-22 §1.6 (Modularity) / §2.4.3
     (Reserved Namespaces) / §3.3.2 (Range Filters) / §8.9 (Authorization Token
     Compression) / §9.20.1 (Parameter Scope))。REGISTER は GOING_AWAY で拒否する場合も
     token cache へ適用する (MUST)
  4. AUTHORIZATION_TOKEN は alias 解決後の (Token Type, Token Value) の一意性をすべての
     受信メッセージで検証するようになった (draft-ietf-moq-transport-22 §8.9
     (Authorization Token Compression))
- moqt-py 側で追随が必要な箇所は次である
  - `src/core.rs` の `transport_from_python` が `"qmux"` を `Transport::Quic` に写している
  - `src/core.rs` の `convert_event` が `SessionEvent::GoawayDrainReady` を扱っていない
  - `tests/test_moqt.py` の
    `test_defined_but_unimplemented_request_is_rejected_with_not_supported` は Request ID
    だけの本体 (Request ID + Track Namespace Prefix + パラメータが揃っていない) を送って
    おり、新しい状態機械では本体の解析に失敗して `PROTOCOL_VIOLATION` でセッションを
    閉じるため失敗する
  - `tests/test_moqt.py` の
    `test_defined_but_unimplemented_response_message_closes_the_session` は終了理由の
    文言 `response-only control message` を期待しており、新しい文言
    `control message type cannot start a request stream` と一致しないため失敗する
  - `tests/test_e2e.py` の `test_subscribe_carries_all_authorization_token_kinds` は
    同じメッセージで REGISTER した alias を USE_ALIAS で参照しており、alias 解決後の
    (Token Type, Token Value) が重複するため MALFORMED_AUTH_TOKEN で拒否される
  - 上記 3 件以外に、未対応 request の新しい検証経路を固定するテストが無い

## 設計方針

- `cargo update -p shiguredo_moqt` で `Cargo.lock` を最新 (`f9536cf`) へ更新する
- `transport_from_python` は `"qmux"` を `Transport::Qmux` へ写すようにする。QMux では
  AUTHORITY / PATH を送れるため、既存の高水準 API の挙動は変わらない
- `SessionEvent::GoawayDrainReady` は Python の `goaway_drain_ready` イベントとして公開する。
  セッションを早期に閉じるかはアプリの判断であるため、I/O 層では何もしない
  (draft-ietf-moq-transport-22 §6.6.1 (Graceful Session Migration))
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
  - `.` 単独または `.session` の Track Namespace Prefix は REQUEST_ERROR
    (DOES_NOT_EXIST) でメッセージ単位に拒否し、セッションを維持すること
  - SUBSCRIBE_TRACKS に MAX_FILTER_RANGES を超える Range Filter が入る場合は
    REQUEST_ERROR (INVALID_FILTER) でメッセージ単位に拒否し、セッションを維持すること
- 応答専用メッセージが request stream の先頭に届く場合の期待メッセージを新しい文言へ更新する
- 既存の AUTHORIZATION_TOKEN の E2E テストは、同一メッセージ内の一意性を満たすよう
  REGISTER と USE_ALIAS を別メッセージに分ける
- `playout` / 音声の再生制御は公開 API に載せない
- 生成物である `python/moqt/_native.pyi` を再生成し、差分が doc コメントの追随だけである
  ことを確認する
- 実装の挙動は未対応 request の検証、AUTHORIZATION_TOKEN の一意性、Transport::Qmux の
  通知、GOAWAY drain イベント以外は変えない

## 完了条件

- `cargo update -p shiguredo_moqt` 後の `Cargo.lock` で `uv run pytest` が全件通ること
- 上記の未対応 request の検証経路を固定するテストが追加されていること
- `cargo fmt` / `cargo clippy` / `cargo test` / `ruff` / `ty` が通ること
- `prek run --all-files` (pre-commit ステージと pre-push ステージ) が通ること
- `python/moqt/_native.pyi` がビルドから再生成した内容と一致すること

## 解決方法

`cargo update -p shiguredo_moqt` で `Cargo.lock` の `shiguredo_moqt` を `3c63f49b` から
`f9536cf0` へ更新した。moqt-py 側は次の 3 点を追随させた。

- `transport_from_python` の `"qmux"` を `Transport::Qmux` へ写すようにした
- `SessionEvent::GoawayDrainReady` を `goaway_drain_ready` イベントとして Python へ公開し、
  `_runtime.py` ではセッションを閉じずに on_event での観測だけを許すようにした
- 既存テスト 3 件を新しい検証と文言へ追随させ、未対応 request の検証経路を固定する
  テスト 8 件と、QMux の transport 通知・GOAWAY drain イベントのテスト 2 件を追加した。
  AUTHORIZATION_TOKEN の E2E テストは REGISTER と USE_ALIAS を別メッセージへ分けた

### 確認

`uv run pytest` は 651 件すべて通る (relay が要る 7 件は skip)。`cargo fmt` /
`cargo clippy` / `cargo test` / `ruff` / `ty` と `prek run --all-files` (pre-commit
ステージと pre-push ステージ) も通ることを確認した。
`python/moqt/_native.pyi` の再生成による差分は `Session.client` の doc コメントの
追随だけであった。
