# Malformed Track の cancel が接続エラーとして扱われる

- Created: 2026-09-22
- Completed: 2026-10-08
- Branch: feature/fix-malformed-track-cancel-events
- Polished:

## 目的

Malformed Track を検出したときの購読単位の cancel を、moqt-py の I/O 層が実行できるようにする。

draft-ietf-moq-transport-21 §12.1 (Malformed Tracks) は、購読者が Malformed Track を検出したら
対応する subscription / fetch を取り消し (MUST)、アプリへエラーを通知する (SHOULD) と定める。
セッションは閉じない。moqt-rs はこの区別を `MessageError::MalformedTrack` と
`Session::terminate_malformed_track` で表現しており、cancel は
`SessionEvent::StopSendingRequestStream` / `SessionEvent::ResetRequestStream` /
`SessionEvent::RequestTerminated` として I/O 層へ渡される。

## 現状

`CoreSession.receive_datagram` と `CoreSession.receive_data_stream` は、状態機械が
エラーを返すと `?` で `RuntimeError` へ変換する。このとき状態機械が積んだ cancel の
イベントは drain されずに残る。

`moqt.moq` の `Runtime.receive_datagram` はこの例外を捕捉せず `Client._on_datagram` へ
伝播し、`Client._fail_connect` が接続エラーとして記録する。結果として次の 2 つが起きる。

- cancel のイベント (RESET_STREAM / STOP_SENDING / 購読終了) が定期処理 (tick) まで遅延する
- セッションが `Established` のままなのに接続エラーとして記録される

再現手順 (低レベル API):

1. `Session.client` / `Session.server` を SETUP まで進め、`Session.send_subscribe` で購読する
2. `PROP_PRIOR_GROUP_ID_GAP` が Group ID を超える Object Datagram を
   `Session.receive_datagram` へ渡す
3. `RuntimeError: session error 0x3: malformed track: PRIOR_GROUP_ID_GAP exceeds the current
   group ID` になるが、`Session.established` は `True` のままで subscription は `terminated`
   になっている
4. もう一度 `Session.receive_datagram` を呼ぶと `stop_sending_request_stream` /
   `reset_request_stream` / `request_terminated` が遅れて現れる

## 設計方針

- 状態機械がエラーを返してもセッションが `Established` のままなら、積まれたイベントを
  drain してからアプリへ失敗を通知する経路を作る
- drain の入口が native に無いため、`CoreSession` に保留イベントを取り出す API を足すか、
  `receive_datagram` / `receive_data_stream` の戻り値にイベントを含める形にする
- `Runtime` はセッションが閉じた場合だけ接続の失敗として扱い、購読単位の cancel は
  イベントの処理として扱う

## 完了条件

- Malformed Track を検出した datagram / subgroup の受信で cancel のイベントが即座に処理されること
- セッションが `Established` のままである場合、接続エラーとして扱わないこと
- 購読単位の cancel とセッション終了を e2e テストで区別できること

## 備考

`Session::recv_datagram` がエラーを返すこと自体は moqt-rs の仕様どおりであり、moqt-py の
I/O 層の扱いの問題である。moqt-rs の `MessageError::MalformedTrack` は「セッションを閉じるか
購読だけ cancel するか」をアプリが判別するために追加された分類であり、本 issue はその分類を
moqt-py の公開 API まで届かせる作業にあたる。

## pending にする理由

moqt-rs の datagram 経路が Malformed Track の検出を購読単位の cancel として扱っておらず、
セッションを `PROTOCOL_VIOLATION` で閉じるため、moqt-py 側だけでは実装できない。

moqt-rs の `0111` は `RecvDataStreamError::MalformedTrack` の追加と
`Session::recv_subgroup_header` / `Session::recv_subgroup_object` /
`Session::recv_object_datagram` / `Session::recv_datagram` /
`Session::recv_data_stream_closed` の戻り値型の変更を設計方針と完了条件に挙げているが、
実装されたのは `MessageError::MalformedTrack` の分類と `Session::terminate_malformed_track`
までである。`src/session/data.rs` の `session_error_from_data_message` は
`MessageError::MalformedTrack` を `SESSION_PROTOCOL_VIOLATION` に写し、
`Session::recv_object_datagram` の検証経路はその結果で `Session::fail` を呼ぶ。そのため
datagram の Object Properties が Malformed Track の条件に当たる場合、購読だけが cancel
されずセッションが閉じる。

moqt-rs が datagram 経路でも `RecvDataStreamError::MalformedTrack` を返すようになったら
reopened にする。現時点で moqt-py 側から観測できる範囲ではセッションが閉じる経路であるため、
cancel のイベントが取り残される事象は起きない。`CoreSession.receive_datagram` /
`receive_data_stream` がエラー時に `drain_events` を呼ばない点は残っており、購読単位の
cancel を返す経路が入った時点で改めて対応が必要になる。

## reopened にする理由

pending の理由に書いた「moqt-rs の datagram 経路が購読単位の cancel を扱わず、セッションを
`PROTOCOL_VIOLATION` で閉じる」という前提が、現行の moqt-rs と一致しない。

現行の `Session::recv_object_datagram` と `Session::recv_subgroup_header` /
`Session::recv_subgroup_object` は、Malformed Track の検出時に `Session::fail` ではなく
`Session::terminate_malformed_track` を呼び、該当の request を終端して
`RequestTerminated` (`TerminationReason::MalformedTrack`) を積んだうえでエラーを返す。
セッションは `Established` のままである。これは更新前の `6c3ab63` でも同じである。

したがって残っているのは moqt-py 側の扱いであり、次の 2 つを直せばよい。

- `CoreSession.receive_datagram` / `receive_data_stream` がエラーを返したときに、状態機械に
  積まれた cancel のイベントを取り出せるようにする
- `Runtime` がそのエラーを接続の失敗として扱わず、購読単位の cancel として処理する

issue 0052 で `Client.runtime` / `Runtime.receive_datagram` / `Runtime.receive_stream` を
公開したため、tick に頼らずテストから直接検証できるようにもなった。

## 解決方法

`src/core.rs` に `CoreSession.drain_pending_events` を追加し、エラーを返した受信 API でも
状態機械に積まれたイベントを取り出せるようにした。

`python/moqt/moq/_runtime.py` の `Runtime` に `_apply_events_or_cancel` を追加し、
`receive_datagram` / `receive_stream` (データストリーム) / `receive_stream_closed` が
エラーを受け取ったときに、積まれたイベントを処理してから判断するようにした。

- セッションが `Established` のままなら購読単位の cancel として扱い、エラーを伝播しない
- セッションが閉じた場合は従来どおり接続の失敗としてアプリへ伝える

`tests/test_low_level.py` に、Malformed Track を datagram 経路と subgroup 経路のそれぞれで
検証するテストを追加した。どちらも低レベル API で状態機械へ直接投入するため、tick に頼らず
「同じ受信で終端が処理されること」「セッションが閉じないこと」「購読し直せること」を確認できる。

### 確認

`uv run pytest` は 541 件すべて通る (relay が要る 7 件は skip)。追加したテストは
`_apply_events_or_cancel` を外すと失敗することを確認した。`cargo fmt` / `cargo clippy` /
`ruff` / `ty` と `prek run --all-files` (pre-commit ステージ) も通ることを確認した。
