//! shiguredo_http2 (Sans I/O) を使った WebTransport over HTTP/2 (WT-H2) の I/O。
//!
//! WebTransport over HTTP/2 は 1 本の拡張 CONNECT ストリームの上に Capsule
//! Protocol でストリームとデータグラムを多重化する
//! (draft-ietf-webtrans-http2-16)。HTTP/2 のフレーミングは shiguredo_http2 の
//! Sans I/O 状態機械が担い、このモジュールが TLS とソケットの読み書きを駆動する。
//! WebTransport の状態機械も同じ crate の `WtSession` を使う。
//!
//! セッションは 1 本のタスクが所有し、ソケットの読み取りとコマンドを `select!` で
//! 待つ。HTTP/2 と WebTransport の状態機械は同期 API なので、ソケットの読み取り
//! 待ちの間だけを非同期にすればよい。

use std::io;
use std::net::SocketAddr;
use std::sync::Arc;
use std::sync::atomic::{AtomicU16, Ordering};
use std::time::Duration;

use shiguredo_http2::webtransport::{
    WtAvailableProtocols, WtConfig, WtErrorKind, WtEvent, WtSession, serialize_wt_protocol,
};
use shiguredo_http2::{Connection, Error as Http2Error, Event, HeaderField, Limits, StreamId};
use tokio::io::{AsyncRead, AsyncReadExt, AsyncWrite, AsyncWriteExt};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::{mpsc, oneshot};
use tokio_rustls::{TlsAcceptor, TlsConnector};

use crate::io::bridge::{AsyncioBridge, Completion, runtime};
use crate::io::client::ClientConfig;
use crate::io::command::{ConnectionCommand, IoError, ServerCommand};
use crate::io::event::EventSpec;
use crate::io::net;
use crate::io::quic::COMMAND_CHANNEL_CAPACITY;
use crate::io::server::ServerConfig;
use crate::io::tls::{build_client_tls, build_server_tls};

/// ハンドシェイクのタイムアウト。
const HANDSHAKE_TIMEOUT: Duration = Duration::from_secs(10);
/// ソケットから 1 回に読むバイト数の上限。
const READ_CHUNK_SIZE: usize = 64 * 1024;
/// HTTP/2 の DATA を 1 回で送るバイト数の上限。
///
/// shiguredo_http2 の送信バッファは 65535 バイトであり、それ以上を渡すと
/// 全量拒否される。Capsule は途中で分割してよい
/// (draft-ietf-webtrans-http2-16 Section 2 / RFC 9297 Section 3.1)。
const SEND_CHUNK_SIZE: usize = 32 * 1024;
/// WebTransport のフロー制御の初期値。
const WT_MAX_DATA: u32 = 64 * 1024 * 1024;
/// WebTransport のストリームあたりのフロー制御の初期値。
const WT_MAX_STREAM_DATA: u32 = 16 * 1024 * 1024;
/// WebTransport の単方向ストリーム数の初期値。
const WT_MAX_STREAMS_UNI: u32 = 10_000;
/// WebTransport の双方向ストリーム数の初期値。
const WT_MAX_STREAMS_BIDI: u32 = 1_000;

/// HTTP/2 と WebTransport の制限を作る。
fn limits() -> Limits {
    Limits::builder()
        .enable_connect_protocol(true)
        .wt_enabled(true)
        .webtransport(
            Some(WT_MAX_DATA),
            Some(WT_MAX_STREAM_DATA),
            Some(WT_MAX_STREAM_DATA),
            Some(WT_MAX_STREAMS_UNI),
            Some(WT_MAX_STREAMS_BIDI),
            Some(WT_MAX_STREAM_DATA),
        )
        .max_concurrent_streams(Some(1_000))
        .build()
        .expect("the HTTP/2 limits are valid")
}

/// 自側が広告した設定から WebTransport のローカル設定を作る。
fn local_wt_config(settings: &shiguredo_http2::Settings) -> WtConfig {
    let mut config = WtConfig::default();
    config.apply_advertised_settings(settings);
    config
}

/// ピアが広告した設定から WebTransport のピア設定を作る。
fn peer_wt_config(settings: &shiguredo_http2::Settings) -> WtConfig {
    let mut config = WtConfig::peer_default();
    config.overlay_settings(settings);
    config
}

