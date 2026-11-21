//! DPoP proof の検証と発行 (`moqt.c4m`)。
//!
//! draft-nandakumar-moq-generic-dpop-proof-00 の JWT 形式の DPoP proof を扱う。
//! proof の署名は埋め込みの JWK で検証し、`cnf` の JWK サムプリントとの一致
//! (鍵バインディング)、`catdpop` のウィンドウによる鮮度、jti によるリプレイ保護、
//! Authorization Context (actx) の検証を行う。
//!
//! CWT 形式の DPoP proof (`dpop-proof+cwt`) は actx の claim label が TBD のため
//! 扱わない。proof の発行は非対称アルゴリズムだけであり、HMAC は使えない。

use pyo3::prelude::*;
use pyo3::types::PyList;

use shiguredo_moqt::c4m::crypto::aws_lc_rs::AwsLcRsCrypto;
use shiguredo_moqt::c4m::dpop::AuthorizationContext as MoqtAuthorizationContext;
use shiguredo_moqt::c4m::dpop::{
    DPOP_PROOF_JWT_TYPE, DpopProof as MoqtDpopProof, DpopProofBuilder as MoqtDpopProofBuilder,
    DpopProofClaims as MoqtDpopProofClaims, DpopProofHeader as MoqtDpopProofHeader,
    DpopReplayCache as MoqtDpopReplayCache, DpopVerification as MoqtDpopVerification,
    MOQT_AUTHORIZATION_CONTEXT_TYPE,
};

use crate::c4m::cat::{CatClaims, CatToken, Confirmation};
use crate::c4m::claims::action_from_key;
use crate::c4m::crypto::CoseKey;
use crate::c4m::jwk::Jwk;
use crate::errors::codec_error;

/// DPoP proof の Authorization Context (draft-nandakumar-moq-generic-dpop-proof-00
/// §4.2 / §5.1)。
///
/// `tns` / `tn` は draft-ietf-moq-transport-23 §8.8 の正規シリアライズを使う。
/// リテラルでないバイトは `.` と 16 進 2 桁へエスケープされるため、`tns` には
/// `moqt.msf.serialize_namespace`、`tn` には `moqt.msf.serialize_track_name` の結果を
/// 渡す。生の名前を渡すと `verify_target` などで一致しない。
///
/// `raw` にしか無い拡張フィールド (`parameters` など) は発行時に出力されない。
#[derive(PartialEq)]
#[pyclass(name = "AuthorizationContext", eq)]
pub(crate) struct AuthorizationContext {
    inner: MoqtAuthorizationContext,
}

impl AuthorizationContext {
    /// 内部の actx を複製して返す。
    pub(crate) fn inner(&self) -> MoqtAuthorizationContext {
        self.inner.clone()
    }

    /// 内部の actx から包む。
    pub(crate) fn from_inner(inner: MoqtAuthorizationContext) -> Self {
        Self { inner }
    }
}

#[pymethods]
impl AuthorizationContext {
    /// Authorization Context を組み立てる。
    ///
    /// 省略したフィールドは空文字列 (`track_name` / `resource` は `None`) になる。
    #[new]
    #[pyo3(signature = (context_type = None, action = None, track_namespace = None, track_name = None, resource = None, raw = None))]
    fn new(
        context_type: Option<String>,
        action: Option<String>,
        track_namespace: Option<String>,
        track_name: Option<String>,
        resource: Option<String>,
        raw: Option<String>,
    ) -> Self {
        Self {
            inner: MoqtAuthorizationContext {
                context_type: context_type.unwrap_or_default(),
                action: action.unwrap_or_default(),
                track_namespace: track_namespace.unwrap_or_default(),
                track_name,
                resource,
                raw: raw.unwrap_or_default(),
            },
        }
    }

    /// Authorization Context の JSON をデコードする。
    ///
    /// メンバー名が重複している場合は `ValueError` になる。
    #[staticmethod]
    fn decode(text: &str) -> PyResult<Self> {
        MoqtAuthorizationContext::decode(text)
            .map(Self::from_inner)
            .map_err(codec_error)
    }

    /// `type` が期待どおりかどうかを検証する。
    fn verify_context_type(&self, expected: &str) -> PyResult<()> {
        self.inner
            .verify_context_type(expected)
            .map_err(codec_error)
    }

