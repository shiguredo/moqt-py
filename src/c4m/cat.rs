//! CAT (Common Access Token) のクレームとトークン (`moqt.c4m`)。
//!
//! CTA-5007-B の CAT を CWT (RFC 8392) のクレームとして扱い、draft-ietf-moq-c4m-01
//! の `moqt` / `moqt-reval` を加えたトークンの発行と検証を公開する。
//!
//! 直列化は compact 形式 (`base64url(protected).base64url(claims).base64url(signature)`)
//! と COSE 形式 (CWT タグ + COSE_Sign1 / COSE_Mac0) の両方を扱う。[`CatToken::decode`]
//! はどちらかを自動判別し、URL に埋め込む標準 Base64 の表記も受理する。

use pyo3::prelude::*;

use shiguredo_moqt::c4m::CatDpop as MoqtCatDpop;
use shiguredo_moqt::c4m::cat::{
    CAT_CONTENT_TYPE, CLAIM_AUDIENCE, CLAIM_CAT_ALPN, CLAIM_CAT_DPOP, CLAIM_CAT_GEO_ALT,
    CLAIM_CAT_GEO_COORD, CLAIM_CAT_GEO_ISO3166, CLAIM_CAT_HEADER, CLAIM_CAT_IF, CLAIM_CAT_IF_DATA,
    CLAIM_CAT_METHOD, CLAIM_CAT_NETWORK_IP, CLAIM_CAT_PROBABILITY_OF_REJECTION, CLAIM_CAT_RENEWAL,
    CLAIM_CAT_REPLAY, CLAIM_CAT_TLS_PUBLIC_KEY, CLAIM_CAT_URI, CLAIM_CAT_VERSION,
    CLAIM_CONFIRMATION, CLAIM_CWT_ID, CLAIM_EXPIRATION, CLAIM_ISSUED_AT, CLAIM_ISSUER,
    CLAIM_NOT_BEFORE, CLAIM_SUBJECT, CONFIRMATION_C4M_DRAFT_JWK_THUMBPRINT,
    CONFIRMATION_JWK_THUMBPRINT, CatClaims as MoqtCatClaims, CatToken as MoqtCatToken,
    CatTokenBuilder as MoqtCatTokenBuilder, ClaimValidationOptions as MoqtClaimValidationOptions,
    Confirmation as MoqtConfirmation, MOQT_AUTH_TOKEN_TYPE_CAT, TokenFormat,
    VerifyOptions as MoqtVerifyOptions,
};
use shiguredo_moqt::c4m::crypto::aws_lc_rs::AwsLcRsCrypto;

use crate::c4m::bytes_or_text;
use crate::c4m::cbor::{self, CborValue};
use crate::c4m::claims::{CatDpop, MoqtClaim, action_from_key};
use crate::c4m::cose::{CoseEncodingOptions, CoseHeader, key_id_from_python, key_id_to_python};
use crate::c4m::crypto::{CoseKey, algorithm_from_identifier};
use crate::c4m::namespace_refs;
use crate::errors::codec_error;

/// `cnf` (confirmation) クレーム (RFC 8747 / CTA-5007-B)。
///
/// IANA 登録の `jkt` (confirmation key 323) と、draft-ietf-moq-c4m-01 のベクタが
/// 使う `jkt` (confirmation key 3) を分けて保持する。検証は 323 を優先する。
#[derive(PartialEq)]
#[pyclass(name = "Confirmation", eq)]
pub(crate) struct Confirmation {
    inner: MoqtConfirmation,
}

impl Confirmation {
    /// 内部の confirmation を複製して返す。
    pub(crate) fn inner(&self) -> MoqtConfirmation {
        self.inner.clone()
    }
}

#[pymethods]
impl Confirmation {
    /// 空の confirmation を組み立てる。
    #[new]
    fn new() -> Self {
        Self {
            inner: MoqtConfirmation::default(),
        }
    }

    /// `cnf` の CBOR のデータ項目をデコードする。
    #[staticmethod]
    fn decode(value: &Bound<'_, CborValue>) -> PyResult<Self> {
        MoqtConfirmation::decode(&value.borrow().inner())
            .map(|inner| Self { inner })
            .map_err(codec_error)
    }

    /// `cnf` を CBOR のデータ項目へエンコードする。
    fn encode(&self) -> CborValue {
        cbor::wrap(self.inner.encode())
    }

    /// IANA 登録の `jkt` (confirmation key 323) の値。
    #[getter]
    fn jwk_thumbprint(&self) -> Option<Vec<u8>> {
        self.inner.jwk_thumbprint.clone()
    }

