//! tobi_webtransport を使った WebTransport over HTTP/3 (WT-H3) の I/O。
//!
//! WebTransport は HTTP/3 の extended CONNECT でセッションを確立し、1 本の
//! CONNECT ストリームの上にストリームとデータグラムを多重化する
//! (draft-ietf-webtrans-http3-16)。MOQT のプロトコル識別子は
//! `WT-Available-Protocols` で提示し、`WT-Protocol` で選択される
//! (draft-ietf-moq-transport-23 §6.2 (Session establishment))。
//!
//! セッションは 1 本のタスクが所有し、受信とコマンドを `select!` で待つ。受信系の
//! API が `&mut self` を要求するため、この形で直列化する。`receive` はキャンセル
//! 安全であり、コマンドの到着で待機を捨てても未受信の項目は失われない。

use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, AtomicU16, Ordering};
use std::time::Duration;

use tobi_quic::core::connection::ConnectionConfig;
use tobi_quic::{
    Connect, Connection, DatagramConfig, IoConfig, Server as QuicServer, ServerTlsConfig,
};
use tobi_webtransport::client as wt_client;
use tobi_webtransport::error::Error as WtError;
use tobi_webtransport::server as wt_server;
use tobi_webtransport::server::{
    WtRecvStream as ServerRecvStream, WtSendStream as ServerSendStream, WtSession as ServerSession,
};
use tobi_webtransport::session::{Incoming as ClientIncoming, Session};
use tobi_webtransport::stream::{WtBidirectionalStream, WtReceiveStream, WtSendStream};
use tokio::sync::{mpsc, oneshot};

use crate::io::bridge::{AsyncioBridge, Completion, runtime};
use crate::io::client::ClientConfig;
use crate::io::command::{ConnectionCommand, IoError, ReadCommand, ServerCommand, WriteCommand};
use crate::io::event::EventSpec;
use crate::io::net;
use crate::io::quic::{COMMAND_CHANNEL_CAPACITY, WRITE_CHANNEL_CAPACITY};
use crate::io::server::ServerConfig;
use crate::io::tls::{build_client_tls, build_server_tls};

/// ハンドシェイクのタイムアウト。
const HANDSHAKE_TIMEOUT: Duration = Duration::from_secs(10);
/// セッション終了後にドライバの終了を待つ上限。
const CLOSE_TIMEOUT: Duration = Duration::from_secs(5);
/// 自側の終了時にピアの終了情報を待つ上限。
const PEER_CLOSE_TIMEOUT: Duration = Duration::from_secs(1);
/// 接続のアイドルタイムアウト (ms)。
const IDLE_TIMEOUT_MS: u64 = 30_000;
/// 双方向ストリームのヘッダー読み込みを待つ時間。
///
/// tobi_webtransport のサーバーはヘッダー読み込みの完了を待たずに次のストリームを
/// 待つため、空の単方向ストリームで受信ループを起こす。ヘッダーの読み込みが
/// 終わるだけの時間を置いてからもう一度起こす。
const KICK_DELAY: Duration = Duration::from_millis(10);
/// HTTP/3 の正常終了コード。
const H3_NO_ERROR: u64 = 0x100;
/// WebTransport のアプリケーションエラーコード範囲の開始。
///
/// draft-ietf-webtrans-http3-16 Section 4.4 の変換則に使う。
const WT_APPLICATION_ERROR_FIRST: u64 = 0x52e4a40fa8db;

/// WebTransport のアプリケーションエラーコードを HTTP/3 のエラーコードへ変換する。
///
/// 予約コードポイント (0x1f * N + 0x21) を飛ばすため、0x1e ごとに 1 を加算する
/// (draft-ietf-webtrans-http3-16 Section 4.4)。
fn app_code_to_http3(app_code: u64) -> u64 {
    WT_APPLICATION_ERROR_FIRST + app_code + app_code / 0x1e
}

/// HTTP/3 のエラーコードを WebTransport のアプリケーションエラーコードへ変換する。
///
/// 範囲外と予約コードポイントは `None` を返す
/// (draft-ietf-webtrans-http3-16 Section 4.4)。
fn app_code_from_http3(http3_code: u64) -> Option<u32> {
    const LAST: u64 = 0x52e5ac983162;
    if !(WT_APPLICATION_ERROR_FIRST..=LAST).contains(&http3_code) {
        return None;
    }
    if http3_code.wrapping_sub(0x21).is_multiple_of(0x1f) {
        return None;
    }
    let shifted = http3_code - WT_APPLICATION_ERROR_FIRST;
    let app_code = shifted - shifted / 0x1f;
    u32::try_from(app_code).ok()
}

/// QUIC の transport parameter を作る。
///
/// WebTransport のクライアントは `reset_stream_at` の広告を前提にするため、
/// サーバー側でも有効にする (draft-ietf-webtrans-http3-16 Section 3.1)。
fn transport_config(server: bool) -> ConnectionConfig {
    let mut config = ConnectionConfig::default();
    config.transport_params.initial_max_streams_uni = 10_000;
    config.transport_params.initial_max_streams_bidi = 1_000;
    config.transport_params.initial_max_data = 64 * 1024 * 1024;
    config.transport_params.initial_max_stream_data_uni = 16 * 1024 * 1024;
    config.transport_params.initial_max_stream_data_bidi_local = 16 * 1024 * 1024;
    config.transport_params.initial_max_stream_data_bidi_remote = 16 * 1024 * 1024;
    config.transport_params.initial_max_path_id = None;
    config.transport_params.max_idle_timeout = IDLE_TIMEOUT_MS;
    if server {
        config.transport_params.reset_stream_at = true;
    }
    config
}

