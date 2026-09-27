//! C4M (Common Access Token for MoQ) の codec (`moqt.c4m`)。
//!
//! draft-ietf-moq-c4m-01 の `moqt` / `moqt-reval` クレームと、その基盤となる
//! CBOR (RFC 8949) / COSE (RFC 9052) / CWT (RFC 8392) / CAT (CTA-5007-B) の
//! トークンを Python から扱う。JWK (RFC 7517) / JWS compact (RFC 7515) /
//! DPoP proof (draft-nandakumar-moq-generic-dpop-proof-00) も公開する。
//!
//! - [`cbor`]: CBOR のコーデック
//! - [`cose`]: COSE の構造とアルゴリズム
//! - [`crypto`]: 鍵表現と aws-lc-rs による署名 / 検証
//! - [`cat`]: CAT のクレームとトークンの発行 / 検証
//! - [`jwk`] / [`jwt`] / [`dpop`]: JWK / JWS compact / DPoP proof
//!
//! 署名 / 検証の暗号実装は aws-lc-rs に固定する。moqt-rs の `CoseCrypto` trait は
//! Python へ公開せず、[`crypto::sign`] / [`crypto::verify`] / [`crypto::digest`] が
//! aws-lc-rs の実装を直接呼ぶ。
//!
//! Rust の enum のうち値が整数であるもの ([`shiguredo_moqt::c4m::MoqtAction`] /
//! [`shiguredo_moqt::c4m::cose::Algorithm`] / [`shiguredo_moqt::c4m::crypto::EcCurve`] /
//! [`shiguredo_moqt::c4m::crypto::OkpCurve`]) は、Python 側の `moqt.c4m` が
//! `enum.IntEnum` として公開する。この層は整数の識別子を受け渡しする。
//!
//! C4M は draft 由来であり、将来の改訂で変更される可能性がある。

pub(crate) mod cat;
pub(crate) mod cbor;
pub(crate) mod claims;
pub(crate) mod cose;
pub(crate) mod crypto;
pub(crate) mod dpop;
pub(crate) mod jwk;
pub(crate) mod jwt;

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyString};

/// bytes または str をバイト列として取り出す。
///
/// compact 形式のトークンは ASCII の str、COSE 形式のトークンは CBOR の bytes で
/// 現れる。どちらの表記でも受けられるようにする。
pub(crate) fn bytes_or_text(value: &Bound<'_, PyAny>) -> PyResult<Vec<u8>> {
    if let Ok(bytes) = value.cast::<PyBytes>() {
        Ok(bytes.as_bytes().to_vec())
    } else if let Ok(text) = value.cast::<PyString>() {
        Ok(text.to_str()?.as_bytes().to_vec())
    } else {
        Err(PyValueError::new_err(format!(
            "expected bytes or str, got {}",
            value.get_type().name()?
        )))
    }
}

/// Track Namespace のフィールド列を借用の参照列へ変換する。
///
/// [`shiguredo_moqt::c4m::MoqtClaim::authorize`] と
/// [`shiguredo_moqt::c4m::MoqtScope::allows`] はマッチの対象を借用の参照列で受ける。
pub(crate) fn namespace_refs(namespace: &[Vec<u8>]) -> Vec<&[u8]> {
    namespace.iter().map(|field| field.as_slice()).collect()
}

/// モジュール定数を登録する。
pub(crate) fn register_constants(module: &Bound<'_, PyModule>) -> PyResult<()> {
    cbor::register_constants(module)?;
    claims::register_constants(module)?;
    cose::register_constants(module)?;
    cat::register_constants(module)?;
    dpop::register_constants(module)?;
    Ok(())
}
