//! Python の asyncio と tokio を接続する I/O 層。
//!
//! MOQT の状態機械は Python 側が駆動し、この層はトランスポートの接続・
//! ストリーム・データグラムだけを担当する。各接続方式の実装は
//! `client` / `server` から呼ばれる接続ドライバに閉じ込める。

pub(crate) mod bridge;
pub(crate) mod client;
pub(crate) mod command;
pub(crate) mod event;
pub(crate) mod net;
pub(crate) mod qmux;
pub(crate) mod quic;
pub(crate) mod server;
pub(crate) mod tls;
pub(crate) mod webtransport_h2;
pub(crate) mod webtransport_h3;
