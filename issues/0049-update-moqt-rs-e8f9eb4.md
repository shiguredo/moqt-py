# moqt-rs の develop を e8f9eb4 へ更新し、GOAWAY の deadline 満了による終端に追随する

- Created: 2026-10-08
- Completed:
- Branch: feature/update-moqt-rs-e8f9eb4
- Polished:

## 目的

`Cargo.toml` が追従すると定めている moqt-rs の `develop` ブランチの最新へ `Cargo.lock` を
更新し、moqt-py が固定しているコミットとの差を埋める。差には request stream 上の GOAWAY の
deadline 満了時に未終端の request を終端する挙動 (draft-ietf-moq-transport-22 §9.2 (GOAWAY))
が含まれ、moqt-py が公開する終端理由と GOAWAY の drain 判定に影響する。

## 現状

- `Cargo.lock` は moqt-rs の `6c3ab63e89f7c196d269deaee51881dfd9d71730` (2026-10-04) を
  固定している
- 現行 `develop` の最新は `e8f9eb4fe01f291e3bf2e15f67e82e8f1d23553f` (2026-10-06) であり、
  `6c3ab63` は現行 `develop` の祖先である。差は 22 コミット
- この差で `src/` が受けた変更は `playout` / `media_clock` と `session` である
  - `src/playout` は `sync` を削除して `buffer` を追加し、`src/media_clock.rs` は新規
    モジュールである。moqt-py はどちらも公開 API に載せていない
  - `src/session` は request stream 上の GOAWAY の deadline 満了時に、未終端の request を
    `TerminationReason::GoawayTimeout` で終端し、`STREAM_GOING_AWAY` でその request stream の
    送信方向を reset するようになった。終端後に遅延して届くメッセージ (応答 / REQUEST_UPDATE /
    PUBLISH_STATE_NOTIFY) と data stream は状態遷移させずに吸収する
- moqt-py 側で追随が必要な差分は次の 2 つである
  - `TerminationReason` に `GoawayTimeout` が増え、`src/core.rs` の
    `termination_reason_to_python` が非網羅パターンとなりコンパイルできない
  - GOAWAY の drain blocker 判定が「破棄できる entry は blocker にしない」に変わり、
    `tests/test_moqt.py` の
    `test_track_status_entry_is_terminated_when_the_requester_cancels` が失敗する
    (終端した TRACK_STATUS は `forget_track_status` で回収でき、回収前でも drain を
    妨げない)

## 設計方針

- `cargo update -p shiguredo_moqt` で `Cargo.lock` を最新へ更新する
- `TerminationReason::GoawayTimeout` を Python 側の `{"kind": "goaway_timeout"}` へ変換する
- 終端した TRACK_STATUS が GOAWAY の drain を妨げないことをテストで固定する
- 新しい GOAWAY の終端と遅延メッセージの吸収を、Python 境界のテストで固定する
  - 終端理由 `goaway_timeout` と `STREAM_GOING_AWAY` による `reset_request_stream`
  - 終端後に届く応答 (SUBSCRIBE_OK / FETCH_OK / TRACK_STATUS_OK) の吸収
  - 終端後に届く RESET_STREAM の吸収
- `playout` / `media_clock` はアプリケーションの再生制御であり、E2E テスト向けの MOQT
  client / server ライブラリである moqt-py の責務外であるため、公開 API に載せない方針を
  維持する
- 生成物である `python/moqt/_native.pyi` を再生成し、diff が出ないことを確認する
- 実装の挙動は GOAWAY の終端理由と drain 判定以外は変えない
- ソースコードの位置は行番号ではなくファイルパスとシンボル名で示す

## 完了条件

- `cargo update -p shiguredo_moqt` 後の `Cargo.lock` で `uv run pytest` が全件通ること
- `cargo fmt` / `cargo clippy` / `cargo test` / `ruff` / `ty` が通ること
- `python/moqt/_native.pyi` がビルドから再生成した内容と一致すること