    /// IANA 登録の `jkt` (confirmation key 323) の値を設定する。
    #[setter]
    fn set_jwk_thumbprint(&mut self, value: Option<Vec<u8>>) {
        self.inner.jwk_thumbprint = value;
    }

    /// draft-ietf-moq-c4m-01 のベクタが使う `jkt` (confirmation key 3) の値。
    #[getter]
    fn c4m_draft_jwk_thumbprint(&self) -> Option<Vec<u8>> {
        self.inner.c4m_draft_jwk_thumbprint.clone()
    }

    /// draft のベクタが使う `jkt` (confirmation key 3) の値を設定する。
    #[setter]
    fn set_c4m_draft_jwk_thumbprint(&mut self, value: Option<Vec<u8>>) {
        self.inner.c4m_draft_jwk_thumbprint = value;
    }

    /// 解釈しなかった confirmation の値。
    #[getter]
    fn raw(&self) -> Vec<(CborValue, CborValue)> {
        cbor::wrap_entries(&self.inner.raw)
    }

    /// 解釈しなかった confirmation の値を設定する。
    #[setter]
    fn set_raw(&mut self, value: Vec<(Bound<'_, CborValue>, Bound<'_, CborValue>)>) {
        self.inner.raw = value
            .iter()
            .map(|(key, value)| (key.borrow().inner(), value.borrow().inner()))
            .collect();
    }

    /// JWK サムプリントを返す。
    ///
    /// IANA 登録の 323 を優先し、無ければドラフトのベクタが使う 3 を返す。
    fn jkt(&self) -> Option<Vec<u8>> {
        self.inner.jkt().map(|jkt| jkt.to_vec())
    }

    fn __repr__(&self) -> String {
        format!(
            "Confirmation(has_jkt={})",
            match self.inner.jkt() {
                Some(_) => "True",
                None => "False",
            }
        )
    }
}

/// CAT のクレームセット (CWT のクレーム + CAT / C4M のクレーム)。
///
/// 型付きで解釈しないクレームは `raw` にそのまま保持する。CAT 固有のクレーム
/// (`catu` / `catnip` など) はクレームキーの定数だけを公開し、値の意味論は評価しない。
#[derive(PartialEq)]
#[pyclass(name = "CatClaims", eq)]
pub(crate) struct CatClaims {
    inner: MoqtCatClaims,
}

impl CatClaims {
    /// 内部のクレームを複製して返す。
    pub(crate) fn inner(&self) -> MoqtCatClaims {
        self.inner.clone()
    }

    /// 内部のクレームから包む。
    pub(crate) fn from_inner(inner: MoqtCatClaims) -> Self {
        Self { inner }
    }
}

#[pymethods]
impl CatClaims {
    /// 空のクレームセットを組み立てる。
    #[new]
    fn new() -> Self {
        Self {
            inner: MoqtCatClaims::default(),
        }
    }

    /// クレームセットの CBOR のデータ項目をデコードする。
    ///
    /// 非有限値 (NaN / 無限大) の数値クレームはこの時点で `ValueError` になる。
    #[staticmethod]
    fn decode(value: &Bound<'_, CborValue>) -> PyResult<Self> {
        MoqtCatClaims::decode(&value.borrow().inner())
            .map(Self::from_inner)
            .map_err(codec_error)
    }

    /// クレームセットを CBOR のデータ項目へエンコードする。
    ///
    /// 型付きフィールドを持つ claim key を `raw` に置いた場合と、非有限値の数値
    /// クレームは `ValueError` になる。
    fn encode(&self) -> PyResult<CborValue> {
        self.inner.encode().map(cbor::wrap).map_err(codec_error)
    }

    /// 整数キーのクレームを取り出す。
    ///
    /// 型付きフィールドとして解釈しなかったクレーム、および未知のクレームが対象で
    /// ある。`catv` / `catu` / `cath` などの値の意味論は評価しない。
    fn get(&self, key: i64) -> Option<CborValue> {
        self.inner.get(key).cloned().map(cbor::wrap)
    }

    /// `moqt` クレームによりアクションが認可されるかどうかを返す。
    ///
    /// `moqt` クレームが無い場合は常に `False` を返す (§2 の「明示的に許可された
    /// アクション以外はブロックする」)。評価するのは `moqt` クレームだけで、`catu`
    /// などの CAT 固有クレームは評価しない。
    fn authorize(&self, action: i64, namespace: Vec<Vec<u8>>, track_name: &[u8]) -> bool {
        match action_from_key(action) {
            Some(action) => self
                .inner
                .authorize(action, &namespace_refs(&namespace), track_name),
            None => false,
        }
    }

