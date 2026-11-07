//! MOQT サーバーの I/O を担う Python オブジェクト。

use std::sync::Arc;
use std::sync::OnceLock;
use std::sync::atomic::{AtomicBool, AtomicU16, Ordering};

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use tokio::sync::{mpsc, oneshot};

use crate::io::bridge::{AsyncioBridge, Completion, runtime, spawn_event_pump, spawn_reply};
use crate::io::client::TransportKind;
use crate::io::command::{ConnectionCommand, IoError, ServerCommand};
use crate::io::event::EventSpec;
use crate::io::qmux;
use crate::io::quic::{self, COMMAND_CHANNEL_CAPACITY, EVENT_CHANNEL_CAPACITY};
use crate::io::webtransport_h2;
use crate::io::webtransport_h3;

/// サーバーの待ち受け設定。
///
/// `allowed_origins` は WebTransport over HTTP/2 のセッション受理で使う。
#[derive(Clone)]
pub(crate) struct ServerConfig {
    pub(crate) host: String,
    pub(crate) port: u16,
    pub(crate) certfile: String,
    pub(crate) keyfile: String,
    pub(crate) alpn: Vec<Vec<u8>>,
    /// クライアントの `WT-Available-Protocols` から選択するプロトコル
    pub(crate) protocols: Vec<String>,
    pub(crate) allowed_origins: Option<Vec<String>>,
}

/// サーバーのトランスポート。
///
/// 接続の受け付けと、接続ごとのストリーム・データグラムの操作を担う。
/// 接続は `connection_id` で識別し、WebTransport のセッション ID とは別である。
#[pyclass(name = "IoServer", frozen)]
pub(crate) struct IoServer {
    bridge: Arc<AsyncioBridge>,
    commands: OnceLock<mpsc::Sender<ServerCommand>>,
    events: mpsc::Sender<EventSpec>,
    kind: TransportKind,
    config: ServerConfig,
    started: AtomicBool,
    actual_port: Arc<AtomicU16>,
}

impl IoServer {
    /// 特定の接続への操作を送り、完了を待つ Future を返す。
    fn session_enqueue(
        &self,
        py: Python<'_>,
        connection_id: u64,
        make: impl FnOnce(oneshot::Sender<Result<Completion, IoError>>) -> ConnectionCommand,
    ) -> PyResult<Py<PyAny>> {
        let commands = self
            .commands
            .get()
            .ok_or_else(|| PyRuntimeError::new_err("the server is not started"))?;
        let future = self.bridge.create_future(py)?;
        let (reply_tx, reply_rx) = oneshot::channel();
        commands
            .try_send(ServerCommand::Connection {
                connection_id,
                command: make(reply_tx),
            })
            .map_err(|_| PyRuntimeError::new_err("the server is closed"))?;
        spawn_reply(Arc::clone(&self.bridge), future.clone_ref(py), reply_rx);
        Ok(future)
    }
}

