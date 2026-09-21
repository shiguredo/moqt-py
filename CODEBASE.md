# CODEBASE

## 現在の運用方針

以下は指示が取り消されるまでの一時的な運用である。

- 変更履歴を `CHANGES.md` に残さないこと
  - `CHANGES.md` を新規作成しないこと
- Pull-Request とブランチを作らないこと
  - `develop` に直接コミットすること
  - 1 Issue 1 コミットとし、コミットするごとに push すること
  - `shiguredo-git` スキルのブランチ命名規則と Git Flow の記述より、この運用を優先すること

## E2E テスト向けライブラリとしての位置づけ

- moqt-py は他プロジェクトの E2E テストから使われることを想定したライブラリである
  - 他プロジェクトのテストへ `moqt.moq.testing` の server と pytest fixture を提供する
- `moqt.moq` が公開するのは client のみとする
  - server 側の型 (`Server` など) を `moqt.moq` に置かない
  - server の用途は E2E テストだけであり、`moqt.moq.testing` に置く
- 実装の細部 (ストリームの断片化、到着順、エラー、タイムアウト、状態遷移など) を検証できるよう、
  かなり細かい機能まで実現できること

## moqt-rs への追従

- `Cargo.toml` は `shiguredo/moqt-rs` の `develop` ブランチを追従すること
  - 実際にビルドしたコミットは `Cargo.lock` が固定する
  - 最新へ更新するときは `cargo update -p shiguredo_moqt` を実行すること
- moqt-rs から削除された API は moqt-py 側でも削除すること
  - 削除された `ControlMessage` / `RequestKind` / `SessionEvent` / パラメータ定数に対応する
    Python の公開 API を残さないこと
- relay 専用の機構は moqt-py に含めないこと