/// HTTP/2 接続の出力をソケットへ書き出す。
async fn flush<W>(connection: &mut Connection, stream: &mut W) -> Result<(), IoError>
where
    W: AsyncWrite + Unpin,
{
    while let Some(output) = connection.poll_output() {
        stream.write_all(&output).await.map_err(map_io_error)?;
    }
    stream.flush().await.map_err(map_io_error)
}

/// WT セッションの出力を CONNECT ストリームへ書き出す。
async fn flush_wt<W>(
    connection: &mut Connection,
    session: &mut WtSession,
    connect_stream: StreamId,
    stream: &mut W,
) -> Result<(), IoError>
where
    W: AsyncWrite + Unpin,
{
    while let Some(output) = session.poll_output() {
        for chunk in output.chunks(SEND_CHUNK_SIZE) {
            connection
                .send_data(connect_stream, chunk.to_vec(), false)
                .map_err(map_http2_error)?;
        }
    }
    flush(connection, stream).await
}

/// 読み取ったバイト列を HTTP/2 の状態機械へ入力する。
fn feed(connection: &mut Connection, data: &[u8]) -> Result<(), IoError> {
    let mut consumed = 0;
    while consumed < data.len() {
        let read = connection
            .feed(&data[consumed..])
            .map_err(map_http2_error)?;
        if read == 0 {
            return Err(IoError::runtime(
                "the HTTP/2 state machine did not consume the input",
            ));
        }
        consumed += read;
    }
    connection.process().map_err(map_http2_error)
}

/// `WT-Available-Protocols` のヘッダー値を作る。
///
/// 値を RFC 9651 の String の List として並べる
/// (draft-ietf-webtrans-http2-16 Section 3.3)。
fn available_protocols(protocols: &[String]) -> Option<Vec<u8>> {
    if protocols.is_empty() {
        return None;
    }
    let mut value = Vec::new();
    for (index, protocol) in protocols.iter().enumerate() {
        if index > 0 {
            value.extend_from_slice(b", ");
        }
        value.extend_from_slice(&serialize_wt_protocol(protocol.as_bytes()).ok()?);
    }
    Some(value)
}

/// ヘッダーから名前で値を探す。
fn header_value<'a>(headers: &'a [HeaderField], name: &[u8]) -> Option<&'a [u8]> {
    headers
        .iter()
        .find(|header| header.name() == name)
        .map(HeaderField::value)
}

/// `:status` を数値として返す。
fn status_code(headers: &[HeaderField]) -> Option<u16> {
    let value = header_value(headers, b":status")?;
    std::str::from_utf8(value).ok()?.parse().ok()
}

/// 動的なヘッダーを作る。
fn header(name: &[u8], value: &[u8]) -> Result<HeaderField, IoError> {
    HeaderField::new(name, value)
        .map_err(|error| IoError::runtime(format!("failed to build an HTTP/2 header: {error}")))
}

/// クライアントとして接続し、セッションを実行する。
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
            fail(ready, events, error).await;
            return;
        }
    };
    let tls = match build_client_tls(&config) {
        Ok(tls) => tls,
        Err(error) => {
            fail(ready, events, error).await;
            return;
        }
    };
    let mut last_error = String::from("no address was tried");
    for address in addresses {
        match connect_client(address, &config, Arc::clone(&tls)).await {
            Ok((connection, tls_stream, connect_stream, local, peer)) => {
                let session_id = u64::from(connect_stream.as_u32());
                let _ = ready.send(Ok(Completion::Unit));
                let _ = events
                    .send(EventSpec::session_ready(0, session_id, None))
                    .await;
                let mut session = WtSession::client(local, peer);
                if let Err(error) = session.initiate() {
                    let _ = events
                        .send(EventSpec::error(
                            0,
                            session_id,
                            format!("failed to start the WebTransport session: {error}"),
                        ))
                        .await;
                    let _ = events.send(EventSpec::end(0, session_id)).await;
                    return;
                }
                run_session(
                    connection,
                    tls_stream,
                    session,
                    connect_stream,
                    0,
                    session_id,
                    commands,
                    events,
                )
                .await;
                return;
            }
            Err(error) => {
                last_error = format!("failed to connect to {address}: {}", error.message);
            }
        }
    }
    fail(ready, events, IoError::connection(last_error)).await;
}

