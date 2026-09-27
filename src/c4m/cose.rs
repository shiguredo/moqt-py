//! COSE (RFC 9052) の構造の codec (`moqt.c4m`)。
//!
//! COSE_Sign1 (タグ 18) と COSE_Mac0 (タグ 17)、および CWT (タグ 61) を扱う。
//! 署名 / 検証の実行は [`crate::c4m::crypto`] が担い、この層は構造の encode /
//! decode と署名対象バイト列の組み立てだけを行う。
//!
//! COSE_Sign1 と COSE_Mac0 は 1 つの [`CoseMessage`] の `kind` で区別する。構築は
//! [`CoseMessage::sign1`] / [`CoseMessage::mac0`] の静的メソッドで行う。

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyString};

use shiguredo_moqt::c4m::cose::{
    C4M_DRAFT_HMAC_SHA256_ALGORITHM_ID, CoseEncodingOptions as MoqtCoseEncodingOptions, CoseMac0,
    CoseMessage as MoqtCoseMessage, CoseSign1, HEADER_ALGORITHM, HEADER_CONTENT_TYPE,
    HEADER_CRITICAL, HEADER_KEY_ID, HEADER_TYPE, Header as MoqtHeader, KeyId, TAG_COSE_MAC0,
    TAG_COSE_SIGN1, TAG_CWT,
};

use crate::c4m::cbor::{self, CborValue};
use crate::c4m::crypto::algorithm_from_identifier;
use crate::errors::codec_error;

/// COSE ヘッダの `kid` を Python の `bytes` / `str` から取り出す。
pub(crate) fn key_id_from_python(value: Option<&Bound<'_, PyAny>>) -> PyResult<Option<KeyId>> {
    let Some(value) = value else {
        return Ok(None);
    };
    if value.is_none() {
        return Ok(None);
    }
    if let Ok(bytes) = value.cast::<PyBytes>() {
        return Ok(Some(KeyId::Bytes(bytes.as_bytes().to_vec())));
    }
    if let Ok(text) = value.cast::<PyString>() {
        return Ok(Some(KeyId::Text(text.to_str()?.to_string())));
    }
    Err(PyValueError::new_err(format!(
        "expected bytes or str for kid, got {}",
        value.get_type().name()?
    )))
}

/// COSE ヘッダの `kid` を Python の値へ変換する。
pub(crate) fn key_id_to_python(py: Python<'_>, key_id: &KeyId) -> Py<PyAny> {
    match key_id {
        KeyId::Bytes(bytes) => PyBytes::new(py, bytes).into_any().unbind(),
        KeyId::Text(text) => PyString::new(py, text).into_any().unbind(),
    }
}

/// COSE の protected / unprotected ヘッダ。
///
/// 解釈しないパラメータは `raw` に保持し、再エンコード時に決定論的な順序で復元する。
/// `crit` のラベルは protected ヘッダに実在し、理解できる必要がある
/// (RFC 9052 §3.1)。
#[derive(PartialEq)]
#[pyclass(name = "CoseHeader", eq)]
pub(crate) struct CoseHeader {
    inner: MoqtHeader,
}

impl CoseHeader {
    /// 内部のヘッダから包む。
    pub(crate) fn from_inner(inner: MoqtHeader) -> Self {
        Self { inner }
    }
}

#[pymethods]
impl CoseHeader {
    /// 空のヘッダを組み立てる。
    #[new]
    fn new() -> Self {
        Self {
            inner: MoqtHeader::default(),
        }
    }

    /// protected ヘッダの CBOR のデータ項目をデコードする。
    #[staticmethod]
    fn decode_protected(value: &Bound<'_, CborValue>) -> PyResult<Self> {
        MoqtHeader::decode_protected(&value.borrow().inner())
            .map(|inner| Self { inner })
            .map_err(codec_error)
    }

