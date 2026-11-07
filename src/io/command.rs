//! I/O 層が利用する操作コマンドとエラー。

use tokio::sync::oneshot;

use crate::io::bridge::Completion;

/// I/O 層のエラー種別。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum ErrorKind {
    /// 接続の確立または利用に失敗した。
    Connection,
    /// トランスポートの内部状態が想定外だった。
    Runtime,
}

/// I/O 層のエラー。
///
/// Python の Future を完了するときに、種別に応じた例外へ変換する。
#[derive(Debug, Clone)]
pub(crate) struct IoError {
    pub(crate) kind: ErrorKind,
    pub(crate) message: String,
}

impl IoError {
    /// 接続の失敗を表すエラーを作る。
    pub(crate) fn connection(message: impl Into<String>) -> Self {
        Self {
            kind: ErrorKind::Connection,
            message: message.into(),
        }
    }

    /// トランスポートの内部エラーを作る。
    pub(crate) fn runtime(message: impl Into<String>) -> Self {
        Self {
            kind: ErrorKind::Runtime,
            message: message.into(),
        }
    }
}

/// 接続に対する操作。
pub(crate) enum ConnectionCommand {
    /// ストリームを開設し、ストリーム ID を返す。
    OpenStream {
        bidirectional: bool,
        reply: oneshot::Sender<Result<Completion, IoError>>,
    },
    /// ストリームへデータを書き込む。
    SendStreamData {
        stream_id: u64,
        data: Vec<u8>,
        fin: bool,
        reply: oneshot::Sender<Result<Completion, IoError>>,
    },
    /// ストリームの送信側をリセットする。
    ResetStream {
        stream_id: u64,
        error_code: u64,
        reply: oneshot::Sender<Result<Completion, IoError>>,
    },
    /// ストリームの受信側へ STOP_SENDING を送る。
    StopSending {
        stream_id: u64,
        error_code: u64,
        reply: oneshot::Sender<Result<Completion, IoError>>,
    },
    /// データグラムを送る。
    SendDatagram {
        data: Vec<u8>,
        reply: oneshot::Sender<Result<Completion, IoError>>,
    },
    /// 接続を終了する。
    Close {
        error_code: u64,
        reason: String,
        reply: oneshot::Sender<Result<Completion, IoError>>,
    },
}

/// 送信タスクへの操作。
pub(crate) enum WriteCommand {
    /// データを書き込み、必要なら FIN を送る。
    Send {
        data: Vec<u8>,
        fin: bool,
        reply: oneshot::Sender<Result<Completion, IoError>>,
    },
    /// 送信側をリセットする。
    Reset {
        error_code: u64,
        reply: oneshot::Sender<Result<Completion, IoError>>,
    },
}

/// 受信タスクへの操作。
pub(crate) enum ReadCommand {
    /// 受信側へ STOP_SENDING を送る。
    StopSending {
        error_code: u64,
        reply: oneshot::Sender<Result<Completion, IoError>>,
    },
}

/// サーバーに対する操作。
pub(crate) enum ServerCommand {
    /// 特定の接続へ操作を転送する。
    Connection {
        connection_id: u64,
        command: ConnectionCommand,
    },
    /// 待ち受けを停止する。
    Stop {
        reply: oneshot::Sender<Result<Completion, IoError>>,
    },
}