/// HTTP/2 の接続を確立し、拡張 CONNECT が受理されるまで待つ。
async fn connect_client(
    address: SocketAddr,
    config: &ClientConfig,
    tls: Arc<rustls::ClientConfig>,
) -> Result<
    (
        Connection,
        tokio_rustls::client::TlsStream<TcpStream>,
        StreamId,
        WtConfig,
        WtConfig,
    ),
    IoError,
> {
    let mut stream = tokio::time::timeout(HANDSHAKE_TIMEOUT, async {
        let tcp = TcpStream::connect(address).await.map_err(map_io_error)?;
        let connector = TlsConnector::from(tls);
        let server_name = rustls::pki_types::ServerName::try_from(config.server_name.clone())
            .map_err(|error| {
                IoError::connection(format!(
                    "invalid server name '{}': {error}",
                    config.server_name
                ))
            })?;
        connector
            .connect(server_name, tcp)
            .await
            .map_err(|error| IoError::connection(format!("the TLS handshake failed: {error}")))
    })
    .await
    .map_err(|_| IoError::connection("the TLS handshake timed out"))??;

    let mut connection = Connection::client(limits());
    connection.initiate().map_err(map_http2_error)?;
    flush(&mut connection, &mut stream).await?;

    // ピアの SETTINGS が届くまで待つ
    let mut buffer = vec![0u8; READ_CHUNK_SIZE];
    let mut settings_received = false;
    while !settings_received {
        let read = tokio::time::timeout(HANDSHAKE_TIMEOUT, stream.read(&mut buffer))
            .await
            .map_err(|_| IoError::connection("timed out waiting for HTTP/2 SETTINGS"))?
            .map_err(map_io_error)?;
        if read == 0 {
            return Err(IoError::connection(
                "the connection closed before HTTP/2 SETTINGS",
            ));
        }
        feed(&mut connection, &buffer[..read])?;
        flush(&mut connection, &mut stream).await?;
        while let Some(event) = connection.poll_event() {
            if matches!(event, Event::SettingsReceived { ack: false }) {
                settings_received = true;
            }
        }
    }

    // 拡張 CONNECT を送る
    let mut headers = vec![
        HeaderField::from_static(b":method", b"CONNECT"),
        HeaderField::from_static(b":protocol", b"webtransport"),
        HeaderField::from_static(b":scheme", b"https"),
        header(b":authority", config.authority.as_bytes())?,
        header(b":path", config.path.as_bytes())?,
    ];
    if !config.origin.is_empty() {
        headers.push(header(b"origin", config.origin.as_bytes())?);
    }
    if let Some(value) = available_protocols(&config.protocols) {
        headers.push(header(b"wt-available-protocols", &value)?);
    }
    let connect_stream = connection
        .start_stream(headers, false)
        .map_err(map_http2_error)?;
    flush(&mut connection, &mut stream).await?;

    // 200 応答を待つ
    let mut response: Option<Vec<HeaderField>> = None;
    while response.is_none() {
        let read = tokio::time::timeout(HANDSHAKE_TIMEOUT, stream.read(&mut buffer))
            .await
            .map_err(|_| IoError::connection("timed out waiting for the WebTransport response"))?
            .map_err(map_io_error)?;
        if read == 0 {
            return Err(IoError::connection(
                "the connection closed before the WebTransport response",
            ));
        }
        feed(&mut connection, &buffer[..read])?;
        flush(&mut connection, &mut stream).await?;
        while let Some(event) = connection.poll_event() {
            if let Event::HeadersReceived {
                stream_id, headers, ..
            } = event
                && stream_id == connect_stream
            {
                response = Some(headers);
            }
        }
    }
    let headers = response.expect("response is set");
    let status = status_code(&headers).unwrap_or(0);
    if !(200..300).contains(&status) {
        return Err(IoError::connection(format!(
            "the WebTransport CONNECT was rejected with status {status}"
        )));
    }
    let selected = header_value(&headers, b"wt-protocol")
        .map(|value| String::from_utf8_lossy(value).into_owned());
    if !config.protocols.is_empty() && selected.is_none() {
        return Err(IoError::connection(
            "the server did not select a WebTransport protocol",
        ));
    }
    let local = local_wt_config(connection.local_settings());
    let peer = peer_wt_config(connection.remote_settings());
    Ok((connection, stream, connect_stream, local, peer))
}