    /// `action` がアクションと一致するかどうかを検証する (C4M Table 2)。
    fn verify_action(&self, action: i64) -> PyResult<()> {
        let action = action_from_key(action)
            .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("unknown MOQT action"))?;
        self.inner.verify_action(action).map_err(codec_error)
    }

    /// `tns` / `tn` が対象の Full Track Name と一致するかどうかを検証する。
    ///
    /// `tn` が proof に無い場合は `ValueError` になる (draft-ietf-moq-c4m-02 §3.1.2 は
    /// `tn` を必須としている)。
    fn verify_target(&self, namespace: Vec<Vec<u8>>, track_name: &[u8]) -> PyResult<()> {
        let namespace = crate::core::track_namespace_from_python(namespace)?;
        self.inner
            .verify_target(&namespace, track_name)
            .map_err(codec_error)
    }

    /// `resource` が指定されている場合に `tns` / `tn` と整合するかどうかを検証する。
    ///
    /// `resource` は `moqt://<relay-endpoint>?tns=<namespace>&tn=<track>` の形式
    /// (draft-ietf-moq-c4m-02 §3.1.3) を前提とし、クエリパラメータを文字列として
    /// 比較する。パーセントエンコーディングは解釈しない。
    ///
    /// `action` によって要求されるパラメータが変わるため、actx の action と同じ値を渡す。
    fn verify_resource_consistency(&self, action: i64) -> PyResult<()> {
        let action = action_from_key(action)
            .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("unknown MOQT action"))?;
        self.inner
            .verify_resource_consistency(action)
            .map_err(codec_error)
    }

    /// `type`。
    #[getter]
    fn context_type(&self) -> String {
        self.inner.context_type.clone()
    }

    /// `type` を設定する。
    #[setter]
    fn set_context_type(&mut self, value: String) {
        self.inner.context_type = value;
    }

    /// `action`。
    #[getter]
    fn action(&self) -> String {
        self.inner.action.clone()
    }

    /// `action` を設定する。
    #[setter]
    fn set_action(&mut self, value: String) {
        self.inner.action = value;
    }

    /// `tns` (namespace のシリアライズ文字列)。
    #[getter]
    fn track_namespace(&self) -> String {
        self.inner.track_namespace.clone()
    }

    /// `tns` を設定する。
    #[setter]
    fn set_track_namespace(&mut self, value: String) {
        self.inner.track_namespace = value;
    }

    /// `tn` (track name のシリアライズ文字列)。
    #[getter]
    fn track_name(&self) -> Option<String> {
        self.inner.track_name.clone()
    }

    /// `tn` を設定する。
    #[setter]
    fn set_track_name(&mut self, value: Option<String>) {
        self.inner.track_name = value;
    }

    /// `resource`。
    #[getter]
    fn resource(&self) -> Option<String> {
        self.inner.resource.clone()
    }

    /// `resource` を設定する。
    #[setter]
    fn set_resource(&mut self, value: Option<String>) {
        self.inner.resource = value;
    }

    /// actx の生 JSON。
    #[getter]
    fn raw(&self) -> String {
        self.inner.raw.clone()
    }

    /// actx の生 JSON を設定する。
    #[setter]
    fn set_raw(&mut self, value: String) {
        self.inner.raw = value;
    }

    fn __repr__(&self) -> String {
        format!(
            "AuthorizationContext(type={:?}, action={:?}, tns={:?})",
            self.inner.context_type, self.inner.action, self.inner.track_namespace
        )
    }
}

/// DPoP proof の JWT ヘッダ (draft-nandakumar-moq-generic-dpop-proof-00 §4.3.1)。
#[derive(PartialEq)]
#[pyclass(name = "DpopProofHeader", eq)]
pub(crate) struct DpopProofHeader {
    inner: MoqtDpopProofHeader,
}

#[pymethods]
impl DpopProofHeader {
    /// `typ`。`"dpop-proof+jwt"` でなければならない。
    #[getter]
    fn typ(&self) -> String {
        self.inner.typ.clone()
    }

