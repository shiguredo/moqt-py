//! COSE / JWT の署名と検証 (`moqt.c4m`)。
//!
//! 鍵表現 ([`CoseKey`]) と、aws-lc-rs を使う署名 / 検証 / ハッシュを公開する。
//! moqt-rs の `CoseCrypto` trait は Python へ公開しない。暗号実装は aws-lc-rs に
//! 固定しており、trait の抽象を持ち込む必要が無いためである。
//!
//! このモジュールは乱数も時計も持たない。署名に必要な乱数は aws-lc-rs が内部で取得し、
//! 時刻は検証 API の引数で渡す。

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use shiguredo_moqt::c4m::cose::Algorithm;
use shiguredo_moqt::c4m::crypto::aws_lc_rs::AwsLcRsCrypto;
use shiguredo_moqt::c4m::crypto::{
    CoseCrypto, CoseKey as MoqtCoseKey, DigestAlgorithm, EcCurve, default_signing_algorithm,
};

use crate::errors::codec_error;

/// 楕円曲線の識別子 (RFC 9053 §7) から曲線を返す。
pub(crate) fn ec_curve_from_identifier(identifier: i64) -> PyResult<EcCurve> {
    match identifier {
        1 => Ok(EcCurve::P256),
        2 => Ok(EcCurve::P384),
        3 => Ok(EcCurve::P521),
        other => Err(PyValueError::new_err(format!(
            "unsupported EC curve identifier: {other}"
        ))),
    }
}

/// COSE のアルゴリズム識別子からアルゴリズムを返す。
///
/// draft-ietf-moq-c4m-01 付録 A のベクタが HMAC-SHA256 に使う `-4` も受理する。
pub(crate) fn algorithm_from_identifier(identifier: i64) -> PyResult<Algorithm> {
    Algorithm::from_identifier_with_c4m_draft_alias(identifier)
        .ok_or_else(|| PyValueError::new_err(format!("unsupported COSE algorithm: {identifier}")))
}

/// COSE Key (RFC 9052 §7) と JWK (RFC 7517) を共通に扱う鍵表現。
///
/// `kind` は `symmetric` / `ec2` / `okp` のいずれかである。秘密鍵は署名にだけ使い、
/// 検証では公開鍵の部分だけを参照する。`repr` は秘密鍵の値を伏せ、長さだけを表示する。
#[derive(PartialEq)]
#[pyclass(name = "CoseKey", eq)]
pub(crate) struct CoseKey {
    pub(crate) inner: MoqtCoseKey,
}

#[pymethods]
impl CoseKey {
    /// 対称鍵 (`kty` = Symmetric) を組み立てる。
    #[staticmethod]
    fn symmetric(key: &[u8]) -> Self {
        Self {
            inner: MoqtCoseKey::symmetric(key.to_vec()),
        }
    }

    /// 公開鍵だけの EC2 鍵 (`kty` = EC2) を組み立てる。
    ///
    /// `curve` は COSE の `crv` の識別子 (P-256 = 1 / P-384 = 2 / P-521 = 3) である。
    /// `x` / `y` はビッグエンディアンの固定長の座標である。
    #[staticmethod]
    fn ec2(curve: i64, x: &[u8], y: &[u8]) -> PyResult<Self> {
        Ok(Self {
            inner: MoqtCoseKey::ec2(ec_curve_from_identifier(curve)?, x.to_vec(), y.to_vec()),
        })
    }

    /// 秘密鍵付きの EC2 鍵を組み立てる。
    ///
    /// `private_key` はビッグエンディアンの固定長のスカラーである。
    #[staticmethod]
    fn ec2_with_private_key(curve: i64, x: &[u8], y: &[u8], private_key: &[u8]) -> PyResult<Self> {
        Ok(Self {
            inner: MoqtCoseKey::ec2_with_private_key(
                ec_curve_from_identifier(curve)?,
                x.to_vec(),
                y.to_vec(),
                private_key.to_vec(),
            ),
        })
    }

    /// 公開鍵だけの Ed25519 鍵 (`kty` = OKP) を組み立てる。
    #[staticmethod]
    fn ed25519(public_key: &[u8]) -> Self {
        Self {
            inner: MoqtCoseKey::ed25519(public_key.to_vec()),
        }
    }

    /// 秘密鍵付きの Ed25519 鍵を組み立てる。
    ///
    /// `private_key` は Ed25519 の種 (32 バイト) である。
    #[staticmethod]
    fn ed25519_with_private_key(public_key: &[u8], private_key: &[u8]) -> Self {
        Self {
            inner: MoqtCoseKey::ed25519_with_private_key(public_key.to_vec(), private_key.to_vec()),
        }
    }

