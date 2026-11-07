//! 接続先と待ち受けアドレスの解決。
//!
//! DNS 名は非同期で解決し、IP リテラルはそのまま使う。接続先のアドレスファミリに
//! 合わせてローカルソケットのワイルドカードを選ぶ。

use std::net::{IpAddr, SocketAddr, ToSocketAddrs};

use crate::io::command::IoError;

/// 接続先のアドレスを名前解決する。
pub(crate) async fn resolve(host: &str, port: u16) -> Result<Vec<SocketAddr>, IoError> {
    if let Ok(ip) = host.parse::<IpAddr>() {
        return Ok(vec![SocketAddr::new(ip, port)]);
    }
    let addresses: Vec<SocketAddr> = tokio::net::lookup_host((host, port))
        .await
        .map_err(|error| IoError::connection(format!("failed to resolve {host}:{port}: {error}")))?
        .collect();
    if addresses.is_empty() {
        return Err(IoError::connection(format!(
            "the host {host} did not resolve to any address"
        )));
    }
    Ok(addresses)
}

/// 接続先のアドレスファミリに合わせたローカルアドレスを返す。
pub(crate) fn local_bind_addr(remote: SocketAddr) -> SocketAddr {
    if remote.is_ipv6() {
        "[::]:0"
            .parse()
            .expect("the IPv6 wildcard address literal must parse")
    } else {
        "0.0.0.0:0"
            .parse()
            .expect("the IPv4 wildcard address literal must parse")
    }
}

/// 待ち受けアドレスを名前解決する。
pub(crate) fn resolve_bind(host: &str, port: u16) -> Result<SocketAddr, IoError> {
    if let Ok(ip) = host.parse::<IpAddr>() {
        return Ok(SocketAddr::new(ip, port));
    }
    (host, port)
        .to_socket_addrs()
        .map_err(|error| {
            IoError::connection(format!(
                "failed to resolve the listen address {host}:{port}: {error}"
            ))
        })?
        .next()
        .ok_or_else(|| {
            IoError::connection(format!("the listen address {host}:{port} did not resolve"))
        })
}