    /// `alg` の識別子。非対称署名アルゴリズムでなければならない。
    #[getter]
    fn algorithm(&self) -> i64 {
        self.inner.algorithm.identifier()
    }

    /// `jwk`。proof の検証に使う公開鍵。
    #[getter]
    fn jwk(&self) -> Jwk {
        Jwk::from_inner(self.inner.jwk.clone())
    }

    /// `kid` (任意)。
    #[getter]
    fn key_id(&self) -> Option<String> {
        self.inner.key_id.clone()
    }

    fn __repr__(&self) -> String {
        format!(
            "DpopProofHeader(typ={:?}, algorithm={})",
            self.inner.typ,
            self.inner.algorithm.identifier()
        )
    }
}

/// DPoP proof の JWT ペイロード (draft-nandakumar-moq-generic-dpop-proof-00 §4.3.2)。
#[derive(PartialEq)]
#[pyclass(name = "DpopProofClaims", eq)]
pub(crate) struct DpopProofClaims {
    inner: MoqtDpopProofClaims,
}

#[pymethods]
impl DpopProofClaims {
    /// ペイロードの JSON をデコードする。
    ///
    /// クレーム名が重複している場合は `ValueError` になる。
    #[staticmethod]
    fn decode(text: &str) -> PyResult<Self> {
        MoqtDpopProofClaims::decode(text)
            .map(|inner| Self { inner })
            .map_err(codec_error)
    }

    /// `jti`。proof の一意な識別子。
    #[getter]
    fn jti(&self) -> String {
        self.inner.jti.clone()
    }

    /// `iat` (UNIX 秒)。
    #[getter]
    fn issued_at(&self) -> f64 {
        self.inner.issued_at
    }

    /// `actx`。
    #[getter]
    fn authorization_context(&self) -> AuthorizationContext {
        AuthorizationContext::from_inner(self.inner.authorization_context.clone())
    }

    /// `ath`。アクセストークンを伴う場合の base64url(SHA-256(token))。
    #[getter]
    fn access_token_hash(&self) -> Option<String> {
        self.inner.access_token_hash.clone()
    }

    /// `nonce`。
    #[getter]
    fn nonce(&self) -> Option<String> {
        self.inner.nonce.clone()
    }

    fn __repr__(&self) -> String {
        format!(
            "DpopProofClaims(jti={:?}, issued_at={})",
            self.inner.jti, self.inner.issued_at
        )
    }
}

/// DPoP proof。
///
/// `repr` は署名の長さだけを表示する。
#[derive(PartialEq)]
#[pyclass(name = "DpopProof", eq)]
pub(crate) struct DpopProof {
    inner: MoqtDpopProof,
}

#[pymethods]
impl DpopProof {
    /// DPoP proof の JWT をデコードする。
    ///
    /// `typ` が `"dpop-proof+jwt"` でない場合、対称鍵アルゴリズムである場合、`jwk` が
    /// 無い場合は `ValueError` になる。
    #[staticmethod]
    fn decode(input: &str) -> PyResult<Self> {
        MoqtDpopProof::decode(input)
            .map(|inner| Self { inner })
            .map_err(codec_error)
    }

    /// ヘッダ。
    #[getter]
    fn header(&self) -> DpopProofHeader {
        DpopProofHeader {
            inner: self.inner.header().clone(),
        }
    }

    /// クレーム。
    #[getter]
    fn claims(&self) -> DpopProofClaims {
        DpopProofClaims {
            inner: self.inner.claims().clone(),
        }
    }

    /// 署名対象のバイト列。
    #[getter]
    fn signing_input(&self) -> Vec<u8> {
        self.inner.signing_input().to_vec()
    }

    /// 署名。
    #[getter]
    fn signature(&self) -> Vec<u8> {
        self.inner.signature().to_vec()
    }

    /// proof の署名を埋め込みの JWK で検証する。
    fn verify_signature(&self) -> PyResult<()> {
        self.inner
            .verify_signature(&AwsLcRsCrypto::new())
            .map_err(codec_error)
    }