#[pymethods]
impl IoServer {
    /// サーバーのトランスポートを作る。
    #[new]
    #[pyo3(signature = (
        kind,
        host,
        port,
        certfile,
        keyfile,
        alpn,
        protocols,
        allowed_origins,
        sink,
    ))]
    #[expect(clippy::too_many_arguments)]
    fn new(
        py: Python<'_>,
        kind: &str,
        host: String,
        port: u16,
        certfile: String,
        keyfile: String,
        alpn: Vec<Vec<u8>>,
        protocols: Vec<String>,
        allowed_origins: Option<Vec<String>>,
        sink: Py<PyAny>,
    ) -> PyResult<Self> {
        // 接続方式の検証はクライアントと同じ変換を共有する
        let kind = match kind {
            "quic" => TransportKind::Quic,
            "qmux" => TransportKind::Qmux,
            "wt-h2" => TransportKind::WebTransportOverHttp2,
            "wt-h3" => TransportKind::WebTransportOverHttp3,
            other => {
                return Err(PyRuntimeError::new_err(format!(
                    "unknown transport kind: {other}"
                )));
            }
        };
        let bridge = Arc::new(AsyncioBridge::new(py, sink)?);
        let (events, event_rx) = mpsc::channel(EVENT_CHANNEL_CAPACITY);
        spawn_event_pump(Arc::clone(&bridge), event_rx);
        Ok(Self {
            bridge,
            commands: OnceLock::new(),
            events,
            kind,
            config: ServerConfig {
                host,
                port,
                certfile,
                keyfile,
                alpn,
                protocols,
                allowed_origins,
            },
            started: AtomicBool::new(false),
            actual_port: Arc::new(AtomicU16::new(0)),
        })
    }

    /// 接続方式の名前。
    #[getter]
    fn kind(&self) -> &'static str {
        match self.kind {
            TransportKind::Quic => "quic",
            TransportKind::Qmux => "qmux",
            TransportKind::WebTransportOverHttp2 => "wt-h2",
            TransportKind::WebTransportOverHttp3 => "wt-h3",
        }
    }

    /// 実際に待ち受けているポート番号。開始前は 0 である。
    #[getter]
    fn actual_port(&self) -> u16 {
        self.actual_port.load(Ordering::SeqCst)
    }

    /// 待ち受けを開始する。
    fn start(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        if self.started.swap(true, Ordering::SeqCst) {
            return Err(PyRuntimeError::new_err(
                "the server transport has already been started",
            ));
        }
        let (commands, command_rx) = mpsc::channel(COMMAND_CHANNEL_CAPACITY);
        if self.commands.set(commands).is_err() {
            return Err(PyRuntimeError::new_err(
                "the server transport has already been started",
            ));
        }
        let future = self.bridge.create_future(py)?;
        let (ready_tx, ready_rx) = oneshot::channel();
        let bridge = Arc::clone(&self.bridge);
        let config = self.config.clone();
        let events = self.events.clone();
        let actual_port = Arc::clone(&self.actual_port);
        match self.kind {
            TransportKind::Quic => {
                runtime().spawn(quic::run_server(
                    config,
                    command_rx,
                    events.clone(),
                    bridge,
                    ready_tx,
                    actual_port,
                ));
            }
            TransportKind::Qmux => {
                runtime().spawn(qmux::run_server(
                    config,
                    command_rx,
                    events.clone(),
                    bridge,
                    ready_tx,
                    actual_port,
                ));
            }
            TransportKind::WebTransportOverHttp2 => {
                runtime().spawn(webtransport_h2::run_server(
                    config,
                    command_rx,
                    events.clone(),
                    bridge,
                    ready_tx,
                    actual_port,
                ));
            }
            TransportKind::WebTransportOverHttp3 => {
                runtime().spawn(webtransport_h3::run_server(
                    config,
                    command_rx,
                    events.clone(),
                    bridge,
                    ready_tx,
                    actual_port,
                ));
            }
        }
        spawn_reply(Arc::clone(&self.bridge), future.clone_ref(py), ready_rx);
        Ok(future)
    }

    /// 待ち受けを停止する。
    fn stop(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let commands = self
            .commands
            .get()
            .ok_or_else(|| PyRuntimeError::new_err("the server is not started"))?;
        let future = self.bridge.create_future(py)?;
        let (reply_tx, reply_rx) = oneshot::channel();
        commands
            .try_send(ServerCommand::Stop { reply: reply_tx })
            .map_err(|_| PyRuntimeError::new_err("the server is closed"))?;
        spawn_reply(Arc::clone(&self.bridge), future.clone_ref(py), reply_rx);
        Ok(future)
    }

    /// 接続上でストリームを開設し、ストリーム ID を返す。
    fn open_stream(
        &self,
        py: Python<'_>,
        connection_id: u64,
        bidirectional: bool,
    ) -> PyResult<Py<PyAny>> {
        self.session_enqueue(py, connection_id, |reply| ConnectionCommand::OpenStream {
            bidirectional,
            reply,
        })
    }

    /// 接続上のストリームへデータを書き込む。
    fn send_stream_data(
        &self,
        py: Python<'_>,
        connection_id: u64,
        stream_id: u64,
        data: Vec<u8>,
        fin: bool,
    ) -> PyResult<Py<PyAny>> {
        self.session_enqueue(py, connection_id, |reply| {
            ConnectionCommand::SendStreamData {
                stream_id,
                data,
                fin,
                reply,
            }
        })
    }

    /// 接続上のストリームの送信側をリセットする。
    fn reset_stream(
        &self,
        py: Python<'_>,
        connection_id: u64,
        stream_id: u64,
        error_code: u64,
    ) -> PyResult<Py<PyAny>> {
        self.session_enqueue(py, connection_id, |reply| ConnectionCommand::ResetStream {
            stream_id,
            error_code,
            reply,
        })
    }

    /// 接続上のストリームの受信側へ STOP_SENDING を送る。
    fn stop_sending(
        &self,
        py: Python<'_>,
        connection_id: u64,
        stream_id: u64,
        error_code: u64,
    ) -> PyResult<Py<PyAny>> {
        self.session_enqueue(py, connection_id, |reply| ConnectionCommand::StopSending {
            stream_id,
            error_code,
            reply,
        })
    }

    /// 接続上でデータグラムを送る。
    fn send_datagram(
        &self,
        py: Python<'_>,
        connection_id: u64,
        data: Vec<u8>,
    ) -> PyResult<Py<PyAny>> {
        self.session_enqueue(py, connection_id, |reply| ConnectionCommand::SendDatagram {
            data,
            reply,
        })
    }

    /// 接続を終了する。
    fn close_session(
        &self,
        py: Python<'_>,
        connection_id: u64,
        error_code: u64,
        reason: String,
    ) -> PyResult<Py<PyAny>> {
        self.session_enqueue(py, connection_id, |reply| ConnectionCommand::Close {
            error_code,
            reason,
            reply,
        })
    }
}