    /// unprotected ヘッダの CBOR のデータ項目をデコードする。
    ///
    /// RFC 9052 §3.1 は `crit` を、RFC 9596 §2 は `typ` を unprotected ヘッダに
    /// 置くことを禁止するため、どちらも `ValueError` になる。
    #[staticmethod]
    fn decode_unprotected(value: &Bound<'_, CborValue>) -> PyResult<Self> {
        MoqtHeader::decode_unprotected(&value.borrow().inner())
            .map(|inner| Self { inner })
            .map_err(codec_error)
    }

    /// ヘッダを CBOR のマップへエンコードする。
    fn encode(&self) -> PyResult<CborValue> {
        self.inner.encode().map(cbor::wrap).map_err(codec_error)
    }

    /// アルゴリズム (`alg`)。
    ///
    /// ヘッダに書かれた識別子を解釈した結果であり、生の識別子は
    /// `algorithm_identifier` で参照できる。
    #[getter]
    fn algorithm(&self) -> Option<i64> {
        self.inner.algorithm.map(|algorithm| algorithm.identifier())
    }

    /// アルゴリズム (`alg`) を設定する。
    #[setter]
    fn set_algorithm(&mut self, value: Option<i64>) -> PyResult<()> {
        self.inner.algorithm = match value {
            Some(identifier) => Some(algorithm_from_identifier(identifier)?),
            None => None,
        };
        Ok(())
    }

    /// ヘッダに書かれていたアルゴリズムの生の識別子。
    #[getter]
    fn algorithm_identifier(&self) -> Option<i64> {
        self.inner.algorithm_identifier
    }

    /// ヘッダに書かれていたアルゴリズムの生の識別子を設定する。
    #[setter]
    fn set_algorithm_identifier(&mut self, value: Option<i64>) {
        self.inner.algorithm_identifier = value;
    }

    /// 鍵識別子 (`kid`)。
    ///
    /// RFC 9052 §3.1 はバイト文字列とするが、CAT の実装にはテキスト文字列を使う
    /// ものもあるため、どちらの表記もそのまま保持する。
    #[getter]
    fn key_id(&self, py: Python<'_>) -> Option<Py<PyAny>> {
        self.inner
            .key_id
            .as_ref()
            .map(|key_id| key_id_to_python(py, key_id))
    }

    /// 鍵識別子 (`kid`) を設定する。
    #[setter]
    fn set_key_id(&mut self, value: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        self.inner.key_id = key_id_from_python(value)?;
        Ok(())
    }

    /// 完全な COSE オブジェクトのコンテンツタイプ (`typ`、ラベル 16)。
    #[getter]
    fn typ(&self) -> Option<CborValue> {
        self.inner.typ.clone().map(cbor::wrap)
    }

    /// 完全な COSE オブジェクトのコンテンツタイプ (`typ`) を設定する。
    #[setter]
    fn set_typ(&mut self, value: Option<&Bound<'_, CborValue>>) {
        self.inner.typ = value.map(|value| value.borrow().inner());
    }

    /// ペイロードのコンテンツタイプ (`content type`、ラベル 3)。
    #[getter]
    fn content_type(&self) -> Option<CborValue> {
        self.inner.content_type.clone().map(cbor::wrap)
    }

    /// ペイロードのコンテンツタイプ (`content type`) を設定する。
    #[setter]
    fn set_content_type(&mut self, value: Option<&Bound<'_, CborValue>>) {
        self.inner.content_type = value.map(|value| value.borrow().inner());
    }

    /// 必ず理解しなければならないヘッダパラメータ (`crit`)。
    #[getter]
    fn critical(&self) -> Vec<CborValue> {
        cbor::wrap_all(&self.inner.critical)
    }

    /// 必ず理解しなければならないヘッダパラメータ (`crit`) を設定する。
    #[setter]
    fn set_critical(&mut self, value: Vec<Bound<'_, CborValue>>) {
        self.inner.critical = value.iter().map(|value| value.borrow().inner()).collect();
    }