    /// proof の JWK がトークンの `cnf` の JWK サムプリントと一致するか検証する。
    ///
    /// `cnf` の confirmation key 323 (IANA 登録の `jkt`) を優先する。323 が無い場合は
    /// `interpretation` が `"c4m_draft_jkt"` のときだけ confirmation key 3 と比較し、
    /// 既定の `"iana_kid"` では 3 を `jkt` として扱わない。
    #[pyo3(signature = (confirmation, interpretation = None))]
    fn verify_key_binding(
        &self,
        confirmation: &Confirmation,
        interpretation: Option<&str>,
    ) -> PyResult<()> {
        let interpretation = crate::c4m::confirmation_key3_from_python(interpretation)?;
        self.inner
            .verify_key_binding(&AwsLcRsCrypto::new(), &confirmation.inner(), interpretation)
            .map_err(codec_error)
    }

    /// `iat` が現在時刻からウィンドウ内にあるかどうかを検証する。
    ///
    /// 未来方向のずれも同じウィンドウで制限する。
    fn verify_freshness(&self, reference_time_seconds: f64, window_seconds: f64) -> PyResult<()> {
        self.inner
            .verify_freshness(reference_time_seconds, window_seconds)
            .map_err(codec_error)
    }

    /// `ath` をアクセストークン (文字列) と照合する。
    ///
    /// `ath` が proof に無い場合は何も行わない。
    fn verify_access_token_hash(&self, access_token: &str) -> PyResult<()> {
        self.inner
            .verify_access_token_hash(&AwsLcRsCrypto::new(), access_token)
            .map_err(codec_error)
    }

    /// `ath` をアクセストークン (バイト列) と照合する。
    fn verify_access_token_hash_bytes(&self, access_token: &[u8]) -> PyResult<()> {
        self.inner
            .verify_access_token_hash_bytes(&AwsLcRsCrypto::new(), access_token)
            .map_err(codec_error)
    }

    /// Authorization Context (actx) を検証する。
    ///
    /// `type` が "moqt"、`action` が一致し、`tns` / `tn` が対象と一致し、`resource`
    /// が与えられている場合は `tns` / `tn` と整合することを確認する。
    fn verify_authorization_context(
        &self,
        action: i64,
        namespace: Vec<Vec<u8>>,
        track_name: &[u8],
    ) -> PyResult<()> {
        let action = action_from_key(action)
            .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("unknown MOQT action"))?;
        let namespace = crate::core::track_namespace_from_python(namespace)?;
        self.inner
            .verify_authorization_context(action, &namespace, track_name)
            .map_err(codec_error)
    }

    /// CAT トークンと同時に送られた DPoP proof を一通り検証する。
    ///
    /// TOKEN の生バイトを `ath` のアクセストークンとして扱う。署名、`ath`、JWK
    /// サムプリントのバインディング、Authorization Context、`catdpop` のウィンドウに
    /// よる鮮度、jti によるリプレイ保護の順に検証する。
    ///
    /// `catdpop` が jti の処理を要求している場合は `replay_cache` が必須である。
    #[expect(clippy::too_many_arguments)]
    #[pyo3(signature = (
        token,
        action,
        namespace,
        track_name,
        reference_time_seconds,
        default_window_seconds,
        replay_cache = None,
        confirmation_key3 = None,
    ))]
    fn verify_against_cat_token(
        &self,
        token: &CatToken,
        action: i64,
        namespace: Vec<Vec<u8>>,
        track_name: &[u8],
        reference_time_seconds: f64,
        default_window_seconds: f64,
        replay_cache: Option<PyRefMut<'_, DpopReplayCache>>,
        confirmation_key3: Option<&str>,
    ) -> PyResult<()> {
        let action = action_from_key(action)
            .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("unknown MOQT action"))?;
        let interpretation = crate::c4m::confirmation_key3_from_python(confirmation_key3)?;
        let namespace = crate::core::track_namespace_from_python(namespace)?;
        let mut replay_cache = replay_cache;
        let replay_cache = replay_cache
            .as_deref_mut()
            .map(|replay_cache| &mut replay_cache.inner);
        self.inner
            .verify_against_cat_token_with(
                &AwsLcRsCrypto::new(),
                &token.inner(),
                action,
                interpretation,
                &namespace,
                track_name,
                reference_time_seconds,
                default_window_seconds,
                replay_cache,
            )
            .map_err(codec_error)
    }

    /// CAT トークンに束縛された DPoP proof を一通り検証する。
    ///
    /// [`DpopProof::verify_against_cat_token`] と異なり、アクセストークンの表現を
    /// 呼び出し側が指定する。`DpopVerification` の `access_token` を渡すと `ath` の
    /// 検証が必須になる (draft-nandakumar-moq-generic-dpop-proof-00 §4.3.2)。
    #[pyo3(signature = (request, replay_cache = None))]
    fn verify_against_token(
        &self,
        request: &DpopVerification,
        replay_cache: Option<PyRefMut<'_, DpopReplayCache>>,
    ) -> PyResult<()> {
        let request = request.to_inner();
        let mut replay_cache = replay_cache;
        let replay_cache = replay_cache
            .as_deref_mut()
            .map(|replay_cache| &mut replay_cache.inner);
        self.inner
            .verify_against_token(&AwsLcRsCrypto::new(), &request, replay_cache)
            .map_err(codec_error)
    }

    fn __repr__(&self) -> String {
        format!(
            "DpopProof(jti={:?}, signature_bytes={})",
            self.inner.claims().jti,
            self.inner.signature().len()
        )
    }
}