/// WebTransport のセッション設定を作る。
fn session_limits() -> wt_client::Limits {
    wt_client::Limits {
        max_sessions: 1,
        initial_max_streams_uni: 10_000,
        initial_max_streams_bidi: 1_000,
        initial_max_data: 64 * 1024 * 1024,
    }
}

/// サーバーが広告する WebTransport のセッション設定を作る。
fn server_limits() -> wt_server::ServerLimits {
    wt_server::ServerLimits {
        max_sessions: 1,
        initial_max_streams_uni: 10_000,
        initial_max_streams_bidi: 1_000,
        initial_max_data: 64 * 1024 * 1024,
    }
}

/// WT-H3 のクライアントとして接続し、セッションを実行する。
pub(crate) async fn run_client(
    config: ClientConfig,
    commands: mpsc::Receiver<ConnectionCommand>,
    events: mpsc::Sender<EventSpec>,
    _bridge: Arc<AsyncioBridge>,
    ready: oneshot::Sender<Result<Completion, IoError>>,
) {
    let addresses = match net::resolve(&config.host, config.port).await {
        Ok(addresses) => addresses,
        Err(error) => {
            fail_client(ready, events, error).await;
            return;
        }
    };
    let tls = match build_client_tls(&config) {
        Ok(tls) => tls,
        Err(error) => {
            fail_client(ready, events, error).await;
            return;
        }
    };
    let mut last_error = String::from("no address was tried");
    for address in addresses {
        let client = match wt_client::Client::builder()
            .with_tls_config(Arc::clone(&tls))
            .with_io(IoConfig::new(net::local_bind_addr(address)))
            .with_handshake_timeout(Some(HANDSHAKE_TIMEOUT))
            .start()
        {
            Ok(client) => client,
            Err(error) => {
                last_error = format!("failed to start the QUIC client: {error}");
                continue;
            }
        };
        let mut session_config =
            wt_client::ClientConfig::new(config.authority.clone(), config.path.clone())
                .with_limits(session_limits());
        if !config.protocols.is_empty() {
            session_config = session_config.with_available_protocols(config.protocols.clone());
        }
        if !config.origin.is_empty() {
            session_config = session_config.with_origin(config.origin.clone());
        }
        match client
            .connect(
                Connect::new(address, config.server_name.as_str()),
                session_config,
            )
            .await
        {
            Ok(session) => {
                let session_id = session.session_id();
                let _ = ready.send(Ok(Completion::Unit));
                let _ = events
                    .send(EventSpec::session_ready(0, session_id, None))
                    .await;
                run_client_session(0, session, commands, events).await;
                return;
            }
            Err(error) => {
                last_error = format!("failed to connect to {address}: {error}");
            }
        }
    }
    fail_client(ready, events, IoError::connection(last_error)).await;
}

/// クライアントの接続失敗を Future とイベントへ伝える。
async fn fail_client(
    ready: oneshot::Sender<Result<Completion, IoError>>,
    events: mpsc::Sender<EventSpec>,
    error: IoError,
) {
    let message = error.message.clone();
    let _ = ready.send(Err(error));
    let _ = events.send(EventSpec::error(0, 0, message)).await;
    let _ = events.send(EventSpec::end(0, 0)).await;
}

/// クライアントのセッションを操作し、受信イベントを配送する。
async fn run_client_session(
    connection_id: u64,
    mut session: Session,
    mut commands: mpsc::Receiver<ConnectionCommand>,
    events: mpsc::Sender<EventSpec>,
) {
    let session_id = session.session_id();
    let connection_closed = Arc::new(AtomicBool::new(false));
    let mut writers: HashMap<u64, mpsc::Sender<WriteCommand>> = HashMap::new();
    let mut readers: HashMap<u64, mpsc::Sender<ReadCommand>> = HashMap::new();
    // 自側が開いた双方向ストリームと、サーバー起こしを送ったストリーム
    let mut bidi_streams: HashSet<u64> = HashSet::new();
    let mut kicked: HashSet<u64> = HashSet::new();
    let mut local_close: Option<(u64, String)> = None;
    loop {
        tokio::select! {
            command = commands.recv() => {
                match command {
                    Some(ConnectionCommand::Close { error_code, reason, reply }) => {
                        let result = match u32::try_from(error_code) {
                            Ok(error_code) => session
                                .close(error_code, reason.clone())
                                .await
                                .map(|_| Completion::Unit)
                                .map_err(map_wt_error),
                            Err(_) => Err(IoError::runtime(format!(
                                "the close code does not fit the WebTransport error code: {error_code}"
                            ))),
                        };
                        let _ = reply.send(result);
                        let mut close = (error_code, reason);
                        // 状態機械はピアの終了を検知してから自側の終了を要求する。
                        // このときピアが送った終了コードと理由の方が利用者にとって
                        // 有用なので、届いていればそちらを使う
                        if error_code != 0
                            && let Ok(Ok(info)) =
                                tokio::time::timeout(PEER_CLOSE_TIMEOUT, session.wait_closed())
                                    .await
                            && u64::from(info.error_code) != 0
                        {
                            close = (u64::from(info.error_code), info.message);
                        }
                        local_close = Some(close);
                        break;
                    }
                    Some(command) => {
                        handle_client_command(
                            command,
                            &mut session,
                            &mut writers,
                            &mut readers,
                            &mut bidi_streams,
                            &mut kicked,
                            &events,
                            session_id,
                        )
                        .await;
                    }
                    None => {
                        break;
                    }
                }
            }
            incoming = session.receive() => {
                match incoming {
                    Ok(ClientIncoming::BidirectionalStream(stream)) => {
                        spawn_client_bidi(
                            stream,
                            &mut writers,
                            &mut readers,
                            events.clone(),
                            session_id,
                            Arc::clone(&connection_closed),
                        );
                    }
                    Ok(ClientIncoming::UnidirectionalStream(recv)) => {
                        spawn_client_reader(
                            recv,
                            &mut readers,
                            events.clone(),
                            session_id,
                            Arc::clone(&connection_closed),
                        );
                    }
                    Ok(ClientIncoming::Datagram(data)) => {
                        let _ = events
                            .send(EventSpec::datagram(connection_id, session_id, data))
                            .await;
                    }
                    Err(error) => {
                        let _ = events
                            .send(EventSpec::error(
                                connection_id,
                                session_id,
                                format!("the WebTransport session receive failed: {error}"),
                            ))
                            .await;
                        break;
                    }
                }
            }
        }
    }
    connection_closed.store(true, Ordering::SeqCst);
    let (code, reason) = match local_close {
        Some(close) => close,
        None => match session.wait_closed().await {
            Ok(info) => (u64::from(info.error_code), info.message),
            Err(WtError::SessionAborted {
                transport_error_code,
                connect_stream_error_code,
            }) => (
                connect_stream_error_code.unwrap_or(transport_error_code),
                String::new(),
            ),
            Err(_) => (0, String::new()),
        },
    };
    let _ = events
        .send(EventSpec::session_closed(
            connection_id,
            session_id,
            code,
            reason,
        ))
        .await;
    let _ = events.send(EventSpec::end(connection_id, session_id)).await;
}

