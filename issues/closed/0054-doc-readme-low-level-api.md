# README を低レベル API 中心に再構成し、詳細を skills/moqt-py/SKILL.md へ移す

- Created: 2026-10-08
- Completed: 2026-10-08
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

## 解決方法

README を 392 行から 206 行へ縮め、低レベル API 中心の入口にした。詳細は
`skills/moqt-py/SKILL.md` (453 行) に移した。

README の構成:

- 「moqt-py について」で本体が MOQT / LOC / MSF / C4M の codec と sans I/O 状態機械であり、
  `moqt.moq` はその上に載るおまけであることを先に書く
- 「対応仕様」「対応プラットフォーム」「対応 Python」「インストール」は据え置く
- 「使い方」は `moqt.moqt` / `moqt.loc` / `moqt.msf` / `moqt.c4m` の最小例だけを置く
- 「おまけ: moqt.moq」は `Client` の最小例と `moqt.moq.testing` の存在だけを書き、
  低レベル API を隠さないことにも触れる
- 詳細へのリンクと「開発」(`docs/DEVELOPMENT.md`) を置く

`skills/moqt-py/SKILL.md` の構成:

- frontmatter (`name` / `description`)、インストールと動作環境、モジュール構成の表
- `moqt.moqt`: `Session` の回し方、API の分類表、codec 関数、パラメータとプロパティ、定数
- `moqt.loc` / `moqt.msf` / `moqt.c4m`: 例と公開 API の一覧
- `moqt.moq`: `Client` の引数とメソッド、`Transport`、購読・配信・取得の型、
  オブジェクトの送信 (subgroup / データグラム / End of Group / サイズ上限)、低レベル API
- `moqt.moq.testing`: fixture の表、`Server` の直接起動、補助 API
- 仕様参照と開発手順

あわせて次を直した。

- 「対応仕様」の MOQT を draft-ietf-moq-transport-22 にした。moqt-rs の README と
  `refs/moq` は -22 であり、moqt-py の ALPN も `moqt-22` である。README 自身が定める
  「対応仕様は moqt-rs に追従する」と一致させた。コードとテストの中の draft-21 引用
  (520 箇所) の棚卸しは目的が別なので、この issue では扱っていない
- `moqt.moqt` の例が「先頭 2 バイトは制御ストリームの stream type (0x2F00)」と書いていた箇所を、
  `decode_varint` で stream type を読む形に直した (wire のバイト列は varint 表現である)
- SKILL.md の `Session` の SETUP 交換の例は、テストと同じく自側の `start()` を先に呼ぶ順序にした
- SKILL.md の低レベル操作の例は、peer が解釈できる PADDING ストリームと PADDING データグラムを
  組み立てる形にした。生の操作が用途を登録しないことと、解釈できないバイト列がプロトコル違反に
  なることも書いた

### 確認

- README と SKILL.md の Python コードブロックのうち単体で実行できる 9 個を実際に実行して成功した
- `moqt.moq` の client の例と低レベル API の例は `moqt.moq.testing` の `Server` に対して実行し、
  購読とオブジェクト受信、PADDING ストリームと PADDING データグラムの送出まで成功した
- `uv run pytest` は 541 件通過、7 件 skip (TEST_MOQT_URI が必要な relay / connect)
- `prek run --all-files` (pre-commit ステージ) が通る
