//! MOQT クライアントの I/O を担う Python オブジェクト。

use std::sync::Arc;
use std::sync::OnceLock;
use std::sync::atomic::{AtomicBool, Ordering};

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use tokio::sync::{mpsc, oneshot};

use crate::io::bridge::{AsyncioBridge, Completion, runtime, spawn_event_pump, spawn_reply};
use crate::io::command::{ConnectionCommand, IoError};
use crate::io::event::EventSpec;
use crate::io::qmux;
use crate::io::quic::{self, COMMAND_CHANNEL_CAPACITY, EVENT_CHANNEL_CAPACITY};
use crate::io::webtransport_h2;
use crate::io::webtransport_h3;

/// 接続方式。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum TransportKind {
    /// QUIC 直接接続。
    Quic,
    /// QMux。
    Qmux,
    /// WebTransport over HTTP/2。
    WebTransportOverHttp2,
    /// WebTransport over HTTP/3。
    WebTransportOverHttp3,
}

impl TransportKind {
    /// Python の文字列を接続方式へ変換する。
    fn parse(value: &str) -> PyResult<Self> {
        match value {
            "quic" => Ok(Self::Quic),
            "qmux" => Ok(Self::Qmux),
            "wt-h2" => Ok(Self::WebTransportOverHttp2),
            "wt-h3" => Ok(Self::WebTransportOverHttp3),
            other => Err(PyRuntimeError::new_err(format!(
                "unknown transport kind: {other}"
            ))),
        }
    }

    /// 接続方式の名前を返す。
    fn as_str(self) -> &'static str {
        match self {
            Self::Quic => "quic",
            Self::Qmux => "qmux",
            Self::WebTransportOverHttp2 => "wt-h2",
            Self::WebTransportOverHttp3 => "wt-h3",
        }
    }
}

/// クライアントの接続設定。
#[derive(Clone)]
pub(crate) struct ClientConfig {
    pub(crate) host: String,
    pub(crate) port: u16,
    pub(crate) path: String,
    pub(crate) authority: String,
    pub(crate) server_name: String,
    pub(crate) alpn: Vec<Vec<u8>>,
    /// WebTransport の `WT-Available-Protocols` で提示するプロトコル
    pub(crate) protocols: Vec<String>,
    pub(crate) verify_peer: bool,
    pub(crate) ca_file: Option<String>,
    pub(crate) origin: String,
}

/// クライアントのトランスポート。
///
/// Python の `Client` はこのオブジェクトへ接続・ストリーム・データグラムの
/// 操作を依頼し、[`IoEvent`](crate::io::event::IoEvent) で結果を受け取る。
/// 状態機械は Python 側が駆動するため、このオブジェクトは I/O だけを担う。
#[pyclass(name = "IoClient", frozen)]
pub(crate) struct IoClient {
    bridge: Arc<AsyncioBridge>,
    commands: OnceLock<mpsc::Sender<ConnectionCommand>>,
    events: mpsc::Sender<EventSpec>,
    kind: TransportKind,
    config: ClientConfig,
    started: AtomicBool,
}

impl IoClient {
    /// 1 つの操作をコマンドとして送り、完了を待つ Future を返す。
    fn enqueue(
        &self,
        py: Python<'_>,
        make: impl FnOnce(oneshot::Sender<Result<Completion, IoError>>) -> ConnectionCommand,
    ) -> PyResult<Py<PyAny>> {
        let commands = self
            .commands
            .get()
            .ok_or_else(|| PyRuntimeError::new_err("the transport is not connected"))?;
        let future = self.bridge.create_future(py)?;
        let (reply_tx, reply_rx) = oneshot::channel();
        commands
            .try_send(make(reply_tx))
            .map_err(|_| PyRuntimeError::new_err("the transport is closed"))?;
        spawn_reply(Arc::clone(&self.bridge), future.clone_ref(py), reply_rx);
        Ok(future)
    }
}