/// クライアントの接続への操作 1 件を処理する。
#[expect(clippy::too_many_arguments)]
async fn handle_client_command(
    command: ConnectionCommand,
    session: &mut Session,
    writers: &mut HashMap<u64, mpsc::Sender<WriteCommand>>,
    readers: &mut HashMap<u64, mpsc::Sender<ReadCommand>>,
    bidi_streams: &mut HashSet<u64>,
    kicked: &mut HashSet<u64>,
    events: &mpsc::Sender<EventSpec>,
    session_id: u64,
) {
    match command {
        ConnectionCommand::OpenStream {
            bidirectional,
            reply,
        } => {
            let result = if bidirectional {
                match session.open_bidirectional_stream().await {
                    Ok(stream) => {
                        let stream_id = stream.stream_id();
                        let (send, recv) = stream.split();
                        spawn_writer(stream_id, send, writers, events, session_id);
                        spawn_client_reader_with_id(
                            stream_id,
                            recv,
                            readers,
                            events.clone(),
                            session_id,
                            Arc::new(AtomicBool::new(false)),
                        );
                        bidi_streams.insert(stream_id);
                        Ok(Completion::U64(stream_id))
                    }
                    Err(error) => Err(map_wt_error(error)),
                }
            } else {
                match session.open_unidirectional_stream().await {
                    Ok(send) => {
                        let stream_id = send.stream_id();
                        spawn_writer(stream_id, send, writers, events, session_id);
                        Ok(Completion::U64(stream_id))
                    }
                    Err(error) => Err(map_wt_error(error)),
                }
            };
            let _ = reply.send(result);
        }
        ConnectionCommand::SendStreamData {
            stream_id,
            data,
            fin,
            reply,
        } => {
            let is_bidi = bidi_streams.contains(&stream_id);
            match writers.get(&stream_id) {
                Some(writer) => {
                    let (result_tx, result_rx) = oneshot::channel();
                    if writer
                        .send(WriteCommand::Send {
                            data,
                            fin,
                            reply: result_tx,
                        })
                        .await
                        .is_err()
                    {
                        let _ = reply.send(Err(IoError::runtime(format!(
                            "the stream writer stopped: {stream_id}"
                        ))));
                        return;
                    }
                    let result = result_rx.await.unwrap_or_else(|_| {
                        Err(IoError::runtime(format!(
                            "the stream writer stopped: {stream_id}"
                        )))
                    });
                    let succeeded = result.is_ok();
                    let _ = reply.send(result);
                    // 双方向ストリームのヘッダーはサーバーの受信タスクが読む。
                    // ヘッダーの読み込みが終わった後に空の単方向ストリームを送ると、
                    // サーバーの受信ループが完了済みの双方向ストリームを引き渡す
                    if succeeded && is_bidi && kicked.insert(stream_id) {
                        kick_server(session).await;
                        tokio::time::sleep(KICK_DELAY).await;
                        kick_server(session).await;
                    }
                }
                None => {
                    let _ = reply.send(Err(IoError::runtime(format!(
                        "unknown stream: {stream_id}"
                    ))));
                }
            }
        }
        ConnectionCommand::ResetStream {
            stream_id,
            error_code,
            reply,
        } => match writers.get(&stream_id) {
            Some(writer) => {
                let _ = writer.send(WriteCommand::Reset { error_code, reply }).await;
            }
            None => {
                let _ = reply.send(Err(IoError::runtime(format!(
                    "unknown stream: {stream_id}"
                ))));
            }
        },
        ConnectionCommand::StopSending {
            stream_id,
            error_code,
            reply,
        } => match readers.get(&stream_id) {
            Some(reader) => {
                let _ = reader
                    .send(ReadCommand::StopSending { error_code, reply })
                    .await;
            }
            None => {
                let _ = reply.send(Err(IoError::runtime(format!(
                    "unknown stream: {stream_id}"
                ))));
            }
        },
        ConnectionCommand::SendDatagram { data, reply } => {
            // データグラムの送信待ちでセッションの受信を止めないよう、
            // 複製可能な送信ハンドルを使って専用タスクで送る。
            let sender = session.datagram_sender();
            runtime().spawn(async move {
                let result = sender
                    .send(&data)
                    .await
                    .map(|_| Completion::Unit)
                    .map_err(map_wt_error);
                let _ = reply.send(result);
            });
        }
        ConnectionCommand::Close { .. } => {
            // セッションの終了は呼び出し側のループで処理する。
        }
    }
}

