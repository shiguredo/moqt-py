//! TLS (rustls) の設定。
//!
//! QUIC / WebTransport over HTTP/3 / WebTransport over HTTP/2 / QMux が共有する。
//! 証明書の読み込みと ALPN の設定だけを担い、接続方式による違いは ALPN だけである。

use std::sync::Arc;

use rustls_pki_types::CertificateDer;
use rustls_pki_types::PrivateKeyDer;
use rustls_pki_types::pem::PemObject;
use rustls_platform_verifier::Verifier;

use crate::io::client::ClientConfig;
use crate::io::command::IoError;

/// CA 証明書ファイルを読み、追加で信頼するルート証明書を返す。
fn read_extra_roots(path: &str) -> Result<Vec<CertificateDer<'static>>, IoError> {
    let iterator = CertificateDer::pem_file_iter(path).map_err(|error| {
        IoError::connection(format!(
            "failed to open the CA certificate file '{path}': {error}"
        ))
    })?;
    let mut roots = Vec::new();
    for certificate in iterator {
        roots.push(certificate.map_err(|error| {
            IoError::connection(format!(
                "failed to read the CA certificate file '{path}': {error}"
            ))
        })?);
    }
    Ok(roots)
}

/// クライアント TLS 設定を作る。
///
/// `verify_peer` が偽の場合は証明書の検証を無効にする。真の場合は OS の
/// 証明書ストアを使い、`ca_file` を指定した場合はその証明書も追加で信頼する。
/// ALPN は `config.alpn` を使う。
pub(crate) fn build_client_tls(
    config: &ClientConfig,
) -> Result<Arc<rustls::ClientConfig>, IoError> {
    let mut tls = if config.verify_peer {
        let extra_roots = match &config.ca_file {
            Some(path) => read_extra_roots(path)?,
            None => Vec::new(),
        };
        // OS の証明書ストアと失効確認を使う。Linux では rustls-native-certs で
        // システムの CA バンドルを読み込む。
        let verifier = Verifier::new_with_extra_roots(
            extra_roots,
            Arc::new(rustls::crypto::aws_lc_rs::default_provider()),
        )
        .map_err(|error| {
            IoError::connection(format!(
                "failed to build the platform certificate verifier: {error}"
            ))
        })?;
        rustls::ClientConfig::builder()
            .dangerous()
            .with_custom_certificate_verifier(Arc::new(verifier))
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
    let certificates = CertificateDer::pem_file_iter(certfile)
        .map_err(|error| {
            IoError::runtime(format!(
                "failed to open the certificate file '{}': {error}",
                certfile
            ))
        })?
        .collect::<Result<Vec<_>, _>>()
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
    let key = PrivateKeyDer::from_pem_file(keyfile).map_err(|error| {
        IoError::runtime(format!(
            "failed to read the private key file '{}': {error}",
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
