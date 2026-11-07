# moqt.moq の I/O を Rust の tobi-quic / http2-rs / http3-rs / qmux-rs へ移行する

- Created: 2026-11-07
- Completed:
- Branch: feature/rust-moq-io
- Polished:

## 目的

`moqt.moq` の接続・ストリーム・データグラムの I/O を Python の `webtransport-py`
から Rust の I/O 層へ移す。MOQT のテストツールとして、FIN、RESET_STREAM、
STOP_SENDING、データグラム、セッション終了コードと理由を Python から直接
制御・観測できることを優先する。

- QUIC 直接接続: tobi-quic
- WebTransport over HTTP/3: tobi-quic / tobi-webtransport (http3-rs)
- WebTransport over HTTP/2: http2-rs (`shiguredo_http2`)
- QMux: qmux-rs

## 現状

移行前は `moqt.moq` の client と `moqt.moq.testing` の server が
`webtransport-py` の `Client` / `Server` を使っていた。`webtransport-py` は
asyncio と C の I/O を前提とし、接続方式ごとに API の非対称性があった
(WT-H2 の STOP_SENDING、QMux のデータグラム、サーバー起点の bidi など)。

移行後は `moqt._native` の `IoClient` / `IoServer` が tokio で接続・ストリーム・
データグラムを所有し、Python の asyncio とは `call_soon_threadsafe` で Future の
完了とイベントをやり取りする。MOQT の状態機械は従来どおり Python 側が駆動する。

## 設計方針

- `IoClient` / `IoServer` は接続方式ごとの接続ドライバを tokio タスクとして起動し、
  コマンド (ストリーム開設、送信、RESET、STOP_SENDING、データグラム、終了) と
  イベント (データ、FIN、RESET、STOP_SENDING、データグラム、セッション終了) を
  チャネルでやり取りする
- 状態機械の終了コードと理由は全経路で peer へ伝える。peer が開始した終了は
  `TransportClosedError` でアプリへ伝える
- テストツールとしての観測性を優先し、低レベル API の差を吸収しない
  (WebTransport のストリーム ID と QUIC のストリーム ID をそのまま扱う)
- 公開 API は client のみとする。`moqt.moq.testing` の server は E2E テストの
  相手役に限定し、アプリケーション向けの server としては提供しない
- server の WebTransport ではサーバー起点の双方向ストリームを `MOQTError` にする
  (MOQT はクライアント起点の request stream だけを使う)

## 作業項目

- [x] `src/io/` に bridge / command / event / tls / net / quic / qmux / webtransport_h3 /
      webtransport_h2 を実装する
- [x] `python/moqt/moq/_io.py` に client / server のトランスポート adapter を実装する
- [x] `client.py` と `testing/server.py` を adapter 経由へ置き換える
- [x] `pyproject.toml` から `webtransport-py` への依存を削除する
- [x] `tests/test_client.py` を Rust I/O の構成に合わせて書き換える
- [x] E2E テストを WT-H3 / WT-H2 / QUIC / QMux の 4 経路で通す
- [x] `allowed_origins` は WT-H2 のみで受け付け、QUIC / QMux / WT-H3 では
      `ValueError` にする
- [ ] 上流の修正が入ったら H3 の回避策 (下記) を削除する

## 上流への申し送り

### tobi-quic / tobi-webtransport

1. **サーバーの双方向ストリーム配送 (再現確認済み)**

   tobi の `issues/` には該当する記載が見当たらない (2026-11-07 時点)。
   `tobi-webtransport/src/server.rs` の `accept_bidi_stream` は、ヘッダー読み込み
   タスクを `JoinSet` に spawn した後、`JoinSet::join_next` ではなく
   `connection.accept_bidirectional_stream()` で次のストリームを待つ。ヘッダー
   読み込みが完了しても、別のストリームやデータグラムが届くまで `receive()` が
   戻らない。

   再現: tobi の `examples/wt_server` と `examples/wt_client` をそのまま起動し、
   クライアントから双方向ストリームを開くと、サーバーは
   `WebTransport: accepted bidi stream 4` を記録するが、アプリの
   `Incoming::Bidirectional` は届かず、クライアントのエコー受信がタイムアウトする。
   空の単方向ストリームを 1 本送ると、その直後に双方向ストリームが届く。

   修正案: `accept_bidi_stream` を `JoinSet::join_next` と
   `accept_bidirectional_stream` の `select!` にし、ヘッダー読み込みの完了でも
   戻るようにする。

   moqt-py 側は、双方向ストリームの最初の送信後に空の単方向ストリームを 2 回
   (直後と 10 ms 後) 送って受信ループを起こしている。サーバー側は、データを
   1 バイトも受信せずに終了した単方向ストリームを状態機械へ通知しない。
   tobi が修正されたらこの回避策を削除する。