    /// 解釈しなかったヘッダパラメータ。
    #[getter]
    fn raw(&self) -> Vec<(CborValue, CborValue)> {
        cbor::wrap_entries(&self.inner.raw)
    }

    /// 解釈しなかったヘッダパラメータを設定する。
    #[setter]
    fn set_raw(&mut self, value: Vec<(Bound<'_, CborValue>, Bound<'_, CborValue>)>) {
        self.inner.raw = value
            .iter()
            .map(|(key, value)| (key.borrow().inner(), value.borrow().inner()))
            .collect();
    }

    fn __repr__(&self) -> String {
        format!(
            "CoseHeader(algorithm={}, key_id={})",
            match self.inner.algorithm {
                Some(algorithm) => algorithm.identifier().to_string(),
                None => "None".to_string(),
            },
            match &self.inner.key_id {
                Some(_) => "True",
                None => "False",
            }
        )
    }
}

/// COSE メッセージのエンコードオプション。
///
/// 既定では CWT タグ (61) と COSE タグ (17 / 18) の両方を付与する。付与は
/// 「メッセージがデコード時に持っていたタグ」との OR で決まる。
#[derive(PartialEq)]
#[pyclass(name = "CoseEncodingOptions", eq)]
pub(crate) struct CoseEncodingOptions {
    /// COSE タグ (17 / 18) を付与する。
    #[pyo3(get, set)]
    pub cose_tag: bool,
    /// CWT タグ (61) を付与する。
    #[pyo3(get, set)]
    pub cwt_tag: bool,
}

impl CoseEncodingOptions {
    /// 内部のエンコードオプションへ変換する。
    pub(crate) fn to_inner(&self) -> MoqtCoseEncodingOptions {
        MoqtCoseEncodingOptions {
            cose_tag: self.cose_tag,
            cwt_tag: self.cwt_tag,
        }
    }
}

#[pymethods]
impl CoseEncodingOptions {
    /// CWT タグと COSE タグの付与を指定して組み立てる。
    ///
    /// 既定はどちらも `True` である。
    #[new]
    #[pyo3(signature = (cose_tag = true, cwt_tag = true))]
    fn new(cose_tag: bool, cwt_tag: bool) -> Self {
        Self { cose_tag, cwt_tag }
    }

    fn __repr__(&self) -> String {
        format!(
            "CoseEncodingOptions(cose_tag={}, cwt_tag={})",
            self.cose_tag, self.cwt_tag
        )
    }
}

/// COSE のメッセージ (COSE_Sign1 / COSE_Mac0)。
///
/// `kind` は `sign1` / `mac0` のいずれかである。MAC では `signature` が MAC (tag) を
/// 表す。CWT タグ (61) は COSE のタグ付きオブジェクトにだけ前置できる
/// (RFC 8392 §6)。
#[derive(PartialEq)]
#[pyclass(name = "CoseMessage", eq)]
pub(crate) struct CoseMessage {
    inner: MoqtCoseMessage,
}

#[pymethods]
impl CoseMessage {
    /// CBOR のバイト列からデコードする。
    ///
    /// CWT タグ (61) と COSE タグ (17 / 18) を許容する。タグが無い場合は protected
    /// ヘッダのアルゴリズム種別から COSE_Sign1 / COSE_Mac0 を判別する。
    #[staticmethod]
    fn decode(data: &[u8]) -> PyResult<Self> {
        MoqtCoseMessage::decode(data)
            .map(|inner| Self { inner })
            .map_err(codec_error)
    }

    /// CBOR のデータ項目からデコードする。
    #[staticmethod]
    fn decode_value(value: &Bound<'_, CborValue>) -> PyResult<Self> {
        MoqtCoseMessage::decode_value(&value.borrow().inner())
            .map(|inner| Self { inner })
            .map_err(codec_error)
    }

