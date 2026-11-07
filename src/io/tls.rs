//! TLS (rustls) の設定。
//!
//! QUIC / WebTransport over HTTP/3 / WebTransport over HTTP/2 / QMux が共有する。
//! 証明書の読み込みと ALPN の設定だけを担い、接続方式による違いは ALPN だけである。

use std::sync::Arc;

use crate::io::client::ClientConfig;
use crate::io::command::IoError;
/// クライアント TLS 設定を作る。
///
/// `verify_peer` が偽の場合は証明書の検証を無効にする。`ca_file` を指定した場合は
/// Mozilla のルート証明書に加えてその証明書を信頼する。ALPN は `config.alpn` を使う。
pub(crate) fn build_client_tls(
    config: &ClientConfig,
) -> Result<Arc<rustls::ClientConfig>, IoError> {
    let mut tls = if config.verify_peer {
        let mut roots = rustls::RootCertStore::empty();
        // 既定の信頼ストアに CA 証明書を追加する。Python の ssl モジュールで
        // load_verify_locations を呼んだときと同じ扱いにする。
        roots.extend(webpki_roots::TLS_SERVER_ROOTS.iter().cloned());
        if let Some(path) = &config.ca_file {
            let file = std::fs::File::open(path).map_err(|error| {
                IoError::connection(format!(
                    "failed to open the CA certificate file '{path}': {error}"
                ))
            })?;
            let mut reader = std::io::BufReader::new(file);
            for certificate in rustls_pemfile::certs(&mut reader) {
                let certificate = certificate.map_err(|error| {
                    IoError::connection(format!(
                        "failed to read the CA certificate file '{path}': {error}"
                    ))
                })?;
                roots.add(certificate).map_err(|error| {
                    IoError::connection(format!(
                        "failed to add the CA certificate '{path}': {error}"
                    ))
                })?;
            }
        }
        rustls::ClientConfig::builder()
            .with_root_certificates(roots)
            .with_no_client_auth()
    } else {
        rustls::ClientConfig::builder()
            .dangerous()
            .with_custom_certificate_verifier(Arc::new(InsecureVerifier::new()))
            .with_no_client_auth()
    };
    tls.alpn_protocols = config.alpn.clone();
    Ok(Arc::new(tls))
}

/// サーバー TLS 設定を作る。
///
/// 証明書と鍵のファイルを読み、ALPN に `alpn` を設定する。
pub(crate) fn build_server_tls(
    certfile: &str,
    keyfile: &str,
    alpn: &[Vec<u8>],
) -> Result<Arc<rustls::ServerConfig>, IoError> {
    let file = std::fs::File::open(certfile).map_err(|error| {
        IoError::runtime(format!(
            "failed to open the certificate file '{}': {error}",
            certfile
        ))
    })?;
    let mut reader = std::io::BufReader::new(file);
    let certificates = rustls_pemfile::certs(&mut reader)
        .collect::<Result<Vec<_>, std::io::Error>>()
        .map_err(|error| {
            IoError::runtime(format!(
                "failed to read the certificate file '{}': {error}",
                certfile
            ))
        })?;
    if certificates.is_empty() {
        return Err(IoError::runtime(format!(
            "the certificate file '{}' contains no certificate",
            certfile
        )));
    }
    let file = std::fs::File::open(keyfile).map_err(|error| {
        IoError::runtime(format!(
            "failed to open the private key file '{}': {error}",
            keyfile
        ))
    })?;
    let mut reader = std::io::BufReader::new(file);
    let key = rustls_pemfile::private_key(&mut reader)
        .map_err(|error| {
            IoError::runtime(format!(
                "failed to read the private key file '{}': {error}",
                keyfile
            ))
        })?
        .ok_or_else(|| {
            IoError::runtime(format!(
                "the private key file '{}' contains no private key",
                keyfile
            ))
        })?;
    let mut tls = rustls::ServerConfig::builder()
        .with_no_client_auth()
        .with_single_cert(certificates, key)
        .map_err(|error| {
            IoError::runtime(format!("failed to build the server TLS config: {error}"))
        })?;
    tls.alpn_protocols = alpn.to_vec();
    Ok(Arc::new(tls))
}

/// 証明書を検証しない `ServerCertVerifier` (開発用)。
///
/// 署名検証だけは既定の暗号プロバイダに委ね、証明書チェーンとサーバー名の
/// 検証を行わない。`verify_peer=False` を指定したときだけ使う。
#[derive(Debug)]
struct InsecureVerifier(Arc<rustls::crypto::CryptoProvider>);

impl InsecureVerifier {
    /// 既定の暗号プロバイダを使う検証器を作る。
    fn new() -> Self {
        Self(Arc::new(rustls::crypto::aws_lc_rs::default_provider()))
    }
}

impl rustls::client::danger::ServerCertVerifier for InsecureVerifier {
    fn verify_server_cert(
        &self,
        _end_entity: &rustls::pki_types::CertificateDer<'_>,
        _intermediates: &[rustls::pki_types::CertificateDer<'_>],
        _server_name: &rustls::pki_types::ServerName<'_>,
        _ocsp_response: &[u8],
        _now: rustls::pki_types::UnixTime,
    ) -> Result<rustls::client::danger::ServerCertVerified, rustls::Error> {
        Ok(rustls::client::danger::ServerCertVerified::assertion())
    }

    fn verify_tls12_signature(
        &self,
        message: &[u8],
        certificate: &rustls::pki_types::CertificateDer<'_>,
        signature: &rustls::DigitallySignedStruct,
    ) -> Result<rustls::client::danger::HandshakeSignatureValid, rustls::Error> {
        rustls::crypto::verify_tls12_signature(
            message,
            certificate,
            signature,
            &self.0.signature_verification_algorithms,
        )
    }

    fn verify_tls13_signature(
        &self,
        message: &[u8],
        certificate: &rustls::pki_types::CertificateDer<'_>,
        signature: &rustls::DigitallySignedStruct,
    ) -> Result<rustls::client::danger::HandshakeSignatureValid, rustls::Error> {
        rustls::crypto::verify_tls13_signature(
            message,
            certificate,
            signature,
            &self.0.signature_verification_algorithms,
        )
    }

    fn supported_verify_schemes(&self) -> Vec<rustls::SignatureScheme> {
        self.0.signature_verification_algorithms.supported_schemes()
    }
}