/// DPoP proof を CAT トークンに束縛して検証するための入力。
///
/// [`DpopProof::verify_against_token`] に渡す。アクセストークンを渡すと `ath` の検証が
/// 必須になる。
#[pyclass(name = "DpopVerification")]
pub(crate) struct DpopVerification {
    /// 検証対象の CAT のクレーム。
    token_claims: shiguredo_moqt::c4m::cat::CatClaims,
    /// 要求されたアクション。
    action: shiguredo_moqt::c4m::MoqtAction,
    /// `cnf` の confirmation key 3 の解釈。
    confirmation_key3: shiguredo_moqt::c4m::cat::ConfirmationKey3Interpretation,
    /// 対象の Track Namespace。
    namespace: shiguredo_moqt::message::common::TrackNamespace,
    /// 対象の Track Name。
    track_name: Vec<u8>,
    /// 検証に使う現在時刻 (UNIX 秒)。
    reference_time_seconds: f64,
    /// `catdpop` が無い / ウィンドウ未指定の場合に使う既定のウィンドウ (秒)。
    default_window_seconds: f64,
    /// proof と同時に送られたアクセストークン。
    access_token: Option<Vec<u8>>,
}

impl DpopVerification {
    /// 借用の検証入力へ変換する。
    fn to_inner(&self) -> MoqtDpopVerification<'_> {
        MoqtDpopVerification {
            token_claims: &self.token_claims,
            action: self.action,
            confirmation_key3: self.confirmation_key3,
            namespace: &self.namespace,
            track_name: &self.track_name,
            reference_time_seconds: self.reference_time_seconds,
            default_window_seconds: self.default_window_seconds,
            access_token: self.access_token.as_deref(),
        }
    }
}

