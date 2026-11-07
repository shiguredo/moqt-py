//! tobi-quic を使った QUIC 直結の I/O。
//!
//! クライアントとサーバーの両方を、同じ接続ドライバで扱う。接続ドライバは
//! 操作コマンドを受け取り、ストリームの送受信とデータグラムをタスクへ振り分ける。
//! 受信したデータはイベントとして Python 側へ配送する。

use std::collections::HashMap;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, AtomicU16, Ordering};
use std::time::Duration;

use tobi_quic::core::connection::ConnectionConfig;
use tobi_quic::{
    Client, ClientTlsConfig, Connect, Connection, ConnectionError, DatagramConfig,
    Error as QuicError, IoConfig, PeerStream, ReceiveStream, SendStream, Server, ServerTlsConfig,
    StreamError,
};
use tokio::sync::{mpsc, oneshot};

use crate::io::bridge::{AsyncioBridge, Completion, runtime};
use crate::io::client::ClientConfig;
use crate::io::command::{ConnectionCommand, IoError, ReadCommand, ServerCommand, WriteCommand};
use crate::io::event::EventSpec;
use crate::io::net;
use crate::io::server::ServerConfig;
use crate::io::tls::{build_client_tls, build_server_tls};

/// 受信 1 回あたりに読み出す最大バイト数。
const RECEIVE_CHUNK_SIZE: usize = 64 * 1024;
/// 操作コマンドのチャネル容量。
pub(crate) const COMMAND_CHANNEL_CAPACITY: usize = 64;
/// 送信コマンドのチャネル容量。
pub(crate) const WRITE_CHANNEL_CAPACITY: usize = 8;
/// イベントのチャネル容量。
pub(crate) const EVENT_CHANNEL_CAPACITY: usize = 256;
/// 接続のアイドルタイムアウト (ms)。
const IDLE_TIMEOUT_MS: u64 = 30_000;
/// ハンドシェイクのタイムアウト。
const HANDSHAKE_TIMEOUT: Duration = Duration::from_secs(10);

/// 接続の役割。
#[derive(Debug, Clone, Copy)]
enum ConnectionRole {
    /// クライアント。接続 ID とセッション ID は 0 である。
    Client,
    /// サーバー。接続ごとに割り当てた接続 ID を持つ。
    Server { connection_id: u64 },
}

impl ConnectionRole {
    /// イベントへ載せる接続 ID とセッション ID を返す。
    fn ids(self) -> (u64, u64) {
        match self {
            Self::Client => (0, 0),
            Self::Server { connection_id } => (connection_id, 0),
        }
    }
}

/// QUIC のストリーム上限とフロー制御の設定を作る。
///
/// MOQT は 1 本の接続で control stream、request stream、Subgroup ごとの
/// data stream を同時に使う。既定値ではストリーム数とウィンドウが不足し、
/// 購読が数秒で止まるため、同時に扱える本数とウィンドウを明示する。
fn transport_config() -> ConnectionConfig {
    let mut config = ConnectionConfig::default();
    // ピアが開ける単方向ストリームの累積上限
    config.transport_params.initial_max_streams_uni = 10_000;
    // ピアが開ける双方向ストリームの累積上限
    config.transport_params.initial_max_streams_bidi = 1_000;
    // 接続レベルで受け入れる総バイト数
    config.transport_params.initial_max_data = 64 * 1024 * 1024;
    // 単方向ストリーム 1 本あたりのウィンドウ
    config.transport_params.initial_max_stream_data_uni = 16 * 1024 * 1024;
    // 双方向ストリーム 1 本あたりのウィンドウ
    config.transport_params.initial_max_stream_data_bidi_local = 16 * 1024 * 1024;
    config.transport_params.initial_max_stream_data_bidi_remote = 16 * 1024 * 1024;
    // MOQT は QUIC の multipath を使わないため、パスの追加を許可しない
    config.transport_params.initial_max_path_id = None;
    // 応答しないピアとの接続が残り続けないようにする
    config.transport_params.max_idle_timeout = IDLE_TIMEOUT_MS;
    config
}

