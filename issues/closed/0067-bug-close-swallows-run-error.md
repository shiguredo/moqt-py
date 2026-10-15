# QMux の接続終了時に受信ループの SSLError が close() から漏れる

- Created: 2026-10-15
- Completed: 2026-10-15
- Branch: feature/fix-close-swallows-run-error
- Polished:

## 目的

CI (ubuntu-26.04) で QMux のテストが `ssl.SSLError: [SSL: APPLICATION_DATA_AFTER_CLOSE_NOTIFY]`
で失敗した。`Client.close()` が受信ループの例外をそのまま送出しており、接続を閉じる側が
閉じる処理自体の失敗で落ちる。閉じる処理は best effort であるべきで、peer の書き込みと
同時に閉じた場合の TLS の失敗で利用者が落ちてはならない。

## 現状

- CI の失敗 (テストは `test_qmux_data_stream_timeout_sends_stop_sending`) のスタックは
  `tests/test_e2e.py` の `finally` の `await client.close()` →
  `python/moqt/moq/client.py` の `Client.close()` の `await self._run_task` →
  `webtransport/qmux/client.py` の `run()` → `_connection.py` の `_pump_once` →
  `asyncio.StreamReader.read` → `sslproto._do_shutdown` → `SSLObject.unwrap()` →
  `ssl.SSLError` である
- 原因は TLS 上の同時クローズである。QMux は TLS 上で動くため、こちらが close_notify を
  送った後に peer がアプリケーションデータ (CONNECTION_CLOSE など) を送ると、asyncio の
  TLS 層が `SSLObject.unwrap()` の時点で `APPLICATION_DATA_AFTER_CLOSE_NOTIFY` を送出する。
  テストでは `client.close()` の直後に server を止めるため、server 側の書き込みと
  close_notify が競合する。macOS では 30 回連続で再現せず、タイミング依存である
- `Client.close()` は `runtime.close()` を `contextlib.suppress(Exception)` で握っている
  一方、受信ループの終了待ちは `asyncio.CancelledError` 以外を送出している。この非対称が
  今回の失敗につながっている
- QUIC 直接接続と WebTransport も接続の終了待ちで例外が送出され得るため、QMux 固有では
  なく `Client.close()` 全体の問題である

## 設計方針

- `Client.close()` で受信ループの終了を待つ箇所では、接続の終了に伴う失敗だけを握る。
  具体的には `OSError` (`ssl.SSLError` と `ConnectionResetError` などを含む) をログに記録し、
  送出しない
- 例外を広く握ってはならない。既存の `test_state_machine_session_close_reaches_the_peer` は、
  peer の終了コードと理由を `close()` で観測できることを前提にしている。終了理由を運ぶ
  WebTransport の例外 (`WebTransportSessionClosedError` / `QuicApplicationError` /
  `QmuxConnectionError` / `QmuxProtocolError`) はいずれも `OSError` の派生ではないため、
  従来どおり送出する
- ログは英語で出し、閉じる処理の途中で起きたことを分かる文言にする。接続の異常自体は
  `_on_run_done` が `_fail_connect` で記録している
- テストの終了順は変えない。順序を変えると競合が server 側へ移るだけで、利用者が
  `close()` を呼ぶ経路の堅牢性は上がらない

## 完了条件

- QMux の e2e テスト (接続の終了を含むもの) が安定して通ること
- ローカルで QMux の e2e テストを 30 回連続で回して失敗しないこと
- `uv run pytest` が全件通ること

## 解決方法

`python/moqt/moq/client.py` の `Client.close()` で、受信ループの終了を待つ箇所の例外処理を
`except OSError` にした。接続の終了に伴う失敗はログに記録して送出しない。`ssl.SSLError` は
`OSError` の派生であるため、CI で観測した `APPLICATION_DATA_AFTER_CLOSE_NOTIFY` はこれで
握られる。`ConnectionResetError` や `BrokenPipeError` などの接続終了時の失敗も同様に扱う。

例外を広く握る実装を先に試したが、既存の `test_state_machine_session_close_reaches_the_peer`
が peer の終了コードと理由を `close()` で観測できることを前提にしていたため取りやめた。
終了理由を運ぶ `WebTransportSessionClosedError` / `QuicApplicationError` /
`QmuxConnectionError` / `QmuxProtocolError` はいずれも `OSError` の派生ではないため、今回の
変更でも従来どおり送出される。

### 確認

- `uv run pytest` は 640 件すべて通る (relay が要る 7 件は skip)。`prek run --all-files`
  (ruff-format / ruff-check / ty / tombi / cargo fmt / cargo clippy / cargo test) も通る
- QMux の e2e テストを 30 回連続で実行して失敗しないことを確認した
- CI (ubuntu-26.04) での再現はタイミング依存であり macOS では再現しないため、修正の確認は
  同じテストを含む CI の再実行で行う

## reopened にした理由

webtransport-py 2026.1.0.dev30 で 0289 がリリースされ、`TRANSPORT_ERRORS` に
`ssl.SSLError` が含まれるようになった。これにより QMux の `ConnectionDriver.run()` は
TLS 終了時の失敗を `QmuxConnectionError` として送出する (原因は `__cause__` に入る)。

`QmuxConnectionError` は `OSError` の派生ではないため、本 issue で入れた
`Client.close()` の `except OSError` では受けられない。QMux の接続断で受信ループが
失敗した場合に `close()` から `QmuxConnectionError` が漏れる状態が残るため、回避策を
見直す必要がある。reopened にして、接続の終了に伴う失敗を QMux の例外も含めて扱う形に
置き換える。

## 解決方法

`python/moqt/moq/client.py` の `Client.close()` で、受信ループの終了待ちに
`QmuxConnectionError` も加えた (`except (OSError, QmuxConnectionError)`)。

webtransport-py 2026.1.0.dev30 の 0289 により、QMux の `ConnectionDriver.run()` は
`TRANSPORT_ERRORS` に含まれる `ssl.SSLError` を `QmuxConnectionError` に包んで送出する。
`QmuxConnectionError` は `OSError` の派生ではないため、0067 で入れた `except OSError` では
受けられない。回避策を撤去するだけでは `close()` から `QmuxConnectionError` が漏れる状態が
残るため、接続の終了に伴う失敗として同じ扱いにした。

peer の終了理由を運ぶ例外 (`WebTransportSessionClosedError` / `QuicApplicationError` /
`QmuxProtocolError`) は従来どおり送出する。`test_state_machine_session_close_reaches_the_peer`
が前提にしている挙動である。

### 確認

- `uv run pytest` は 641 件すべて通る (relay が要る 7 件は skip)。`prek run --all-files`
  (ruff-format / ruff-check / ty / tombi / cargo fmt / cargo clippy / cargo test) も通る
- 接続の終了時に peer が書き込み続ける状況と、peer を先に止めてから `close()` を呼ぶ状況を
  実測したが、macOS では `close()` から例外は出なかった。競合はタイミング依存であるため、
  最終確認は CI の再実行で行う
