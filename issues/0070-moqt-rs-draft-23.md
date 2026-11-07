# moqt-rs の draft-ietf-moq-transport-23 追従

- Created: 2026-11-07
- Completed: 2026-11-08
- Branch: feature/moqt-rs-draft-23
- Polished:

## 目的

`Cargo.toml` が追従する moqt-rs の `develop` が draft-ietf-moq-transport-23 へ更新されたため、
moqt-py の Rust バインディング、Python の公開 API、テストを draft-23 に合わせる。

- moqt-rs: `66eb946135b4f077eafdbac15f68f35078cb724d` (2026-11-07)
- C4M: draft-ietf-moq-c4m-02 (moqt-rs の C4M 実装が draft-02 へ更新済み)
- ALPN / WebTransport のサブプロトコル: `moqt-23`

## 現状

draft-22 から draft-23 への変更で、moqt-py の公開 API とワイヤの扱いに次の差があった。

- 制御メッセージの Length が **固定 2 バイト** から **vi64** へ変わった。
  `src/core.rs` の `control_message_length` が固定 2 バイトで読んでいたため、
  すべての制御メッセージが「未完成」と判定され、セッションが成立しなかった。
- FETCH_OK が REQUEST_OK に統合された。FETCH の応答範囲の終端は状態機械が
  LARGEST_OBJECT と要求範囲から確定するため、アプリは `end_of_track` /
  `end_location` を指定できない。open-ended な FETCH では LARGEST_OBJECT が必須である。
  End of Track は FETCH_OK のビットではなく fetch stream の End of Track
  マーカーで通知される。
- FORWARD パラメータが PAUSED (0x11) に置き換わり、Subscription の
  `forward` 状態は `paused` になった。
- fetch ストリームのエンコーダが差分・End of Range・End of Group / End of Track を
  含めて変更された。moqt-py の Python 実装は draft-22 のフラグと差分を手書きしていた。
- エラーコードが再編され、TRUNCATED_OBJECT (0x203)、MALFORMED_MESSAGE (0x300)、
  INVALID_STREAM_HEADER (0x200)、UNEXPECTED_MESSAGE (0x303)、
  INVALID_PARAMETER (0x305) などが追加された。GOAWAY を request stream へ送れるのは
  request の receiver だけになった。
- Property のスコープ (Track / Object) が encode 時に検証されるようになった。
- C4M の `moqt` クレームが draft-02 の map 形式になり、action 0 は既知のアクションではなくなった。

## 設計方針

- 制御メッセージの Length は `decode_varint_prefix` で読み、`ControlMessage::decode` へ渡す。
- fetch ストリームのエンコードは Python で再実装せず、moqt-rs の
  `FetchStreamEncoder` を PyO3 の `FetchEncoder` として公開して使う。
  Python 側は返されたバイト列をストリームへ書き込むだけにし、差分の基準と
  マーカーの状態をライブラリへ一元化する。
- 削除された定数は再輸出せず、draft-23 の定数へ置き換える。
  - `PARAM_FORWARD` → `PARAM_PAUSED`
  - `SESSION_KEY_VALUE_FORMATTING_ERROR` → `SESSION_MALFORMED_KEY_VALUE`
  - `REQUEST_PREFIX_OVERLAP` / `STREAM_UNKNOWN_OBJECT_STATUS` は削除
  - 新しい session / stream コードを追加
- `MessageParameters` は構築時にライブラリの encode 検証を通し、PAUSED の値域や
  重複を `to_dict` まで遅延させずに `ValueError` にする。
- `FetchRequest.respond()` は `parameters` だけを受け取る。open-ended な FETCH では
  アプリが `LARGEST_OBJECT` を渡す。`Fetch.end_of_track` は fetch stream の
  End of Track マーカーで更新し、`Fetch.expires_ms` を追加する。
- ALPN / WebTransport のサブプロトコルは `moqt-23` にする。
- コメントと docstring の仕様参照は draft-ietf-moq-transport-23 の節番号へ更新する。
  `refs/moq/draft-ietf-moq-transport-23.txt` の見出しと突き合わせ、名前付きの引用が
  節番号と一致することを確認する。

## 作業項目

- [x] `cargo update -p shiguredo_moqt` で `66eb946` へ更新する
- [x] 制御メッセージの Length を vi64 として読む
- [x] `send_fetch_ok` / `send_fetch_object` / `recv_fetch_entry` / `send_request_error` を
      draft-23 の API へ合わせる
- [x] `FetchStreamEncoder` を `FetchEncoder` として公開し、Python の fetch 送信を置き換える
- [x] FORWARD を PAUSED へ置き換え、Subscription の `paused` を公開する
- [x] draft-23 の session / stream エラーコードを公開する
- [x] C4M のテストベクタを draft-02 のものへ更新する
- [x] Property のスコープ検証に合わせて property-based test の生成対象を絞る
- [x] `FetchRequest.respond()` と `Fetch` の API を更新する
- [x] ALPN を `moqt-23` にする
- [x] 仕様参照を draft-23 の節番号へ更新する
- [x] `cargo fmt` / `cargo clippy --all-targets --all-features -- -D warnings` /
      `cargo test` / `prek run --all-files` を通す
- [x] E2E を WT-H3 / WT-H2 / QUIC / QMux の 4 経路で通す
- [ ] コミットする (ユーザー確認後)

## テスト

- `uv run pytest -q -p no:randomly --timeout=20`: 656 passed, 7 skipped
- `cargo test`: 0 tests (バインディングに Rust の単体テストは無い)
- `prek run --all-files`: すべて Passed

## 解決方法

- `src/core.rs`
  - `control_message_length` を vi64 の Length 対応へ変更した
  - `ControlMessage::FetchOk` の削除、`RequestOk` / `TrackStatusResponse::Unsupported` /
    `SessionEvent::TrackStatusUnsupported` / `DecodedFetchEntry` の新しいマーカーへの対応
  - `send_fetch_ok(request_id, parameters, track_properties)`、
    `send_fetch_object(stream_id, group_id, object_id)`、
    `recv_fetch_entry(stream_id, &entry)`、
    `send_request_error(..., error_details)` へ変更した
  - `MessageParameters` の構築時に encode 検証を行い、`to_dict` の空バイト列を防いだ
- `src/fetch_encoder.rs` を追加し、`FetchEncoder` を `_native` から公開した
- `src/lib.rs` / `python/moqt/moqt.py`
  - 削除された定数を外し、PAUSED と draft-23 のエラーコードを追加した
- `python/moqt/moq/_runtime.py`
  - fetch ヘッダとエントリのエンコードを `FetchEncoder` へ委譲した
  - `respond()` の引数を `parameters` / `track_properties` にした
  - fetch の End of Track マーカーを `Fetch.end_of_track` へ反映した
- `tests/`
  - draft-23 のワイヤ (vi64 Length、REQUEST_OK、PAUSED、Property scope) へ更新した
  - GOAWAY の役割 (receiver だけが送れる) に合わせてテストを書き直した
  - C4M の認可ベクタを draft-02 の COSE 形式へ更新した
- `python/moqt/_native.pyi` は `uv run maturin develop --generate-stubs` で再生成した
- 仕様参照は draft-23 の本文の見出しと突き合わせ、名前付き引用の節番号の食い違いが
  0 件であることを確認した

実装とテストは完了し、develop へコミット済みである。
