# WT-H3 で受信した STOP_SENDING を状態機械へ通知する

- Created: 2026-10-14
- Completed: 2026-10-14
- Branch: feature/add-wt-h3-recv-stop-sending
- Polished:

## 目的

WT-H3 接続でも、ピアが自側の送信ストリームへ STOP_SENDING を送ったことを状態機械へ
通知する。WT-H2 と QUIC 直接接続と QMux は通知できており、WT-H3 だけが取りこぼして
いる。webtransport-py 2026.1.0.dev28 で h3 層がピアの STOP_SENDING を通知できるように
なったため、追随する。

## 現状

- `python/moqt/moq/client.py` の `Client.__init__` は、WT-H2 のときだけ
  `h2.Client.on_stop_sending` を登録している。WT-H3 では登録していない
- `python/moqt/moq/testing/server.py` の `Server.__init__` も、統一 API の
  `Server.on_stop_sending` を `Transport.WebTransportOverHTTP2` のときだけ呼んでいる
- webtransport-py 2026.1.0.dev28 で次が追加された
  - `h3.Client.on_stop_sending(callback(stream_id, error_code))`。WebTransport の
    データストリームのみが対象であり、受信すると nghttp3 へ書き込み側の終了を伝える
  - `h3.Server.on_stop_sending(callback(session_id, stream_id, error_code, addr))`
  - `error_code` は WT_APPLICATION_ERROR レンジ外のコードでは `None`
    (アプリケーションエラーコード無し) になる
    (draft-ietf-webtrans-http3-16 §4.4 (Resetting Data Streams))
- 統一 API の `webtransport.Server.on_stop_sending` は HTTP/2 専用のままであり、
  WT-H3 では `ValueError` になる。ただし `webtransport.Server.h3` と
  `webtransport.Client.h3` は公開されており、h3 ハンドルから登録できる。WT-H2 も同じ
  理由でハンドルから登録している
- moqt-py の `Runtime.receive_stop_sending` は `int | None` を受け取れるため、WT-H3 の
  `None` をそのまま渡せる
- コメントに「受信 STOP_SENDING を公開していないのは WT-H3 だけである」と書いてある

## 設計方針

- `pyproject.toml` の webtransport-py の下限を 2026.1.0.dev28 へ上げる
- `Client.__init__` の WT-H3 分岐で `transport.h3.on_stop_sending` を登録する。
  `Client._on_stop_sending` の `error_code` を `int | None` にする
- `Server.__init__` の WT-H3 分岐で `transport.h3.on_stop_sending` を登録し、
  コールバックが受け取る `(session_id, stream_id, error_code, addr)` から
  `(addr, session_id)` の組で接続を引く
- WT-H3 の制約を書いたコメントを削除する
- `tests/test_e2e.py` の実通信テスト 2 件のパラメータに WT-H3 を追加し、
  WT-H2 / WT-H3 / QUIC の 3 接続方式で回す

## 完了条件

- WT-H3 でデータストリームへ STOP_SENDING を送ると、publisher が再オープン禁止として
  記録すること
- WT-H3 で fetch stream へ STOP_SENDING を送ると、publisher の fetch が終端すること
- `uv run pytest` が全件通ること

## 解決方法

`pyproject.toml` の webtransport-py の下限を 2026.1.0.dev28 へ上げ、`uv lock` と `uv sync`
で追随した。

`python/moqt/moq/client.py` の `Client.__init__` で、WT-H3 のときは `transport.h3` の
`on_stop_sending` を登録するようにした。`Client._on_stop_sending` の `error_code` は
`int | None` にした。WT-H3 では WT_APPLICATION_ERROR レンジ外のコードが
「アプリケーションエラーコード無し」として `None` で届くためである。状態機械へは
そのまま渡す (`Runtime.receive_stop_sending` が `int | None` を受け取る)。

`python/moqt/moq/testing/server.py` の `Server.__init__` で、WT-H3 のときは
`transport.h3` の `on_stop_sending` を登録するようにした。統一 API の `Server` の
`on_stop_sending` は HTTP/2 専用であり WT-H3 では `ValueError` になるため、WT-H2 と
同じくハンドルから登録する。コールバックは `(session_id, stream_id, error_code, addr)`
を受け取るため、`_on_h3_stop_sending` で `(address, session_id)` の組から接続を引いて
`Runtime.receive_stop_sending` へ渡す。

WT-H3 の制約を書いていたコメントを削除し、`tests/test_e2e.py` の実通信テスト 2 件の
パラメータに WT-H3 を追加した。

### 確認

- `test_received_stop_sending_marks_the_subgroup_stopped` と
  `test_received_stop_sending_terminates_the_fetch` が WT-H2 / WT-H3 / QUIC の 3 接続方式で
  通り、6 件すべて成功する
- `uv run pytest` は 636 件すべて通る (relay が要る 7 件は skip)。`prek run --all-files`
  (ruff-format / ruff-check / ty / tombi / cargo fmt / cargo clippy / cargo test) も通る