/// サーバーの受信ループを起こすための空の単方向ストリームを開く。
///
/// tobi_webtransport のサーバーは、双方向ストリームのヘッダー読み込みが完了しても
/// 新しいストリームの到着を待ち続け、アプリケーションへ引き渡さない
/// (`accept_bidi_stream` が `JoinSet` の完了を待たずに
/// `accept_bidirectional_stream` で待機するため)。空の単方向ストリームを 1 本
/// 開くと受信ループが 1 度戻り、次の呼び出しで完了済みの双方向ストリームが
/// 引き渡される。サーバー側はデータ無しで終了した単方向ストリームを捨てる。
async fn kick_server(session: &Session) {
    if let Ok(mut stream) = session.open_unidirectional_stream().await {
        let _ = stream.finish().await;
    }
}

/// クライアントの双方向ストリームを送受信のタスクへ分ける。
fn spawn_client_bidi(
    stream: WtBidirectionalStream,
    writers: &mut HashMap<u64, mpsc::Sender<WriteCommand>>,
    readers: &mut HashMap<u64, mpsc::Sender<ReadCommand>>,
    events: mpsc::Sender<EventSpec>,
    session_id: u64,
    connection_closed: Arc<AtomicBool>,
) {
    let stream_id = stream.stream_id();
    let (send, recv) = stream.split();
    spawn_writer(stream_id, send, writers, &events, session_id);
    spawn_client_reader_with_id(
        stream_id,
        recv,
        readers,
        events,
        session_id,
        connection_closed,
    );
}

/// クライアントの受信ストリームのタスクを起動する。
fn spawn_client_reader(
    stream: WtReceiveStream,
    readers: &mut HashMap<u64, mpsc::Sender<ReadCommand>>,
    events: mpsc::Sender<EventSpec>,
    session_id: u64,
    connection_closed: Arc<AtomicBool>,
) {
    let stream_id = stream.stream_id();
    spawn_client_reader_with_id(
        stream_id,
        stream,
        readers,
        events,
        session_id,
        connection_closed,
    );
}

/// ストリーム ID を指定してクライアントの受信タスクを起動する。
fn spawn_client_reader_with_id(
    stream_id: u64,
    stream: WtReceiveStream,
    readers: &mut HashMap<u64, mpsc::Sender<ReadCommand>>,
    events: mpsc::Sender<EventSpec>,
    session_id: u64,
    connection_closed: Arc<AtomicBool>,
) {
    let (sender, receiver) = mpsc::channel(WRITE_CHANNEL_CAPACITY);
    readers.insert(stream_id, sender);
    runtime().spawn(client_reader_task(
        stream,
        receiver,
        events,
        session_id,
        connection_closed,
    ));
}

/// クライアントの受信ストリームを所有し、データと終端を配送するタスク。
async fn client_reader_task(
    mut stream: WtReceiveStream,
    mut commands: mpsc::Receiver<ReadCommand>,
    events: mpsc::Sender<EventSpec>,
    session_id: u64,
    connection_closed: Arc<AtomicBool>,
) {
    let stream_id = stream.stream_id();
    loop {
        tokio::select! {
            result = stream.recv() => {
                match result {
                    Ok(Some(data)) => {
                        let _ = events
                            .send(EventSpec::stream_data(
                                0,
                                session_id,
                                stream_id,
                                data,
                                false,
                            ))
                            .await;
                    }
                    Ok(None) => {
                        let _ = events
                            .send(EventSpec::stream_data(
                                0,
                                session_id,
                                stream_id,
                                Vec::new(),
                                true,
                            ))
                            .await;
                        break;
                    }
                    Err(WtError::StreamReset { error_code, .. }) => {
                        if !connection_closed.load(Ordering::SeqCst) {
                            let _ = events
                                .send(EventSpec::stream_reset(
                                    0,
                                    session_id,
                                    stream_id,
                                    error_code.map(u64::from),
                                ))
                                .await;
                        }
                        break;
                    }
                    Err(_) => {
                        if !connection_closed.load(Ordering::SeqCst) {
                            let _ = events
                                .send(EventSpec::stream_reset(0, session_id, stream_id, None))
                                .await;
                        }
                        break;
                    }
                }
            }
            command = commands.recv() => {
                match command {
                    Some(ReadCommand::StopSending { error_code, reply }) => {
                        let result = match u32::try_from(error_code) {
                            Ok(error_code) => {
                                // 受信ストリームをドロップすると、設定したコードで
                                // STOP_SENDING が送られる
                                stream.set_drop_error_code(error_code);
                                Ok(Completion::Unit)
                            }
                            Err(_) => Err(IoError::runtime(format!(
                                "the error code does not fit the WebTransport error code: {error_code}"
                            ))),
                        };
                        let failed = result.is_err();
                        let _ = reply.send(result);
                        if failed {
                            break;
                        }
                        // ドロップで STOP_SENDING が送られる
                        break;
                    }
                    None => break,
                }
            }
        }
    }
}

