//! `moqt` クレームのアクション、マッチ、スコープ (`moqt.c4m`)。
//!
//! draft-ietf-moq-c4m-01 §2.1 の `moqt` クレームと `moqt-reval` (§2.2)、および
//! `catdpop` (§3.1.1) を公開する。`moqt` クレームのアクションとマッチの評価は
//! バイト単位であり、正規化はしない。
//!
//! アクションは COSE のアルゴリズムと同じく整数の識別子で受け渡しする。Python 側の
//! `moqt.c4m` が `enum.IntEnum` として公開する。

use pyo3::prelude::*;

use shiguredo_moqt::c4m::{
    CLAIM_MOQT, CLAIM_MOQT_REVAL, CatDpop as MoqtCatDpop, MATCH_TYPE_PREFIX, MATCH_TYPE_SUFFIX,
    Match as MoqtMatch, MoqtAction, MoqtClaim as MoqtClaimInner, MoqtScope as MoqtScopeInner,
    NamespaceMatch as MoqtNamespaceMatch,
};

use crate::c4m::cbor::CborValue;
use crate::c4m::namespace_refs;
use crate::errors::codec_error;

/// アクションの識別子 (draft-ietf-moq-c4m-01 §2.1 Table 1) からアクションを返す。
///
/// 未知の識別子は `None` になる。認可判定では未知の識別子を「認可しない」として扱う。
pub(crate) fn action_from_key(key: i64) -> Option<MoqtAction> {
    MoqtAction::from_key(key)
}

/// `bin-match` (draft-ietf-moq-c4m-01 §2.1)。
///
/// バイト文字列は完全一致、prefix / suffix は前方 / 後方一致を表す。マッチは
/// バイト単位で行い、正規化はしない。
#[derive(PartialEq)]
#[pyclass(name = "Match", eq)]
pub(crate) struct Match {
    inner: MoqtMatch,
}

impl Match {
    /// 内部のマッチを複製して返す。
    pub(crate) fn inner(&self) -> MoqtMatch {
        self.inner.clone()
    }

    /// マッチの種別を表す文字列を返す。
    fn kind_str(&self) -> &'static str {
        match self.inner {
            MoqtMatch::Exact(_) => "exact",
            MoqtMatch::Prefix(_) => "prefix",
            MoqtMatch::Suffix(_) => "suffix",
        }
    }

    /// マッチのパターンのバイト列を返す。
    fn pattern(&self) -> Vec<u8> {
        match &self.inner {
            MoqtMatch::Exact(value) | MoqtMatch::Prefix(value) | MoqtMatch::Suffix(value) => {
                value.clone()
            }
        }
    }
}

#[pymethods]
impl Match {
    /// 完全一致 (`bstr`) を組み立てる。
    #[staticmethod]
    fn exact(value: &[u8]) -> Self {
        Self {
            inner: MoqtMatch::Exact(value.to_vec()),
        }
    }

    /// 前方一致 (`[1, bstr]`) を組み立てる。
    #[staticmethod]
    fn prefix(value: &[u8]) -> Self {
        Self {
            inner: MoqtMatch::Prefix(value.to_vec()),
        }
    }

    /// 後方一致 (`[2, bstr]`) を組み立てる。
    #[staticmethod]
    fn suffix(value: &[u8]) -> Self {
        Self {
            inner: MoqtMatch::Suffix(value.to_vec()),
        }
    }

    /// `bin-match` の CBOR のデータ項目をデコードする。
    #[staticmethod]
    fn decode(value: &Bound<'_, CborValue>) -> PyResult<Self> {
        MoqtMatch::decode(&value.borrow().inner())
            .map(|inner| Self { inner })
            .map_err(codec_error)
    }

    /// `bin-match` を CBOR のデータ項目へエンコードする。
    fn encode(&self) -> CborValue {
        crate::c4m::cbor::wrap(self.inner.encode())
    }

    /// 値がマッチするかどうかを返す。
    fn matches(&self, value: &[u8]) -> bool {
        self.inner.matches(value)
    }

    /// マッチの種別を表す文字列。
    ///
    /// `exact` / `prefix` / `suffix` のいずれかである。
    #[getter]
    fn kind(&self) -> &'static str {
        self.kind_str()
    }

    /// マッチのパターンのバイト列。
    #[getter]
    fn value(&self) -> Vec<u8> {
        self.pattern()
    }

    fn __repr__(&self) -> String {
        format!(
            "Match(kind={}, value={:?})",
            self.kind_str(),
            self.pattern()
        )
    }
}

