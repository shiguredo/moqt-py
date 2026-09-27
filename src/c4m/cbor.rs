//! CBOR (RFC 8949) の codec (`moqt.c4m`)。
//!
//! CWT / COSE / CAT が必要とする範囲の CBOR を encode / decode する。encode は
//! RFC 8949 §4.2 の決定論的エンコードに従い、decode は definite / indefinite の
//! 両方の長さ表現を受理する。
//!
//! Rust 側の `Value` は variant ごとに Python のクラスへ分けず、1 つの
//! [`CborValue`] の `kind` で区別する。構築は静的メソッドで行う。

use pyo3::prelude::*;

use shiguredo_moqt::c4m::cbor::{self, MAX_DEPTH, Value};

use crate::errors::codec_error;

/// CBOR のデータ項目 (RFC 8949 §3)。
///
/// variant は `kind` で区別する。`kind` は `unsigned` / `negative` / `byte_string` /
/// `text_string` / `array` / `map` / `tag` / `bool` / `null` / `undefined` / `float` /
/// `simple` のいずれかである。
///
/// デコードで得た値も、静的メソッドで組み立てた値も同じクラスで表す。値は不変であり、
/// 組み立てた後の書き換えはできない。
#[derive(PartialEq)]
#[pyclass(name = "CborValue", eq)]
pub(crate) struct CborValue {
    pub(crate) inner: Value,
}

/// Rust 側のデータ項目を Python の [`CborValue`] へ包む。
pub(crate) fn wrap(inner: Value) -> CborValue {
    CborValue { inner }
}

/// Rust 側のデータ項目の列を Python の [`CborValue`] の列へ変換する。
pub(crate) fn wrap_all(values: &[Value]) -> Vec<CborValue> {
    values.iter().cloned().map(wrap).collect()
}

/// Rust 側のマップの列を Python の [`CborValue`] の組の列へ変換する。
pub(crate) fn wrap_entries(entries: &[(Value, Value)]) -> Vec<(CborValue, CborValue)> {
    entries
        .iter()
        .map(|(key, value)| (wrap(key.clone()), wrap(value.clone())))
        .collect()
}

impl CborValue {
    /// 内部のデータ項目を複製して返す。
    pub(crate) fn inner(&self) -> Value {
        self.inner.clone()
    }
}

#[pymethods]
impl CborValue {
    /// 符号なし整数 (major type 0) を組み立てる。
    #[staticmethod]
    fn unsigned(value: u64) -> Self {
        wrap(Value::Unsigned(value))
    }

    /// 負の整数 (major type 1) を組み立てる。
    ///
    /// 引数はエンコードされた大きさであり、表す値は `-1 - value` である
    /// (RFC 8949 §3.1)。通常は [`CborValue::integer`] を使う。
    #[staticmethod]
    fn negative(value: u64) -> Self {
        wrap(Value::Negative(value))
    }

    /// `int` を整数のデータ項目 (major type 0 / 1) として組み立てる。
    ///
    /// 負の値は major type 1 になる。
    #[staticmethod]
    fn integer(value: i64) -> Self {
        wrap(Value::integer(value))
    }

    /// バイト文字列 (major type 2) を組み立てる。
    #[staticmethod]
    fn byte_string(value: &[u8]) -> Self {
        wrap(Value::ByteString(value.to_vec()))
    }

    /// テキスト文字列 (major type 3) を組み立てる。
    #[staticmethod]
    fn text_string(value: String) -> Self {
        wrap(Value::TextString(value))
    }

    /// 配列 (major type 4) を組み立てる。
    #[staticmethod]
    fn array(values: Vec<Bound<'_, CborValue>>) -> Self {
        wrap(Value::Array(
            values.iter().map(|value| value.borrow().inner()).collect(),
        ))
    }

    /// マップ (major type 5) を組み立てる。
    #[staticmethod]
    fn map(entries: Vec<(Bound<'_, CborValue>, Bound<'_, CborValue>)>) -> Self {
        wrap(Value::Map(
            entries
                .iter()
                .map(|(key, value)| (key.borrow().inner(), value.borrow().inner()))
                .collect(),
        ))
    }

    /// タグ付きデータ項目 (major type 6) を組み立てる。
    #[staticmethod]
    fn tag(tag: u64, value: &Bound<'_, CborValue>) -> Self {
        wrap(Value::Tag(tag, Box::new(value.borrow().inner())))
    }

    /// 真偽値 (major type 7 の 20 / 21) を組み立てる。
    #[staticmethod]
    fn boolean(value: bool) -> Self {
        wrap(Value::Bool(value))
    }

    /// null (major type 7 の 22) を組み立てる。
    #[staticmethod]
    fn null() -> Self {
        wrap(Value::Null)
    }

    /// undefined (major type 7 の 23) を組み立てる。
    #[staticmethod]
    fn undefined() -> Self {
        wrap(Value::Undefined)
    }

    /// 浮動小数点数 (major type 7 の 25 / 26 / 27) を組み立てる。
    #[staticmethod]
    fn float_value(value: f64) -> Self {
        wrap(Value::Float(value))
    }

    /// 上記以外の単純値 (major type 7 の 0 〜 19 と 32 〜 255) を組み立てる。
    #[staticmethod]
    fn simple(value: u8) -> Self {
        wrap(Value::Simple(value))
    }

