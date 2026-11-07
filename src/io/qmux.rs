//! shiguredo_tokio_qmux を使った QMux の I/O。
//!
//! QMux は TCP + TLS 上の 1 本の双方向バイトストリームで、QUIC version 1 相当の
//! ストリームと DATAGRAM を多重化する (draft-ietf-quic-qmux-02)。MOQT のストリームは
//! QMux のストリームへ 1 対 1 で対応する
//! (draft-nandakumar-moq-qmux-moqt-00 §4.1 (Stream Mapping))。
//!
//! 現在の MOQT 経路は QMux の DATAGRAM を使わないため、DATAGRAM は広告しない。

use std::collections::HashMap;
use std::net::SocketAddr;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, AtomicU16, Ordering};
use std::time::Duration;

use shiguredo_qmux::codec::role::Role;
use shiguredo_qmux::codec::time::Duration as QmuxDuration;
use shiguredo_qmux::config::Config;
use shiguredo_qmux::event::CloseReason;
use shiguredo_tokio_qmux::Connection as QmuxConnection;
use shiguredo_tokio_qmux::Error as QmuxError;
use shiguredo_tokio_qmux::RecvStream as QmuxRecvStream;
use shiguredo_tokio_qmux::SendStream as QmuxSendStream;
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::{mpsc, oneshot};
use tokio_rustls::{TlsAcceptor, TlsConnector};

use crate::io::bridge::{AsyncioBridge, Completion, runtime};
use crate::io::client::ClientConfig;
use crate::io::command::{ConnectionCommand, IoError, ReadCommand, ServerCommand, WriteCommand};
use crate::io::event::EventSpec;
use crate::io::net;
use crate::io::server::ServerConfig;
use crate::io::tls::{build_client_tls, build_server_tls};

/// 受信 1 回あたりに読み出す最大バイト数。
const RECEIVE_CHUNK_SIZE: usize = 64 * 1024;
/// 接続を閉じた後にドライバの終了を待つ上限。
const CLOSE_TIMEOUT: Duration = Duration::from_secs(5);
/// アイドルタイムアウト (ms)。
const IDLE_TIMEOUT_MS: u64 = 30_000;
/// QMux の Record サイズの既定値。
const MAX_RECORD_SIZE: u64 = 16_382;

/// 接続の役割。
#[derive(Debug, Clone, Copy)]
enum ConnectionRole {
    /// クライアント。接続 ID とセッション ID は 0 である。
    Client,
    /// サーバー。接続ごとに割り当てた接続 ID をセッション ID にも使う。
    Server { connection_id: u64 },
}

impl ConnectionRole {
    /// イベントへ載せる接続 ID とセッション ID を返す。
    fn ids(self) -> (u64, u64) {
        match self {
            Self::Client => (0, 0),
            Self::Server { connection_id } => (connection_id, connection_id),
        }
    }
}

/// QMux のトランスポートパラメータを作る。
///
/// MOQT は 1 本の接続で制御・要求・データのストリームを同時に使うため、
/// ストリーム数とウィンドウを明示する。DATAGRAM は現在の MOQT 経路では使わない。
fn qmux_config() -> Config {
    Config {
        max_idle_timeout: QmuxDuration::from_millis(IDLE_TIMEOUT_MS),
        initial_max_data: 64 * 1024 * 1024,
        initial_max_stream_data_bidi_local: 16 * 1024 * 1024,
        initial_max_stream_data_bidi_remote: 16 * 1024 * 1024,
        initial_max_stream_data_uni: 16 * 1024 * 1024,
        initial_max_streams_bidi: 1_000,
        initial_max_streams_uni: 10_000,
        max_record_size: MAX_RECORD_SIZE,
        max_datagram_frame_size: None,
    }
}

/// TLS のハンドシェイク後に ALPN が期待値と一致するか確認する。
fn verify_alpn(negotiated: Option<&[u8]>, expected: &[Vec<u8>]) -> Result<(), IoError> {
    let Some(expected) = expected.first() else {
        return Ok(());
    };
    if negotiated == Some(expected.as_slice()) {
        return Ok(());
    }
    Err(IoError::connection(format!(
        "ALPN mismatch: expected {}, got {:?}",
        String::from_utf8_lossy(expected),
        negotiated.map(String::from_utf8_lossy)
    )))
}