/// `moqt-ns-match` (draft-ietf-moq-c4m-01 §2.1)。
///
/// 名前空間フィールドのマッチ ([`Match`]) と、名前空間の末尾にそれ以上のフィールドが
/// 無いことを要求する `nil` のいずれかである。
#[derive(PartialEq)]
#[pyclass(name = "NamespaceMatch", eq)]
pub(crate) struct NamespaceMatch {
    inner: MoqtNamespaceMatch,
}

#[pymethods]
impl NamespaceMatch {
    /// `bin-match` による名前空間フィールドのマッチを組み立てる。
    #[staticmethod]
    #[pyo3(name = "match")]
    fn match_value(value: &Match) -> Self {
        Self {
            inner: MoqtNamespaceMatch::Match(value.inner()),
        }
    }

    /// 名前空間の末尾にだけ現れる `nil` を組み立てる。
    #[staticmethod]
    fn end() -> Self {
        Self {
            inner: MoqtNamespaceMatch::End,
        }
    }

    /// マッチの種別を表す文字列。
    ///
    /// `match` / `end` のいずれかである。
    #[getter]
    fn kind(&self) -> &'static str {
        match self.inner {
            MoqtNamespaceMatch::Match(_) => "match",
            MoqtNamespaceMatch::End => "end",
        }
    }

    /// `bin-match` によるマッチ。`nil` の場合は `None` になる。
    #[getter]
    fn matcher(&self) -> Option<Match> {
        match &self.inner {
            MoqtNamespaceMatch::Match(matcher) => Some(Match {
                inner: matcher.clone(),
            }),
            MoqtNamespaceMatch::End => None,
        }
    }

    fn __repr__(&self) -> String {
        match &self.inner {
            MoqtNamespaceMatch::Match(matcher) => {
                format!("NamespaceMatch(kind=match, value={:?})", matcher)
            }
            MoqtNamespaceMatch::End => String::from("NamespaceMatch(kind=end)"),
        }
    }
}

/// `moqt-scope` (draft-ietf-moq-c4m-01 §2.1)。
///
/// アクションの配列と、省略可能な名前空間マッチの配列 / トラック名マッチを持つ。
/// 名前空間マッチ無しでトラック名マッチだけを持つスコープは encode できない。
#[derive(PartialEq)]
#[pyclass(name = "MoqtScope", eq)]
pub(crate) struct MoqtScope {
    inner: MoqtScopeInner,
}

#[pymethods]
impl MoqtScope {
    /// スコープを組み立てる。
    ///
    /// `actions` はアクションの整数値の列である。省略するとアクション無しになり、
    /// その状態の encode は `ValueError` になる。
    #[new]
    #[pyo3(signature = (actions = None))]
    fn new(actions: Option<Vec<i64>>) -> Self {
        Self {
            inner: MoqtScopeInner {
                actions: actions.unwrap_or_default(),
                namespace: Vec::new(),
                track: None,
            },
        }
    }

    /// アクションを追加する (draft-ietf-moq-c4m-01 §2.1 Table 1)。
    fn action(&mut self, action: i64) {
        self.inner.actions.push(action);
    }

    /// 名前空間フィールドのマッチを追加する。
    fn namespace_match(&mut self, namespace_match: &NamespaceMatch) {
        self.inner.namespace.push(namespace_match.inner.clone());
    }

    /// 名前空間の末尾を固定する `nil` を追加する。
    fn namespace_end(&mut self) {
        self.inner.namespace.push(MoqtNamespaceMatch::End);
    }

    /// アクションと Full Track Name がこのスコープで認可されるかどうかを返す。
    ///
    /// `namespace` は Track Namespace のフィールド列、`track_name` は Track Name を
    /// 表す。未知のアクションの識別子は認可されないものとして `False` を返す。
    fn allows(&self, action: i64, namespace: Vec<Vec<u8>>, track_name: &[u8]) -> bool {
        match action_from_key(action) {
            Some(action) => self
                .inner
                .allows(action, &namespace_refs(&namespace), track_name),
            None => false,
        }
    }

    /// `moqt-scope` の CBOR のデータ項目をデコードする。
    #[staticmethod]
    fn decode(value: &Bound<'_, CborValue>) -> PyResult<Self> {
        MoqtScopeInner::decode(&value.borrow().inner())
            .map(|inner| Self { inner })
            .map_err(codec_error)
    }

    /// `moqt-scope` を CBOR のデータ項目へエンコードする。
    ///
    /// アクションが空の場合、`nil` が末尾以外にある場合、名前空間マッチ無しで
    /// トラック名マッチだけを持つ場合は `ValueError` になる。
    fn encode(&self) -> PyResult<CborValue> {
        self.inner
            .encode()
            .map(crate::c4m::cbor::wrap)
            .map_err(codec_error)
    }

    /// 認可するアクションの整数値の列。
    #[getter]
    fn actions(&self) -> Vec<i64> {
        self.inner.actions.clone()
    }

