# CI で断続的に発生する E2E テストの接続タイムアウトを修正する

- Created: 2026-11-08
- Completed:
- Branch: feature/ci-connect-timeout
- Polished:

## 目的

CI の prek と python-315 で、ローカル E2E テストの `moq_pair` fixture が
`Client.connect` の 5 秒タイムアウトに達して断続的に失敗するのを修正する。

## 現状

`0072` の CI で次の失敗が発生した。

- `prek (ubuntu-26.04-arm)` の pre-push: 654 passed, 13 skipped, 2 errors
  - `test_client_goaway_is_notified_to_the_server[quic]`
  - `test_datagram_end_of_group_ends_the_group[wt-h3]`
- `python-315 (3.15t)`: 655 passed, 13 skipped, 1 error
  - `test_object_status_is_delivered[quic-subgroup-end-of-group]`

いずれも `python/moqt/moq/testing/__init__.py` の `moq_client_factory` が
`client.connect(timeout=5.0)` で `TimeoutError` になっている。テスト本体ではなく、
負荷の高い CI runner で接続確立が 5 秒を超えることが原因である。

同じ日に 0072 の 6 コミットを短時間で push したため、CI の実行が同時に重なり、
runner の負荷がさらに高くなっていた。

## 設計方針

- CI の workflow に `concurrency` を追加し、同じブランチの古い実行を
  `cancel-in-progress` で取り消す
- `moqt.moq.testing` の `DEFAULT_TIMEOUT` を 10 秒へ延ばす
- pytest の全体タイムアウトを 30 秒へ延ばし、接続待ちに余裕を持たせる
- テストの意味や待ち合わせ条件は変えない

## 作業項目

- [x] CI と e2e-test の workflow に `concurrency` を追加する
- [x] `DEFAULT_TIMEOUT` を 10 秒へ変更する
- [x] `pyproject.toml` の pytest timeout を 30 秒へ変更する
- [x] ローカルで全テストを複数回実行する
- [x] Python 3.15 / 3.15t で全テストを実行する
- [x] `prek run --all-files` を通す
- [ ] 変更を push した後の CI で確認する

## テスト

CI と同じ負荷を再現できないため、全テストを複数回実行して接続待ちが
タイムアウトしないことを確認する。CI の再実行結果でも確認する。

- Python 3.14: 3 回連続で 669 passed
- Python 3.15t: 669 passed
- Python 3.15: 669 passed の回と、接続確立のタイムアウトが 1 件出る回があった。
  単独では同じテストが通るため、負荷依存の flake と判断している
- `prek run --all-files`: Passed