    /// COSE_Sign1 を組み立てる。
    ///
    /// `payload` を省略すると detached payload を表す。`cose_tagged` / `cwt_tagged` は
    /// デコード時に持っていたタグを再現するために使う。
    #[staticmethod]
    #[pyo3(signature = (protected = None, unprotected = None, payload = None, signature = None, cose_tagged = false, cwt_tagged = false))]
    fn sign1(
        protected: Option<&[u8]>,
        unprotected: Option<Vec<(Bound<'_, CborValue>, Bound<'_, CborValue>)>>,
        payload: Option<&[u8]>,
        signature: Option<&[u8]>,
        cose_tagged: bool,
        cwt_tagged: bool,
    ) -> Self {
        Self {
            inner: MoqtCoseMessage::Sign1(CoseSign1 {
                protected: protected.unwrap_or_default().to_vec(),
                unprotected: to_inner_entries(unprotected),
                payload: payload.map(|payload| payload.to_vec()),
                signature: signature.unwrap_or_default().to_vec(),
                cose_tagged,
                cwt_tagged,
            }),
        }
    }

    /// COSE_Mac0 を組み立てる。
    ///
    /// MAC は `tag` で受ける。`payload` を省略すると detached payload を表す。
    #[staticmethod]
    #[pyo3(signature = (protected = None, unprotected = None, payload = None, tag = None, cose_tagged = false, cwt_tagged = false))]
    fn mac0(
        protected: Option<&[u8]>,
        unprotected: Option<Vec<(Bound<'_, CborValue>, Bound<'_, CborValue>)>>,
        payload: Option<&[u8]>,
        tag: Option<&[u8]>,
        cose_tagged: bool,
        cwt_tagged: bool,
    ) -> Self {
        Self {
            inner: MoqtCoseMessage::Mac0(CoseMac0 {
                protected: protected.unwrap_or_default().to_vec(),
                unprotected: to_inner_entries(unprotected),
                payload: payload.map(|payload| payload.to_vec()),
                tag: tag.unwrap_or_default().to_vec(),
                cose_tagged,
                cwt_tagged,
            }),
        }
    }

