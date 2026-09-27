# 実サーバーへの最低限の接続テストを追加する

- Created: 2026-09-27
- Completed:
- Branch: feature/add-connect-test
- Polished:

## 目的

moqt-py の client が実サーバーへ接続できることを確認できるようにする。ローカルの
`moqt.moq.testing` の server を使う E2E テストは同一プロセス内の相互接続であり、
実環境の TLS やサーバー実装との相互接続の失敗を検出できない。

接続そのものだけを確認する最小のテストと、GitHub Actions の repository secrets に
接続先がある場合だけ実行するワークフローを追加する。

## 現状

- 実通信のテストは `tests/test_e2e.py` が `moqt.moq.testing` の server を
  同一プロセスで動かしており、外部のサーバーへは接続しない
- 接続先を外部から与えて実行するテストが無く、CI から実サーバーへ接続する
  ワークフローも無い

## 設計方針

- `TEST_MOQT_URI` 環境変数の値へ接続する最小のテストを追加する
  - `Client.connect` が成功し、SETUP の交換が完了することだけを確認する
  - 接続方式は `Client` の既定 (WebTransport over HTTP/3) を使う
- `TEST_MOQT_URI` が未設定の場合は `pytest.mark.skipif` で skip する
- `.github/workflows/e2e-test.yml` を追加し、repository secrets の
  `TEST_MOQT_URI` を環境変数として渡してテストを実行する
  - secret が未設定の場合は環境変数が空になり、テストが skip するためジョブは成功する
- runner は PyO3 拡張のビルドに cargo と C コンパイラが必要なため `ubuntu-26.04`
  を使う (`ci.yml` と同じ理由)

## 完了条件

- `TEST_MOQT_URI` を設定しない場合に接続テストが skip され、`uv run pytest` が
  全件通ること
- `e2e-test.yml` が secret を環境変数として渡して接続テストを実行すること
- `prek run --all-files` が通ること

## 解決方法
