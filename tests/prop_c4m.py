"""`moqt.c4m` の C4M codec に対する Property-Based Testing。"""

from hypothesis import given
from hypothesis import strategies as st
from moqt import c4m
from moqt.c4m import (
    Algorithm,
    CatToken,
    CatTokenBuilder,
    CborValue,
    CoseKey,
    Match,
    MoqtAction,
    MoqtClaim,
    MoqtScope,
    NamespaceMatch,
)

# CBOR のデータ項目の葉。NaN は encode で正規化されて値の比較ができないため除く。
CBOR_LEAVES = st.one_of(
    st.integers(min_value=0, max_value=2**63).map(CborValue.unsigned),
    st.integers(min_value=-(2**63), max_value=-1).map(CborValue.integer),
    st.binary(max_size=16).map(CborValue.byte_string),
    st.text(max_size=16).map(CborValue.text_string),
    st.booleans().map(CborValue.boolean),
    st.just(CborValue.null()),
    st.just(CborValue.undefined()),
    st.floats(allow_nan=False, allow_infinity=True).map(CborValue.float_value),
    # 単純値 24〜31 は予約されているため生成しない (RFC 8949 §3.3)。
    st.one_of(st.integers(min_value=0, max_value=19), st.integers(min_value=32, max_value=255)).map(
        CborValue.simple
    ),
)

# マップのキーは整数に限る。重複キーは decode が拒否するため、辞書で一意性を保証する。
CBOR_MAP_KEYS = st.integers(min_value=-(2**31), max_value=2**31)


def cbor_values() -> st.SearchStrategy[CborValue]:
    """任意の CBOR のデータ項目を生成する。"""
    return st.recursive(
        CBOR_LEAVES,
        lambda children: st.one_of(
            st.lists(children, max_size=4).map(CborValue.array),
            st.dictionaries(CBOR_MAP_KEYS, children, max_size=4).map(
                lambda entries: CborValue.map(
                    [(CborValue.integer(key), value) for key, value in entries.items()]
                )
            ),
            st.tuples(st.integers(min_value=0, max_value=2**32), children).map(
                lambda pair: CborValue.tag(pair[0], pair[1])
            ),
        ),
        max_leaves=10,
    )


# `bin-match` のパターン。空のパターンも仕様上は許される。
MATCHES = st.one_of(
    st.binary(max_size=8).map(Match.exact),
    st.binary(max_size=8).map(Match.prefix),
    st.binary(max_size=8).map(Match.suffix),
)

# 認可対象のアクション。Table 1 の全アクションを生成する。
ACTIONS = st.sampled_from(list(MoqtAction))

# 認可対象の Full Track Name。フィールドのバイト列は任意である。
NAMESPACES = st.lists(st.binary(max_size=8), max_size=3)
TRACK_NAMES = st.binary(max_size=8)


@st.composite
def moqt_scopes(draw: st.DrawFn) -> MoqtScope:
    """encode できる `moqt-scope` を生成する。

    アクションは 1 つ以上、`nil` は末尾にだけ置き、トラック名マッチは名前空間
    マッチがある場合だけ設定する (draft-ietf-moq-c4m-01 §2.1)。
    """
    scope = MoqtScope(draw(st.lists(ACTIONS, min_size=1, max_size=4, unique=True)))
    namespace = draw(st.lists(MATCHES, max_size=3))
    for matcher in namespace:
        scope.namespace_match(NamespaceMatch.match(matcher))
    if namespace and draw(st.booleans()):
        scope.track = draw(MATCHES)
    return scope


@st.composite
def moqt_claims(draw: st.DrawFn) -> MoqtClaim:
    """encode できる `moqt` クレームを生成する。"""
    claim = MoqtClaim()
    for scope in draw(st.lists(moqt_scopes(), min_size=1, max_size=3)):
        claim.scope(scope)
    return claim