/// QMux のクライアントとして接続し、接続ドライバを実行する。
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
        match connect_tls(address, &config.server_name, Arc::clone(&tls), &config.alpn).await {
            Ok(stream) => match QmuxConnection::new(Role::Client, stream, qmux_config()) {
                Ok(connection) => {
                    let _ = ready.send(Ok(Completion::Unit));
                    run_connection(
                        ConnectionRole::Client,
                        Arc::new(connection),
                        commands,
                        events,
                        None,
                    )
                    .await;
                    return;
                }
                Err(error) => {
                    last_error = format!("failed to start the QMux connection: {error}");
                }
            },
            Err(error) => {
                last_error = error.message;
            }
        }
    }
    fail_client(ready, events, IoError::connection(last_error)).await;
}

/// 接続の失敗を Future とイベントへ伝える。
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

/// TCP 接続と TLS ハンドシェイクを行い、ALPN を確認する。
async fn connect_tls(
    address: SocketAddr,
    server_name: &str,
    tls: Arc<rustls::ClientConfig>,
    alpn: &[Vec<u8>],
) -> Result<tokio_rustls::client::TlsStream<TcpStream>, IoError> {
    let tcp = TcpStream::connect(address)
        .await
        .map_err(|error| IoError::connection(format!("failed to connect to {address}: {error}")))?;
    tcp.set_nodelay(true).map_err(|error| {
        IoError::connection(format!("failed to configure the TCP socket: {error}"))
    })?;
    let server_name = rustls::pki_types::ServerName::try_from(server_name.to_string())
        .map_err(|error| IoError::connection(format!("invalid server name: {error}")))?;
    let connector = TlsConnector::from(tls);
    let stream = connector
        .connect(server_name, tcp)
        .await
        .map_err(|error| IoError::connection(format!("TLS handshake failed: {error}")))?;
    verify_alpn(stream.get_ref().1.alpn_protocol(), alpn)?;
    Ok(stream)
}