    /// variant を表す文字列。
    #[getter]
    fn kind(&self) -> &'static str {
        match self.inner {
            Value::Unsigned(_) => "unsigned",
            Value::Negative(_) => "negative",
            Value::ByteString(_) => "byte_string",
            Value::TextString(_) => "text_string",
            Value::Array(_) => "array",
            Value::Map(_) => "map",
            Value::Tag(_, _) => "tag",
            Value::Bool(_) => "bool",
            Value::Null => "null",
            Value::Undefined => "undefined",
            Value::Float(_) => "float",
            Value::Simple(_) => "simple",
        }
    }

    /// 符号なし整数として取り出す。
    fn as_unsigned(&self) -> Option<u64> {
        self.inner.as_unsigned()
    }

    /// `int` の範囲に収まる整数として取り出す。
    fn as_int(&self) -> Option<i64> {
        self.inner.as_int()
    }

    /// 整数または浮動小数点数の数値として取り出す。
    ///
    /// 負の整数は 1 回だけ丸めて `float` へ変換する (2 段階の丸めで 2^53 を超える値が
    /// ずれないようにするため)。
    fn as_number(&self) -> Option<f64> {
        self.inner.as_number()
    }

    /// バイト文字列として取り出す。
    fn as_bytes(&self) -> Option<Vec<u8>> {
        self.inner.as_bytes().map(|bytes| bytes.to_vec())
    }

    /// テキスト文字列として取り出す。
    fn as_text(&self) -> Option<String> {
        self.inner.as_text().map(String::from)
    }

    /// 配列として取り出す。
    fn as_array(&self) -> Option<Vec<CborValue>> {
        self.inner.as_array().map(wrap_all)
    }

    /// マップとして取り出す。
    ///
    /// デコードでは入力の順序、encode 後の wire では決定論的な順序になる。
    fn as_map(&self) -> Option<Vec<(CborValue, CborValue)>> {
        self.inner.as_map().map(wrap_entries)
    }

    /// 真偽値として取り出す。
    fn as_bool(&self) -> Option<bool> {
        self.inner.as_bool()
    }

    /// タグ付きデータ項目の `(タグ, 値)` として取り出す。
    fn as_tag(&self) -> Option<(u64, CborValue)> {
        match &self.inner {
            Value::Tag(tag, value) => Some((*tag, wrap((**value).clone()))),
            _ => None,
        }
    }

    /// 単純値として取り出す。
    fn as_simple(&self) -> Option<u8> {
        match self.inner {
            Value::Simple(value) => Some(value),
            _ => None,
        }
    }

    /// マップからキーに対応する値を取り出す。
    ///
    /// マップ以外では常に `None` を返す。
    fn map_get(&self, key: &Bound<'_, CborValue>) -> Option<CborValue> {
        self.inner.map_get(&key.borrow().inner()).cloned().map(wrap)
    }

    fn __repr__(&self) -> String {
        match &self.inner {
            Value::Unsigned(value) => format!("CborValue(kind=unsigned, value={value})"),
            Value::Negative(value) => format!("CborValue(kind=negative, value=-{})", value + 1),
            Value::TextString(value) => format!("CborValue(kind=text_string, value={value:?})"),
            Value::Bool(value) => format!("CborValue(kind=bool, value={value})"),
            Value::Float(value) => format!("CborValue(kind=float, value={value})"),
            Value::Simple(value) => format!("CborValue(kind=simple, value={value})"),
            other => format!("CborValue(kind={})", wrap(other.clone()).kind()),
        }
    }
}

/// CBOR のデータ項目をエンコードする。
///
/// RFC 8949 §4.2 の決定論的エンコードに従う。マップのキーはキーのエンコード済み
/// バイト列の昇順に並び、浮動小数点数は値を保つ最短の幅になる。
#[pyfunction]
pub(crate) fn encode_cbor(value: &Bound<'_, CborValue>) -> PyResult<Vec<u8>> {
    cbor::encode(&value.borrow().inner()).map_err(codec_error)
}

/// CBOR のデータ項目をデコードする。
///
/// 入力の全バイトをデータ項目として消費する。末尾に余分なバイトがある場合は
/// `ValueError` になる。複数のデータ項目を続けて読む場合は
/// [`decode_cbor_partial`] を使う。
#[pyfunction]
pub(crate) fn decode_cbor(data: &[u8]) -> PyResult<CborValue> {
    cbor::decode(data).map(wrap).map_err(codec_error)
}

/// CBOR のデータ項目をデコードし `(値, 消費バイト数)` を返す。
///
/// ブロックの後ろに続くバイト列は消費しない。
#[pyfunction]
pub(crate) fn decode_cbor_partial(data: &[u8]) -> PyResult<(CborValue, usize)> {
    cbor::decode_partial(data)
        .map(|(value, consumed)| (wrap(value), consumed))
        .map_err(codec_error)
}

/// CBOR の定数をモジュールへ登録する。
pub(crate) fn register_constants(module: &Bound<'_, PyModule>) -> PyResult<()> {
    // ネスト深度の上限 (RFC 8949 のデコードでスタック枯渇を防ぐ)
    module.add("CBOR_MAX_DEPTH", MAX_DEPTH as u64)?;
    Ok(())
}