    /// 時刻と期待値に対するクレームの検証を行う。
    ///
    /// `exp` / `nbf` / `iss` / `aud` を検証する。署名の検証は [`CatToken::verify`] が
    /// 行う。
    fn validate(&self, options: &ClaimValidationOptions) -> PyResult<()> {
        let issuers: Vec<&str> = options
            .expected_issuers
            .iter()
            .map(String::as_str)
            .collect();
        let audiences: Vec<&str> = options
            .expected_audiences
            .iter()
            .map(String::as_str)
            .collect();
        let options = MoqtClaimValidationOptions {
            reference_time_seconds: options.reference_time_seconds,
            clock_tolerance_seconds: options.clock_tolerance_seconds,
            expected_issuers: &issuers,
            expected_audiences: &audiences,
        };
        self.inner.validate(&options).map_err(codec_error)
    }

    /// `iss`。
    #[getter]
    fn issuer(&self) -> Option<String> {
        self.inner.issuer.clone()
    }

    /// `iss` を設定する。
    #[setter]
    fn set_issuer(&mut self, value: Option<String>) {
        self.inner.issuer = value;
    }

    /// `sub`。
    #[getter]
    fn subject(&self) -> Option<String> {
        self.inner.subject.clone()
    }

    /// `sub` を設定する。
    #[setter]
    fn set_subject(&mut self, value: Option<String>) {
        self.inner.subject = value;
    }

    /// `aud`。単一のテキストと配列の両方を受ける。
    #[getter]
    fn audience(&self) -> Vec<String> {
        self.inner.audience.clone()
    }

    /// `aud` を設定する。
    #[setter]
    fn set_audience(&mut self, value: Vec<String>) {
        self.inner.audience = value;
    }

    /// `exp` (UNIX 秒)。
    #[getter]
    fn expiration(&self) -> Option<f64> {
        self.inner.expiration
    }

    /// `exp` (UNIX 秒) を設定する。
    #[setter]
    fn set_expiration(&mut self, value: Option<f64>) {
        self.inner.expiration = value;
    }

    /// `nbf` (UNIX 秒)。
    #[getter]
    fn not_before(&self) -> Option<f64> {
        self.inner.not_before
    }

    /// `nbf` (UNIX 秒) を設定する。
    #[setter]
    fn set_not_before(&mut self, value: Option<f64>) {
        self.inner.not_before = value;
    }

    /// `iat` (UNIX 秒)。
    #[getter]
    fn issued_at(&self) -> Option<f64> {
        self.inner.issued_at
    }

    /// `iat` (UNIX 秒) を設定する。
    #[setter]
    fn set_issued_at(&mut self, value: Option<f64>) {
        self.inner.issued_at = value;
    }

    /// `cti`。バイト文字列とテキスト文字列の両方を受ける。
    #[getter]
    fn cwt_id(&self) -> Option<Vec<u8>> {
        self.inner.cwt_id.clone()
    }

    /// `cti` を設定する。
    #[setter]
    fn set_cwt_id(&mut self, value: Option<Vec<u8>>) {
        self.inner.cwt_id = value;
    }

    /// `cnf`。
    #[getter]
    fn confirmation(&self) -> Option<Confirmation> {
        self.inner
            .confirmation
            .clone()
            .map(|inner| Confirmation { inner })
    }

    /// `cnf` を設定する。
    #[setter]
    fn set_confirmation(&mut self, value: Option<&Confirmation>) {
        self.inner.confirmation = value.map(Confirmation::inner);
    }

    /// `moqt` クレーム (draft-ietf-moq-c4m-01 §2.1)。
    #[getter]
    fn moqt(&self) -> Option<MoqtClaim> {
        self.inner.moqt.clone().map(MoqtClaim::from_inner)
    }

    /// `moqt` クレームを設定する。
    #[setter]
    fn set_moqt(&mut self, value: Option<&MoqtClaim>) {
        self.inner.moqt = value.map(MoqtClaim::inner);
    }

    /// `moqt-reval` (再検証間隔、秒) (draft-ietf-moq-c4m-01 §2.2)。
    ///
    /// このライブラリは Sans-I/O のため再検証を実行しない。拒否の判断は利用側が
    /// 行う。
    #[getter]
    fn moqt_reval(&self) -> Option<f64> {
        self.inner.moqt_reval
    }

