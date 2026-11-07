//! Python の asyncio と tokio を接続する。
//!
//! I/O 層のタスクは tokio のスレッドで動くため、Python の Future の完了と
//! イベントの配送は asyncio のイベントループへ `call_soon_threadsafe` で依頼する。
//! Python 側のコルーチンは、このモジュールが返す Future をそのまま `await` する。

use std::sync::Arc;
use std::sync::OnceLock;

use pyo3::IntoPyObjectExt;
use pyo3::exceptions::{PyConnectionError, PyRuntimeError};
use pyo3::prelude::*;
use tokio::runtime::Runtime;
use tokio::sync::{mpsc, oneshot};

use crate::io::command::{ErrorKind, IoError};
use crate::io::event::{EventSpec, IoEvent};

/// プロセス全体で 1 つだけ持つ tokio ランタイム。
///
/// I/O 層のすべてのタスクをこのランタイムで動かす。Python のイベントループとは
/// チャネルと `call_soon_threadsafe` だけで接続する。
pub(crate) fn runtime() -> &'static Runtime {
    static RUNTIME: OnceLock<Runtime> = OnceLock::new();
    RUNTIME.get_or_init(|| {
        tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .thread_name("moqt-io")
            .build()
            .expect("failed to build the tokio runtime")
    })
}

/// I/O 操作の完了結果。
pub(crate) enum Completion {
    /// 値を返さない操作。
    Unit,
    /// 整数を返す操作。
    U64(u64),
}

/// asyncio のイベントループとイベント配送先。
///
/// 生成は Python のスレッドで行い、以後は tokio のスレッドから
/// [`AsyncioBridge::complete`] と [`AsyncioBridge::emit`] を呼ぶ。
pub(crate) struct AsyncioBridge {
    /// 接続を作ったイベントループ
    loop_object: Py<PyAny>,
    /// イベントを積む Python の呼び出し可能オブジェクト
    sink: Py<PyAny>,
}

impl AsyncioBridge {
    /// 現在実行中のイベントループとイベント配送先を保持する。
    pub(crate) fn new(py: Python<'_>, sink: Py<PyAny>) -> PyResult<Self> {
        let loop_object = py
            .import("asyncio")?
            .call_method0("get_running_loop")?
            .unbind();
        Ok(Self { loop_object, sink })
    }

    /// `await` できる asyncio の Future を作る。
    pub(crate) fn create_future(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        Ok(self
            .loop_object
            .bind(py)
            .call_method0("create_future")?
            .unbind())
    }

    /// 別スレッドから Future を完了する。
    ///
    /// Python が終了している場合は配送できない。終了処理中の失敗であるため無視する。
    /// 完了はイベントループのスレッドで行い、既にキャンセルされた Future へは
    /// 書き込まない。呼び出し側が待つのをやめた操作の結果で例外を出さないためである。
    pub(crate) fn complete(&self, future: Py<PyAny>, result: Result<Completion, IoError>) {
        let _ = Python::try_attach(|py| -> PyResult<()> {
            let (value, error): (Py<PyAny>, Option<Py<PyAny>>) = match result {
                Ok(Completion::Unit) => (py.None(), None),
                Ok(Completion::U64(value)) => (value.into_py_any(py)?, None),
                Err(error) => (py.None(), Some(python_error(py, error))),
            };
            let completion = Py::new(
                py,
                FutureCompletion {
                    future,
                    value,
                    error,
                },
            )?;
            self.loop_object
                .bind(py)
                .call_method1("call_soon_threadsafe", (completion.bind(py),))?;
            Ok(())
        });
    }

    /// イベントを asyncio のスレッドへ配送する。
    pub(crate) fn emit(&self, spec: EventSpec) {
        let _ = Python::try_attach(|py| -> PyResult<()> {
            let event = Py::new(
                py,
                IoEvent {
                    kind: spec.kind.as_str(),
                    connection_id: spec.connection_id,
                    session_id: spec.session_id,
                    stream_id: spec.stream_id,
                    data: spec.data,
                    fin: spec.fin,
                    error_code: spec.error_code,
                    code: spec.code,
                    reason: spec.reason,
                    address: spec.address,
                    message: spec.message,
                },
            )?;
            self.loop_object
                .bind(py)
                .call_method1("call_soon_threadsafe", (self.sink.bind(py), event))?;
            Ok(())
        });
    }
}

/// イベントループのスレッドで Future を完了する呼び出し可能オブジェクト。
///
/// 呼び出し側が待つのをやめた Future はキャンセル済みである。その場合は何もしない。
#[pyclass]
struct FutureCompletion {
    /// 完了する Future
    future: Py<PyAny>,
    /// 結果の値
    value: Py<PyAny>,
    /// 例外。`None` なら結果を設定する
    error: Option<Py<PyAny>>,
}

#[pymethods]
impl FutureCompletion {
    /// イベントループのスレッドで Future を完了する。
    fn __call__(&self, py: Python<'_>) -> PyResult<()> {
        let future = self.future.bind(py);
        if future.call_method0("done")?.is_truthy()? {
            return Ok(());
        }
        match &self.error {
            Some(error) => {
                future.call_method1("set_exception", (error.bind(py),))?;
            }
            None => {
                future.call_method1("set_result", (self.value.bind(py),))?;
            }
        }
        Ok(())
    }
}

/// I/O 層のエラーを Python の例外へ変換する。
fn python_error(py: Python<'_>, error: IoError) -> Py<PyAny> {
    let exception = match error.kind {
        ErrorKind::Connection => PyConnectionError::new_err(error.message),
        ErrorKind::Runtime => PyRuntimeError::new_err(error.message),
    };
    exception.into_value(py).into_any()
}

/// oneshot の結果で Python の Future を完了するタスクを起動する。
pub(crate) fn spawn_reply(
    bridge: Arc<AsyncioBridge>,
    future: Py<PyAny>,
    reply: oneshot::Receiver<Result<Completion, IoError>>,
) {
    runtime().spawn(async move {
        match reply.await {
            Ok(result) => bridge.complete(future, result),
            Err(_) => bridge.complete(
                future,
                Err(IoError::runtime(
                    "the transport task stopped before replying",
                )),
            ),
        }
    });
}

/// イベントを Python へ配送し続けるタスクを起動する。
pub(crate) fn spawn_event_pump(bridge: Arc<AsyncioBridge>, mut events: mpsc::Receiver<EventSpec>) {
    runtime().spawn(async move {
        while let Some(spec) = events.recv().await {
            bridge.emit(spec);
        }
    });
}