    /// 認可するアクションの整数値の列を置き換える。
    #[setter]
    fn set_actions(&mut self, actions: Vec<i64>) {
        self.inner.actions = actions;
    }

    /// 名前空間フィールドのマッチの列。
    #[getter]
    fn namespace(&self) -> Vec<NamespaceMatch> {
        self.inner
            .namespace
            .iter()
            .cloned()
            .map(|inner| NamespaceMatch { inner })
            .collect()
    }

    /// 名前空間フィールドのマッチの列を置き換える。
    #[setter]
    fn set_namespace(&mut self, namespace: Vec<Bound<'_, NamespaceMatch>>) {
        self.inner.namespace = namespace
            .iter()
            .map(|namespace_match| namespace_match.borrow().inner.clone())
            .collect();
    }

    /// トラック名のマッチ。
    ///
    /// `None` の場合はすべてのトラック名にマッチする。設定すると、そのスコープは
    /// トラック名のマッチだけを持つ状態になるため、名前空間マッチが無い場合は
    /// encode が `ValueError` になる。
    #[getter]
    fn track(&self) -> Option<Match> {
        self.inner.track.clone().map(|inner| Match { inner })
    }

    /// トラック名のマッチを置き換える。
    #[setter]
    fn set_track(&mut self, matcher: Option<&Match>) {
        self.inner.track = matcher.map(Match::inner);
    }

    fn __repr__(&self) -> String {
        format!(
            "MoqtScope(actions={}, namespace_matches={}, track={})",
            self.inner.actions.len(),
            self.inner.namespace.len(),
            match &self.inner.track {
                Some(_) => "True",
                None => "False",
            }
        )
    }
}

/// `moqt` クレーム (draft-ietf-moq-c4m-01 §2.1)。
///
/// アクションスコープの配列を持つ。いずれかのスコープが認可すれば許可となり、評価順は
/// 問わない (§2.1.2)。
#[derive(PartialEq)]
#[pyclass(name = "MoqtClaim", eq)]
pub(crate) struct MoqtClaim {
    inner: MoqtClaimInner,
}

impl MoqtClaim {
    /// 内部のクレームを複製して返す。
    pub(crate) fn inner(&self) -> MoqtClaimInner {
        self.inner.clone()
    }

    /// 内部のクレームから包む。
    pub(crate) fn from_inner(inner: MoqtClaimInner) -> Self {
        Self { inner }
    }
}

#[pymethods]
impl MoqtClaim {
    /// 空のクレームを組み立てる。
    ///
    /// スコープを持たない状態の encode は `ValueError` になる。
    #[new]
    fn new() -> Self {
        Self {
            inner: MoqtClaimInner::new(),
        }
    }

    /// スコープを追加する。
    fn scope(&mut self, scope: &MoqtScope) {
        self.inner.scopes.push(scope.inner.clone());
    }

    /// アクションと Full Track Name が認可されるかどうかを返す。
    ///
    /// いずれかのスコープが認可すれば `True` を返す。`moqt` クレームを持たない
    /// `CatClaims` の認可判定は [`crate::c4m::cat::CatClaims`] を参照。
    fn authorize(&self, action: i64, namespace: Vec<Vec<u8>>, track_name: &[u8]) -> bool {
        match action_from_key(action) {
            Some(action) => self
                .inner
                .authorize(action, &namespace_refs(&namespace), track_name),
            None => false,
        }
    }

    /// `moqt` クレームの CBOR のデータ項目をデコードする。
    #[staticmethod]
    fn decode(value: &Bound<'_, CborValue>) -> PyResult<Self> {
        MoqtClaimInner::decode(&value.borrow().inner())
            .map(Self::from_inner)
            .map_err(codec_error)
    }

    /// `moqt` クレームを CBOR のデータ項目へエンコードする。
    fn encode(&self) -> PyResult<CborValue> {
        self.inner
            .encode()
            .map(crate::c4m::cbor::wrap)
            .map_err(codec_error)
    }

    /// 認可スコープの列。
    #[getter]
    fn scopes(&self) -> Vec<MoqtScope> {
        self.inner
            .scopes
            .iter()
            .cloned()
            .map(|inner| MoqtScope { inner })
            .collect()
    }

    /// 認可スコープの列を置き換える。
    #[setter]
    fn set_scopes(&mut self, scopes: Vec<Bound<'_, MoqtScope>>) {
        self.inner.scopes = scopes
            .iter()
            .map(|scope| scope.borrow().inner.clone())
            .collect();
    }

    fn __repr__(&self) -> String {
        format!("MoqtClaim(scopes={})", self.inner.scopes.len())
    }
}