#[pymethods]
impl DpopVerification {
    /// 検証入力を組み立てる。
    ///
    /// `namespace` は正規の Track Namespace でなければ `ValueError` になる。
    #[expect(clippy::too_many_arguments)]
    #[new]
    #[pyo3(signature = (
        token_claims,
        action,
        namespace,
        track_name,
        reference_time_seconds,
        default_window_seconds,
        access_token = None,
        confirmation_key3 = None,
    ))]
    fn new(
        token_claims: &CatClaims,
        action: i64,
        namespace: Vec<Vec<u8>>,
        track_name: Vec<u8>,
        reference_time_seconds: f64,
        default_window_seconds: f64,
        access_token: Option<Vec<u8>>,
        confirmation_key3: Option<&str>,
    ) -> PyResult<Self> {
        let action = action_from_key(action)
            .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("unknown MOQT action"))?;
        let confirmation_key3 = crate::c4m::confirmation_key3_from_python(confirmation_key3)?;
        let namespace = crate::core::track_namespace_from_python(namespace)?;
        Ok(Self {
            token_claims: token_claims.inner(),
            action,
            confirmation_key3,
            namespace,
            track_name,
            reference_time_seconds,
            default_window_seconds,
            access_token,
        })
    }

    /// 検証対象の CAT のクレーム。
    #[getter]
    fn token_claims(&self) -> CatClaims {
        CatClaims::from_inner(self.token_claims.clone())
    }

    /// 要求されたアクションの識別子。
    #[getter]
    fn action(&self) -> i64 {
        self.action.key()
    }

    /// `cnf` の confirmation key 3 の解釈。
    ///
    /// `"iana_kid"` (既定) は RFC 8747 §3.4 の `kid`、`"c4m_draft_jkt"` は
    /// draft-ietf-moq-c4m-01 のベクタに合わせて `jkt` として扱う。
    #[getter]
    fn confirmation_key3(&self) -> &'static str {
        crate::c4m::confirmation_key3_to_python(self.confirmation_key3)
    }

    /// 対象の Track Namespace のフィールド列。
    #[getter]
    fn namespace(&self, py: Python<'_>) -> PyResult<Py<PyList>> {
        crate::core::track_namespace_to_python(py, &self.namespace)
    }

    /// 対象の Track Name。
    #[getter]
    fn track_name(&self) -> Vec<u8> {
        self.track_name.clone()
    }

    /// 検証に使う現在時刻 (UNIX 秒)。
    #[getter]
    fn reference_time_seconds(&self) -> f64 {
        self.reference_time_seconds
    }

    /// 既定のウィンドウ (秒)。
    #[getter]
    fn default_window_seconds(&self) -> f64 {
        self.default_window_seconds
    }

    /// proof と同時に送られたアクセストークン。
    #[getter]
    fn access_token(&self) -> Option<Vec<u8>> {
        self.access_token.clone()
    }

    fn __repr__(&self) -> String {
        format!(
            "DpopVerification(action={}, reference_time_seconds={}, default_window_seconds={}, has_access_token={})",
            self.action.key(),
            self.reference_time_seconds,
            self.default_window_seconds,
            match self.access_token {
                Some(_) => "True",
                None => "False",
            }
        )
    }
}

/// jti によるリプレイ保護のキャッシュ。
///
/// アプリケーションが 1 つの主体 (セッションやアクセストークン) ごとに保持する。
/// エントリ数と jti 長の上限は持たないため、アプリケーションが主体ごとのレート制限や
/// jti の長さ制限で肥大化を防ぐこと (RFC 9449 §11.1)。
#[pyclass(name = "DpopReplayCache")]
pub(crate) struct DpopReplayCache {
    inner: MoqtDpopReplayCache,
}

#[pymethods]
impl DpopReplayCache {
    /// 空のキャッシュを組み立てる。
    ///
    /// `max_window_seconds` は記録の保持期間の上限 (秒) である。省略した場合は
    /// moqt-rs の既定値を使う。0 以下や非有限の値は `ValueError` になる。
    ///
    /// 記録は `iat + max_window_seconds` を過ぎるまで保持する。proof の
    /// `catdpop` ウィンドウが上限を超える場合は `ValueError` になる (fail-closed)。
    #[new]
    #[pyo3(signature = (max_window_seconds = None))]
    fn new(max_window_seconds: Option<f64>) -> PyResult<Self> {
        let inner = match max_window_seconds {
            Some(max_window_seconds) => {
                MoqtDpopReplayCache::with_max_window(max_window_seconds).map_err(codec_error)?
            }
            None => MoqtDpopReplayCache::new(),
        };
        Ok(Self { inner })
    }

    /// 記録の保持期間の上限 (秒)。
    #[getter]
    fn max_window_seconds(&self) -> f64 {
        self.inner.max_window_seconds()
    }

    /// jti を確認して記録する。
    ///
    /// `window_seconds` は proof の鮮度に使った `catdpop` のウィンドウである。
    /// 保持期限 (`iat + 保持期間の上限`) を過ぎた記録は破棄する。同じ jti が
    /// 残っている場合は `ValueError` になる。
    fn check_and_record(
        &mut self,
        jti: &str,
        issued_at: f64,
        window_seconds: f64,
        reference_time_seconds: f64,
    ) -> PyResult<()> {
        self.inner
            .check_and_record(jti, issued_at, window_seconds, reference_time_seconds)
            .map_err(codec_error)
    }

    /// 記録数を返す。
    fn __len__(&self) -> usize {
        self.inner.len()
    }