    /// `moqt-reval` (再検証間隔、秒) を設定する。
    #[setter]
    fn set_moqt_reval(&mut self, value: Option<f64>) {
        self.inner.moqt_reval = value;
    }

    /// `catdpop` (draft-ietf-moq-c4m-01 §3.1.1)。
    #[getter]
    fn catdpop(&self) -> Option<CatDpop> {
        self.inner.catdpop.clone().map(CatDpop::from_inner)
    }

    /// `catdpop` を設定する。
    #[setter]
    fn set_catdpop(&mut self, value: Option<&CatDpop>) {
        self.inner.catdpop = value.map(CatDpop::inner);
    }

    /// 型付きで解釈しなかったクレーム。
    #[getter]
    fn raw(&self) -> Vec<(CborValue, CborValue)> {
        cbor::wrap_entries(&self.inner.raw)
    }

    /// 型付きで解釈しなかったクレームを設定する。
    #[setter]
    fn set_raw(&mut self, value: Vec<(Bound<'_, CborValue>, Bound<'_, CborValue>)>) {
        self.inner.raw = value
            .iter()
            .map(|(key, value)| (key.borrow().inner(), value.borrow().inner()))
            .collect();
    }

    fn __repr__(&self) -> String {
        format!(
            "CatClaims(issuer={}, moqt={}, raw={})",
            match &self.inner.issuer {
                Some(issuer) => format!("{issuer:?}"),
                None => String::from("None"),
            },
            match &self.inner.moqt {
                Some(_) => "True",
                None => "False",
            },
            self.inner.raw.len()
        )
    }
}

/// クレームの検証オプション。
#[derive(PartialEq)]
#[pyclass(name = "ClaimValidationOptions", eq)]
pub(crate) struct ClaimValidationOptions {
    /// 検証に使う現在時刻 (UNIX 秒)。
    #[pyo3(get, set)]
    pub reference_time_seconds: f64,
    /// `exp` / `nbf` に許容するずれ (秒)。
    #[pyo3(get, set)]
    pub clock_tolerance_seconds: f64,
    /// 期待する `iss` の一覧。空の場合は検証しない。
    #[pyo3(get, set)]
    pub expected_issuers: Vec<String>,
    /// 期待する `aud` の一覧。空の場合は検証しない。
    #[pyo3(get, set)]
    pub expected_audiences: Vec<String>,
}

#[pymethods]
impl ClaimValidationOptions {
    /// 検証オプションを組み立てる。
    ///
    /// 現在時刻と許容ずれの既定値は 0、期待する `iss` / `aud` の既定値は空である。
    #[new]
    #[pyo3(signature = (reference_time_seconds = 0.0, clock_tolerance_seconds = 0.0, expected_issuers = None, expected_audiences = None))]
    fn new(
        reference_time_seconds: f64,
        clock_tolerance_seconds: f64,
        expected_issuers: Option<Vec<String>>,
        expected_audiences: Option<Vec<String>>,
    ) -> Self {
        Self {
            reference_time_seconds,
            clock_tolerance_seconds,
            expected_issuers: expected_issuers.unwrap_or_default(),
            expected_audiences: expected_audiences.unwrap_or_default(),
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "ClaimValidationOptions(reference_time_seconds={}, clock_tolerance_seconds={}, expected_issuers={}, expected_audiences={})",
            self.reference_time_seconds,
            self.clock_tolerance_seconds,
            self.expected_issuers.len(),
            self.expected_audiences.len()
        )
    }
}

/// 署名検証のオプション。
#[derive(PartialEq)]
#[pyclass(name = "VerifyOptions", eq)]
pub(crate) struct VerifyOptions {
    /// トークンの `alg` に期待するアルゴリズムの識別子。
    #[pyo3(get, set)]
    pub expected_algorithm: Option<i64>,
    /// トークンの `typ` に期待する値。
    ///
    /// CAT では `CAT_CONTENT_TYPE` (`"CAT"`) を指定する。未指定の場合は `typ` を
    /// 検証しない。
    #[pyo3(get, set)]
    pub expected_type: Option<String>,
}

#[pymethods]
impl VerifyOptions {
    /// 検証オプションを組み立てる。
    #[new]
    #[pyo3(signature = (expected_algorithm = None, expected_type = None))]
    fn new(expected_algorithm: Option<i64>, expected_type: Option<String>) -> Self {
        Self {
            expected_algorithm,
            expected_type,
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "VerifyOptions(expected_algorithm={}, expected_type={})",
            match self.expected_algorithm {
                Some(identifier) => identifier.to_string(),
                None => String::from("None"),
            },
            match &self.expected_type {
                Some(expected_type) => format!("{expected_type:?}"),
                None => String::from("None"),
            }
        )
    }
}