/// `catdpop` クレーム (CTA-5007-B / draft-ietf-moq-c4m-01 §3.1.1)。
///
/// DPoP proof の処理設定を持つ。label 0 が受理ウィンドウ (秒)、label 1 が jti による
/// リプレイ保護を行うかどうかを表す。解釈しなかった設定は `raw` に保持する。
#[derive(PartialEq)]
#[pyclass(name = "CatDpop", eq)]
pub(crate) struct CatDpop {
    inner: MoqtCatDpop,
}

impl CatDpop {
    /// 内部の設定から包む。
    pub(crate) fn from_inner(inner: MoqtCatDpop) -> Self {
        Self { inner }
    }

    /// 内部の設定を複製して返す。
    pub(crate) fn inner(&self) -> MoqtCatDpop {
        self.inner.clone()
    }
}

#[pymethods]
impl CatDpop {
    /// ウィンドウと jti の扱いを指定して組み立てる。
    #[new]
    fn new(window_seconds: f64, honor_jti: bool) -> Self {
        Self {
            inner: MoqtCatDpop::new(window_seconds, honor_jti),
        }
    }

    /// `catdpop` の CBOR のデータ項目をデコードする。
    ///
    /// ウィンドウは整数と浮動小数点の両方、jti の扱いは真偽値と整数 (0 / 1) の両方を
    /// 受ける。
    #[staticmethod]
    fn decode(value: &Bound<'_, CborValue>) -> PyResult<Self> {
        MoqtCatDpop::decode(&value.borrow().inner())
            .map(|inner| Self { inner })
            .map_err(codec_error)
    }

    /// `catdpop` を CBOR のデータ項目へエンコードする。
    ///
    /// label 1 はドラフトの例に合わせて整数 (1 / 0) で書く。ウィンドウが有限でない
    /// 場合は `ValueError` になる。
    fn encode(&self) -> PyResult<CborValue> {
        self.inner
            .encode()
            .map(crate::c4m::cbor::wrap)
            .map_err(codec_error)
    }

    /// DPoP proof を受理する時間ウィンドウ (秒)。
    #[getter]
    fn window_seconds(&self) -> Option<f64> {
        self.inner.window_seconds
    }

    /// DPoP proof を受理する時間ウィンドウ (秒) を設定する。
    #[setter]
    fn set_window_seconds(&mut self, value: Option<f64>) {
        self.inner.window_seconds = value;
    }

    /// jti によるリプレイ保護を行うかどうか。
    #[getter]
    fn honor_jti(&self) -> Option<bool> {
        self.inner.honor_jti
    }

    /// jti によるリプレイ保護を行うかどうかを設定する。
    #[setter]
    fn set_honor_jti(&mut self, value: Option<bool>) {
        self.inner.honor_jti = value;
    }

    /// 解釈しなかった設定。
    #[getter]
    fn raw(&self) -> Vec<(i64, CborValue)> {
        self.inner
            .raw
            .iter()
            .map(|(label, value)| (*label, crate::c4m::cbor::wrap(value.clone())))
            .collect()
    }

    /// 解釈しなかった設定を置き換える。
    #[setter]
    fn set_raw(&mut self, raw: Vec<(i64, Bound<'_, CborValue>)>) {
        self.inner.raw = raw
            .iter()
            .map(|(label, value)| (*label, value.borrow().inner()))
            .collect();
    }

    /// ウィンドウを返す (未指定の場合は `default` を返す)。
    fn window_seconds_or(&self, default: f64) -> f64 {
        self.inner.window_seconds_or(default)
    }

    /// jti によるリプレイ保護を行うかどうかを返す。
    ///
    /// 未指定の場合は `False` を返す。
    fn honors_jti(&self) -> bool {
        self.inner.honors_jti()
    }

    fn __repr__(&self) -> String {
        format!(
            "CatDpop(window_seconds={}, honor_jti={})",
            match self.inner.window_seconds {
                Some(window) => window.to_string(),
                None => "None".to_string(),
            },
            match self.inner.honor_jti {
                Some(honor) => honor.to_string(),
                None => "None".to_string(),
            }
        )
    }
}

/// クレームとマッチの定数をモジュールへ登録する。
pub(crate) fn register_constants(module: &Bound<'_, PyModule>) -> PyResult<()> {
    // `moqt` / `moqt-reval` の claim key (draft-ietf-moq-c4m-01 §2)
    module.add("CLAIM_MOQT", CLAIM_MOQT)?;
    module.add("CLAIM_MOQT_REVAL", CLAIM_MOQT_REVAL)?;

    // `bin-match` の match-type (draft-ietf-moq-c4m-01 §2.1)
    module.add("MATCH_TYPE_PREFIX", MATCH_TYPE_PREFIX)?;
    module.add("MATCH_TYPE_SUFFIX", MATCH_TYPE_SUFFIX)?;
    Ok(())
}