/// QMux のサーバーとして待ち受け、接続ごとに接続ドライバを実行する。
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
    let listener = match TcpListener::bind(bind).await {
        Ok(listener) => listener,
        Err(error) => {
            fail_server(
                ready,
                events,
                IoError::connection(format!("failed to listen on {bind}: {error}")),
            )
            .await;
            return;
        }
    };
    match listener.local_addr() {
        Ok(address) => {
            actual_port.store(address.port(), Ordering::SeqCst);
        }
        Err(error) => {
            fail_server(
                ready,
                events,
                IoError::connection(format!("failed to get the listen address: {error}")),
            )
            .await;
            return;
        }
    }
    let _ = ready.send(Ok(Completion::Unit));

    let acceptor = TlsAcceptor::from(tls);
    let alpn = config.alpn.clone();
    let (closed_tx, mut closed_rx) = mpsc::channel::<u64>(64);
    let mut connections: HashMap<u64, mpsc::Sender<ConnectionCommand>> = HashMap::new();
    let mut next_connection_id: u64 = 1;
    loop {
        tokio::select! {
            accepted = listener.accept() => {
                match accepted {
                    Ok((tcp, peer)) => {
                        let connection_id = next_connection_id;
                        next_connection_id += 1;
                        // 接続先の登録は TLS の完了前に行う。session_ready の直後に
                        // Python 側が操作を送っても取りこぼさないためである。
                        let (command_tx, command_rx) =
                            mpsc::channel(crate::io::quic::COMMAND_CHANNEL_CAPACITY);
                        connections.insert(connection_id, command_tx);
                        let acceptor = acceptor.clone();
                        let alpn = alpn.clone();
                        let events = events.clone();
                        let closed = closed_tx.clone();
                        runtime().spawn(async move {
                            let result = accept_connection(
                                connection_id,
                                peer,
                                tcp,
                                acceptor,
                                alpn,
                                command_rx,
                                events.clone(),
                            )
                            .await;
                            if let Err(error) = result {
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
                                format!("the QMux server stopped accepting connections: {error}"),
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
    drop(listener);
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

/// TLS を受理して QMux 接続を作り、接続ドライバを実行する。
async fn accept_connection(
    connection_id: u64,
    peer: SocketAddr,
    tcp: TcpStream,
    acceptor: TlsAcceptor,
    alpn: Vec<Vec<u8>>,
    commands: mpsc::Receiver<ConnectionCommand>,
    events: mpsc::Sender<EventSpec>,
) -> Result<(), IoError> {
    tcp.set_nodelay(true).map_err(|error| {
        IoError::connection(format!("failed to configure the TCP socket: {error}"))
    })?;
    let stream = acceptor
        .accept(tcp)
        .await
        .map_err(|error| IoError::connection(format!("TLS handshake failed: {error}")))?;
    verify_alpn(stream.get_ref().1.alpn_protocol(), &alpn)?;
    let connection = QmuxConnection::new(Role::Server, stream, qmux_config()).map_err(|error| {
        IoError::runtime(format!("failed to start the QMux connection: {error}"))
    })?;
    let _ = events
        .send(EventSpec::session_ready(
            connection_id,
            connection_id,
            Some((peer.ip().to_string(), peer.port())),
        ))
        .await;
    run_connection(
        ConnectionRole::Server { connection_id },
        Arc::new(connection),
        commands,
        events,
        None,
    )
    .await;
    Ok(())
}

/// 1 本の QMux 接続を操作し、受信イベントを配送する。
async fn run_connection(
    role: ConnectionRole,
    connection: Arc<QmuxConnection>,
    mut commands: mpsc::Receiver<ConnectionCommand>,
    events: mpsc::Sender<EventSpec>,
    closed: Option<mpsc::Sender<u64>>,
) {
    let (connection_id, session_id) = role.ids();
    let mut writers: HashMap<u64, mpsc::Sender<WriteCommand>> = HashMap::new();
    let mut readers: HashMap<u64, mpsc::Sender<ReadCommand>> = HashMap::new();
    let connection_closed = Arc::new(AtomicBool::new(false));
    loop {
        tokio::select! {
            command = commands.recv() => {
                match command {
                    Some(ConnectionCommand::Close { error_code, reason, reply }) => {
                        let result = connection
                            .close(error_code, &reason)
                            .map(|_| Completion::Unit)
                            .map_err(map_qmux_error);
                        let _ = reply.send(result);
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
            accepted = connection.accept_bidirectional() => {
                match accepted {
                    Ok(Some((send, recv))) => {
                        let stream_id = send.id().as_u64();
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
                    Ok(None) => break,
                    Err(_) => break,
                }
            }
            accepted = connection.accept_unidirectional() => {
                match accepted {
                    Ok(Some(recv)) => {
                        let stream_id = recv.id().as_u64();
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
                    Ok(None) => break,
                    Err(_) => break,
                }
            }
            observed = connection.recv_stop_sending() => {
                match observed {
                    Ok(Some(observed)) => {
                        let _ = events
                            .send(EventSpec::stop_sending(
                                connection_id,
                                session_id,
                                observed.id.as_u64(),
                                Some(observed.error_code),
                            ))
                            .await;
                    }
                    Ok(None) => break,
                    Err(_) => break,
                }
            }
            datagram = connection.recv_datagram() => {
                match datagram {
                    Ok(Some(data)) => {
                        let _ = events
                            .send(EventSpec::datagram(connection_id, session_id, data))
                            .await;
                    }
                    Ok(None) => break,
                    Err(_) => break,
                }
            }
            _reason = connection.closed() => {
                break;
            }
        }
    }
    connection_closed.store(true, Ordering::SeqCst);
    // ローカルから閉じた場合は、CONNECTION_CLOSE の送信とピアの shutdown 待ちが
    // 終わるまで接続を保持する。Connection をドロップするとドライバが即座に
    // 停止し、CONNECTION_CLOSE が送られないためである。
    let reason = match tokio::time::timeout(CLOSE_TIMEOUT, connection.closed()).await {
        Ok(reason) => reason,
        Err(_) => CloseReason::TransportClosed,
    };
    let (code, reason) = map_close_reason(reason);
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
    connection: &Arc<QmuxConnection>,
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
                match connection.open_bidirectional().await {
                    Ok((send, recv)) => {
                        let stream_id = send.id().as_u64();
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
                    Err(error) => Err(map_qmux_error(error)),
                }
            } else {
                match connection.open_unidirectional().await {
                    Ok(send) => {
                        let stream_id = send.id().as_u64();
                        spawn_writer(stream_id, send, writers);
                        Ok(Completion::U64(stream_id))
                    }
                    Err(error) => Err(map_qmux_error(error)),
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
            let connection = Arc::clone(connection);
            runtime().spawn(async move {
                let result = connection
                    .send_datagram(&data)
                    .await
                    .map(|_| Completion::Unit)
                    .map_err(map_qmux_error);
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
    stream: QmuxSendStream,
    writers: &mut HashMap<u64, mpsc::Sender<WriteCommand>>,
) {
    let (sender, receiver) = mpsc::channel(crate::io::quic::WRITE_CHANNEL_CAPACITY);
    writers.insert(stream_id, sender);
    runtime().spawn(writer_task(stream, receiver));
}

/// 送信ストリームを所有し、指示されたデータを書き込むタスク。
async fn writer_task(mut stream: QmuxSendStream, mut commands: mpsc::Receiver<WriteCommand>) {
    while let Some(command) = commands.recv().await {
        match command {
            WriteCommand::Send { data, fin, reply } => {
                // 終端だけを送る書き込みは、ピアが既に STOP_SENDING を送っていても
                // 失敗にしない。データを送らないため、停止の通知と競合しても
                // アプリケーションの操作を失敗させる意味が無い
                let empty_fin = data.is_empty() && fin;
                let result = match stream.write(&data).await {
                    Ok(_) if fin => stream.finish().await,
                    Ok(_) => Ok(()),
                    Err(error) => Err(error),
                };
                let result = match result {
                    Err(QmuxError::Stopped(_)) if empty_fin => Ok(()),
                    result => result,
                };
                let failed = result.is_err();
                let _ = reply.send(result.map(|_| Completion::Unit).map_err(map_qmux_error));
                if failed {
                    break;
                }
            }
            WriteCommand::Reset { error_code, reply } => {
                let result = stream
                    .reset(error_code)
                    .await
                    .map(|_| Completion::Unit)
                    .map_err(map_qmux_error);
                let _ = reply.send(result);
                break;
            }
        }
    }
}

/// 受信ストリームを所有するタスクを起動する。
fn spawn_reader(
    stream_id: u64,
    stream: QmuxRecvStream,
    readers: &mut HashMap<u64, mpsc::Sender<ReadCommand>>,
    events: mpsc::Sender<EventSpec>,
    connection_id: u64,
    session_id: u64,
    connection_closed: Arc<AtomicBool>,
) {
    let (sender, receiver) = mpsc::channel(crate::io::quic::WRITE_CHANNEL_CAPACITY);
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
    mut stream: QmuxRecvStream,
    mut commands: mpsc::Receiver<ReadCommand>,
    events: mpsc::Sender<EventSpec>,
    connection_id: u64,
    session_id: u64,
    connection_closed: Arc<AtomicBool>,
) {
    let stream_id = stream.id().as_u64();
    let mut buffer = vec![0u8; RECEIVE_CHUNK_SIZE];
    // STOP_SENDING を送った後も受信側を保持する。ドロップするとエラーコード 0 の
    // STOP_SENDING が重ねて送られるためである。
    let mut stopping = false;
    loop {
        tokio::select! {
            result = stream.read(&mut buffer) => {
                match result {
                    Ok(Some(0)) => {}
                    Ok(Some(length)) => {
                        if !stopping {
                            let event = EventSpec::stream_data(
                                connection_id,
                                session_id,
                                stream_id,
                                buffer[..length].to_vec(),
                                false,
                            );
                            if events.send(event).await.is_err() {
                                break;
                            }
                        }
                    }
                    Ok(None) => {
                        if !stopping {
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
                    Err(QmuxError::Reset(error_code)) => {
                        if !connection_closed.load(Ordering::SeqCst) && !stopping {
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
                        let result = stream
                            .stop_sending(error_code)
                            .await
                            .map(|_| Completion::Unit)
                            .map_err(map_qmux_error);
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

/// QMux のエラーを I/O 層のエラーへ変換する。
fn map_qmux_error(error: QmuxError) -> IoError {
    match error {
        QmuxError::ConnectionClosed => IoError::connection("the QMux connection is closed"),
        QmuxError::Reset(code) => IoError::connection(format!(
            "the QMux stream was reset by the peer: code={code}"
        )),
        QmuxError::Stopped(code) => IoError::connection(format!(
            "the QMux stream was stopped by the peer: code={code}"
        )),
        error => IoError::runtime(format!("the QMux transport failed: {error}")),
    }
}

/// QMux の終了理由を終了コードと理由へ変換する。
fn map_close_reason(reason: CloseReason) -> (u64, String) {
    match reason {
        CloseReason::IdleTimeout => (0, "idle timeout".to_string()),
        CloseReason::Local {
            error_code, reason, ..
        }
        | CloseReason::Peer {
            error_code, reason, ..
        } => (error_code, reason),
        CloseReason::PeerShutdown => (0, "peer shutdown".to_string()),
        CloseReason::TransportClosed => (0, "transport closed".to_string()),
    }
}
