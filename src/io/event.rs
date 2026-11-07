//! Python へ配送するイベント。

use pyo3::prelude::*;
use pyo3::types::PyBytes;

/// イベントの種別。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum EventKind {
    /// ストリームのデータを受信した。
    StreamData,
    /// ストリームがリセットされた。
    StreamReset,
    /// ピアがストリームの送信停止を要求した。
    StopSending,
    /// データグラムを受信した。
    Datagram,
    /// 接続またはセッションが確立した。
    SessionReady,
    /// 接続またはセッションが終了した。
    SessionClosed,
    /// トランスポートでエラーが発生した。
    Error,
    /// I/O タスクが終了した。
    End,
}

impl EventKind {
    /// Python へ渡す種別名を返す。
    pub(crate) fn as_str(self) -> &'static str {
        match self {
            Self::StreamData => "stream_data",
            Self::StreamReset => "stream_reset",
            Self::StopSending => "stop_sending",
            Self::Datagram => "datagram",
            Self::SessionReady => "session_ready",
            Self::SessionClosed => "session_closed",
            Self::Error => "error",
            Self::End => "end",
        }
    }
}

/// Python へ配送する前のイベント。
#[derive(Debug)]
pub(crate) struct EventSpec {
    pub(crate) kind: EventKind,
    pub(crate) connection_id: u64,
    pub(crate) session_id: u64,
    pub(crate) stream_id: Option<u64>,
    pub(crate) data: Option<Vec<u8>>,
    pub(crate) fin: bool,
    pub(crate) error_code: Option<u64>,
    pub(crate) code: Option<u64>,
    pub(crate) reason: Option<String>,
    pub(crate) address: Option<(String, u16)>,
    pub(crate) message: Option<String>,
}

impl EventSpec {
    /// すべてのフィールドを空にしたイベントを作る。
    fn base(kind: EventKind, connection_id: u64, session_id: u64) -> Self {
        Self {
            kind,
            connection_id,
            session_id,
            stream_id: None,
            data: None,
            fin: false,
            error_code: None,
            code: None,
            reason: None,
            address: None,
            message: None,
        }
    }

    /// ストリームのデータ受信を表すイベントを作る。
    pub(crate) fn stream_data(
        connection_id: u64,
        session_id: u64,
        stream_id: u64,
        data: Vec<u8>,
        fin: bool,
    ) -> Self {
        Self {
            stream_id: Some(stream_id),
            data: Some(data),
            fin,
            ..Self::base(EventKind::StreamData, connection_id, session_id)
        }
    }

    /// ストリームのリセットを表すイベントを作る。
    pub(crate) fn stream_reset(
        connection_id: u64,
        session_id: u64,
        stream_id: u64,
        error_code: Option<u64>,
    ) -> Self {
        Self {
            stream_id: Some(stream_id),
            error_code,
            ..Self::base(EventKind::StreamReset, connection_id, session_id)
        }
    }

    /// ピアからの STOP_SENDING を表すイベントを作る。
    pub(crate) fn stop_sending(
        connection_id: u64,
        session_id: u64,
        stream_id: u64,
        error_code: Option<u64>,
    ) -> Self {
        Self {
            stream_id: Some(stream_id),
            error_code,
            ..Self::base(EventKind::StopSending, connection_id, session_id)
        }
    }

    /// データグラムの受信を表すイベントを作る。
    pub(crate) fn datagram(connection_id: u64, session_id: u64, data: Vec<u8>) -> Self {
        Self {
            data: Some(data),
            ..Self::base(EventKind::Datagram, connection_id, session_id)
        }
    }

    /// 接続またはセッションの確立を表すイベントを作る。
    pub(crate) fn session_ready(
        connection_id: u64,
        session_id: u64,
        address: Option<(String, u16)>,
    ) -> Self {
        Self {
            address,
            ..Self::base(EventKind::SessionReady, connection_id, session_id)
        }
    }

