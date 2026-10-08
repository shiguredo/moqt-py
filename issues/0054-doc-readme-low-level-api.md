# README を低レベル API 中心に再構成し、詳細を skills/moqt-py/SKILL.md へ移す

- Created: 2026-10-08
- Completed:
- Branch: feature/doc-readme-low-level-api
- Polished:

## 目的

moqt-py の本体は MOQT / LOC / MSF / C4M の codec と sans I/O セッション状態機械であり、
`moqt.moq` の WebTransport / QUIC client はその上に載る付属物である。README は入口として
この立場を明確にし、低レベル API をアピールする。

現状の README は「使い方 (高レベル API)」から始まり `moqt.moq` が主役に見えるうえ、392 行の
詳細なリファレンスになっていて概要を掴みにくい。詳細は利用リファレンスとして
`skills/moqt-py/SKILL.md` にまとめ、README は短い入口にする。

## 現状

- `README.md` は 392 行で、構成は「moqt-py について」「対応仕様」「対応プラットフォーム」
  「対応 Python」「インストール」「使い方 (高レベル API)」「使い方 (低レベル API)」
  「ライセンス」である
- 「使い方 (高レベル API)」が `Client` の説明と `moqt.moq.testing` の fixture に 170 行を
  使い、低レベル API の説明はその後に置かれている
- `skills/` ディレクトリは存在しない。姉妹プロジェクトの webtransport-py は
  `skills/webtransport-py/SKILL.md` に利用リファレンスを持つ
- 「対応仕様」は MOQT を draft-ietf-moq-transport-21 としているが、moqt-rs の README と
  `refs/moq` は draft-ietf-moq-transport-22 であり、moqt-py の ALPN も `moqt-22` である。
  README 自身が「対応仕様は moqt-rs に追従する」と定めているため、記載が古い

## 設計方針

- README は次で構成し、詳細は SKILL.md へリンクする
  - 「moqt-py について」: 本体が codec と sans I/O 状態機械であることを先に書き、
    `moqt.moq` は付属物として最後に触れる
  - 「対応仕様」「対応プラットフォーム」「対応 Python」「インストール」
  - 「使い方」: 低レベル API の最小例 (`moqt.moqt` / `moqt.loc` / `moqt.msf` / `moqt.c4m`)
    だけを置く
  - 「おまけ: moqt.moq」: `Client` の最小例と `moqt.moq.testing` の存在のみを書き、
    詳細は SKILL.md に委ねる
  - 「開発」「ライセンス」
- `skills/moqt-py/SKILL.md` を webtransport-py の SKILL.md と同じ形 (frontmatter +
  利用リファレンス) で作り、README から移した詳細と API 一覧をまとめる
  - モジュール構成、`moqt.moqt` / `moqt.loc` / `moqt.msf` / `moqt.c4m` の公開 API と例
  - `moqt.moq` の `Client` / `Transport` / `Subscription` / `Publication` / `Fetch` /
    `MOQTObject` / `PeerGoaway` と低レベル API (`Client.runtime` / `Client.session` /
    `Client.on_event` / 生のストリーム操作)
  - `moqt.moq.testing` の fixture と `Server` の使い方
- 仕様参照は moqt-rs が実装する draft-ietf-moq-transport-22 に合わせる。コードとテストの
  中の draft-21 引用 (520 箇所) の棚卸しは目的が別なので、この issue では扱わない
- README と SKILL.md の Python コードブロックは ruff-format の整形対象であるため、
  整形済みの内容で書く

## 完了条件

- README が低レベル API を先に説明し、`moqt.moq` を付属物として扱っていること
- API 一覧と使い方の詳細が `skills/moqt-py/SKILL.md` にあること
- README から `skills/moqt-py/SKILL.md` へリンクがあること
- `prek run --all-files` (pre-commit ステージ) が通ること