/// WT-H3 のサーバーとして待ち受け、接続ごとにセッションを実行する。
pub(crate) async fn run_server(
    config: ServerConfig,
    mut commands: mpsc::Receiver<ServerCommand>,
    events: mpsc::Sender<EventSpec>,
    _bridge: Arc<AsyncioBridge>,
    ready: oneshot::Sender<Result<Completion, IoError>>,
    actual_port: Arc<AtomicU16>,
) {
    let tls = match build_server_tls(&config.certfile, &config.keyfile, &config.alpn) {
        Ok(tls) => tls,
        Err(error) => {
            fail_server(ready, events, error).await;
            return;
        }
    };
    let bind = match net::resolve_bind(&config.host, config.port) {
        Ok(bind) => bind,
        Err(error) => {
            fail_server(ready, events, error).await;
            return;
        }
    };
    let mut server = match QuicServer::builder()
        .with_tls(ServerTlsConfig::new(tls))
        .with_io(IoConfig::new(bind))
        .with_transport(transport_config(true))
        .with_datagram(DatagramConfig::default())
        .with_background_driver(true)
        .start()
    {
        Ok(server) => server,
        Err(error) => {
            fail_server(
                ready,
                events,
                IoError::runtime(format!("failed to start the QUIC server: {error}")),
            )
            .await;
            return;
        }
    };
    actual_port.store(server.local_addr().port(), Ordering::SeqCst);
    let _ = ready.send(Ok(Completion::Unit));

    let (closed_tx, mut closed_rx) = mpsc::channel::<u64>(COMMAND_CHANNEL_CAPACITY);
    let mut connections: HashMap<u64, mpsc::Sender<ConnectionCommand>> = HashMap::new();
    let mut next_connection_id: u64 = 1;
    loop {
        tokio::select! {
            accepted = server.accept() => {
                match accepted {
                    Ok(connection) => {
                        let connection_id = next_connection_id;
                        next_connection_id += 1;
                        // セッションの確立前に操作が届いても取りこぼさないよう、
                        // コマンドの受信側を先に用意して登録する
                        let (command_tx, command_rx) = mpsc::channel(COMMAND_CHANNEL_CAPACITY);
                        connections.insert(connection_id, command_tx);
                        let events = events.clone();
                        let closed = closed_tx.clone();
                        let protocols = config.protocols.clone();
                        runtime().spawn(async move {
                            if let Err(error) = accept_connection(
                                connection_id,
                                connection,
                                protocols,
                                command_rx,
                                events.clone(),
                            )
                            .await
                            {
                                let _ = events
                                    .send(EventSpec::error(connection_id, connection_id, error.message))
                                    .await;
                            }
                            let _ = closed.send(connection_id).await;
                        });
                    }
                    Err(error) => {
                        let _ = events
                            .send(EventSpec::error(
                                0,
                                0,
                                format!("the WebTransport server stopped accepting connections: {error}"),
                            ))
                            .await;
                        break;
                    }
                }
            }
            command = commands.recv() => {
                match command {
                    Some(ServerCommand::Connection { connection_id, command }) => {
                        if let Some(sender) = connections.get(&connection_id) {
                            let _ = sender.send(command).await;
                        }
                    }
                    Some(ServerCommand::Stop { reply }) => {
                        let _ = reply.send(Ok(Completion::Unit));
                        break;
                    }
                    None => break,
                }
            }
            connection_id = closed_rx.recv() => {
                if let Some(connection_id) = connection_id {
                    connections.remove(&connection_id);
                }
            }
        }
    }
    drop(server);
    let _ = events.send(EventSpec::end(0, 0)).await;
}

/// サーバーの起動失敗を Future とイベントへ伝える。
async fn fail_server(
    ready: oneshot::Sender<Result<Completion, IoError>>,
    events: mpsc::Sender<EventSpec>,
    error: IoError,
) {
    let message = error.message.clone();
    let _ = ready.send(Err(error));
    let _ = events.send(EventSpec::error(0, 0, message)).await;
    let _ = events.send(EventSpec::end(0, 0)).await;
}

/// QUIC 接続から WebTransport セッションを確立して実行する。
async fn accept_connection(
    connection_id: u64,
    connection: Connection,
    protocols: Vec<String>,
    commands: mpsc::Receiver<ConnectionCommand>,
    events: mpsc::Sender<EventSpec>,
) -> Result<(), IoError> {
    let address = connection
        .remote_addr()
        .await
        .ok()
        .map(|address| (address.ip().to_string(), address.port()));
    // WebTransport は HTTP/3 (ALPN h3) の上でだけ使える
    if connection.application_protocol().await.as_deref() != Some(b"h3") {
        let _ = connection.close_application(H3_NO_ERROR, b"").await;
        return Err(IoError::connection(
            "the connection did not negotiate the h3 ALPN",
        ));
    }
    let request = wt_server::WtSessionRequest::from_connection(connection, server_limits(), false)
        .await
        .map_err(map_wt_server_error)?;
    // クライアントが提示したプロトコルから MOQT の識別子を選ぶ。提示が無い場合は
    // 交渉に失敗したものとして拒否する
    let mut request = request;
    if !protocols.is_empty() {
        let selected = protocols
            .iter()
            .find(|protocol| request.available_protocols().contains(protocol))
            .cloned();
        let Some(selected) = selected else {
            let available = request.available_protocols().to_vec();
            let _ = request.reject(400).await;
            return Err(IoError::connection(format!(
                "the client did not offer a supported WebTransport protocol: {available:?}"
            )));
        };
        request = request.with_protocol(selected);
    }
    let session = request.accept().await.map_err(map_wt_server_error)?;
    let session_id = session.session_id();
    let _ = events
        .send(EventSpec::session_ready(connection_id, session_id, address))
        .await;
    run_server_session(connection_id, session, commands, events).await;
    Ok(())
}