/// QUIC のクライアントとして接続し、接続ドライバを実行する。
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
            let message = error.message.clone();
            let _ = ready.send(Err(error));
            let _ = events.send(EventSpec::error(0, 0, message)).await;
            let _ = events.send(EventSpec::end(0, 0)).await;
            return;
        }
    };
    let tls = match build_client_tls(&config) {
        Ok(tls) => tls,
        Err(error) => {
            let message = error.message.clone();
            let _ = ready.send(Err(error));
            let _ = events.send(EventSpec::error(0, 0, message)).await;
            let _ = events.send(EventSpec::end(0, 0)).await;
            return;
        }
    };
    let mut last_error = String::from("no address was tried");
    for address in addresses {
        let builder = Client::builder()
            .with_tls(ClientTlsConfig::new(Arc::clone(&tls)))
            .with_io(IoConfig::new(net::local_bind_addr(address)))
            .with_transport(transport_config())
            .with_datagram(DatagramConfig::default())
            .with_handshake_timeout(Some(HANDSHAKE_TIMEOUT))
            .with_background_driver(true);
        let client = match builder.start() {
            Ok(client) => client,
            Err(error) => {
                last_error = format!("failed to start the QUIC client: {error}");
                continue;
            }
        };
        match client
            .connect(Connect::new(address, config.server_name.as_str()))
            .await
        {
            Ok(connection) => {
                let _ = ready.send(Ok(Completion::Unit));
                run_connection(ConnectionRole::Client, connection, commands, events, None).await;
                return;
            }
            Err(error) => {
                last_error = format!("failed to connect to {address}: {error}");
            }
        }
    }
    let error = IoError::connection(last_error.clone());
    let _ = ready.send(Err(error));
    let _ = events.send(EventSpec::error(0, 0, last_error)).await;
    let _ = events.send(EventSpec::end(0, 0)).await;
}