    /// 記録が空かどうかを返す。
    fn is_empty(&self) -> bool {
        self.inner.is_empty()
    }

    fn __repr__(&self) -> String {
        format!("DpopReplayCache(entries={})", self.inner.len())
    }
}

/// DPoP proof を発行するビルダー。
///
/// 署名鍵と埋め込む JWK が同じ公開鍵を表していることを確認してから署名する。
/// `iat` が有限でない場合は `ValueError` になる。
#[derive(PartialEq)]
#[pyclass(name = "DpopProofBuilder", eq)]
pub(crate) struct DpopProofBuilder {
    inner: MoqtDpopProofBuilder,
}

#[pymethods]
impl DpopProofBuilder {
    /// 必須の値を指定して組み立てる。
    #[new]
    fn new(jti: String, issued_at: f64, authorization_context: &AuthorizationContext) -> Self {
        Self {
            inner: MoqtDpopProofBuilder::new(jti, issued_at, authorization_context.inner()),
        }
    }

    /// proof の JWT を発行する。
    ///
    /// `jwk` は埋め込む公開鍵で、`key` と同じ公開鍵でなければならない。署名は非対称
    /// アルゴリズムだけで行う。
    fn build(&self, key: &CoseKey, jwk: &Jwk) -> PyResult<String> {
        self.inner
            .build(&AwsLcRsCrypto::new(), &key.inner, &jwk.inner())
            .map_err(codec_error)
    }

    /// `kid` (任意)。
    #[getter]
    fn key_id(&self) -> Option<String> {
        self.inner.key_id.clone()
    }

    /// `kid` を設定する。
    #[setter]
    fn set_key_id(&mut self, value: Option<String>) {
        self.inner.key_id = value;
    }

    /// `jti`。
    #[getter]
    fn jti(&self) -> String {
        self.inner.jti.clone()
    }

    /// `jti` を設定する。
    #[setter]
    fn set_jti(&mut self, value: String) {
        self.inner.jti = value;
    }

    /// `iat` (UNIX 秒)。
    #[getter]
    fn issued_at(&self) -> f64 {
        self.inner.issued_at
    }

    /// `iat` (UNIX 秒) を設定する。
    #[setter]
    fn set_issued_at(&mut self, value: f64) {
        self.inner.issued_at = value;
    }

    /// `actx`。
    #[getter]
    fn authorization_context(&self) -> AuthorizationContext {
        AuthorizationContext::from_inner(self.inner.authorization_context.clone())
    }

    /// `actx` を設定する。
    #[setter]
    fn set_authorization_context(&mut self, value: &AuthorizationContext) {
        self.inner.authorization_context = value.inner();
    }

    /// `ath` (任意)。
    #[getter]
    fn access_token_hash(&self) -> Option<String> {
        self.inner.access_token_hash.clone()
    }

    /// `ath` を設定する。
    #[setter]
    fn set_access_token_hash(&mut self, value: Option<String>) {
        self.inner.access_token_hash = value;
    }

    /// `nonce` (任意)。
    #[getter]
    fn nonce(&self) -> Option<String> {
        self.inner.nonce.clone()
    }

    /// `nonce` を設定する。
    #[setter]
    fn set_nonce(&mut self, value: Option<String>) {
        self.inner.nonce = value;
    }

    fn __repr__(&self) -> String {
        format!(
            "DpopProofBuilder(jti={:?}, issued_at={})",
            self.inner.jti, self.inner.issued_at
        )
    }
}

/// DPoP の定数をモジュールへ登録する。
pub(crate) fn register_constants(module: &Bound<'_, PyModule>) -> PyResult<()> {
    // DPoP proof の JWT の `typ`
    // (draft-nandakumar-moq-generic-dpop-proof-00 §4.3.1)
    module.add("DPOP_PROOF_JWT_TYPE", DPOP_PROOF_JWT_TYPE)?;

    // MOQT の Authorization Context の `type`
    // (draft-nandakumar-moq-generic-dpop-proof-00 §5.1)
    module.add(
        "MOQT_AUTHORIZATION_CONTEXT_TYPE",
        MOQT_AUTHORIZATION_CONTEXT_TYPE,
    )?;
    Ok(())
}