/// サーバーとして待ち受け、接続ごとにセッションを実行する。
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
            fail(ready, events, error).await;
            return;
        }
    };
    let bind = match net::resolve_bind(&config.host, config.port) {
        Ok(bind) => bind,
        Err(error) => {
            fail(ready, events, error).await;
            return;
        }
    };
    let listener = match TcpListener::bind(bind).await {
        Ok(listener) => listener,
        Err(error) => {
            fail(
                ready,
                events,
                IoError::runtime(format!("failed to bind the HTTP/2 listener: {error}")),
            )
            .await;
            return;
        }
    };
    let port = match listener.local_addr() {
        Ok(address) => address.port(),
        Err(error) => {
            fail(
                ready,
                events,
                IoError::runtime(format!("failed to read the listener address: {error}")),
            )
            .await;
            return;
        }
    };
    actual_port.store(port, Ordering::SeqCst);
    let _ = ready.send(Ok(Completion::Unit));

    let acceptor = TlsAcceptor::from(tls);
    let (closed_tx, mut closed_rx) = mpsc::channel::<u64>(COMMAND_CHANNEL_CAPACITY);
    let mut connections: std::collections::HashMap<u64, mpsc::Sender<ConnectionCommand>> =
        std::collections::HashMap::new();
    let mut next_connection_id: u64 = 1;
    loop {
        tokio::select! {
            accepted = listener.accept() => {
                match accepted {
                    Ok((stream, address)) => {
                        let connection_id = next_connection_id;
                        next_connection_id += 1;
                        let (command_tx, command_rx) = mpsc::channel(COMMAND_CHANNEL_CAPACITY);
                        connections.insert(connection_id, command_tx);
                        let acceptor = acceptor.clone();
                        let events = events.clone();
                        let closed = closed_tx.clone();
                        let protocols = config.protocols.clone();
                        let allowed_origins = config.allowed_origins.clone();
                        runtime().spawn(async move {
                            if let Err(error) = accept_connection(
                                connection_id,
                                stream,
                                address,
                                acceptor,
                                protocols,
                                allowed_origins,
                                command_rx,
                                events.clone(),
                            )
                            .await
                            {
                                let _ = events
                                    .send(EventSpec::error(
                                        connection_id,
                                        connection_id,
                                        error.message,
                                    ))
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
                                format!("the HTTP/2 server stopped accepting: {error}"),
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
    let _ = events.send(EventSpec::end(0, 0)).await;
}

/// 接続を受け入れ、拡張 CONNECT でセッションを確立する。
#[expect(clippy::too_many_arguments)]
async fn accept_connection(
    connection_id: u64,
    stream: TcpStream,
    address: SocketAddr,
    acceptor: TlsAcceptor,
    protocols: Vec<String>,
    allowed_origins: Option<Vec<String>>,
    commands: mpsc::Receiver<ConnectionCommand>,
    events: mpsc::Sender<EventSpec>,
) -> Result<(), IoError> {
    let mut stream = tokio::time::timeout(HANDSHAKE_TIMEOUT, acceptor.accept(stream))
        .await
        .map_err(|_| IoError::connection("the TLS handshake timed out"))?
        .map_err(|error| IoError::connection(format!("the TLS handshake failed: {error}")))?;
    let mut connection = Connection::server(limits());
    connection.initiate().map_err(map_http2_error)?;
    flush(&mut connection, &mut stream).await?;

    let mut buffer = vec![0u8; READ_CHUNK_SIZE];
    loop {
        let read = stream.read(&mut buffer).await.map_err(map_io_error)?;
        if read == 0 {
            return Err(IoError::connection(
                "the connection closed before the WebTransport request",
            ));
        }
        feed(&mut connection, &buffer[..read])?;
        flush(&mut connection, &mut stream).await?;

        let mut request: Option<(StreamId, Vec<HeaderField>)> = None;
        while let Some(event) = connection.poll_event() {
            if let Event::HeadersReceived {
                stream_id,
                headers,
                protocol,
                ..
            } = event
                && protocol.as_deref() == Some(b"webtransport")
            {
                request = Some((stream_id, headers));
            }
        }
        let Some((connect_stream, headers)) = request else {
            continue;
        };

        // Origin の検査 (draft-ietf-webtrans-http2-16 Section 3.2)
        if let Some(allowed) = &allowed_origins
            && let Some(origin) = header_value(&headers, b"origin")
        {
            let accepted = allowed
                .iter()
                .any(|value| value.as_bytes().eq_ignore_ascii_case(origin));
            if !accepted {
                reject(&mut connection, &mut stream, connect_stream, b"403").await?;
                return Err(IoError::connection(
                    "the WebTransport request had a disallowed origin",
                ));
            }
        }

        // プロトコルの選択 (draft-ietf-webtrans-http2-16 Section 3.3)
        let offered = header_value(&headers, b"wt-available-protocols")
            .and_then(|value| WtAvailableProtocols::parse(value).ok())
            .map(|available| available.protocols)
            .unwrap_or_default();
        let selected = if protocols.is_empty() {
            None
        } else {
            match protocols
                .iter()
                .find(|protocol| offered.iter().any(|value| value == *protocol))
            {
                Some(protocol) => Some(protocol.clone()),
                None => {
                    reject(&mut connection, &mut stream, connect_stream, b"400").await?;
                    return Err(IoError::connection(
                        "the client did not offer a supported WebTransport protocol",
                    ));
                }
            }
        };
        let mut response = vec![HeaderField::from_static(b":status", b"200")];
        if let Some(protocol) = &selected {
            let value = serialize_wt_protocol(protocol.as_bytes()).map_err(|error| {
                IoError::runtime(format!(
                    "failed to encode the WebTransport protocol: {error}"
                ))
            })?;
            response.push(header(b"wt-protocol", &value)?);
        }
        connection
            .send_response(connect_stream, response, false)
            .map_err(map_http2_error)?;
        flush(&mut connection, &mut stream).await?;

        let local = local_wt_config(connection.local_settings());
        let peer = peer_wt_config(connection.remote_settings());
        let mut session = WtSession::server(local, peer);
        if let Err(error) = session.initiate() {
            return Err(IoError::runtime(format!(
                "failed to start the WebTransport session: {error}"
            )));
        }
        let session_id = u64::from(connect_stream.as_u32());
        let _ = events
            .send(EventSpec::session_ready(
                connection_id,
                session_id,
                Some((address.ip().to_string(), address.port())),
            ))
            .await;
        run_session(
            connection,
            stream,
            session,
            connect_stream,
            connection_id,
            session_id,
            commands,
            events,
        )
        .await;
        return Ok(());
    }
}

/// 要求をステータスコード付きで拒否する。
async fn reject<W>(
    connection: &mut Connection,
    stream: &mut W,
    connect_stream: StreamId,
    status: &[u8],
) -> Result<(), IoError>
where
    W: AsyncWrite + Unpin,
{
    let headers = vec![header(b":status", status)?];
    let _ = connection.send_response(connect_stream, headers, true);
    flush(connection, stream).await
}

/// セッションを所有し、ソケットの入力とコマンドを処理する。
#[expect(clippy::too_many_arguments)]
async fn run_session<W>(
    mut connection: Connection,
    mut stream: W,
    mut session: WtSession,
    connect_stream: StreamId,
    connection_id: u64,
    session_id: u64,
    mut commands: mpsc::Receiver<ConnectionCommand>,
    events: mpsc::Sender<EventSpec>,
) where
    W: AsyncRead + AsyncWrite + Unpin,
{
    let mut buffer = vec![0u8; READ_CHUNK_SIZE];
    let mut closed: Option<(u64, String)> = None;
    loop {
        tokio::select! {
            command = commands.recv() => {
                match command {
                    Some(ConnectionCommand::Close { error_code, reason, reply }) => {
                        let result = match u32::try_from(error_code) {
                            Ok(error_code) => session
                                .close(error_code, &reason)
                                .map(|_| Completion::Unit)
                                .map_err(|error| IoError::runtime(format!(
                                    "failed to close the WebTransport session: {error}"
                                ))),
                            Err(_) => Err(IoError::runtime(format!(
                                "the close code does not fit the WebTransport error code: {error_code}"
                            ))),
                        };
                        let _ = reply.send(result);
                        if flush_wt(&mut connection, &mut session, connect_stream, &mut stream)
                            .await
                            .is_ok()
                        {
                            // CONNECT ストリームを END_STREAM で閉じる
                            let _ = connection.send_data(connect_stream, Vec::new(), true);
                            let _ = flush(&mut connection, &mut stream).await;
                        }
                        closed = Some((error_code, reason));
                        break;
                    }
                    Some(command) => {
                        handle_command(
                            command,
                            &mut connection,
                            &mut session,
                            connect_stream,
                            &mut stream,
                            connection_id,
                            session_id,
                            &events,
                        )
                        .await;
                    }
                    None => break,
                }
            }
            read = stream.read(&mut buffer) => {
                match read {
                    Ok(0) => break,
                    Ok(n) => {
                        if feed(&mut connection, &buffer[..n]).is_err() {
                            break;
                        }
                        if flush(&mut connection, &mut stream).await.is_err() {
                            break;
                        }
                        let mut end_stream = false;
                        while let Some(event) = connection.poll_event() {
                            match event {
                                Event::DataReceived { stream_id, data, end_stream: end } if stream_id == connect_stream => {
                                    if session.feed(&data).is_err() || session.process().is_err() {
                                        closed = Some((0, String::new()));
                                        break;
                                    }
                                    if end {
                                        end_stream = true;
                                    }
                                }
                                Event::StreamReset { stream_id, error_code, .. } if stream_id == connect_stream => {
                                    closed = Some((u64::from(error_code.as_u32()), String::new()));
                                    break;
                                }
                                _ => {}
                            }
                        }
                        if closed.is_none() {
                            closed = drain_wt_events(
                                &mut session,
                                connection_id,
                                session_id,
                                &events,
                            )
                            .await;
                        }
                        if closed.is_none() && end_stream {
                            closed = Some((0, String::new()));
                        }
                        if closed.is_none()
                            && flush_wt(&mut connection, &mut session, connect_stream, &mut stream)
                                .await
                                .is_err()
                        {
                            break;
                        }
                    }
                    Err(_) => break,
                }
            }
        }
        if closed.is_some() {
            break;
        }
    }
    let (code, reason) = closed.unwrap_or_default();
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

/// 1 件のコマンドを WebTransport の状態機械へ適用する。
#[expect(clippy::too_many_arguments)]
async fn handle_command<W>(
    command: ConnectionCommand,
    connection: &mut Connection,
    session: &mut WtSession,
    connect_stream: StreamId,
    stream: &mut W,
    connection_id: u64,
    session_id: u64,
    events: &mpsc::Sender<EventSpec>,
) where
    W: AsyncWrite + Unpin,
{
    match command {
        ConnectionCommand::OpenStream {
            bidirectional,
            reply,
        } => {
            let opened = if bidirectional {
                session.open_bidi_stream()
            } else {
                session.open_uni_stream()
            };
            let result = opened
                .map(Completion::U64)
                .map_err(|error| IoError::runtime(format!("failed to open a stream: {error}")));
            if result.is_ok() {
                let _ = flush_wt(connection, session, connect_stream, stream).await;
            }
            let _ = reply.send(result);
        }
        ConnectionCommand::SendStreamData {
            stream_id,
            data,
            fin,
            reply,
        } => {
            // 終端だけを送る書き込みは、ピアが既に STOP_SENDING を送ってストリームが
            // 削除されていても失敗にしない。データを送らないため、停止の通知と競合
            // してもアプリケーションの操作を失敗させる意味が無い
            let empty_fin = data.is_empty() && fin;
            let result = match session.send_stream_data(stream_id, &data, fin) {
                Err(error)
                    if empty_fin
                        && matches!(
                            error.kind(),
                            WtErrorKind::InvalidStreamId | WtErrorKind::StreamStateError
                        ) =>
                {
                    Ok(())
                }
                result => result,
            }
            .map(|_| Completion::Unit)
            .map_err(|error| IoError::runtime(format!("failed to send stream data: {error}")));
            if result.is_ok() {
                let _ = flush_wt(connection, session, connect_stream, stream).await;
            }
            let _ = reply.send(result);
        }
        ConnectionCommand::ResetStream {
            stream_id,
            error_code,
            reply,
        } => {
            let result = session
                .reset_stream(stream_id, error_code)
                .map(|_| Completion::Unit)
                .map_err(|error| IoError::runtime(format!("failed to reset the stream: {error}")));
            if result.is_ok() {
                let _ = flush_wt(connection, session, connect_stream, stream).await;
            }
            let _ = reply.send(result);
        }
        ConnectionCommand::StopSending {
            stream_id,
            error_code,
            reply,
        } => {
            let result = session
                .stop_sending(stream_id, error_code)
                .map(|_| Completion::Unit)
                .map_err(|error| IoError::runtime(format!("failed to stop the stream: {error}")));
            if result.is_ok() {
                let _ = flush_wt(connection, session, connect_stream, stream).await;
            }
            let _ = reply.send(result);
        }
        ConnectionCommand::SendDatagram { data, reply } => {
            let result = session
                .send_datagram(&data)
                .map(|_| Completion::Unit)
                .map_err(|error| IoError::runtime(format!("failed to send a datagram: {error}")));
            if result.is_ok() {
                let _ = flush_wt(connection, session, connect_stream, stream).await;
            }
            let _ = reply.send(result);
        }
        ConnectionCommand::Close { .. } => {
            let _ = events.try_send(EventSpec::error(
                connection_id,
                session_id,
                "the close command was not handled by the session loop".to_string(),
            ));
        }
    }
}

/// WebTransport のイベントをアプリケーション向けのイベントへ変換する。
async fn drain_wt_events(
    session: &mut WtSession,
    connection_id: u64,
    session_id: u64,
    events: &mpsc::Sender<EventSpec>,
) -> Option<(u64, String)> {
    while let Some(event) = session.poll_event() {
        match event {
            WtEvent::StreamData {
                stream_id,
                data,
                fin,
            } => {
                let _ = events
                    .send(EventSpec::stream_data(
                        connection_id,
                        session_id,
                        stream_id,
                        data,
                        fin,
                    ))
                    .await;
            }
            WtEvent::StreamReset {
                stream_id,
                error_code,
            } => {
                let _ = events
                    .send(EventSpec::stream_reset(
                        connection_id,
                        session_id,
                        stream_id,
                        Some(error_code),
                    ))
                    .await;
            }
            WtEvent::StopSending {
                stream_id,
                error_code,
            } => {
                let _ = events
                    .send(EventSpec::stop_sending(
                        connection_id,
                        session_id,
                        stream_id,
                        Some(error_code),
                    ))
                    .await;
            }
            WtEvent::DatagramReceived { data } => {
                let _ = events
                    .send(EventSpec::datagram(connection_id, session_id, data))
                    .await;
            }
            WtEvent::SessionClosed { error_code, reason } => {
                return Some((u64::from(error_code), reason));
            }
            WtEvent::StreamOpened { .. } | WtEvent::SessionDraining => {}
        }
    }
    None
}

/// HTTP/2 のエラーを I/O 層のエラーへ変換する。
fn map_http2_error(error: Http2Error) -> IoError {
    IoError::runtime(format!("the HTTP/2 connection failed: {error}"))
}

/// ソケットのエラーを I/O 層のエラーへ変換する。
fn map_io_error(error: io::Error) -> IoError {
    IoError::connection(format!("the HTTP/2 socket failed: {error}"))
}

/// セッション開始前の失敗を Future とイベントへ伝える。
async fn fail(
    ready: oneshot::Sender<Result<Completion, IoError>>,
    events: mpsc::Sender<EventSpec>,
    error: IoError,
) {
    let message = error.message.clone();
    let _ = ready.send(Err(error));
    let _ = events.send(EventSpec::error(0, 0, message)).await;
    let _ = events.send(EventSpec::end(0, 0)).await;
}