/// QUIC のサーバーとして待ち受け、接続ごとに接続ドライバを実行する。
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
            let message = error.message.clone();
            let _ = ready.send(Err(error));
            let _ = events.send(EventSpec::error(0, 0, message)).await;
            let _ = events.send(EventSpec::end(0, 0)).await;
            return;
        }
    };
    let bind = match net::resolve_bind(&config.host, config.port) {
        Ok(bind) => bind,
        Err(error) => {
            let message = error.message.clone();
            let _ = ready.send(Err(error));
            let _ = events.send(EventSpec::error(0, 0, message)).await;
            let _ = events.send(EventSpec::end(0, 0)).await;
            return;
        }
    };
    let mut server = match Server::builder()
        .with_tls(ServerTlsConfig::new(tls))
        .with_io(IoConfig::new(bind))
        .with_transport(transport_config())
        .with_datagram(DatagramConfig::default())
        .with_background_driver(true)
        .start()
    {
        Ok(server) => server,
        Err(error) => {
            let message = format!("failed to start the QUIC server: {error}");
            let _ = ready.send(Err(IoError::runtime(message.clone())));
            let _ = events.send(EventSpec::error(0, 0, message)).await;
            let _ = events.send(EventSpec::end(0, 0)).await;
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
                        let address = connection
                            .remote_addr()
                            .await
                            .ok()
                            .map(|address| (address.ip().to_string(), address.port()));
                        let (command_tx, command_rx) = mpsc::channel(COMMAND_CHANNEL_CAPACITY);
                        connections.insert(connection_id, command_tx);
                        let _ = events
                            .send(EventSpec::session_ready(connection_id, 0, address))
                            .await;
                        let connection_events = events.clone();
                        let closed = closed_tx.clone();
                        runtime().spawn(async move {
                            run_connection(
                                ConnectionRole::Server { connection_id },
                                connection,
                                command_rx,
                                connection_events,
                                Some(closed),
                            )
                            .await;
                        });
                    }
                    Err(error) => {
                        // 待ち受けの継続が不可能なエラーである。接続中のセッションは
                        // それぞれの接続ドライバが終了を通知する。
                        let message = format!("the QUIC server stopped accepting connections: {error}");
                        let _ = events.send(EventSpec::error(0, 0, message)).await;
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
    // 待ち受けを止める。接続中のセッションは接続ドライバが保持している。
    drop(server);
    let _ = events.send(EventSpec::end(0, 0)).await;
}

/// 1 本の接続を操作し、受信イベントを配送する。
async fn run_connection(
    role: ConnectionRole,
    connection: Connection,
    mut commands: mpsc::Receiver<ConnectionCommand>,
    events: mpsc::Sender<EventSpec>,
    closed: Option<mpsc::Sender<u64>>,
) {
    let (connection_id, session_id) = role.ids();
    let mut writers: HashMap<u64, mpsc::Sender<WriteCommand>> = HashMap::new();
    let mut readers: HashMap<u64, mpsc::Sender<ReadCommand>> = HashMap::new();
    // 接続の終了を reader へ伝える。終了に伴う読み取りエラーを個々のストリームの
    // リセットとして通知すると、状態機械がセッション終了を二重に処理してしまう。
    let connection_closed = Arc::new(AtomicBool::new(false));
    let mut local_close: Option<(u64, String)> = None;
    loop {
        tokio::select! {
            command = commands.recv() => {
                match command {
                    Some(ConnectionCommand::Close { error_code, reason, reply }) => {
                        let result = connection
                            .close(error_code, reason.as_bytes())
                            .await
                            .map(|_| Completion::Unit)
                            .map_err(map_quic_error);
                        let _ = reply.send(result);
                        local_close = Some((error_code, reason));
                        break;
                    }
                    Some(command) => {
                        handle_command(
                            command,
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
            accepted = connection.accept_stream() => {
                match accepted {
                    Ok(PeerStream::Bidirectional(stream)) => {
                        let stream_id = stream.id();
                        let (send, recv) = stream.split();
                        spawn_writer(stream_id, send, &mut writers);
                        spawn_reader(
                            stream_id,
                            recv,
                            &mut readers,
                            events.clone(),
                            connection_id,
                            session_id,
                            Arc::clone(&connection_closed),
                        );
                    }
                    Ok(PeerStream::Receive(recv)) => {
                        let stream_id = recv.id();
                        spawn_reader(
                            stream_id,
                            recv,
                            &mut readers,
                            events.clone(),
                            connection_id,
                            session_id,
                            Arc::clone(&connection_closed),
                        );
                    }
                    Err(_) => break,
                }
            }
            datagram = connection.receive_datagram() => {
                match datagram {
                    Ok(data) => {
                        let _ = events
                            .send(EventSpec::datagram(connection_id, session_id, data))
                            .await;
                    }
                    Err(_) => break,
                }
            }
            observed = connection.accept_stop_sending() => {
                match observed {
                    Ok((stream_id, error_code)) => {
                        let _ = events
                            .send(EventSpec::stop_sending(
                                connection_id,
                                session_id,
                                stream_id,
                                Some(error_code),
                            ))
                            .await;
                    }
                    Err(_) => break,
                }
            }
            reason = connection.closed() => {
                local_close = Some(match reason {
                    Some(reason) => map_close(reason),
                    None => (0, String::new()),
                });
                break;
            }
        }
    }
    connection_closed.store(true, Ordering::SeqCst);
    let (code, reason) = match local_close {
        Some(close) => close,
        None => match connection.close_reason().await {
            Some(reason) => map_close(reason),
            None => (0, String::new()),
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
    if let Some(closed) = closed {
        let _ = closed.send(connection_id).await;
    }
}

/// 接続への操作 1 件を処理する。
#[expect(clippy::too_many_arguments)]
async fn handle_command(
    command: ConnectionCommand,
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
                match connection.open_bidirectional_stream_wait().await {
                    Ok(stream) => {
                        let stream_id = stream.id();
                        let (send, recv) = stream.split();
                        spawn_writer(stream_id, send, writers);
                        spawn_reader(
                            stream_id,
                            recv,
                            readers,
                            events.clone(),
                            connection_id,
                            session_id,
                            Arc::clone(connection_closed),
                        );
                        Ok(Completion::U64(stream_id))
                    }
                    Err(error) => Err(map_quic_error(error)),
                }
            } else {
                match connection.open_send_stream_wait().await {
                    Ok(send) => {
                        let stream_id = send.id();
                        spawn_writer(stream_id, send, writers);
                        Ok(Completion::U64(stream_id))
                    }
                    Err(error) => Err(map_quic_error(error)),
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
                // 送信タスクが終了していると reply が破棄され、Python の Future は
                // 「トランスポートが応答せず終了した」として失敗する。
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
            // データグラムの送信キューが詰まる可能性があるため、接続ドライバを
            // 止めないよう専用のタスクで送る。
            let connection = connection.clone();
            runtime().spawn(async move {
                let result = connection
                    .send_datagram_wait(data)
                    .await
                    .map(|_| Completion::Unit)
                    .map_err(map_quic_error);
                let _ = reply.send(result);
            });
        }
        ConnectionCommand::Close { .. } => {
            // 接続の終了は呼び出し側のループで処理する。
        }
    }
}

/// 送信ストリームを所有するタスクを起動する。
fn spawn_writer(
    stream_id: u64,
    stream: SendStream,
    writers: &mut HashMap<u64, mpsc::Sender<WriteCommand>>,
) {
    let (sender, receiver) = mpsc::channel(WRITE_CHANNEL_CAPACITY);
    writers.insert(stream_id, sender);
    runtime().spawn(writer_task(stream, receiver));
}

/// 送信ストリームを所有し、指示されたデータを書き込むタスク。
async fn writer_task(mut stream: SendStream, mut commands: mpsc::Receiver<WriteCommand>) {
    while let Some(command) = commands.recv().await {
        match command {
            WriteCommand::Send { data, fin, reply } => {
                // 終端だけを送る書き込みは、ピアが既に STOP_SENDING を送っていても
                // 失敗にしない。データを送らないため、停止の通知と競合しても
                // アプリケーションの操作を失敗させる意味が無い
                let empty_fin = data.is_empty() && fin;
                let result = match stream.send_all(&data).await {
                    Ok(()) if fin => stream.finish().await,
                    Ok(()) => Ok(()),
                    Err(error) => Err(error),
                };
                let result = match result {
                    Err(QuicError::Stream(StreamError::Stopped { .. })) if empty_fin => Ok(()),
                    result => result,
                };
                let failed = result.is_err();
                let _ = reply.send(result.map(|_| Completion::Unit).map_err(map_quic_error));
                if failed {
                    break;
                }
            }
            WriteCommand::Reset { error_code, reply } => {
                let result = stream
                    .reset_stream(error_code)
                    .await
                    .map(|_| Completion::Unit)
                    .map_err(map_quic_error);
                let _ = reply.send(result);
                break;
            }
        }
    }
}

/// 受信ストリームを所有するタスクを起動する。
fn spawn_reader(
    stream_id: u64,
    stream: ReceiveStream,
    readers: &mut HashMap<u64, mpsc::Sender<ReadCommand>>,
    events: mpsc::Sender<EventSpec>,
    connection_id: u64,
    session_id: u64,
    connection_closed: Arc<AtomicBool>,
) {
    let (sender, receiver) = mpsc::channel(WRITE_CHANNEL_CAPACITY);
    readers.insert(stream_id, sender);
    runtime().spawn(reader_task(
        stream,
        receiver,
        events,
        connection_id,
        session_id,
        connection_closed,
    ));
}

/// 受信ストリームを所有し、データと終端をイベントとして配送するタスク。
async fn reader_task(
    mut stream: ReceiveStream,
    mut commands: mpsc::Receiver<ReadCommand>,
    events: mpsc::Sender<EventSpec>,
    connection_id: u64,
    session_id: u64,
    connection_closed: Arc<AtomicBool>,
) {
    let stream_id = stream.id();
    loop {
        tokio::select! {
            chunk = stream.receive_vec(RECEIVE_CHUNK_SIZE) => {
                match chunk {
                    Ok(chunk) => {
                        let fin = chunk.fin;
                        if !chunk.data.is_empty() || fin {
                            let event = EventSpec::stream_data(
                                connection_id,
                                session_id,
                                stream_id,
                                chunk.data,
                                fin,
                            );
                            if events.send(event).await.is_err() {
                                break;
                            }
                        }
                        if fin {
                            break;
                        }
                    }
                    Err(QuicError::Stream(StreamError::Reset { error_code, .. })) => {
                        if !connection_closed.load(Ordering::SeqCst) {
                            let _ = events
                                .send(EventSpec::stream_reset(
                                    connection_id,
                                    session_id,
                                    stream_id,
                                    Some(error_code),
                                ))
                                .await;
                        }
                        break;
                    }
                    Err(_) => {
                        if !connection_closed.load(Ordering::SeqCst) {
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
                        let result = stream
                            .stop_sending(error_code)
                            .await
                            .map(|_| Completion::Unit)
                            .map_err(map_quic_error);
                        let failed = result.is_err();
                        let _ = reply.send(result);
                        if failed {
                            break;
                        }
                        // STOP_SENDING を送った後は受信を続けない
                        break;
                    }
                    None => break,
                }
            }
        }
    }
}

/// QUIC のエラーを I/O 層のエラーへ変換する。
fn map_quic_error(error: QuicError) -> IoError {
    match error {
        QuicError::Connection(reason) => {
            IoError::connection(format!("the QUIC connection failed: {reason}"))
        }
        QuicError::Stream(error) => IoError::connection(format!("the QUIC stream failed: {error}")),
        error => IoError::runtime(format!("the QUIC transport failed: {error}")),
    }
}

/// 接続の終了理由を終了コードと理由へ変換する。
fn map_close(reason: ConnectionError) -> (u64, String) {
    match reason {
        ConnectionError::Closed => (0, String::new()),
        ConnectionError::Application { code, reason } => {
            (code, String::from_utf8_lossy(&reason).into_owned())
        }
        ConnectionError::Transport { code, reason } => (code, reason),
        ConnectionError::TimedOut => (0, "connection timed out".to_string()),
        ConnectionError::Internal(message) => (0, message),
    }
}