impl VerifyOptions {
    /// 期待するアルゴリズムの識別子を `Algorithm` へ解決する。
    ///
    /// Python へは公開しない。`CatToken::verify_with` が内部で使う。
    fn resolve_algorithm(&self) -> PyResult<Option<shiguredo_moqt::c4m::cose::Algorithm>> {
        match self.expected_algorithm {
            Some(identifier) => Ok(Some(algorithm_from_identifier(identifier)?)),
            None => Ok(None),
        }
    }
}

/// CAT のトークン。
///
/// 生トークン (bearer クレデンシャル) と署名は `repr` では長さだけを表示する。
/// デコードしたトークンは不変であり、書き換えはできない。
#[derive(PartialEq)]
#[pyclass(name = "CatToken", eq)]
pub(crate) struct CatToken {
    inner: MoqtCatToken,
}

impl CatToken {
    /// 内部のトークンから包む。
    pub(crate) fn from_inner(inner: MoqtCatToken) -> Self {
        Self { inner }
    }

    /// 内部のトークンを複製して返す。
    pub(crate) fn inner(&self) -> MoqtCatToken {
        self.inner.clone()
    }
}

/// トークンの直列化の形式を表す文字列を返す。
fn format_str(format: TokenFormat) -> &'static str {
    match format {
        TokenFormat::Compact => "compact",
        TokenFormat::CoseSign1 => "cose_sign1",
        TokenFormat::CoseMac0 => "cose_mac0",
    }
}

#[pymethods]
impl CatToken {
    /// トークンをデコードする。
    ///
    /// `.` で区切られた 3 分割の compact 形式、COSE 形式の CBOR、COSE 形式を
    /// base64url または標準 Base64 で包んだテキストの順に判別する。`data` には
    /// `bytes` と `str` のどちらも渡せる。
    #[staticmethod]
    fn decode(data: &Bound<'_, PyAny>) -> PyResult<Self> {
        MoqtCatToken::decode(&bytes_or_text(data)?)
            .map(Self::from_inner)
            .map_err(codec_error)
    }

    /// compact 形式 (`base64url(protected).base64url(claims).base64url(signature)`)
    /// をデコードする。
    #[staticmethod]
    fn decode_compact(text: &str) -> PyResult<Self> {
        MoqtCatToken::decode_compact(text)
            .map(Self::from_inner)
            .map_err(codec_error)
    }

    /// COSE 形式 (CBOR) をデコードする。
    #[staticmethod]
    fn decode_cose(data: &[u8]) -> PyResult<Self> {
        MoqtCatToken::decode_cose(data)
            .map(Self::from_inner)
            .map_err(codec_error)
    }

    /// MOQT の Auth Token Type と Token Value からデコードする
    /// (draft-ietf-moq-c4m-01 §7.1)。
    ///
    /// Token Type が `MOQT_AUTH_TOKEN_TYPE_CAT` (0x01) 以外の場合は `ValueError` に
    /// なる。`value` には `bytes` と `str` のどちらも渡せる。
    #[staticmethod]
    fn decode_moqt_auth_token(token_type: u64, value: &Bound<'_, PyAny>) -> PyResult<Self> {
        MoqtCatToken::decode_moqt_auth_token(token_type, &bytes_or_text(value)?)
            .map(Self::from_inner)
            .map_err(codec_error)
    }

