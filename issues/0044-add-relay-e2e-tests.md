# 実 relay への E2E テストでダミーの映像と音声の配送を確認する

- Created: 2026-10-01
- Completed: 2026-10-01
- Branch: feature/add-relay-e2e-tests
- Polished: {YYYY-MM-DD}

## 目的

`TEST_MOQT_URI` が指す実 relay に対して、moqt-py の client が publisher と subscriber の
両方の役割で相互接続できることを CI で確認する。

`tests/test_connect.py` は SETUP の交換までしか確認しないため、relay を挟んだ PUBLISH /
SUBSCRIBE / FETCH と object の配送、LOC のプロパティ、MSF カタログが実環境で成立するかを
検出できない。映像と音声は実コーデックで符号化せず、配送の確認に必要なダミーのペイロードを
使う。

## 現状

- `tests/test_connect.py` は `TEST_MOQT_URI` へ接続し、SETUP の交換が完了することだけを
  確認する
- `.github/workflows/e2e-test.yml` は repository secrets の `TEST_MOQT_URI` を環境変数として
  渡し、`tests/test_connect.py` を実行する
- relay を挟んだ publisher / subscriber の配送を確認するテストが無い。同一プロセスで
  `moqt.moq.testing` の server を動かす `tests/test_e2e.py` では、実 relay の request 転送と
  object fan-out を検出できない
- `Client` の接続先の証明書は既定で検証する。開発用の relay は自己署名証明書を使うため、
  ローカルで実 relay のテストを実行する手段が無い

## 設計方針

- `tests/test_relay.py` を追加し、`TEST_MOQT_URI` が指す relay へ publisher と subscriber の
  2 つの client を接続する。接続方式は `Client` の既定 (WebTransport over HTTP/3) を使う
- 映像と音声は実コーデックで符号化しない。LOC のプロパティを付けた固定のダミーペイロードを
  使い、配送の確認に必要な最小限の内容にする
- 確認する経路ごとにテストを分ける。失敗したときにどの経路が壊れたかを特定できるようにする
  - 映像の subgroup stream 配送と LOC の TIMESTAMP / TIMESCALE / VIDEO_FRAME_MARKING
  - 音声の subgroup stream 配送と LOC の TIMESTAMP / TIMESCALE / AUDIO_LEVEL
  - 音声のデータグラム配送
  - MSF カタログの購読
  - MSF カタログの FETCH
- PUBLISH の応答を受けてから SUBSCRIBE し、SUBSCRIBE_OK を待ってから object を送る。
  relay は購読が確立する前に届いた object を保持しない場合があるため、順序を固定する
- データグラムは再送されない (draft-ietf-moq-transport-21 §11.2 (Object Datagrams)) ため、
  同じ内容を複数件送り、最初に届いた 1 件だけを確認する
- Track Namespace は実行ごとに変える。relay に前回の実行の state が残っていても衝突しない
  ようにするためである
- `TEST_MOQT_VERIFY_PEER=0` で証明書の検証を切れるようにする。既定は検証する
  (`tests/test_connect.py` も同じ扱いに揃える)
- `.github/workflows/e2e-test.yml` は `tests/test_connect.py` と `tests/test_relay.py` の
  両方を実行する
- 接続先の MOQT URI とその relay の構成は repository secrets が正であり、テストは値に
  依存しない

## 完了条件

- `TEST_MOQT_URI` を設定しない場合に relay のテストが skip され、`uv run pytest` が全件通ること
- `TEST_MOQT_URI` を設定した場合に映像・音声・データグラム・カタログの各テストが通ること
- `e2e-test.yml` が secret を環境変数として渡して `tests/test_relay.py` を実行すること
- `docs/DEVELOPMENT.md` に実行手順と `TEST_MOQT_VERIFY_PEER` の扱いが書かれていること
- `cargo clippy` / `ruff` / `ty` と `prek run --all-files` が通ること

## 解決方法

`tests/test_relay.py` を追加し、`e2e-test.yml` と `docs/DEVELOPMENT.md` を追随させた。

### `tests/test_relay.py`

`TEST_MOQT_URI` が指す relay へ publisher と subscriber の 2 つの client を接続し、次の
5 件を確認する。

- `test_relay_delivers_dummy_video`: ダミー映像 2 件を subgroup stream で送り、Group ID /
  Object ID / ペイロードと LOC の TIMESTAMP / TIMESCALE / VIDEO_FRAME_MARKING を確認する
- `test_relay_delivers_dummy_audio`: ダミー音声 2 件を subgroup stream で送り、同じく
  LOC の TIMESTAMP / TIMESCALE / AUDIO_LEVEL を確認する
- `test_relay_delivers_the_msf_catalog`: 映像と音声を告知する完全カタログを `catalog`
  Track で送り、購読側で同じ内容へ復元できることを確認する
- `test_relay_serves_the_msf_catalog_over_fetch`: 購読で object が relay へ届いたことを
  確かめてから同じ Track を FETCH し、fetch stream から同じ object が届くことを確認する
- `test_relay_delivers_dummy_audio_as_datagrams`: ダミー音声をデータグラムで送り、受信側の
  `MOQTObject.stream_id` が `None` になることとペイロードを確認する

Track Namespace は実行ごとに `os.urandom` で変える。テストは `TEST_MOQT_URI` が未設定の
場合は `pytest.mark.skipif` で skip する。

### 証明書の検証

`tests/test_relay.py` と `tests/test_connect.py` に `TEST_MOQT_VERIFY_PEER` を追加した。
`0` を設定したときだけ `Client(..., verify_peer=False)` になり、既定は検証する。開発用の
relay は自己署名証明書を使い、証明書をファイルとして取り出せないため、ローカルで実 relay の
テストを回すには検証を切る手段が要る。

### CI と開発手順

`.github/workflows/e2e-test.yml` の実行対象に `tests/test_relay.py` を加えた。secret が
未設定の場合は環境変数が空になり、いずれのテストも skip するためジョブは成功する。
`docs/DEVELOPMENT.md` に実行コマンド、`TEST_MOQT_VERIFY_PEER` の扱い、確認する経路を
追記した。

### 確認

ローカルで開発用の relay を起動し、次で 6 件すべて通ることを確認した (13 回連続で成功)。

```bash
TEST_MOQT_URI=moqt://127.0.0.1:14443/ TEST_MOQT_VERIFY_PEER=0 uv run pytest tests/test_relay.py tests/test_connect.py
```

実環境の relay は CI で secret を渡して確認する。`TEST_MOQT_URI` を設定しない
`uv run pytest` は 513 件通過し、relay のテスト 5 件と接続テスト 1 件が skip する。

### 補足

`Transport.Quic` では接続できないことを、このテストの検討中に確認した。別の issue で扱う。
