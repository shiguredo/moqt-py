# wt-h3 のデータグラム配送がまれに失われ、E2E テストが時々失敗する

- Created: 2026-10-08
- Completed:
- Branch: feature/fix-flaky-wt-h3-datagram-delivery
- Polished:

## 目的

`tests/test_e2e.py` のデータグラム系テストがまれに失敗し、pre-push フックや CI が原因不明の
まま落ちる。データグラムが失われているのか、テストの前提が誤っているのかを切り分けて
再発を止める。

## 現状

`uv run pytest tests/test_e2e.py -k datagram` を 25 回繰り返すと、次の割合で失敗する。

- moqt-rs `6c3ab63` (moqt-rs 更新前): 4/25 回
- moqt-rs `e8f9eb4` (moqt-rs 更新後): 1/25 回

いずれも wt-h3 のデータグラム系テストだけが失敗する。

- `test_object_status_is_delivered[wt-h3-datagram-end-of-group]`
- `test_datagram_properties_reject_a_non_normal_status[wt-h3]`
- `test_subscribe_and_receive_objects_over_datagram[wt-h3]`
- `test_datagram_publisher_priority_is_delivered[wt-h3]`

失敗はいずれも `_take_objects` が使う `OBJECT_TIMEOUT` (5 秒) の超過であり、遅延ではなく
消失である。`test_datagram_properties_reject_a_non_normal_status` だけを単独で 30 回
実行した場合は 1 回も失敗しない。

`Runtime.send_object_datagram` と `Runtime.receive_datagram` に一時的なログを入れて観測
したところ、失敗した実行では送信側が `allowed=True` で `TransportOps.send_datagram` を
呼んでいるのに対し、受信側の `Runtime.receive_datagram` が呼ばれていない。状態機械の
フィルタや購読状態で捨てられているのではなく、transport (webtransport-py の h3 DATAGRAM)
の区間で失われている。

### 追記: transport 層まで計測した結果

webtransport-py の h3 サーバー / クライアントと `Runtime` に一時的なログを入れて計測した
(CPU 負荷をかけた状態で `uv run pytest -q -s tests/test_e2e.py -k datagram` を繰り返し、
数回に 1 回再現する失敗を捕捉した)。失敗した実行では次の順で観測された。

1. `Runtime.send_object_datagram` が `allowed=True` で送信を決めている
2. h3 サーバーの `send_datagram` が呼ばれ、WebTransport セッションがデータグラムを
   キューし、`_send_to` がクライアントのアドレスへ 1 パケットを送出している
3. クライアントの socket はほぼ同時刻に UDP パケットを受信している
   (30 / 30 / 32 bytes の 3 パケット)
4. しかしクライアントの QUIC 層から DATAGRAM イベントが生成されず、
   `h3.Client._process_quic_events` の `EventType.DATAGRAM` 分岐にも到達しない
5. 5 秒待っても `Runtime.receive_datagram` が呼ばれず、テストがタイムアウトする

つまりデータグラムは送信側で 1 度キューされて送出まで進んでいるが、受信側の QUIC 層で
DATAGRAM フレームが捨てられている。moqt-py のフィルタ・購読状態・状態機械は関与していない。

## 設計方針

- まず transport 側で失われる条件を特定する
  - `TransportOps.send_datagram` の戻り値と例外、`max_datagram_frame_size` の交換、
    フロー制御、ソケットの受信バッファの状態を観測する
  - `moqt.moq.transport` と `moqt.moq.testing` のデータグラム経路で、送信失敗や受信失敗を
    握りつぶしている箇所がないか確認する
  - 観測の結果、送信側 (webtransport-py の `h3.Server.send_datagram` と `_send_to`) は
    データグラムを送出しており、受信側の QUIC 層 (`h3.Client._process_quic_events` の
    `EventType.DATAGRAM`) で DATAGRAM フレームが観測できていない。次はこの区間を絞り込む
- 原因が moqt-py 側にあれば修正する。webtransport-py 側にあれば再現手順と観測結果を
  添えて報告し、修正が入るまでテストの扱い (前提の見直しを含む) を決める
- QUIC の DATAGRAM は再送されないため、リトライで吸収して失敗を覆い隠すことはしない
- 原因を特定するまでは、再現できる条件と発生率を記録する

## 完了条件

- `uv run pytest tests/test_e2e.py -k datagram` を 25 回以上繰り返して 1 回も失敗しないこと
- データグラムが失われる原因 (moqt-py / webtransport-py / テストの前提のいずれか) と、
  実施した修正または報告を issue に記録すること