    /// 接続またはセッションの終了を表すイベントを作る。
    pub(crate) fn session_closed(
        connection_id: u64,
        session_id: u64,
        code: u64,
        reason: String,
    ) -> Self {
        Self {
            code: Some(code),
            reason: Some(reason),
            ..Self::base(EventKind::SessionClosed, connection_id, session_id)
        }
    }

    /// トランスポートのエラーを表すイベントを作る。
    pub(crate) fn error(connection_id: u64, session_id: u64, message: String) -> Self {
        Self {
            message: Some(message),
            ..Self::base(EventKind::Error, connection_id, session_id)
        }
    }

    /// I/O タスクの終了を表すイベントを作る。
    pub(crate) fn end(connection_id: u64, session_id: u64) -> Self {
        Self::base(EventKind::End, connection_id, session_id)
    }
}

/// Python へ渡すイベント。
///
/// 状態機械を駆動する Python 側が、接続・ストリーム・データグラムの変化を
/// 到着順に観測するために使う。`kind` ごとに意味を持つフィールドだけが入る。
#[pyclass(name = "IoEvent", frozen)]
pub(crate) struct IoEvent {
    pub(crate) kind: &'static str,
    pub(crate) connection_id: u64,
    pub(crate) session_id: u64,
    pub(crate) stream_id: Option<u64>,
    pub(crate) data: Option<Vec<u8>>,
    pub(crate) fin: bool,
    pub(crate) error_code: Option<u64>,
    pub(crate) code: Option<u64>,
    pub(crate) reason: Option<String>,
    pub(crate) address: Option<(String, u16)>,
    pub(crate) message: Option<String>,
}

#[pymethods]
impl IoEvent {
    /// イベントの種別。
    ///
    /// `stream_data` / `stream_reset` / `stop_sending` / `datagram` /
    /// `session_ready` / `session_closed` / `error` / `end` のいずれかである。
    #[getter]
    fn kind(&self) -> &'static str {
        self.kind
    }

    /// 接続を識別する番号。クライアントでは常に 0 である。
    #[getter]
    fn connection_id(&self) -> u64 {
        self.connection_id
    }

    /// WebTransport セッション ID。QUIC 直接接続と QMux では常に 0 である。
    #[getter]
    fn session_id(&self) -> u64 {
        self.session_id
    }

    /// ストリーム ID。ストリームを伴わないイベントでは `None` である。
    #[getter]
    fn stream_id(&self) -> Option<u64> {
        self.stream_id
    }

    /// 受信したデータ。データを伴わないイベントでは `None` である。
    #[getter]
    fn data<'py>(&self, py: Python<'py>) -> Option<Bound<'py, PyBytes>> {
        self.data
            .as_ref()
            .map(|data| PyBytes::new(py, data.as_slice()))
    }

    /// FIN を受信したか。ストリームのデータ受信以外では常に偽である。
    #[getter]
    fn fin(&self) -> bool {
        self.fin
    }

    /// リセットまたは STOP_SENDING のエラーコード。
    ///
    /// `None` はアプリケーションエラーコードを持たない終端を表す。
    #[getter]
    fn error_code(&self) -> Option<u64> {
        self.error_code
    }

    /// 接続またはセッションの終了コード。
    #[getter]
    fn code(&self) -> Option<u64> {
        self.code
    }

    /// 接続またはセッションの終了理由。
    #[getter]
    fn reason(&self) -> Option<String> {
        self.reason.clone()
    }

    /// 接続元のアドレス。クライアントでは `None` である。
    ///
    /// サーバーが接続を受け付けたときにだけ値が入る。
    #[getter]
    fn address(&self) -> Option<(String, u16)> {
        self.address.clone()
    }

    /// トランスポートのエラー内容。
    #[getter]
    fn message(&self) -> Option<String> {
        self.message.clone()
    }

    /// 内容を表す文字列を返す。
    fn __repr__(&self) -> String {
        format!(
            "IoEvent(kind={}, connection_id={}, session_id={}, stream_id={:?})",
            self.kind, self.connection_id, self.session_id, self.stream_id
        )
    }
}
