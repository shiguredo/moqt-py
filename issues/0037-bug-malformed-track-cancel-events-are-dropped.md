# Malformed Track の cancel が接続エラーとして扱われる

- Created: 2026-09-22
- Completed:
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
