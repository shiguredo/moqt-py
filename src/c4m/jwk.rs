//! JWK (RFC 7517) と JWK サムプリント (RFC 7638) (`moqt.c4m`)。
//!
//! DPoP proof の JWT ヘッダに埋め込まれる公開鍵を扱う。JWK サムプリントは
//! RFC 7638 §3.2 の正規化 JSON (必須メンバーを辞書順に並べ、空白を入れない) に
//! 対する SHA-256 である。
//!
//! 秘密鍵のメンバー (`d` / `p` / `q` / `k` など) を持つ JWK は拒否する
//! (RFC 9449 §4.3)。

use pyo3::prelude::*;

use shiguredo_moqt::c4m::crypto::aws_lc_rs::AwsLcRsCrypto;
use shiguredo_moqt::c4m::jwk::Jwk as MoqtJwk;

use crate::c4m::crypto::CoseKey;
use crate::errors::codec_error;

/// JWK (RFC 7517 §4)。
///
/// `kty` は `EC` / `OKP` / `RSA` のいずれかである。`x` / `y` / `n` / `e` は
/// base64url (パディング無し) の文字列として保持し、デコード時に正規化しない。
#[derive(PartialEq)]
#[pyclass(name = "Jwk", eq)]
pub(crate) struct Jwk {
    inner: MoqtJwk,
}

impl Jwk {
    /// 内部の JWK から包む。
    pub(crate) fn from_inner(inner: MoqtJwk) -> Self {
        Self { inner }
    }

    /// 内部の JWK を複製して返す。
    pub(crate) fn inner(&self) -> MoqtJwk {
        self.inner.clone()
    }
}

#[pymethods]
impl Jwk {
    /// JWK の JSON をデコードする。
    ///
    /// メンバー名が重複している場合と、秘密鍵のメンバーを含む場合は `ValueError` に
    /// なる (RFC 7517 §4 / RFC 9449 §4.3)。
    #[staticmethod]
    fn decode(text: &str) -> PyResult<Self> {
        MoqtJwk::decode(text)
            .map(Self::from_inner)
            .map_err(codec_error)
    }

    /// EC 公開鍵 (`kty` = "EC") を組み立てる。
    ///
    /// `curve` は `P-256` / `P-384` / `P-521`、`x` / `y` は base64url の文字列である。
    #[staticmethod]
    fn ec(curve: String, x: String, y: String) -> Self {
        Self::from_inner(MoqtJwk::Ec { curve, x, y })
    }

    /// OKP 公開鍵 (`kty` = "OKP") を組み立てる。
    ///
    /// `curve` は `Ed25519`、`x` は base64url の文字列である。
    #[staticmethod]
    fn okp(curve: String, x: String) -> Self {
        Self::from_inner(MoqtJwk::Okp { curve, x })
    }

    /// RSA 公開鍵 (`kty` = "RSA") を組み立てる。
    ///
    /// `n` / `e` は base64url の文字列である。RSA は COSE の鍵表現を持たないため、
    /// `to_cose_key` は `ValueError` になる。
    #[staticmethod]
    fn rsa(n: String, e: String) -> Self {
        Self::from_inner(MoqtJwk::Rsa { n, e })
    }

    /// `kty` を返す。
    #[getter]
    fn kty(&self) -> &'static str {
        match self.inner {
            MoqtJwk::Ec { .. } => "EC",
            MoqtJwk::Okp { .. } => "OKP",
            MoqtJwk::Rsa { .. } => "RSA",
        }
    }

    /// `crv` を返す。`kty` が `RSA` の場合は `None` になる。
    #[getter]
    fn curve(&self) -> Option<String> {
        match &self.inner {
            MoqtJwk::Ec { curve, .. } | MoqtJwk::Okp { curve, .. } => Some(curve.clone()),
            MoqtJwk::Rsa { .. } => None,
        }
    }

    /// `x` を返す。`kty` が `RSA` の場合は `None` になる。
    #[getter]
    fn x(&self) -> Option<String> {
        match &self.inner {
            MoqtJwk::Ec { x, .. } | MoqtJwk::Okp { x, .. } => Some(x.clone()),
            MoqtJwk::Rsa { .. } => None,
        }
    }

    /// `y` を返す。`kty` が `EC` 以外の場合は `None` になる。
    #[getter]
    fn y(&self) -> Option<String> {
        match &self.inner {
            MoqtJwk::Ec { y, .. } => Some(y.clone()),
            _ => None,
        }
    }

    /// `n` を返す。`kty` が `RSA` 以外の場合は `None` になる。
    #[getter]
    fn n(&self) -> Option<String> {
        match &self.inner {
            MoqtJwk::Rsa { n, .. } => Some(n.clone()),
            _ => None,
        }
    }

    /// `e` を返す。`kty` が `RSA` 以外の場合は `None` になる。
    #[getter]
    fn e(&self) -> Option<String> {
        match &self.inner {
            MoqtJwk::Rsa { e, .. } => Some(e.clone()),
            _ => None,
        }
    }

    /// 公開鍵を [`CoseKey`] へ変換する。
    ///
    /// `kty` が `RSA` の場合は [`CoseKey`] が表現を持たないため `ValueError` に
    /// なる。
    fn to_cose_key(&self) -> PyResult<CoseKey> {
        self.inner
            .to_cose_key()
            .map(|inner| CoseKey { inner })
            .map_err(codec_error)
    }

    /// 指定した鍵と同じ公開鍵を表すかどうかを返す。
    ///
    /// DPoP proof を発行するときに、埋め込む JWK と署名鍵の食い違いを検出するために
    /// 使う。`kty` が `RSA` の場合は `ValueError` になる。
    fn matches_public_key(&self, key: &CoseKey) -> PyResult<bool> {
        self.inner
            .matches_public_key(&key.inner)
            .map_err(codec_error)
    }

    /// RFC 7638 §3.2 の正規化 JSON を返す。
    ///
    /// 必須メンバーを辞書順に並べ、空白を入れない。base64url の値はパディング無しに
    /// 正規化する。
    fn canonical_json(&self) -> PyResult<String> {
        self.inner.canonical_json().map_err(codec_error)
    }

    /// JWK サムプリント (RFC 7638) の SHA-256 を計算する。
    fn thumbprint_sha256(&self) -> PyResult<Vec<u8>> {
        self.inner
            .thumbprint_sha256(&AwsLcRsCrypto::new())
            .map_err(codec_error)
    }

    fn __repr__(&self) -> String {
        format!(
            "Jwk(kty={}, curve={})",
            self.kty(),
            match self.curve() {
                Some(curve) => curve,
                None => String::from("None"),
            }
        )
    }
}
