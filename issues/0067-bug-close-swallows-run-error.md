# QMux の接続終了時に受信ループの SSLError が close() から漏れる

- Created: 2026-10-15
- Completed:
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

- `Client.close()` で受信ループの終了を待つ箇所も best effort にする。`CancelledError` は
  従来どおり握り、それ以外の例外はログに記録して送出しない (`runtime.close()` と同じ扱い)
- ログは英語で出し、閉じる処理の途中で起きたことを分かる文言にする。接続の異常自体は
  `_on_run_done` が `_fail_connect` で記録しており、閉じる側で再度送出しない
- テストの終了順は変えない。順序を変えると競合が server 側へ移るだけで、利用者が
  `close()` を呼ぶ経路の堅牢性は上がらない

## 完了条件

- QMux の e2e テスト (接続の終了を含むもの) が安定して通ること
- ローカルで QMux の e2e テストを 30 回連続で回して失敗しないこと
- `uv run pytest` が全件通ること