/// サーバーのセッションを操作し、受信イベントを配送する。
async fn run_server_session(
    connection_id: u64,
    mut session: ServerSession,
    mut commands: mpsc::Receiver<ConnectionCommand>,
    events: mpsc::Sender<EventSpec>,
) {
    let session_id = session.session_id();
    let connection = session.connection();
    let connection_closed = Arc::new(AtomicBool::new(false));
    let mut writers: HashMap<u64, mpsc::Sender<WriteCommand>> = HashMap::new();
    let mut readers: HashMap<u64, mpsc::Sender<ReadCommand>> = HashMap::new();
    let mut local_close: Option<(u64, String)> = None;
    loop {
        tokio::select! {
            command = commands.recv() => {
                match command {
                    Some(ConnectionCommand::Close { error_code, reason, reply }) => {
                        let result = match u32::try_from(error_code) {
                            Ok(error_code) => session
                                .close(error_code, &reason)
                                .await
                                .map(|_| Completion::Unit)
                                .map_err(map_wt_server_error),
                            Err(_) => Err(IoError::runtime(format!(
                                "the close code does not fit the WebTransport error code: {error_code}"
                            ))),
                        };
                        let _ = reply.send(result);
                        let mut close = (error_code, reason);
                        // 状態機械はピアの終了を検知してから自側の終了を要求する。
                        // このときピアが送った終了コードと理由の方が利用者にとって
                        // 有用なので、届いていればそちらを使う
                        if error_code != 0
                            && let Ok(Ok(info)) =
                                tokio::time::timeout(PEER_CLOSE_TIMEOUT, session.wait_closed())
                                    .await
                            && u64::from(info.error_code) != 0
                        {
                            close = (u64::from(info.error_code), info.message);
                        }
                        local_close = Some(close);
                        break;
                    }
                    Some(command) => {
                        handle_server_command(
                            command,
                            &mut session,
                            &connection,
                            &mut writers,
                            &mut readers,
                            &events,
                            connection_id,
                            session_id,
                            &connection_closed,
                        )
                        .await;
                    }
                    None => break,
                }
            }
            observed = connection.accept_stop_sending() => {
                match observed {
                    Ok((stream_id, http3_code)) => {
                        // tobi_webtransport のサーバーは STOP_SENDING をアプリへ
                        // 通知しないため、QUIC の観測キューから直接取り出す。
                        // 送信側の send は停止を検出するまで失敗しない
                        let _ = events
                            .send(EventSpec::stop_sending(
                                connection_id,
                                session_id,
                                stream_id,
                                app_code_from_http3(http3_code).map(u64::from),
                            ))
                            .await;
                    }
                    Err(_) => break,
                }
            }
            incoming = session.receive() => {
                match incoming {
                    Ok(wt_server::Incoming::Bidirectional(stream)) => {
                        let stream_id = stream.stream_id();
                        let (send, recv) = stream.into_parts();
                        spawn_server_writer(stream_id, send, &mut writers, &connection);
                        spawn_server_reader(
                            stream_id,
                            recv,
                            &mut readers,
                            events.clone(),
                            connection_id,
                            session_id,
                            Arc::clone(&connection_closed),
                            connection.clone(),
                            false,
                        );
                    }
                    Ok(wt_server::Incoming::Unidirectional(recv)) => {
                        let stream_id = recv.stream_id();
                        spawn_server_reader(
                            stream_id,
                            recv,
                            &mut readers,
                            events.clone(),
                            connection_id,
                            session_id,
                            Arc::clone(&connection_closed),
                            connection.clone(),
                            true,
                        );
                    }
                    Ok(wt_server::Incoming::Datagram(data)) => {
                        let _ = events
                            .send(EventSpec::datagram(connection_id, session_id, data))
                            .await;
                    }
                    Err(error) => {
                        let _ = events
                            .send(EventSpec::error(
                                connection_id,
                                session_id,
                                format!("the WebTransport session receive failed: {error}"),
                            ))
                            .await;
                        break;
                    }
                }
            }
        }
    }
    connection_closed.store(true, Ordering::SeqCst);
    let (code, reason) = match local_close {
        Some(close) => {
            // WT_CLOSE_SESSION と CONNECT ストリームの FIN を送り切ってから
            // QUIC 接続を閉じる
            let _ = tokio::time::timeout(CLOSE_TIMEOUT, session.wait_closed()).await;
            let _ = connection.close_application(H3_NO_ERROR, b"").await;
            close
        }
        None => match session.wait_closed().await {
            Ok(info) => (u64::from(info.error_code), info.message),
            Err(_) => (0, String::new()),
        },
    };
    let _ = events
        .send(EventSpec::session_closed(
            connection_id,
            session_id,
            code,
            reason,
        ))
        .await;
    let _ = events.send(EventSpec::end(connection_id, session_id)).await;
}