    /// メッセージの種別を表す文字列。
    ///
    /// `sign1` / `mac0` のいずれかである。
    #[getter]
    fn kind(&self) -> &'static str {
        match self.inner {
            MoqtCoseMessage::Sign1(_) => "sign1",
            MoqtCoseMessage::Mac0(_) => "mac0",
        }
    }

    /// protected ヘッダの CBOR バイト列 (bstr の中身)。
    #[getter]
    fn protected(&self) -> Vec<u8> {
        match &self.inner {
            MoqtCoseMessage::Sign1(message) => message.protected.clone(),
            MoqtCoseMessage::Mac0(message) => message.protected.clone(),
        }
    }

    /// unprotected ヘッダのマップ。
    #[getter]
    fn unprotected(&self) -> Vec<(CborValue, CborValue)> {
        match &self.inner {
            MoqtCoseMessage::Sign1(message) => cbor::wrap_entries(&message.unprotected),
            MoqtCoseMessage::Mac0(message) => cbor::wrap_entries(&message.unprotected),
        }
    }

    /// ペイロード。`None` は detached payload を表す。
    #[getter]
    fn payload(&self) -> Option<Vec<u8>> {
        self.inner.payload().map(|payload| payload.to_vec())
    }

    /// 署名または MAC。
    #[getter]
    fn signature(&self) -> Vec<u8> {
        self.inner.signature().to_vec()
    }

    /// COSE タグ (17 / 18) が付いていたかどうか。
    #[getter]
    fn cose_tagged(&self) -> bool {
        match &self.inner {
            MoqtCoseMessage::Sign1(message) => message.cose_tagged,
            MoqtCoseMessage::Mac0(message) => message.cose_tagged,
        }
    }

    /// CWT タグ (61) が付いていたかどうか。
    #[getter]
    fn cwt_tagged(&self) -> bool {
        match &self.inner {
            MoqtCoseMessage::Sign1(message) => message.cwt_tagged,
            MoqtCoseMessage::Mac0(message) => message.cwt_tagged,
        }
    }

    /// protected / unprotected を統合したヘッダを返す。
    ///
    /// `alg` は protected ヘッダに必須であり、同じラベルが両方のバケットにある場合は
    /// `ValueError` になる。
    fn header(&self) -> PyResult<CoseHeader> {
        self.inner
            .header()
            .map(|inner| CoseHeader { inner })
            .map_err(codec_error)
    }

    /// 署名 / MAC の対象バイト列を組み立てる。
    ///
    /// COSE_Sign1 は `Sig_structure`、COSE_Mac0 は `MAC_structure` を返す
    /// (RFC 9052 §4.4 / §6.3)。external_aad は空のバイト文字列である。detached
    /// payload は扱わないため、その場合は `ValueError` になる。
    fn signing_input(&self) -> PyResult<Vec<u8>> {
        self.inner.signing_input().map_err(codec_error)
    }

    /// COSE メッセージをエンコードする。
    ///
    /// タグの付与はデコード時に持っていたタグと `options` の OR で決まる。CWT タグを
    /// 付ける場合は COSE タグも必要になる (RFC 8392 §6)。
    #[pyo3(signature = (options = None))]
    fn encode(&self, options: Option<&CoseEncodingOptions>) -> PyResult<Vec<u8>> {
        let options = options.map_or_else(Default::default, CoseEncodingOptions::to_inner);
        self.inner.encode(&options).map_err(codec_error)
    }

    fn __repr__(&self) -> String {
        format!(
            "CoseMessage(kind={}, payload_bytes={}, signature_bytes={})",
            match self.inner {
                MoqtCoseMessage::Sign1(_) => "sign1",
                MoqtCoseMessage::Mac0(_) => "mac0",
            },
            match self.inner.payload() {
                Some(payload) => payload.len().to_string(),
                None => "None".to_string(),
            },
            self.inner.signature().len()
        )
    }
}

/// Python の (キー, 値) の組の列を Rust のマップの列へ変換する。
fn to_inner_entries(
    entries: Option<Vec<(Bound<'_, CborValue>, Bound<'_, CborValue>)>>,
) -> Vec<(
    shiguredo_moqt::c4m::cbor::Value,
    shiguredo_moqt::c4m::cbor::Value,
)> {
    entries
        .unwrap_or_default()
        .iter()
        .map(|(key, value)| (key.borrow().inner(), value.borrow().inner()))
        .collect()
}

/// COSE の定数をモジュールへ登録する。
pub(crate) fn register_constants(module: &Bound<'_, PyModule>) -> PyResult<()> {
    // CBOR タグ (RFC 8392 §6 / RFC 9052 §4.2 / §6.2)
    module.add("TAG_CWT", TAG_CWT)?;
    module.add("TAG_COSE_MAC0", TAG_COSE_MAC0)?;
    module.add("TAG_COSE_SIGN1", TAG_COSE_SIGN1)?;

    // ヘッダパラメータ (RFC 9052 §3.1 / RFC 9596 §2)
    module.add("HEADER_ALGORITHM", HEADER_ALGORITHM)?;
    module.add("HEADER_CRITICAL", HEADER_CRITICAL)?;
    module.add("HEADER_CONTENT_TYPE", HEADER_CONTENT_TYPE)?;
    module.add("HEADER_KEY_ID", HEADER_KEY_ID)?;
    module.add("HEADER_TYPE", HEADER_TYPE)?;

    // ドラフトのテストベクタが HMAC-SHA256 に使う識別子
    // (検証では受理し、発行では使わない)
    module.add(
        "C4M_DRAFT_HMAC_SHA256_ALGORITHM_ID",
        C4M_DRAFT_HMAC_SHA256_ALGORITHM_ID,
    )?;
    Ok(())
}