    /// 直列化の形式を表す文字列。
    ///
    /// `compact` / `cose_sign1` / `cose_mac0` のいずれかである。
    #[getter]
    fn format(&self) -> &'static str {
        format_str(self.inner.format())
    }

    /// `decode` に渡された生バイト。
    ///
    /// compact 形式では ASCII のトークン文字列、COSE 形式では CBOR のバイト列、
    /// base64url で包んだ入力を渡した場合はそのテキストである。DPoP の `ath` は
    /// このバイト列をハッシュする。
    #[getter]
    fn raw_token(&self) -> Vec<u8> {
        self.inner.raw_token().to_vec()
    }

    /// protected ヘッダの CBOR バイト列。
    #[getter]
    fn protected_header(&self) -> Vec<u8> {
        self.inner.protected_header().to_vec()
    }

    /// クレームセットの CBOR バイト列。
    #[getter]
    fn payload(&self) -> Vec<u8> {
        self.inner.payload().to_vec()
    }

    /// 署名または MAC。
    #[getter]
    fn signature(&self) -> Vec<u8> {
        self.inner.signature().to_vec()
    }

    /// COSE 形式の場合の unprotected ヘッダ。
    #[getter]
    fn unprotected_header(&self) -> Vec<(CborValue, CborValue)> {
        cbor::wrap_entries(self.inner.unprotected_header())
    }

    /// 署名対象のバイト列。
    #[getter]
    fn signing_input(&self) -> Vec<u8> {
        self.inner.signing_input().to_vec()
    }

    /// protected / unprotected を統合したヘッダ。
    #[getter]
    fn header(&self) -> CoseHeader {
        CoseHeader::from_inner(self.inner.header().clone())
    }

    /// クレーム。
    #[getter]
    fn claims(&self) -> CatClaims {
        CatClaims::from_inner(self.inner.claims().clone())
    }

    /// トークンの署名 / MAC を検証する。
    ///
    /// トークンの `alg` と鍵の種別が一致しない場合、および署名が一致しない場合は
    /// `ValueError` になる。
    fn verify(&self, key: &CoseKey) -> PyResult<()> {
        self.inner
            .verify(&AwsLcRsCrypto::new(), &key.inner)
            .map_err(codec_error)
    }

    /// 期待するアルゴリズムと `typ` を指定してトークンの署名 / MAC を検証する。
    #[pyo3(signature = (key, options = None))]
    fn verify_with(&self, key: &CoseKey, options: Option<&VerifyOptions>) -> PyResult<()> {
        let default_options;
        let options = match options {
            Some(options) => MoqtVerifyOptions {
                expected_algorithm: options.resolve_algorithm()?,
                expected_type: options.expected_type.as_deref(),
            },
            None => {
                default_options = MoqtVerifyOptions::default();
                default_options
            }
        };
        self.inner
            .verify_with(&AwsLcRsCrypto::new(), &key.inner, &options)
            .map_err(codec_error)
    }

    fn __repr__(&self) -> String {
        format!(
            "CatToken(format={}, claims={}, raw_bytes={})",
            format_str(self.inner.format()),
            self.inner.claims().raw.len(),
            self.inner.raw_token().len()
        )
    }
}

/// CAT のトークンを作るビルダー。
///
/// 発行 (署名) には秘密鍵が必要である。署名アルゴリズムは鍵の種別から自動選択し、
/// `algorithm` で明示もできる。
#[pyclass(name = "CatTokenBuilder")]
pub(crate) struct CatTokenBuilder {
    inner: MoqtCatTokenBuilder,
}

#[pymethods]
impl CatTokenBuilder {
    /// 空のビルダーを組み立てる。
    #[new]
    fn new() -> Self {
        Self {
            inner: MoqtCatTokenBuilder::new(),
        }
    }

    /// `iss` を設定する。
    fn issuer(&mut self, issuer: String) {
        self.inner.claims.issuer = Some(issuer);
    }

    /// `sub` を設定する。
    fn subject(&mut self, subject: String) {
        self.inner.claims.subject = Some(subject);
    }

    /// `aud` を追加する。
    fn audience(&mut self, audience: String) {
        self.inner.claims.audience.push(audience);
    }

    /// `exp` (UNIX 秒) を設定する。
    fn expiration(&mut self, expiration: f64) {
        self.inner.claims.expiration = Some(expiration);
    }

    /// `nbf` (UNIX 秒) を設定する。
    fn not_before(&mut self, not_before: f64) {
        self.inner.claims.not_before = Some(not_before);
    }

    /// `iat` (UNIX 秒) を設定する。
    fn issued_at(&mut self, issued_at: f64) {
        self.inner.claims.issued_at = Some(issued_at);
    }

    /// `cti` をバイト文字列として設定する。
    fn cwt_id(&mut self, cwt_id: Vec<u8>) {
        self.inner.claims.cwt_id = Some(cwt_id);
    }

    /// `moqt` クレームを設定する。
    fn moqt(&mut self, moqt: &MoqtClaim) {
        self.inner.claims.moqt = Some(moqt.inner());
    }

    /// `moqt-reval` (再検証間隔、秒) を設定する。
    fn moqt_reval(&mut self, seconds: f64) {
        self.inner.claims.moqt_reval = Some(seconds);
    }

    /// `cnf` の `jkt` を IANA 登録の confirmation key 323 で設定する。
    fn jwk_thumbprint(&mut self, thumbprint: Vec<u8>) {
        let confirmation = self
            .inner
            .claims
            .confirmation
            .get_or_insert_with(Default::default);
        confirmation.jwk_thumbprint = Some(thumbprint);
    }

