# Client.track_status の扱いを決める

- Created: 2026-09-16
- Completed: 2026-09-22
- Branch: feature/change-track-status-policy
- Polished:

## 目的

`moq.moq.Client.track_status` を残すか削除するかを決める。

`CODEBASE.md` は「relay 専用の機構は moqt-py に含めないこと」と定めている。一方で
moqt-rs は TRACK_STATUS の送信側 (subscriber が問い合わせる側) を意図的に残しており、
moqt-py だけが送信 API を持たない状態は moqt-rs の公開 API と揃わない。

## 現状

`moq.moq.Client.track_status` は TRACK_STATUS を送信し、応答の受信を待つ。しかし
moqt-rs は TRACK_STATUS を endpoint が受信する request として受理せず、
`SESSION_PROTOCOL_VIOLATION` でセッションを閉じる。

そのため moqt-py の client から moqt-py の server へ `track_status` を呼ぶと、次のように
なる。

- 要求側には応答が返らず、制御メッセージの期限で失敗する
- 要求を受け取った側の MOQT セッションはプロトコル違反で閉じる

`tests/test_e2e.py` の `test_track_status_is_not_answered_by_an_endpoint` がこの挙動を
記録している。

TRACK_STATUS に応答できるのは relay などの第三者実装だけであり、moqt-py 同士では
成立しない。

## 設計方針

次のいずれかを選ぶ。

- 削除する: `CODEBASE.md` の「relay 専用の機構は含めない」に従い、`Client.track_status` と
  `TrackStatus` を削除する。低レベル API (`moqt.moqt.Session.send_track_status`) は
  moqt-rs の公開 API と揃えるため残す
- 残す: relay など応答する実装が相手の場合にだけ使える API として、doc にその制約を
  明記する。`moqt.moqt` の低レベル API と同じ表現を保つ

## 完了条件

- どちらを選ぶかが決まり、issue に記録されていること
- 選んだ方針がコードと doc に反映されていること
- 既存のテストがすべて通ること

## pending にする理由

削除は公開 API の削除であり、moqt-rs が意図的に残している送信側 API との整合をどう取るかは
方針判断である。`CODEBASE.md` の relay 除外方針と moqt-rs の公開 API のどちらを優先するかを
決める必要があり、実装だけでは決められない。

方針が決まった時点で reopened にして対応する。

## 解決方法

「削除する」を選ぶ。`CODEBASE.md` の「relay 専用の機構は moqt-py に含めないこと」に従い、
高レベル API である `Client.track_status` と `TrackStatus` を削除する。あわせて、送る API が
無くなると参照する意味が消える `Client.track_status_state` と
`Client.track_status_requests` も削除する。

- `moqt.moq` は client 側の要求から TRACK_STATUS を外す。`moqt.moq` のモジュール docstring と
  `Client` の docstring からも TRACK_STATUS を消し、client が TRACK_STATUS を送らないことと
  peer から届いた request に応答しないことを明記する
- `moqt.moq._runtime.Runtime.track_status` (送信と応答待ち) は呼び出し元が無くなるため削除する。
  状態の照会 (`Runtime.track_status_state` / `Runtime.track_status_requests`) は
  `moqt.moq.testing.Server` が使うため残す
- 低レベル API (`moqt.moqt.Session.send_track_status` と状態照会) は moqt-rs の公開 API と
  揃えるため残す。moqt-rs が TRACK_STATUS の受信側 (自側 publisher) を実装したため、
  状態機械側の往復は `tests/test_moqt.py` の低レベルテストで検証する
- e2e テストは高レベル API を使っていた `test_track_status_*` を削除する。テスト相手の
  `moqt.moq.testing.Server` は TRACK_STATUS を REQUEST_NOT_SUPPORTED で拒否する経路だけを持つ

この判断は、moqt-rs が TRACK_STATUS の受信側を実装した後も、moqt-py の client が
TRACK_STATUS を送る用途を持たないことによる。TRACK_STATUS の送信と応答受信は relay を
含む第三者実装との組み合わせで意味を持つ機能であり、moqt-py の client は購読と配信に
必要な request だけを公開する。
