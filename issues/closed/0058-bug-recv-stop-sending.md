# 受信した STOP_SENDING を状態機械へ通知していない

- Created: 2026-10-14
- Completed: 2026-10-14
- Branch: feature/fix-recv-stop-sending
- Polished:

## 目的

peer が自側の送信ストリームへ STOP_SENDING を送っても、moqt-py は状態機械へ通知して
いない。moqt-rs は I/O 層に対し、受信した STOP_SENDING を終端通知より先に
`recv_data_stream_stop_sending` / `fetch_stop_sending_received` で渡す契約を課して
いるが、Python 層からはどちらも呼ばれていない。

このため、購読者が購読や fetch を cancel しても publisher は把握できず、再オープン
禁止 (draft-ietf-moq-transport-22 §11.3.2 (Closing Subgroup Streams)) が記録されない。
FETCH の cancel では、仕様が bidi request stream と uni data stream の reset を MUST と
定めているのに publisher が送信を続ける。

## 現状

- `python/moqt/moq/_runtime.py` の `Runtime` は受信系として `receive_stream` /
  `receive_stream_closed` / `receive_datagram` を持つが、STOP_SENDING を受ける経路が無い
  (`recv_data_stream_stop_sending` と `fetch_stop_sending_received` の呼び出しがリポジトリ
  内に存在しない)
- `moqt.moq.Client` は transport のコールバックとして `on_stream_data` /
  `on_stream_reset` / `on_session_closed` / `on_session_ready` / `on_datagram` を登録するが、
  STOP_SENDING の受信は登録していない
- webtransport-py の統一 `Client` / `Server` はプロトコル非依存の `on_stop_sending` を
  持たない。WT-H2 だけが `webtransport._h2_client.Client.on_stop_sending` と
  `webtransport.Server.on_stop_sending` を持ち、コールバックは
  `(stream_id, error_code)` を受け取る。WT-H3 / QUIC は受信 STOP_SENDING を公開して
  いないため、今回は WT-H2 のみを対象とする
- 状態機械側の受け口は `moqt-py` の直近の moqt-rs 追随で
  `recv_data_stream_stop_sending(stream_id, error_code=None)` と
  `fetch_stop_sending_received(request_id, error_code=None)` として整っている
- 状態機械は通知された cancel を `Session::stopped_outgoing_subgroup_error_code` で
  参照できるが、moqt-py はこれを公開していない

## 設計方針

- `Runtime.receive_stop_sending(stream_id, error_code)` を追加し、ストリームの種別で
  通知先を分ける
  - 自側が開いた fetch stream は `fetch_stop_sending_received(request_id, error_code)`
  - subgroup stream と fill fetch stream は
    `recv_data_stream_stop_sending(stream_id, error_code)`
    (状態機械は fill fetch への STOP_SENDING を独立 cancel として吸収する)
  - 種別の判定のため `FetchWriter` に request_id と fill fetch かどうかを持たせる
  - 終端済みのストリームへ遅れて届いた STOP_SENDING は状態機械がエラーにするため、
    ログに記録して継続する (peer の STOP_SENDING は自側の FIN と競合しうる)
- WT-H2 のときだけ transport のコールバックを登録する。登録箇所は
  `moqt.moq.Client` と `moqt.moq.testing.Server` の両方とし、WT-H3 / QUIC では
  webtransport-py が受信 STOP_SENDING を公開していないことをコメントに残す
- `recv_data_stream_stop_sending` の効果をテストから観測できるよう、
  `Session::stopped_outgoing_subgroup_error_code` を `Runtime` の
  `stopped_outgoing_subgroup_error_code` (`request_id` / `track_alias` / `group_id` /
  `subgroup_id`) として公開する (外側の Option を「再オープン禁止中か」、内側を
  「エラーコードを解釈できたか」として `tuple[bool, int | None]` で返す)

## 完了条件

- WT-H2 で購読者がデータストリームへ STOP_SENDING を送ると、publisher の状態機械が
  cancel を記録すること
- FETCH の cancel では publisher の fetch が終端し、request stream の reset が
  送られること
- 終端済みストリームへの遅延した STOP_SENDING でセッションが壊れないこと
- `uv run pytest` が全件通ること

## 解決方法

`python/moqt/moq/_runtime.py` の `Runtime` に `receive_stop_sending` を追加し、自側が
開いたストリームの種別で状態機械への通知先を分けた。fetch stream は
`fetch_stop_sending_received(request_id, error_code)`、subgroup stream と fill fetch
stream は `recv_data_stream_stop_sending(stream_id, error_code)` へ渡す。種別の判定の
ため `FetchWriter` に `request_id` と `is_fill_fetch` を持たせた。終端済みストリームへ
遅れて届いた STOP_SENDING は状態機械が拒否するため、例外を送出せずログに記録して
継続する。

`python/moqt/moq/client.py` の `Client.__init__` は WT-H2 のときだけ
`webtransport._h2_client.Client.on_stop_sending` を登録し、`Client._on_stop_sending` から
`Runtime.receive_stop_sending` へ渡す。`python/moqt/moq/testing/server.py` の `Server` も
WT-H2 のときだけ統一 API の `webtransport.Server.on_stop_sending` を登録する。WT-H3 と
QUIC 直接接続は webtransport-py が受信 STOP_SENDING を公開していないため対象外とし、
その旨をコメントに残した。

`src/core.rs` に `stopped_outgoing_subgroup_error_code` を追加し、moqt-rs の
`Session::stopped_outgoing_subgroup_error_code` の `Option<Option<u64>>` を
`(bool, Option<u64>)` として公開した。`Runtime` からも同じ名前で呼べる。

`tests/test_e2e.py` に WT-H2 の実通信テストを 2 件追加した。

- `test_received_stop_sending_marks_the_subgroup_stopped`: 購読者がデータストリームへ
  STOP_SENDING を送ると、publisher の状態機械が `(True, STREAM_CANCELLED)` を記録し、
  購読が生きたままであること
- `test_received_stop_sending_terminates_the_fetch`: 購読者が fetch stream へ
  STOP_SENDING を送ると、publisher の fetch が `terminated` になること

### 確認

`uv run pytest` は 626 件すべて通る (relay が要る 7 件は skip)。`prek run --all-files`
(ruff-format / ruff-check / ty / tombi / cargo fmt / cargo clippy) も通ることを確認した。