@given(value=cbor_values())
def prop_encode_decode_cbor_round_trips(value: CborValue) -> None:
    """
    任意の CBOR のデータ項目が encode と decode で往復することを確認する。

    決定論的エンコードは値を正規化するため、往復後のデータ項目が元の値と等しく
    なることを検証する。(RFC 8949 §4.2 (Deterministic Encoding))
    """
    encoded = c4m.encode_cbor(value)

    decoded, consumed = c4m.decode_cbor_partial(encoded + b"\x00")

    assert consumed == len(encoded)
    # マップは決定論的なキー順に並べ替えられるため、再エンコードの一致で比較する
    assert c4m.encode_cbor(decoded) == encoded


@given(scope=moqt_scopes(), action=ACTIONS, namespace=NAMESPACES, track_name=TRACK_NAMES)
def prop_moqt_scope_round_trips(
    scope: MoqtScope,
    action: MoqtAction,
    namespace: list[bytes],
    track_name: bytes,
) -> None:
    """
    任意の `moqt-scope` が encode と decode で往復することを確認する。

    認可判定が decode の前後で変わらないことも検証する
    (draft-ietf-moq-c4m-01 §2.1 (moqt claim))。
    """
    decoded = MoqtScope.decode(scope.encode())

    assert decoded == scope
    assert decoded.allows(action, namespace, track_name) == scope.allows(
        action, namespace, track_name
    )


@given(claim=moqt_claims(), action=ACTIONS, namespace=NAMESPACES, track_name=TRACK_NAMES)
def prop_moqt_claim_round_trips(
    claim: MoqtClaim,
    action: MoqtAction,
    namespace: list[bytes],
    track_name: bytes,
) -> None:
    """
    任意の `moqt` クレームが encode と decode で往復することを確認する。

    スコープのいずれかが認可すれば許可になる評価が decode の前後で変わらない
    ことも検証する (draft-ietf-moq-c4m-01 §2.1.2)。
    """
    decoded = MoqtClaim.decode(claim.encode())

    assert decoded == claim
    assert decoded.authorize(action, namespace, track_name) == claim.authorize(
        action, namespace, track_name
    )


# HMAC-SHA256 の鍵。発行と検証の往復だけで使う。
HMAC_KEY = CoseKey.symmetric(bytes(range(32)))

# トークンに載せるテキストの最大長。
MAX_TOKEN_TEXT = 16


@given(
    issuer=st.text(max_size=MAX_TOKEN_TEXT),
    audiences=st.lists(st.text(max_size=MAX_TOKEN_TEXT), max_size=3, unique=True),
    expiration=st.floats(min_value=0.0, max_value=2.0**40, allow_nan=False, allow_infinity=False),
    moqt=st.one_of(st.none(), moqt_claims()),
    action=ACTIONS,
    namespace=NAMESPACES,
    track_name=TRACK_NAMES,
)
def prop_cat_token_round_trips(
    issuer: str,
    audiences: list[str],
    expiration: float,
    moqt: MoqtClaim | None,
    action: MoqtAction,
    namespace: list[bytes],
    track_name: bytes,
) -> None:
    """
    任意のクレームを持つ CAT トークンが発行・検証・デコードで往復することを確認する。

    compact 形式の発行は常に HMAC-SHA256 (RFC 9053 の識別子 5) になり、`exp` の
    浮動小数点数と `moqt` クレームのスコープが保たれることを検証する。
    """
    builder = CatTokenBuilder()
    builder.issuer(issuer)
    for audience in audiences:
        builder.audience(audience)
    builder.expiration(expiration)
    if moqt is not None:
        builder.moqt(moqt)

    token = CatToken.decode(builder.build_compact(HMAC_KEY))

    assert token.claims == builder.claims
    token.verify(HMAC_KEY)
    assert token.header.algorithm == Algorithm.HMAC_SHA256
    assert token.claims.authorize(action, namespace, track_name) == (
        moqt is not None and moqt.authorize(action, namespace, track_name)
    )
