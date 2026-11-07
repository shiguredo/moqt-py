# TEST_MOQT_URI を使った relay の E2E テストを充実させる

- Created: 2026-11-08
- Completed: 2026-11-08
- Branch: feature/relay-e2e-tests
- Polished:

## 目的

`TEST_MOQT_URI` が指す実 relay に対する E2E テストを増やし、ローカルの
`moqt.moq.testing` の server では確認できない relay の振る舞いを検証する。

現在は接続、映像・音声の object 配送、MSF カタログ、fetch、データグラム、
native QUIC 接続を確認している。これに複数 Track の同時購読、複数 Group と
End of Group、PUBLISH_DONE、PAUSED による停止と再開、Group 範囲を指定した
fetch と cancel、再接続を加える。

## 設計方針

- 既存の `tests/test_relay.py` の `_relay_clients` / `_publish_and_subscribe` を
  使う。relay の URL は `TEST_MOQT_URI`、証明書検証は
  `TEST_MOQT_VERIFY_PEER` に従う
- 購読の停止・再開のように配送の有無を確認するテストは、購読の iterator を
  専用タスクで回し、一定時間 object が増えないことを確認する。iterator の
  `anext` をタイムアウトでキャンセルすると購読を再開できないためである
- relay が購読確立前に object を保持するとは限らないため、object は購読の
  確立後に送る
- `TEST_MOQT_URI` が未設定の環境では従来どおり全テストを skip する

## 作業項目

- [x] 同じ relay セッションで映像と音声の 2 Track を同時に購読し、交互に送った
      object が混ざらずに届くことを確認するテストを追加する
- [x] 複数 Group、End of Group の status、32 KiB の object が relay を経由して
      保たれることを確認するテストを追加する
- [x] PUBLISH_DONE が購読へ伝わり、object の反復が終了することを確認するテストを追加する
- [x] PAUSED で配送が止まり、解除後に再開することを確認するテストを追加する
- [x] Group 範囲を指定した FETCH と cancel を確認するテストを追加する
- [x] 接続、close、再接続を確認するテストを追加する
- [x] `TEST_MOQT_URI` 未設定でテストが収集・skip できることを確認する
- [x] `prek run --all-files` を通す
- [x] `TEST_MOQT_URI` を設定した実 relay で新しいテストを通す

## テスト

`TEST_MOQT_URI` が未設定のローカル環境では relay テストを実行できないため、
pytest の収集と skip、ruff / ty / prek で確認する。

2026-11-08 に `TEST_MOQT_URI` を設定した環境で
`tests/test_connect.py` / `tests/test_relay.py` の 13 テストがすべて通ることを確認した。
全体では 669 passed である。

## 解決方法

`TEST_MOQT_URI` を使う relay E2E に、複数 Track の同時購読、複数 Group と
End of Group、32 KiB の object、PUBLISH_DONE、PAUSED による停止と再開、
Group 範囲を指定した FETCH と cancel、再接続を追加した。

実 relay で 13 テストが通った。その過程で、終端済みの fetch への `Fetch.cancel`
を no-op にし、3.15t の PBT が既知の LOC Property の値域・UTF-8 制約に当たる
問題も修正した。全体のテストは 3.14 / 3.15 / 3.15t で 669 passed である。