    /// `cnf` の `jkt` を draft-ietf-moq-c4m-01 のベクタが使う key 3 で設定する。
    fn c4m_draft_jwk_thumbprint(&mut self, thumbprint: Vec<u8>) {
        let confirmation = self
            .inner
            .claims
            .confirmation
            .get_or_insert_with(Default::default);
        confirmation.c4m_draft_jwk_thumbprint = Some(thumbprint);
    }

    /// `catdpop` を設定する。
    fn catdpop(&mut self, window_seconds: f64, honor_jti: bool) {
        self.inner.claims.catdpop = Some(MoqtCatDpop::new(window_seconds, honor_jti));
    }

    /// 任意のクレームを追加する。
    ///
    /// 型付きフィールドを持つ claim key (`iss` / `moqt` / `catdpop` など) には専用の
    /// 設定メソッドを使うこと。型付きキーをここへ渡した場合は、encode 時に
    /// `ValueError` になる。
    fn claim(&mut self, key: i64, value: &Bound<'_, CborValue>) {
        self.inner.claims.raw.push((
            shiguredo_moqt::c4m::cbor::Value::integer(key),
            value.borrow().inner(),
        ));
    }

    /// `kid` を設定する。
    #[setter]
    fn set_key_id(&mut self, value: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        self.inner.key_id = key_id_from_python(value)?;
        Ok(())
    }

    /// `kid` を返す。
    #[getter]
    fn key_id(&self, py: Python<'_>) -> Option<Py<PyAny>> {
        self.inner
            .key_id
            .as_ref()
            .map(|key_id| key_id_to_python(py, key_id))
    }

    /// `typ` を設定する。
    #[setter]
    fn set_typ(&mut self, value: Option<String>) {
        self.inner.typ = value;
    }

    /// `typ` を返す。
    #[getter]
    fn typ(&self) -> Option<String> {
        self.inner.typ.clone()
    }

    /// 署名アルゴリズムを設定する。
    #[setter]
    fn set_algorithm(&mut self, value: Option<i64>) -> PyResult<()> {
        self.inner.algorithm = match value {
            Some(identifier) => Some(algorithm_from_identifier(identifier)?),
            None => None,
        };
        Ok(())
    }

    /// 署名アルゴリズムの識別子。
    #[getter]
    fn algorithm(&self) -> Option<i64> {
        self.inner.algorithm.map(|algorithm| algorithm.identifier())
    }

    /// 発行するクレームセット。
    ///
    /// ゲッターは複製を返すため、返した値を変更してもビルダーには反映されない。
    /// 変更を反映する場合はセッターに渡すこと。
    #[getter]
    fn claims(&self) -> CatClaims {
        CatClaims::from_inner(self.inner.claims.clone())
    }

    /// 発行するクレームセットを置き換える。
    #[setter]
    fn set_claims(&mut self, value: &CatClaims) {
        self.inner.claims = value.inner();
    }

    /// compact 形式 (draft-ietf-moq-c4m-01 付録 A) のトークンを発行する。
    ///
    /// HMAC-SHA256 のアルゴリズム識別子は RFC 9053 の HMAC 256/256 (5) を使う。
    /// ドラフト付録 A のベクタは -4 を使うが、IANA の COSE Algorithms レジストリでは
    /// -4 は A192KW であり発行には使わない。
    fn build_compact(&self, key: &CoseKey) -> PyResult<String> {
        self.inner
            .build_compact(&AwsLcRsCrypto::new(), &key.inner)
            .map_err(codec_error)
    }

    /// COSE 形式 (CWT + COSE_Sign1 / COSE_Mac0) のトークンを発行する。
    ///
    /// CWT タグ (61) と COSE タグ (17 / 18) を付与する。
    fn build_cose(&self, key: &CoseKey) -> PyResult<Vec<u8>> {
        self.inner
            .build_cose(&AwsLcRsCrypto::new(), &key.inner)
            .map_err(codec_error)
    }

    /// タグの付与を指定して COSE 形式のトークンを発行する。
    #[pyo3(signature = (key, options = None))]
    fn build_cose_with(
        &self,
        key: &CoseKey,
        options: Option<&CoseEncodingOptions>,
    ) -> PyResult<Vec<u8>> {
        let options = options.map_or_else(Default::default, CoseEncodingOptions::to_inner);
        self.inner
            .build_cose_with(&AwsLcRsCrypto::new(), &key.inner, &options)
            .map_err(codec_error)
    }