2. **並行受信 API (tobi issue 0635) が未実装**

   `Session::receive` が `&mut self` を取るため、受信とコマンドを同じタスクで
   `select!` して多重化している。0635 が入ったら受信専用タスクへ分ける。

3. **受信 STOP_SENDING の通知 (tobi issue 0636) が未実装**

   - サーバー: `WtSession::connection()` の `accept_stop_sending` を直接回して
     回避している。tobi-webtransport はこのキューを消費しないため競合しない
   - クライアント: `Session` から接続を取り出せないため、送信が
     `StreamStopped` で失敗した時点で STOP_SENDING として通知する。書き込みを
     続けないストリームでは検知が遅れる。0636 が入ったら書き換える

4. **サーバーが RESET_STREAM のコードを観測できない**

   `tobi-webtransport/src/server.rs` の `recv_data` は `Err(_) => Ok(None)` と
   しており、RESET_STREAM を FIN と同じ `StreamClosed` に畳む。サーバーは
   リセットのコードも、リセットかどうかも観測できない。moqt-py は
   `stream_data(fin=true)` として状態機械へ渡している。

5. **サーバーが Origin ヘッダーを公開しない**

   `WtSessionRequest` に Origin のアクセサーが無い。`allowed_origins` を黙って
   無視すると指定外の Origin を受け入れるため、WT-H3 では `ValueError` にして
   いる (`test_wt_h3_server_rejects_allowed_origins`)。

6. **サーバーの送信ストリームに reset が無い**

   `tobi_webtransport::server::WtSendStream` に `reset` が無いため、
   `Connection::reset_stream` を HTTP/3 のアプリケーションエラーコードへ変換して
   呼んでいる。クライアントの `WtSendStream` には `reset` がある。

### http2-rs

1. **WebTransport over HTTP/2 のクライアント API が無い**

   `tokio-http2` はサーバー (`WtServerRequest` / `WtServerSession`) だけを提供し、
   クライアント API を持たない。`tokio-http2` は `publish = false` である。
   moqt-py は `shiguredo_http2` の Sans I/O 状態機械 (`Connection` と
   `WtSession`) を TLS ソケット上で直接駆動し、クライアントとサーバーの両方を
   実装している (tokio-http2 は使っていない)。

2. **STOP_SENDING の通知**

   `shiguredo_http2::webtransport::WtEvent::StopSending` を使い、クライアント・
   サーバーの両方で受信できる。`tokio-http2` 経由では通知されないが、
   moqt-py は Sans I/O を直接使うためこの制限を受けない。

3. **サーバーのストリーム受信 API がリセットのコードを失う**

   `tokio-http2` の `WtBidiStream::recv` / `WtUniRecvStream::recv` は
   RESET_STREAM を文字列のエラーへ変換する。moqt-py は Sans I/O を直接使うため
   `WtEvent::StreamReset { error_code }` でコードを観測できる。

### qmux-rs

1. 双方向・単方向、RESET_STREAM、STOP_SENDING、データグラムは `Connection` の
   キューで観測できる
2. `RecvStream` を drop するとコード 0 の STOP_SENDING が送られるため、
   STOP_SENDING 送信後も受信側を保持して読み捨てている
3. `Connection` を drop しても CONNECTION_CLOSE が送られないため、
   `closed()` をタイムアウト付きで待ってから drop する
4. DATAGRAM は信頼配送であり、最大 16379 バイトである。MOQT のデータグラム
   (1 オブジェクト 1 データグラム) には QUIC と同じ意味にならないため、
   `moqt.moq.testing` の QMux 経路ではデータグラムを使わない