    /// 鍵の種別を表す文字列。
    #[getter]
    fn kind(&self) -> &'static str {
        match self.inner {
            MoqtCoseKey::Symmetric { .. } => "symmetric",
            MoqtCoseKey::Ec2 { .. } => "ec2",
            MoqtCoseKey::Okp { .. } => "okp",
        }
    }

    /// 対称鍵のバイト列。
    #[getter]
    fn key(&self) -> Option<Vec<u8>> {
        match &self.inner {
            MoqtCoseKey::Symmetric { key } => Some(key.clone()),
            _ => None,
        }
    }

    /// EC2 鍵の曲線の識別子。
    #[getter]
    fn curve(&self) -> Option<i64> {
        match &self.inner {
            MoqtCoseKey::Ec2 { curve, .. } => Some(curve.identifier()),
            _ => None,
        }
    }

    /// EC2 鍵の x 座標 (ビッグエンディアンの固定長)。
    #[getter]
    fn x(&self) -> Option<Vec<u8>> {
        match &self.inner {
            MoqtCoseKey::Ec2 { x, .. } => Some(x.clone()),
            _ => None,
        }
    }

    /// EC2 鍵の y 座標 (ビッグエンディアンの固定長)。
    #[getter]
    fn y(&self) -> Option<Vec<u8>> {
        match &self.inner {
            MoqtCoseKey::Ec2 { y, .. } => Some(y.clone()),
            _ => None,
        }
    }

    /// 秘密鍵 (EC2 のスカラー / Ed25519 の種)。
    #[getter]
    fn private_key(&self) -> Option<Vec<u8>> {
        match &self.inner {
            MoqtCoseKey::Ec2 { private_key, .. } | MoqtCoseKey::Okp { private_key, .. } => {
                private_key.clone()
            }
            MoqtCoseKey::Symmetric { .. } => None,
        }
    }

    /// OKP 鍵の公開鍵。
    #[getter]
    fn public_key(&self) -> Option<Vec<u8>> {
        match &self.inner {
            MoqtCoseKey::Okp { public_key, .. } => Some(public_key.clone()),
            _ => None,
        }
    }

    fn __repr__(&self) -> String {
        match &self.inner {
            MoqtCoseKey::Symmetric { key } => {
                format!("CoseKey(kind=symmetric, key_bytes={})", key.len())
            }
            MoqtCoseKey::Ec2 {
                curve, private_key, ..
            } => format!(
                "CoseKey(kind=ec2, curve={}, private_key_bytes={})",
                curve.identifier(),
                match private_key {
                    Some(private_key) => private_key.len().to_string(),
                    None => "None".to_string(),
                }
            ),
            MoqtCoseKey::Okp {
                curve, private_key, ..
            } => format!(
                "CoseKey(kind=okp, curve={}, private_key_bytes={})",
                curve.identifier(),
                match private_key {
                    Some(private_key) => private_key.len().to_string(),
                    None => "None".to_string(),
                }
            ),
        }
    }
}

/// メッセージに署名または MAC を付ける。
///
/// 対称鍵の場合は MAC を返す。EC2 / OKP の場合は COSE の固定長形式 (ECDSA は
/// `r || s`) の署名を返す。`algorithm` は COSE のアルゴリズム識別子であり、
/// draft-ietf-moq-c4m-01 付録 A のベクタが HMAC-SHA256 に使う `-4` も受理する。
///
/// 対応するアルゴリズムは HMAC 256/384/512、ES256/384/512、EdDSA (Ed25519) である。
#[pyfunction]
pub(crate) fn sign(algorithm: i64, key: &CoseKey, message: &[u8]) -> PyResult<Vec<u8>> {
    let algorithm = algorithm_from_identifier(algorithm)?;
    AwsLcRsCrypto::new()
        .sign(algorithm, &key.inner, message)
        .map_err(codec_error)
}

/// 署名または MAC を検証する。
///
/// 検証に失敗した場合は `ValueError` になる。埋め込みの JWK を検証する場合は
/// [`crate::c4m::jwk::Jwk::to_cose_key`] で公開鍵へ変換して渡す。
#[pyfunction]
pub(crate) fn verify(
    algorithm: i64,
    key: &CoseKey,
    message: &[u8],
    signature: &[u8],
) -> PyResult<()> {
    let algorithm = algorithm_from_identifier(algorithm)?;
    AwsLcRsCrypto::new()
        .verify(algorithm, &key.inner, message, signature)
        .map_err(codec_error)
}

/// メッセージのハッシュを計算する。
///
/// `algorithm` は `sha256` / `sha384` / `sha512` のいずれかである。JWK サムプリント
/// (RFC 7638) など、署名以外でハッシュが必要な処理に使う。
#[pyfunction]
pub(crate) fn digest(algorithm: &str, message: &[u8]) -> PyResult<Vec<u8>> {
    let algorithm = match algorithm {
        "sha256" => DigestAlgorithm::Sha256,
        "sha384" => DigestAlgorithm::Sha384,
        "sha512" => DigestAlgorithm::Sha512,
        other => {
            return Err(PyValueError::new_err(format!(
                "unknown digest algorithm '{other}': expected sha256 / sha384 / sha512"
            )));
        }
    };
    AwsLcRsCrypto::new()
        .digest(algorithm, message)
        .map_err(codec_error)
}

/// 鍵の種別から既定の署名アルゴリズムの識別子を返す。
///
/// 対称鍵は HMAC-SHA256、EC2 は曲線に対応する ES256 / ES384 / ES512、OKP は
/// EdDSA になる。
#[pyfunction]
#[pyo3(name = "default_signing_algorithm")]
pub(crate) fn default_signing_algorithm_id(key: &CoseKey) -> i64 {
    default_signing_algorithm(&key.inner).identifier()
}