/// サーバーの接続への操作 1 件を処理する。
#[expect(clippy::too_many_arguments)]
async fn handle_server_command(
    command: ConnectionCommand,
    session: &mut ServerSession,
    connection: &Connection,
    writers: &mut HashMap<u64, mpsc::Sender<WriteCommand>>,
    readers: &mut HashMap<u64, mpsc::Sender<ReadCommand>>,
    events: &mpsc::Sender<EventSpec>,
    connection_id: u64,
    session_id: u64,
    connection_closed: &Arc<AtomicBool>,
) {
    match command {
        ConnectionCommand::OpenStream {
            bidirectional,
            reply,
        } => {
            let result = if bidirectional {
                match session.open_bi_stream().await {
                    Ok(stream) => {
                        let stream_id = stream.stream_id();
                        let (send, recv) = stream.into_parts();
                        spawn_server_writer(stream_id, send, writers, connection);
                        spawn_server_reader(
                            stream_id,
                            recv,
                            readers,
                            events.clone(),
                            connection_id,
                            session_id,
                            Arc::clone(connection_closed),
                            connection.clone(),
                            false,
                        );
                        Ok(Completion::U64(stream_id))
                    }
                    Err(error) => Err(map_wt_server_error(error)),
                }
            } else {
                match session.open_uni_stream().await {
                    Ok(send) => {
                        let stream_id = send.stream_id();
                        spawn_server_writer(stream_id, send, writers, connection);
                        Ok(Completion::U64(stream_id))
                    }
                    Err(error) => Err(map_wt_server_error(error)),
                }
            };
            let _ = reply.send(result);
        }
        ConnectionCommand::SendStreamData {
            stream_id,
            data,
            fin,
            reply,
        } => match writers.get(&stream_id) {
            Some(writer) => {
                let _ = writer.send(WriteCommand::Send { data, fin, reply }).await;
            }
            None => {
                let _ = reply.send(Err(IoError::runtime(format!(
                    "unknown stream: {stream_id}"
                ))));
            }
        },
        ConnectionCommand::ResetStream {
            stream_id,
            error_code,
            reply,
        } => match writers.get(&stream_id) {
            Some(writer) => {
                let _ = writer.send(WriteCommand::Reset { error_code, reply }).await;
            }
            None => {
                let _ = reply.send(Err(IoError::runtime(format!(
                    "unknown stream: {stream_id}"
                ))));
            }
        },
        ConnectionCommand::StopSending {
            stream_id,
            error_code,
            reply,
        } => match readers.get(&stream_id) {
            Some(reader) => {
                let _ = reader
                    .send(ReadCommand::StopSending { error_code, reply })
                    .await;
            }
            None => {
                let _ = reply.send(Err(IoError::runtime(format!(
                    "unknown stream: {stream_id}"
                ))));
            }
        },
        ConnectionCommand::SendDatagram { data, reply } => {
            let result = session
                .send_datagram(&data)
                .await
                .map(|_| Completion::Unit)
                .map_err(map_wt_server_error);
            let _ = reply.send(result);
        }
        ConnectionCommand::Close { .. } => {
            // セッションの終了は呼び出し側のループで処理する。
        }
    }
}

/// サーバーの送信ストリームを所有するタスクを起動する。
fn spawn_server_writer(
    stream_id: u64,
    stream: ServerSendStream,
    writers: &mut HashMap<u64, mpsc::Sender<WriteCommand>>,
    connection: &Connection,
) {
    let (sender, receiver) = mpsc::channel(WRITE_CHANNEL_CAPACITY);
    writers.insert(stream_id, sender);
    runtime().spawn(server_writer_task(stream, receiver, connection.clone()));
}

/// サーバーの受信ストリームを所有するタスクを起動する。
#[expect(clippy::too_many_arguments)]
fn spawn_server_reader(
    stream_id: u64,
    stream: ServerRecvStream,
    readers: &mut HashMap<u64, mpsc::Sender<ReadCommand>>,
    events: mpsc::Sender<EventSpec>,
    connection_id: u64,
    session_id: u64,
    connection_closed: Arc<AtomicBool>,
    connection: Connection,
    uni: bool,
) {
    let (sender, receiver) = mpsc::channel(WRITE_CHANNEL_CAPACITY);
    readers.insert(stream_id, sender);
    runtime().spawn(server_reader_task(
        stream,
        receiver,
        events,
        connection_id,
        session_id,
        connection_closed,
        connection,
        uni,
    ));
}

/// サーバーの送信ストリームを所有し、指示されたデータを書き込むタスク。
async fn server_writer_task(
    mut stream: ServerSendStream,
    mut commands: mpsc::Receiver<WriteCommand>,
    connection: Connection,
) {
    let stream_id = stream.stream_id();
    while let Some(command) = commands.recv().await {
        match command {
            WriteCommand::Send { data, fin, reply } => {
                let empty_fin = data.is_empty() && fin;
                let result = match stream.send(&data).await {
                    Ok(()) if fin => stream.finish().await,
                    Ok(()) => Ok(()),
                    Err(error) => Err(error),
                };
                // 終端だけを送る書き込みは、ピアが既に STOP_SENDING を送っていても
                // 失敗にしない。データを送らないため、停止の通知と競合しても
                // アプリケーションの操作を失敗させる意味が無い
                let result = match result {
                    Err(wt_server::Error::Transport(_)) if empty_fin => Ok(()),
                    result => result,
                };
                let failed = result.is_err();
                let _ = reply.send(
                    result
                        .map(|_| Completion::Unit)
                        .map_err(map_wt_server_error),
                );
                if failed {
                    break;
                }
            }
            WriteCommand::Reset { error_code, reply } => {
                // サーバーの送信ストリームには reset が無いため、QUIC 層の
                // RESET_STREAM を使う
                let result = connection
                    .reset_stream(stream_id, app_code_to_http3(error_code))
                    .await
                    .map(|_| Completion::Unit)
                    .map_err(map_quic_error);
                let _ = reply.send(result);
                break;
            }
        }
    }
}