    fn __repr__(&self) -> String {
        format!(
            "CatTokenBuilder(issuer={}, audience={}, moqt={})",
            match &self.inner.claims.issuer {
                Some(issuer) => format!("{issuer:?}"),
                None => String::from("None"),
            },
            self.inner.claims.audience.len(),
            match &self.inner.claims.moqt {
                Some(_) => "True",
                None => "False",
            }
        )
    }

    fn __eq__(&self, other: &Bound<'_, PyAny>) -> bool {
        match other.cast::<CatTokenBuilder>() {
            Ok(other) => {
                let other = other.borrow();
                self.inner.claims == other.inner.claims
                    && self.inner.key_id == other.inner.key_id
                    && self.inner.typ == other.inner.typ
                    && self.inner.algorithm == other.inner.algorithm
            }
            Err(_) => false,
        }
    }
}

/// CAT の定数をモジュールへ登録する。
pub(crate) fn register_constants(module: &Bound<'_, PyModule>) -> PyResult<()> {
    // CWT の claim key (RFC 8392 §3.1)
    module.add("CLAIM_ISSUER", CLAIM_ISSUER)?;
    module.add("CLAIM_SUBJECT", CLAIM_SUBJECT)?;
    module.add("CLAIM_AUDIENCE", CLAIM_AUDIENCE)?;
    module.add("CLAIM_EXPIRATION", CLAIM_EXPIRATION)?;
    module.add("CLAIM_NOT_BEFORE", CLAIM_NOT_BEFORE)?;
    module.add("CLAIM_ISSUED_AT", CLAIM_ISSUED_AT)?;
    module.add("CLAIM_CWT_ID", CLAIM_CWT_ID)?;
    module.add("CLAIM_CONFIRMATION", CLAIM_CONFIRMATION)?;

    // CAT の claim key (IANA CWT Claims レジストリ / CTA-5007)
    module.add("CLAIM_CAT_REPLAY", CLAIM_CAT_REPLAY)?;
    module.add(
        "CLAIM_CAT_PROBABILITY_OF_REJECTION",
        CLAIM_CAT_PROBABILITY_OF_REJECTION,
    )?;
    module.add("CLAIM_CAT_VERSION", CLAIM_CAT_VERSION)?;
    module.add("CLAIM_CAT_NETWORK_IP", CLAIM_CAT_NETWORK_IP)?;
    module.add("CLAIM_CAT_URI", CLAIM_CAT_URI)?;
    module.add("CLAIM_CAT_METHOD", CLAIM_CAT_METHOD)?;
    module.add("CLAIM_CAT_ALPN", CLAIM_CAT_ALPN)?;
    module.add("CLAIM_CAT_HEADER", CLAIM_CAT_HEADER)?;
    module.add("CLAIM_CAT_GEO_ISO3166", CLAIM_CAT_GEO_ISO3166)?;
    module.add("CLAIM_CAT_GEO_COORD", CLAIM_CAT_GEO_COORD)?;
    module.add("CLAIM_CAT_GEO_ALT", CLAIM_CAT_GEO_ALT)?;
    module.add("CLAIM_CAT_TLS_PUBLIC_KEY", CLAIM_CAT_TLS_PUBLIC_KEY)?;
    module.add("CLAIM_CAT_IF_DATA", CLAIM_CAT_IF_DATA)?;
    module.add("CLAIM_CAT_DPOP", CLAIM_CAT_DPOP)?;
    module.add("CLAIM_CAT_IF", CLAIM_CAT_IF)?;
    module.add("CLAIM_CAT_RENEWAL", CLAIM_CAT_RENEWAL)?;

    // `cnf` の `jkt` の confirmation key
    module.add("CONFIRMATION_JWK_THUMBPRINT", CONFIRMATION_JWK_THUMBPRINT)?;
    module.add(
        "CONFIRMATION_C4M_DRAFT_JWK_THUMBPRINT",
        CONFIRMATION_C4M_DRAFT_JWK_THUMBPRINT,
    )?;

    // MOQT の Auth Token Type (draft-ietf-moq-c4m-01 §7.1)
    module.add("MOQT_AUTH_TOKEN_TYPE_CAT", MOQT_AUTH_TOKEN_TYPE_CAT)?;

    // CAT の COSE ヘッダの `typ` の値
    module.add("CAT_CONTENT_TYPE", CAT_CONTENT_TYPE)?;
    Ok(())
}
