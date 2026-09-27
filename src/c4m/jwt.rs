//! JWS compact 形式の JWT (RFC 7515 §7.1) (`moqt.c4m`)。
//!
//! JWT のヘッダ (JSON) をパースし、署名対象 (`base64url(header).base64url(payload)`)
//! と署名を保持する。ペイロードの解釈は利用側 ([`crate::c4m::dpop`] など) が行う。

use pyo3::prelude::*;

use shiguredo_moqt::c4m::crypto::aws_lc_rs::AwsLcRsCrypto;
use shiguredo_moqt::c4m::jwt::{JwsCompact as MoqtJwsCompact, JwsHeader as MoqtJwsHeader};

use crate::c4m::crypto::CoseKey;
use crate::c4m::jwk::Jwk;
use crate::errors::codec_error;

/// JWS compact のヘッダ (RFC 7515 §4)。
///
/// `alg` は JOSE の名前 (ES256 など) から COSE のアルゴリズムの識別子へ変換して
/// 保持する。`crit` を持つ JWS は、この実装が拡張ヘッダを 1 つも解釈しないため
/// 拒否する (RFC 7515 §4.1.11)。
#[derive(PartialEq)]
#[pyclass(name = "JwsHeader", eq)]
pub(crate) struct JwsHeader {
    inner: MoqtJwsHeader,
}

#[pymethods]
impl JwsHeader {
    /// ヘッダの JSON をデコードする。
    ///
    /// メンバー名が重複している場合と、`crit` を持つ場合は `ValueError` になる。
    #[staticmethod]
    fn decode(text: &str) -> PyResult<Self> {
        MoqtJwsHeader::decode(text)
            .map(|inner| Self { inner })
            .map_err(codec_error)
    }

    /// `alg` を COSE のアルゴリズムの識別子として返す。
    #[getter]
    fn algorithm(&self) -> i64 {
        self.inner.algorithm.identifier()
    }

    /// `typ`。
    #[getter]
    fn typ(&self) -> Option<String> {
        self.inner.typ.clone()
    }

    /// `kid`。
    #[getter]
    fn key_id(&self) -> Option<String> {
        self.inner.key_id.clone()
    }

    /// `jwk` (DPoP proof が埋め込む公開鍵)。
    #[getter]
    fn jwk(&self) -> Option<Jwk> {
        self.inner.jwk.clone().map(Jwk::from_inner)
    }

    fn __repr__(&self) -> String {
        format!(
            "JwsHeader(algorithm={}, typ={}, key_id={})",
            self.inner.algorithm.identifier(),
            match &self.inner.typ {
                Some(typ) => typ.clone(),
                None => String::from("None"),
            },
            match &self.inner.key_id {
                Some(key_id) => key_id.clone(),
                None => String::from("None"),
            }
        )
    }
}

/// JWS compact 形式の JWT (RFC 7515 §7.1)。
///
/// `header.payload.signature` の 3 分割形式を保持する。`signature` は COSE の固定長
/// 形式 (ECDSA は `r || s`、Ed25519 は 64 バイト) である。
#[derive(PartialEq)]
#[pyclass(name = "JwsCompact", eq)]
pub(crate) struct JwsCompact {
    inner: MoqtJwsCompact,
}

#[pymethods]
impl JwsCompact {
    /// `header.payload.signature` の 3 分割形式をデコードする。
    #[staticmethod]
    fn decode(input: &str) -> PyResult<Self> {
        MoqtJwsCompact::decode(input)
            .map(|inner| Self { inner })
            .map_err(codec_error)
    }

    /// ヘッダ。
    #[getter]
    fn header(&self) -> JwsHeader {
        JwsHeader {
            inner: self.inner.header().clone(),
        }
    }

    /// ペイロードの生バイト列。
    #[getter]
    fn payload(&self) -> Vec<u8> {
        self.inner.payload().to_vec()
    }

    /// 署名。
    #[getter]
    fn signature(&self) -> Vec<u8> {
        self.inner.signature().to_vec()
    }

    /// 署名対象のバイト列 (`base64url(header).base64url(payload)`)。
    #[getter]
    fn signing_input(&self) -> Vec<u8> {
        self.inner.signing_input().to_vec()
    }

    /// ヘッダの `alg` と鍵で署名を検証する。
    fn verify(&self, key: &CoseKey) -> PyResult<()> {
        self.inner
            .verify(&AwsLcRsCrypto::new(), &key.inner)
            .map_err(codec_error)
    }

    fn __repr__(&self) -> String {
        format!(
            "JwsCompact(algorithm={}, payload_bytes={}, signature_bytes={})",
            self.inner.header().algorithm.identifier(),
            self.inner.payload().len(),
            self.inner.signature().len()
        )
    }
}
