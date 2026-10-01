# moqt-rs の develop を 1105e61 へ更新し、アプリケーションエラーコード無しのリセットに追随する

- Created: 2026-10-01
- Completed: 2026-10-01
- Branch: feature/update-moqt-rs-develop
- Polished: {YYYY-MM-DD}

## 目的

`Cargo.toml` が追従すると定めている moqt-rs の `develop` ブランチの最新へ `Cargo.lock` を
更新し、moqt-rs 側の公開 API の変更と挙動変更に moqt-py のコード・doc を追随させる。

## 現状

`Cargo.lock` は moqt-rs の `cc3e5fe` を固定している。`develop` の最新は `1105e61` で
あり、この差に含まれる 93 コミットのうち `src/` を変更するのは次の 6 件である。

- `f1a8529` / `85706f0` / `b8fc86a`: C4M (CBOR / COSE / CAT) の認可トークンの
  コーデックを `c4m` モジュールとして追加する
- `5d502a9`: `RequestStreamEnd::Reset` と `TerminationReason::PeerStreamReset` の
  `error_code` を `Option<u64>` にし、`None` を「アプリケーションエラーコード無し」にする
- `6a2fd05` / `1105e61`: 音声の時間圧縮・伸長と目標遅延の学習・A/V 同期を `playout`
  モジュールとして追加する

moqt-py のビルドと挙動に影響するのは `5d502a9` だけである。`src/name.rs` の関数追加と
`pub mod c4m` / `pub mod playout` は追加のみであり、削除された公開 API は無い。

### ビルドできない

`src/core.rs` の `request_stream_end` が `RequestStreamEnd::Reset` へ `u64` の `error_code` を
渡しているため、型が合わずビルドが通らない。

### リセットと FIN を取り違える

`python/moqt/moq/_runtime.py` の `Runtime.receive_stream_closed` は `error_code` が `None` か
どうかで終端の種類を決めている (`reset = error_code is not None`)。

WebTransport over HTTP/3 のトランスポート (webtransport-py の `h3.Client.on_stream_reset` と
`h3.Server.on_stream_reset`) は、wire のコードが WT_APPLICATION_ERROR レンジ外、または
レンジ内の予約コードポイントの場合に `error_code=None` を渡す。これは FIN ではなく
「アプリケーションエラーコード無しのリセット」である (draft-ietf-webtrans-http3-16 §4.4
(Resetting Data Streams))。現状はこれを FIN として状態機械へ渡すため、購読が正常終了として
終端し、`request_terminated` の理由が `peer_stream_reset` ではなく `peer_stream_fin` になる。

QUIC 経路と WebTransport over HTTP/2 経路のリセットは常にコードを持つため、`None` が
現れるのは WebTransport over HTTP/3 経路だけである。

## 設計方針

- moqt-rs の新しい挙動を正とし、moqt-py 側を合わせる
- 終端の種類 (`reset` か FIN か) は `error_code` から推測せず、I/O 層が明示して渡す。
  ネイティブ API は既に `reset: bool` と `error_code: Option<u64>` を別引数で受けているため、
  `Runtime.receive_stream_closed` の引数をそれに揃える
- `reset` が真で `error_code` が `None` の組み合わせを「アプリケーションエラーコード無しの
  リセット」として通し、`reset` が偽で `error_code` か `reliable_size` を渡す組み合わせを
  `ValueError` にする
- `c4m` と `playout` は moqt-py の公開 API に載せない。`c4m` は認可トークンの発行・検証で
  ありアプリケーションの責務、`playout` はアプリケーションの音声再生処理であり、
  E2E テスト向けの MOQT client / server ライブラリである moqt-py の責務外である。
  `name` に追加された関数も moqt-py に利用箇所が無い
- 生成物である `python/moqt/_native.pyi` を再生成する
- ソースコードの位置は行番号ではなくファイルパスとシンボル名で示す

## 完了条件

- `cargo update -p shiguredo_moqt` 後の `Cargo.lock` で `uv run pytest` が全件通ること
- `reset` が真で `error_code` が `None` のリセットが、FIN ではなく `peer_stream_reset` の
  `error_code: None` として `request_terminated` に現れること
- `reset` が偽のときの `error_code` / `reliable_size` の指定が `ValueError` になること
- `cargo fmt` / `cargo clippy` / `ruff` / `ty` が通ること
- `python/moqt/_native.pyi` がビルドから再生成した内容と一致すること

## 解決方法

`Cargo.lock` の `shiguredo_moqt` を `cc3e5fe` から `1105e61` へ更新し、`Option<u64>` 化に
伴うビルドエラーの修正と、リセットと FIN の取り違えの解消を行った。

### `Option<u64>` 化への追随 (`src/core.rs`)

- `request_stream_end` は `reset` が真のときに `error_code` の `Some` / `None` の両方を受け、
  そのまま `RequestStreamEnd::Reset` へ渡すようにした。これで「アプリケーションエラーコード
  無しのリセット」が表現できる
- あわせて `reset` が偽のときに `error_code` か `reliable_size` を渡す組み合わせを
  `ValueError` にした。従来はこの 2 つを黙って捨てていたため、`reset` を落とした呼び出しに
  気づけなかった
- 引数の検証を `receive_request_stream_closed` と `receive_data_stream_closed` の先頭へ移し、
  不正な呼び出しで状態だけが変わるのを防いだ
- `termination_reason_to_python` が返す `peer_stream_reset` の `error_code` が `None` に
  なりうることを doc に明記した

### リセットと FIN の区別 (`python/moqt/moq/`)

- `Runtime.receive_stream_closed` は `error_code` からの推測をやめ、`reset` をキーワード専用
  引数として受け取るようにした
- `Client` は WebTransport の `on_stream_reset` を `_on_stream_reset` で受けて `reset=True`、
  QUIC の FIN を `reset=False` として通知するようにした
- `testing` の server は WebTransport over HTTP/2 / HTTP/3 のどちらのリセットも `reset=True`
  で通知するようにした
- `python/moqt/_native.pyi` を maturin の型スタブ生成で再生成した

### 公開しない API

`c4m` (認可トークンのコーデック) と `playout` (音声の再生処理) は moqt-py の公開 API に
載せない。前者は認可トークンを発行・検証するアプリケーションの責務、後者はアプリケーションの
音声再生処理であり、E2E テスト向けの MOQT client / server ライブラリの責務外である。
`name` に追加された `serialize_namespace` / `parse_namespace` / `serialize_track_name` /
`parse_track_name` も moqt-py に利用箇所が無いため公開しない。

### 確認

`uv run pytest` は 418 件すべて通る (リセットと FIN の区別、FIN へのコード指定の拒否を
検証する 2 件を追加した)。`cargo fmt` / `cargo clippy` / `cargo test` / `ruff` / `ty` と
`prek run --all-files` (pre-commit / pre-push の両ステージ) も通ることを確認した。