/// サーバーの受信ストリームを所有し、データと終端を配送するタスク。
#[expect(clippy::too_many_arguments)]
async fn server_reader_task(
    mut stream: ServerRecvStream,
    mut commands: mpsc::Receiver<ReadCommand>,
    events: mpsc::Sender<EventSpec>,
    connection_id: u64,
    session_id: u64,
    connection_closed: Arc<AtomicBool>,
    connection: Connection,
    uni: bool,
) {
    let stream_id = stream.stream_id();
    // STOP_SENDING を送った後も受信側を保持する。ドロップするとコード 0 の
    // STOP_SENDING が重ねて送られるためである。
    let mut stopping = false;
    // データを 1 バイトも受信せずに終了した単方向ストリムは、クライアントが
    // 送るサーバー起こしのための空ストリームである。MOQT の状態機械へは
    // 通知しない。
    let mut received_any = false;
    loop {
        tokio::select! {
            result = stream.recv() => {
                match result {
                    Ok(data) => {
                        received_any = received_any || !data.is_empty();
                        if !stopping {
                            let _ = events
                                .send(EventSpec::stream_data(
                                    connection_id,
                                    session_id,
                                    stream_id,
                                    data,
                                    false,
                                ))
                                .await;
                        }
                    }
                    Err(wt_server::Error::StreamClosed) => {
                        // FIN を受信した。サーバーの受信 API は RESET_STREAM も
                        // 同じエラーへ畳むため、リセットかどうかは区別できない。
                        // データ無しで終了した単方向ストリームは、クライアントが
                        // 送るサーバー起こしの空ストリームなので通知しない。
                        if !stopping && (received_any || !uni) {
                            let _ = events
                                .send(EventSpec::stream_data(
                                    connection_id,
                                    session_id,
                                    stream_id,
                                    Vec::new(),
                                    true,
                                ))
                                .await;
                        }
                        break;
                    }
                    Err(_) => {
                        if !connection_closed.load(Ordering::SeqCst) && !stopping {
                            let _ = events
                                .send(EventSpec::stream_reset(
                                    connection_id,
                                    session_id,
                                    stream_id,
                                    None,
                                ))
                                .await;
                        }
                        break;
                    }
                }
            }
            command = commands.recv() => {
                match command {
                    Some(ReadCommand::StopSending { error_code, reply }) => {
                        let result = connection
                            .stop_sending(stream_id, app_code_to_http3(error_code))
                            .await
                            .map(|_| Completion::Unit)
                            .map_err(map_quic_error);
                        let failed = result.is_err();
                        let _ = reply.send(result);
                        if failed {
                            break;
                        }
                        stopping = true;
                    }
                    None => break,
                }
            }
        }
    }
}

/// クライアントの送信ストリームを所有するタスクを起動する。
fn spawn_writer(
    stream_id: u64,
    stream: WtSendStream,
    writers: &mut HashMap<u64, mpsc::Sender<WriteCommand>>,
    events: &mpsc::Sender<EventSpec>,
    session_id: u64,
) {
    let (sender, receiver) = mpsc::channel(WRITE_CHANNEL_CAPACITY);
    writers.insert(stream_id, sender);
    runtime().spawn(writer_task(stream, receiver, events.clone(), session_id));
}

/// クライアントの送信ストリームを所有し、指示されたデータを書き込むタスク。
///
/// ピアの STOP_SENDING は送信の失敗でしか観測できないため、失敗を
/// STOP_SENDING のイベントとしても通知する。セッションの受信ループとは別の
/// タスクで動くため、ここからイベントを送る。
async fn writer_task(
    mut stream: WtSendStream,
    mut commands: mpsc::Receiver<WriteCommand>,
    events: mpsc::Sender<EventSpec>,
    session_id: u64,
) {
    let stream_id = stream.stream_id();
    while let Some(command) = commands.recv().await {
        match command {
            WriteCommand::Send { data, fin, reply } => {
                let empty_fin = data.is_empty() && fin;
                let result = match stream.send(&data).await {
                    Ok(()) => {
                        if fin {
                            stream.finish().await
                        } else {
                            Ok(())
                        }
                    }
                    Err(error) => Err(error),
                };
                // 終端だけを送る書き込みは、ピアが既に STOP_SENDING を送っていても
                // 失敗にしない。データを送らないため、停止の通知と競合しても
                // アプリケーションの操作を失敗させる意味が無い
                let result = match result {
                    Err(WtError::StreamStopped { .. }) if empty_fin => Ok(()),
                    result => result,
                };
                match result {
                    Ok(()) => {
                        let _ = reply.send(Ok(Completion::Unit));
                    }
                    Err(error) => {
                        // 停止の通知を受信側へも伝える
                        if let WtError::StreamStopped { error_code, .. } = &error {
                            let _ = events
                                .send(EventSpec::stop_sending(
                                    0,
                                    session_id,
                                    stream_id,
                                    error_code.map(u64::from),
                                ))
                                .await;
                        }
                        let _ = reply.send(Err(map_wt_error(error)));
                        break;
                    }
                }
            }
            WriteCommand::Reset { error_code, reply } => {
                let result = match u32::try_from(error_code) {
                    Ok(error_code) => stream.reset(error_code).await.map_err(map_wt_error),
                    Err(_) => Err(IoError::runtime(format!(
                        "the error code does not fit the WebTransport error code: {error_code}"
                    ))),
                };
                let _ = reply.send(result.map(|_| Completion::Unit));
                break;
            }
        }
    }
}

/// WebTransport のクライアントエラーを I/O 層のエラーへ変換する。
fn map_wt_error(error: WtError) -> IoError {
    match error {
        WtError::SessionClosed => IoError::connection("the WebTransport session is closed"),
        WtError::StreamReset { error_code, .. } => IoError::connection(format!(
            "the WebTransport stream was reset by the peer: code={error_code:?}"
        )),
        WtError::StreamStopped { error_code, .. } => IoError::connection(format!(
            "the WebTransport stream was stopped by the peer: code={error_code:?}"
        )),
        error => IoError::runtime(format!("the WebTransport session failed: {error}")),
    }
}

/// WebTransport のサーバーエラーを I/O 層のエラーへ変換する。
fn map_wt_server_error(error: wt_server::Error) -> IoError {
    match error {
        wt_server::Error::ConnectionClosed | wt_server::Error::SessionClosed => {
            IoError::connection("the WebTransport session is closed")
        }
        error => IoError::runtime(format!("the WebTransport session failed: {error}")),
    }
}

/// QUIC のエラーを I/O 層のエラーへ変換する。
fn map_quic_error(error: tobi_quic::Error) -> IoError {
    IoError::connection(format!("the QUIC operation failed: {error}"))
}
