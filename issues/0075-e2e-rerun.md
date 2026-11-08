# E2E テストの接続タイムアウトを再実行で安定化する

- Created: 2026-11-08
- Completed:
- Branch: feature/e2e-rerun
- Polished:

## 目的

ローカルの E2E テストで、サーバーへの接続確立が稀に `TimeoutError` または
`ConnectionError` になり、CI が断続的に失敗するのを防ぐ。

## 現状

`moq_pair` fixture の `Client.connect(timeout=10)` が、負荷の高い環境で
タイムアウトすることがある。タイムアウトを 5 秒から 10 秒へ延ばし、CI の
`concurrency` も追加したが、全テストを 10 回実行すると数回は失敗する。

失敗するテストは毎回異なり、単独では同じテストが通る。サーバー側の接続受付が
一時的に遅れる、または止まる現象で、テスト対象のロジックの失敗ではない。

## 設計方針

- `pytest-rerunfailures` を開発依存に追加する
- `ConnectionError` と `TimeoutError` だけを最大 2 回再実行する
- テストの内容や待ち合わせ条件は変えない
- 恒久的な原因調査は別途行う。今回は CI を安定させることを優先する

## 作業項目

- [ ] `pytest-rerunfailures` を開発依存に追加する
- [ ] `ConnectionError` / `TimeoutError` だけを再実行する設定を追加する
- [ ] 全テストを複数回実行して安定することを確認する
- [ ] Python 3.15 / 3.15t でも確認する
- [ ] `prek run --all-files` を通す

## テスト

全テストを 10 回実行し、失敗したテストが再実行で回復することを確認する。
修正を push した後の CI でも確認する。