#[pymethods]
impl IoClient {
    /// トランスポートを作る。
    ///
    /// `sink` はイベントを 1 つ受け取る呼び出し可能オブジェクトである。イベントは
    /// 生成したイベントループのスレッドで呼ばれる。
    #[new]
    #[pyo3(signature = (
        kind,
        host,
        port,
        path,
        authority,
        server_name,
        alpn,
        protocols,
        verify_peer,
        ca_file,
        origin,
        sink,
    ))]
    #[expect(clippy::too_many_arguments)]
    fn new(
        py: Python<'_>,
        kind: &str,
        host: String,
        port: u16,
        path: String,
        authority: String,
        server_name: String,
        alpn: Vec<Vec<u8>>,
        protocols: Vec<String>,
        verify_peer: bool,
        ca_file: Option<String>,
        origin: String,
        sink: Py<PyAny>,
    ) -> PyResult<Self> {
        let bridge = Arc::new(AsyncioBridge::new(py, sink)?);
        let (events, event_rx) = mpsc::channel(EVENT_CHANNEL_CAPACITY);
        spawn_event_pump(Arc::clone(&bridge), event_rx);
        Ok(Self {
            bridge,
            commands: OnceLock::new(),
            events,
            kind: TransportKind::parse(kind)?,
            config: ClientConfig {
                host,
                port,
                path,
                authority,
                server_name,
                alpn,
                protocols,
                verify_peer,
                ca_file,
                origin,
            },
            started: AtomicBool::new(false),
        })
    }

    /// 接続方式の名前。
    #[getter]
    fn kind(&self) -> &'static str {
        self.kind.as_str()
    }

    /// 接続を開始し、確立まで待つ。
    fn connect(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        if self.started.swap(true, Ordering::SeqCst) {
            return Err(PyRuntimeError::new_err(
                "the client transport has already been started",
            ));
        }
        let (commands, command_rx) = mpsc::channel(COMMAND_CHANNEL_CAPACITY);
        if self.commands.set(commands).is_err() {
            return Err(PyRuntimeError::new_err(
                "the client transport has already been started",
            ));
        }
        let future = self.bridge.create_future(py)?;
        let (ready_tx, ready_rx) = oneshot::channel();
        let bridge = Arc::clone(&self.bridge);
        let config = self.config.clone();
        let events = self.events.clone();
        match self.kind {
            TransportKind::Quic => {
                runtime().spawn(quic::run_client(
                    config,
                    command_rx,
                    events.clone(),
                    bridge,
                    ready_tx,
                ));
            }
            TransportKind::Qmux => {
                runtime().spawn(qmux::run_client(
                    config,
                    command_rx,
                    events.clone(),
                    bridge,
                    ready_tx,
                ));
            }
            TransportKind::WebTransportOverHttp2 => {
                runtime().spawn(webtransport_h2::run_client(
                    config,
                    command_rx,
                    events.clone(),
                    bridge,
                    ready_tx,
                ));
            }
            TransportKind::WebTransportOverHttp3 => {
                runtime().spawn(webtransport_h3::run_client(
                    config,
                    command_rx,
                    events.clone(),
                    bridge,
                    ready_tx,
                ));
            }
        }
        spawn_reply(Arc::clone(&self.bridge), future.clone_ref(py), ready_rx);
        Ok(future)
    }

    /// ストリームを開設し、ストリーム ID を返す。
    fn open_stream(&self, py: Python<'_>, bidirectional: bool) -> PyResult<Py<PyAny>> {
        self.enqueue(py, |reply| ConnectionCommand::OpenStream {
            bidirectional,
            reply,
        })
    }

    /// ストリームへデータを書き込む。
    fn send_stream_data(
        &self,
        py: Python<'_>,
        stream_id: u64,
        data: Vec<u8>,
        fin: bool,
    ) -> PyResult<Py<PyAny>> {
        self.enqueue(py, |reply| ConnectionCommand::SendStreamData {
            stream_id,
            data,
            fin,
            reply,
        })
    }

    /// ストリームの送信側をリセットする。
    fn reset_stream(&self, py: Python<'_>, stream_id: u64, error_code: u64) -> PyResult<Py<PyAny>> {
        self.enqueue(py, |reply| ConnectionCommand::ResetStream {
            stream_id,
            error_code,
            reply,
        })
    }

    /// ストリームの受信側へ STOP_SENDING を送る。
    fn stop_sending(&self, py: Python<'_>, stream_id: u64, error_code: u64) -> PyResult<Py<PyAny>> {
        self.enqueue(py, |reply| ConnectionCommand::StopSending {
            stream_id,
            error_code,
            reply,
        })
    }

    /// データグラムを送る。
    fn send_datagram(&self, py: Python<'_>, data: Vec<u8>) -> PyResult<Py<PyAny>> {
        self.enqueue(py, |reply| ConnectionCommand::SendDatagram { data, reply })
    }

    /// 接続を終了する。
    fn close(&self, py: Python<'_>, error_code: u64, reason: String) -> PyResult<Py<PyAny>> {
        self.enqueue(py, |reply| ConnectionCommand::Close {
            error_code,
            reason,
            reply,
        })
    }
}
