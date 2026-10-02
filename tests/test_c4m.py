"""`moqt.c4m` の C4M (CAT) codec のテスト。

draft-ietf-moq-c4m-01 付録 A のテストベクタ、CBOR / COSE / JWK / JWT / DPoP の
境界値、および発行と検証の往復を検証する。署名と検証には aws-lc-rs を使う。
"""

import binascii

import pytest
from moqt import c4m, msf
from moqt.c4m import (
    Algorithm,
    AuthorizationContext,
    CatClaims,
    CatToken,
    CatTokenBuilder,
    CborValue,
    ClaimValidationOptions,
    Confirmation,
    CoseEncodingOptions,
    CoseHeader,
    CoseKey,
    CoseMessage,
    DpopProof,
    DpopProofBuilder,
    DpopReplayCache,
    DpopVerification,
    EcCurve,
    Jwk,
    JwsCompact,
    JwsHeader,
    Match,
    MoqtAction,
    MoqtClaim,
    MoqtScope,
    NamespaceMatch,
    OkpCurve,
    TokenFormat,
    VerifyOptions,
)

# 付録 A.1 の HMAC-SHA256 鍵
HMAC_KEY_HEX = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
# 付録 A.1 の ES256 秘密鍵と公開鍵
ES256_PRIVATE_KEY_HEX = "c9afa9d845ba75166b5c215767b1d6934e50c3db36e89b127b8a622b120f6721"
ES256_PUBLIC_KEY_X_HEX = "60fed4ba255a9d31c961eb74c6356d68c049b8923b61fa6ce669622e60f29fb6"
ES256_PUBLIC_KEY_Y_HEX = "7903fe1008b8bc99a41ae9e95628bc64f2f1b20c2d7e9f5177a3c294d4462299"


def hex_bytes(text: str) -> bytes:
    """hex 文字列をバイト列へ変換する。"""
    return binascii.unhexlify(text)


def hmac_key() -> CoseKey:
    """付録 A.1 の HMAC-SHA256 鍵を返す。"""
    return CoseKey.symmetric(hex_bytes(HMAC_KEY_HEX))


def es256_key() -> CoseKey:
    """付録 A.1 の ES256 秘密鍵を返す。"""
    return CoseKey.ec2_with_private_key(
        EcCurve.P256,
        hex_bytes(ES256_PUBLIC_KEY_X_HEX),
        hex_bytes(ES256_PUBLIC_KEY_Y_HEX),
        hex_bytes(ES256_PRIVATE_KEY_HEX),
    )


def es256_public_key() -> CoseKey:
    """付録 A.1 の ES256 公開鍵を返す。"""
    return CoseKey.ec2(
        EcCurve.P256,
        hex_bytes(ES256_PUBLIC_KEY_X_HEX),
        hex_bytes(ES256_PUBLIC_KEY_Y_HEX),
    )


def es256_jwk() -> Jwk:
    """付録 A.1 の ES256 公開鍵の JWK を返す。"""
    return Jwk.ec(
        "P-256",
        "YP7UuiVanTHJYet0xjVtaMBJuJI7Yfps5mliLmDyn7Y",
        "eQP-EAi4vJmkGunpVii8ZPLxsgwtfp9Rd6PClNRGIpk",
    )


def moqt_claim_for_publish() -> MoqtClaim:
    """`example.com` の `video-` prefix を PUBLISH できる `moqt` クレームを返す。"""
    scope = MoqtScope([MoqtAction.PUBLISH])
    scope.namespace_match(NamespaceMatch.match(Match.exact(b"example.com")))
    scope.track = Match.prefix(b"video-")
    claim = MoqtClaim()
    claim.scope(scope)
    return claim


# 付録 A.2 の CBOR エンコードのベクタ (payload hex)
CLAIM_VECTORS: list[tuple[str, str]] = [
    ("cbor_issuer_only", "a101781868747470733a2f2f617574682e6578616d706c652e636f6d"),
    (
        "cbor_core_claims",
        "a501781868747470733a2f2f617574682e6578616d706c652e636f6d0381781968747470733a2f2f"
        "72656c61792e6578616d706c652e636f6d041a65554280051a6553f100074e746573742d746f6b"
        "656e2d303031",
    ),
    ("cbor_cat_version_usage", "a2190136664341542d763119013805"),
    (
        "cbor_network_identifiers",
        "a1190137846d3139322e3136382e312e313030a16869705f72616e67656a31302e302e302e302f38"
        "a16361736e19fc00a16961736e5f72616e67658219fc0019fd00",
    ),
    (
        "cbor_geographic_claims",
        "a419011a6639713879796b19013c8262555362434119013da3636c6174fb4042e32fec56d5d0636c"
        "6f6efbc05e9ad77318fc50686163637572616379f9564019013e0a",
    ),
    (
        "cbor_uri_patterns",
        "a119013b83782068747470733a2f2f6578616d706c652e636f6d2f6c6976652f73747265616d31a1"
        "66707265666978781868747470733a2f2f6578616d706c652e636f6d2f766f642fa16673756666"
        "6978652e6d337538",
    ),
    ("cbor_alpn", "a119013a82666d6f712d3030626833"),
]

# 付録 A.3 の HMAC-SHA256 の最小トークン
TOKEN_HMAC_MINIMAL = (
    "ogEjEGNDQVQ.owF4GGh0dHBzOi8vYXV0aC5leGFtcGxlLmNvbQOBeBlodHRwczovL3JlbGF5LmV4YW1w"
    "bGUuY29tBBplVUKA.W17GD7Gj-B0YtejX7fRwLlUmEkje-ME81oCc9oZaaYY"
)
# 付録 A.3 の HMAC-SHA256 の全クレームのトークン
TOKEN_HMAC_FULL = (
    "ogEjEGNDQVQ.qgF4Gmh0dHBzOi8vaXNzdWVyLm1vcS5leGFtcGxlAnZ1c2VyOmFsaWNlQGV4YW1wbGUu"
    "Y29tA4J4Gmh0dHBzOi8vcmVsYXkxLmV4YW1wbGUuY29teBpodHRwczovL3JlbGF5Mi5leGFtcGxlLmNv"
    "bQQaZVVCgAUaZVPxAAYaZVPxAAdKdmVjdG9yLTAwMhkBNmZDQVQtdjEZATeBbDIwMy4wLjExMy41MBkB"
    "OAo.AqpYox40q1P6s8dVtHzwj0WKNgPaTZM9fAsc5GFPRNo"
)
# 付録 A.3 の ES256 のトークン
TOKEN_ES256 = (
    "ogEmEGNDQVQ.pAF4GGh0dHBzOi8vYXV0aC5leGFtcGxlLmNvbQOBeB1odHRwczovL21vcS1yZWxheS5l"
    "eGFtcGxlLmNvbQQaZVVCgAUaZVPxAA.-jMV6d4GH9d9gUOUQormHaPXoh_f-xmAKwxXXFeAmOfNS2t1"
    "oWkN7tTCuq6ZS_xGLg2KIAbz6JeA80NXOClNeg"
)

# 付録 A.4 の DPoP バインディングのトークン
TOKEN_DPOP_JWK_BINDING = (
    "ogEjEGNDQVQ.pAF4GGh0dHBzOi8vYXV0aC5leGFtcGxlLmNvbQQaZVVCgAihA1ggoLHC0-T1prfI2eDx"
    "orPE1eb3qLnA0eLzpLXG1-j5oLEZAUGiABg8AQE.sN9kLIp64zIN9zDXoTLYC0xsJU_1FNF3kaO0"
    "CbdA_3M"
)
TOKEN_DPOP_NO_JTI = (
    "ogEjEGNDQVQ.pAF4GGh0dHBzOi8vYXV0aC5leGFtcGxlLmNvbQQaZVVCgAihA1ggPILf1jWLqAS9kIec"
    "NOdDu-E66reYBmSUTzeg7ABj_pUZAUGiABkBLAEA.M4lF5pQdxav6eIWqDjbchDkijVYOM7xa3oJR"
    "2IwWt9g"
)
TOKEN_DPOP_ES256 = (
    "ogEmEGNDQVQ.pQF4GGh0dHBzOi8vYXV0aC5leGFtcGxlLmNvbQOBeBlodHRwczovL3JlbGF5LmV4YW1w"
    "bGUuY29tBBplVUKACKEDWCAM6_G8mIB0ipVYiQW3mEO0K6dcsXQFXj4ka_h_4AtKbRkBQaEAGHg."
    "5andoxOhWXQIKWR3EMHWT-WIMPBDMYQFc61nzlfZs8zmgzwcOARpmlaB3ZS5MbJ9iCYWykYAcIzJ8"
    "1nMyyZoQw"
)

# 付録 A.5 の認可テストのベクタ
SCOPE_VECTOR_PUBLISHER_EXACT = (
    "ogEjEGNDQVQ.owF4GGh0dHBzOi8vYXV0aC5leGFtcGxlLmNvbQQaZVVCgBkBR4GDggIGgktleGFtcGxl"
    "LmNvbUVhbGljZYIBRnZpZGVvLQ.oAPD24Wu_zHnDcuM6a-ePeGvRJjbCa6U7iswdsKzFDk"
)
SCOPE_VECTOR_SUBSCRIBER_PREFIX = (
    "ogEjEGNDQVQ.owF4GGh0dHBzOi8vYXV0aC5leGFtcGxlLmNvbQQaZVVCgBkBR4GCgwMEB4GCAVJjb25m"
    "ZXJlbmNlLmV4YW1wbGU.pfUPZultmyCm1GF2PvPXAYXzvK6d1D-OFNBLG1AwjDg"
)
SCOPE_VECTOR_MULTI_SCOPE = (
    "ogEjEGNDQVQ.pAF4GGh0dHBzOi8vYXV0aC5leGFtcGxlLmNvbQQaZVVCgBkBR4KCggIGgkxsaXZlLmV4"
    "YW1wbGVIc3R1ZGlvLWGCggQHgYIBTGxpdmUuZXhhbXBsZRkBSPlcsA.byEzQmxc28UXFyFekHtgOtaV"
    "mWyIPl-63xNMOF0Q_IU"
)
SCOPE_VECTOR_ADMIN_WILDCARD = (
    "ogEjEGNDQVQ.owF4GGh0dHBzOi8vYXV0aC5leGFtcGxlLmNvbQQaZVVCgBkBR4GBiQABAgMEBQYHCA."
    "XlNItz7OGqnNEbaqZ_bQh6TL-wV6SDr8hXyOLmtQkj4"
)
SCOPE_VECTOR_SUFFIX_MATCH = (
    "ogEjEGNDQVQ.owF4GGh0dHBzOi8vYXV0aC5leGFtcGxlLmNvbQQaZVVCgBkBR4GDgQSBggJMLmV4YW1w"
    "bGUuY29tggJGLWF1ZGlv.-eGYTPe_n1PeC0sgHdWCqgnKRHGYF-T89WTk269liBg"
)

# (ベクタ, アクション, namespace, track, 期待値)
AUTHORIZATION_CASES: list[tuple[str, int, tuple[bytes, ...], bytes, bool]] = [
    (SCOPE_VECTOR_PUBLISHER_EXACT, 2, (b"example.com", b"alice"), b"video-hd", True),
    (SCOPE_VECTOR_PUBLISHER_EXACT, 6, (b"example.com", b"alice"), b"video-sd", True),
    (SCOPE_VECTOR_PUBLISHER_EXACT, 6, (b"example.com", b"alice"), b"audio-main", False),
    (SCOPE_VECTOR_PUBLISHER_EXACT, 4, (b"example.com", b"alice"), b"video-hd", False),
    (SCOPE_VECTOR_PUBLISHER_EXACT, 6, (b"example.com", b"bob"), b"video-hd", False),
    (SCOPE_VECTOR_SUBSCRIBER_PREFIX, 4, (b"conference.example.room1",), b"audio", True),
    (SCOPE_VECTOR_SUBSCRIBER_PREFIX, 7, (b"conference.example.room2",), b"video", True),
    (SCOPE_VECTOR_SUBSCRIBER_PREFIX, 4, (b"other.domain",), b"audio", False),
    (SCOPE_VECTOR_SUBSCRIBER_PREFIX, 6, (b"conference.example.room1",), b"audio", False),
    (SCOPE_VECTOR_MULTI_SCOPE, 6, (b"live.example", b"studio-a"), b"cam1", True),
    (SCOPE_VECTOR_MULTI_SCOPE, 4, (b"live.example.studio-b",), b"cam1", True),
    (SCOPE_VECTOR_MULTI_SCOPE, 6, (b"live.example", b"studio-b"), b"cam1", False),
    (SCOPE_VECTOR_MULTI_SCOPE, 2, (b"other.example", b"studio-a"), b"", False),
    (SCOPE_VECTOR_ADMIN_WILDCARD, 0, (b"any.namespace",), b"any-track", True),
    (SCOPE_VECTOR_ADMIN_WILDCARD, 6, (b"any.namespace",), b"any-track", True),
    (SCOPE_VECTOR_ADMIN_WILDCARD, 8, (b"any.namespace",), b"status", True),
    (SCOPE_VECTOR_SUFFIX_MATCH, 4, (b"cdn.example.com",), b"stream1-audio", True),
    (SCOPE_VECTOR_SUFFIX_MATCH, 4, (b"cdn.example.com",), b"stream1-video", False),
    (SCOPE_VECTOR_SUFFIX_MATCH, 4, (b"cdn.other.org",), b"stream1-audio", False),
]
AUTHORIZATION_IDS = [f"case-{index}" for index in range(len(AUTHORIZATION_CASES))]

# 付録 A.6 のクレーム検証のベクタ
# (トークン, 現在時刻, 期待する iss, 期待する aud, 例外メッセージの断片)
CLAIM_VALIDATION_CASES: list[tuple[str, float, list[str], list[str], str | None]] = [
    (
        "ogEjEGNDQVQ.pAF4GGh0dHBzOi8vYXV0aC5leGFtcGxlLmNvbQOBeBlodHRwczovL3JlbGF5LmV4YW1w"
        "bGUuY29tBBplVUKABRplU_EA.9SztgnG4xgw8U9zDFnqPIuPn6hLwuilSigQcfPsArSg",
        1700003600.0,
        ["https://auth.example.com"],
        ["https://relay.example.com"],
        None,
    ),
    (
        "ogEjEGNDQVQ.ogF4GGh0dHBzOi8vYXV0aC5leGFtcGxlLmNvbQQaX14QAA.lq8nGBiZm80yUwl1kH_T"
        "v2prKu_nV20JvxVJW8ZGkho",
        1700000000.0,
        [],
        [],
        "token is expired",
    ),
    (
        "ogEjEGNDQVQ.owF4GGh0dHBzOi8vYXV0aC5leGFtcGxlLmNvbQQaZVaUAAUaZVVCgA.fPIUugY7_oSeHlhe"
        "u83_8Yyljsk3iP2zGeWRUi7NtUs",
        1700000000.0,
        [],
        [],
        "token is not yet valid",
    ),
    (
        "ogEjEGNDQVQ.owF4GGh0dHBzOi8vZXZpbC5leGFtcGxlLmNvbQOBeBlodHRwczovL3JlbGF5LmV4YW1w"
        "bGUuY29tBBplVUKA.Xo7FCr_MGSyVX0C9sueeapSfboIHkrkysurn2VjC9PU",
        1700003600.0,
        ["https://auth.example.com"],
        [],
        "token issuer does not match",
    ),
    (
        "ogEjEGNDQVQ.owF4GGh0dHBzOi8vYXV0aC5leGFtcGxlLmNvbQOBeB9odHRwczovL290aGVyLXJlbGF5"
        "LmV4YW1wbGUuY29tBBplVUKA.b8KxAKxJglzhELMuc9bYmsikrx3F9Y3YdvpfHLbsyk0",
        1700003600.0,
        ["https://auth.example.com"],
        ["https://relay.example.com"],
        "token audience does not match",
    ),
]

# 付録 A.6 の署名検証のベクタ
# (トークン, 鍵, 期待するアルゴリズム, 例外メッセージの断片)
SPOOFED_TOKENS = [
    (
        "ogEjEGNDQVQ.owF4GGh0dHBzOi8vYXV0aC5leGFtcGxlLmNvbQOBeBlodHRwczovL3JlbGF5LmV4YW1w"
        "bGUuY29tBBplVUKA.pF7GD7Gj-B0YtejX7fRwLlUmEkje-ME81oCc9oZaaYY",
        HMAC_KEY_HEX,
        None,
        "signature verification failed",
    ),
    (
        "ogEjEGNDQVQ.ogF4GGh0dHBzOi8vYXV0aC5leGFtcGxlLmNvbQQaZVVCgA.zmbxdkvbWtGtX0DExLC2"
        "nIxPDDmgAVImqk4rRSCCkCY",
        "f" * 64,
        None,
        "signature verification failed",
    ),
    (
        "ogEjEGNDQVQ.ogF4GGh0dHBzOi8vYXV0aC5leGFtcGxlLmNvbQQaZVVCgA.zmbxdkvbWtGtX0DExLC2"
        "nIxPDDmgAVImqk4rRSCCkCY",
        HMAC_KEY_HEX,
        -7,
        "does not match expected",
    ),
]


def test_compact_token_matches_appendix_a3() -> None:
    """
    付録 A.3 の compact トークンの構造が vector の hex と一致することを確認する。

    protected ヘッダ、クレーム、署名のそれぞれを vector の hex と照合し、`alg` の
    別名 (-4) が HMAC-SHA256 として解釈されることも確認する。
    """
    token = CatToken.decode(TOKEN_HMAC_MINIMAL)

    assert token.format == TokenFormat.COMPACT
    assert token.protected_header == hex_bytes("a201231063434154")
    assert token.payload == hex_bytes(
        "a301781868747470733a2f2f617574682e6578616d706c652e636f6d03817819"
    ) + hex_bytes("68747470733a2f2f72656c61792e6578616d706c652e636f6d041a65554280")
    assert token.signature == hex_bytes(
        "5b5ec60fb1a3f81d18b5e8d7edf4702e55261248def8c13cd6809cf6865a6986"
    )
    assert token.header.algorithm == Algorithm.HMAC_SHA256
    assert token.header.algorithm_identifier == c4m.C4M_DRAFT_HMAC_SHA256_ALGORITHM_ID
    # compact 形式は ASCII の `protected.claims` が署名対象である
    assert token.signing_input == b".".join(
        (TOKEN_HMAC_MINIMAL.split(".")[0].encode(), TOKEN_HMAC_MINIMAL.split(".")[1].encode())
    )


def test_hmac_token_claims_and_verification() -> None:
    """
    付録 A.3 の全クレームの HMAC トークンがデコード・検証・認可できることを確認する。
    """
    token = CatToken.decode(TOKEN_HMAC_FULL)
    claims = token.claims

    assert claims.issuer == "https://issuer.moq.example"
    assert claims.subject == "user:alice@example.com"
    assert claims.audience == ["https://relay1.example.com", "https://relay2.example.com"]
    assert claims.expiration == 1700086400.0
    assert claims.not_before == 1700000000.0
    assert claims.issued_at == 1700000000.0
    assert claims.cwt_id == b"vector-002"
    # 型付きで解釈しない CAT クレームは raw に残る
    cat_version = claims.get(c4m.CLAIM_CAT_VERSION)
    network_ip = claims.get(c4m.CLAIM_CAT_NETWORK_IP)
    assert cat_version is not None
    assert cat_version.as_text() == "CAT-v1"
    assert network_ip is not None
    assert claims.moqt is None

    token.verify(hmac_key())
    token.verify_with(
        hmac_key(),
        VerifyOptions(
            expected_algorithm=Algorithm.HMAC_SHA256,
            expected_type=c4m.CAT_CONTENT_TYPE,
        ),
    )
    claims.validate(
        ClaimValidationOptions(
            reference_time_seconds=1700003600.0,
            expected_issuers=["https://issuer.moq.example"],
            expected_audiences=["https://relay1.example.com"],
        )
    )


def test_es256_token_verification() -> None:
    """
    付録 A.3 の ES256 トークンが公開鍵で検証できることを確認する。

    署名は COSE の固定長 r || s 形式である。
    """
    token = CatToken.decode(TOKEN_ES256)

    assert token.header.algorithm == Algorithm.ES256
    assert token.header.algorithm_identifier == -7
    assert len(token.signature) == 64
    token.verify(es256_public_key())
    token.verify_with(
        es256_public_key(),
        VerifyOptions(expected_algorithm=Algorithm.ES256, expected_type="CAT"),
    )


def test_wrong_expected_type_is_rejected() -> None:
    """
    `typ` が期待する値と一致しない場合に検証が拒否されることを確認する。

    RFC 9596 §2 の `typ` は VerifyOptions で検証できる。
    """
    token = CatToken.decode(TOKEN_HMAC_MINIMAL)

    with pytest.raises(ValueError, match="token typ does not match the expected type"):
        token.verify_with(hmac_key(), VerifyOptions(expected_type="other"))


def test_decode_moqt_auth_token_rejects_other_types() -> None:
    """
    MOQT の Auth Token Type が CAT (0x01) 以外の場合に拒否されることを確認する。

    draft-ietf-moq-c4m-01 §7.1 は Token Type 0x01 を CAT と定める。
    """
    token = CatToken.decode_moqt_auth_token(c4m.MOQT_AUTH_TOKEN_TYPE_CAT, TOKEN_HMAC_MINIMAL)
    assert token.claims.issuer == "https://auth.example.com"

    with pytest.raises(ValueError, match="unsupported MOQT auth token type"):
        CatToken.decode_moqt_auth_token(0x02, TOKEN_HMAC_MINIMAL)


@pytest.mark.parametrize(
    "payload_hex",
    [payload_hex for _, payload_hex in CLAIM_VECTORS],
    ids=[vector_id for vector_id, _ in CLAIM_VECTORS],
)
def test_appendix_a2_cbor_vectors_reencode_identically(payload_hex: str) -> None:
    """
    付録 A.2 の CBOR が decode して再 encode すると元のバイト列に戻ることを確認する。

    付録 A.2 のバイト列は RFC 8949 §4.2 の決定論的エンコードであるため、
    再 encode の結果は入力と完全に一致する。
    """
    payload = hex_bytes(payload_hex)

    assert c4m.encode_cbor(c4m.decode_cbor(payload)) == payload


@pytest.mark.parametrize(
    ("token_text", "action", "namespace", "track_name", "expected"),
    AUTHORIZATION_CASES,
    ids=AUTHORIZATION_IDS,
)
def test_appendix_a5_authorization(
    token_text: str,
    action: int,
    namespace: tuple[bytes, ...],
    track_name: bytes,
    expected: bool,
) -> None:
    """
    付録 A.5 の `moqt` クレームの認可判定が vector と一致することを確認する。
    """
    claims = CatToken.decode(token_text).claims

    assert claims.authorize(action, namespace, track_name) is expected


def test_unknown_action_is_not_authorized() -> None:
    """
    未知のアクションの識別子を持つアクションが認可されないことを確認する。

    Table 1 に無い識別子はどのスコープにも現れないため、fail-closed として拒否する。
    """
    claims = CatToken.decode(SCOPE_VECTOR_ADMIN_WILDCARD).claims

    assert not claims.authorize(99, (b"any.namespace",), b"any-track")


@pytest.mark.parametrize(
    ("token_text", "reference_time", "issuers", "audiences", "message"),
    CLAIM_VALIDATION_CASES,
    ids=[f"case-{index}" for index in range(len(CLAIM_VALIDATION_CASES))],
)
def test_appendix_a6_claim_validation(
    token_text: str,
    reference_time: float,
    issuers: list[str],
    audiences: list[str],
    message: str | None,
) -> None:
    """
    付録 A.6 のクレーム検証が vector どおりの結果になることを確認する。
    """
    claims = CatToken.decode(token_text).claims
    options = ClaimValidationOptions(
        reference_time_seconds=reference_time,
        expected_issuers=issuers,
        expected_audiences=audiences,
    )

    if message is None:
        claims.validate(options)
        return

    with pytest.raises(ValueError, match=message):
        claims.validate(options)


def test_clock_tolerance_allows_expired_token() -> None:
    """
    `exp` の許容ずれの範囲内であれば期限切れとして拒否しないことを確認する。

    draft-ietf-moq-c4m-01 の検証は `clock_tolerance_seconds` でずれを許容する。
    このベクタの `exp` は 1600000000 である。
    """
    expired = CatToken.decode(CLAIM_VALIDATION_CASES[1][0]).claims

    with pytest.raises(ValueError, match="token is expired"):
        expired.validate(ClaimValidationOptions(reference_time_seconds=1600000001.0))

    # exp + 60 秒までは許容する
    expired.validate(
        ClaimValidationOptions(
            reference_time_seconds=1600000060.0,
            clock_tolerance_seconds=60.0,
        )
    )

    with pytest.raises(ValueError, match="token is expired"):
        expired.validate(
            ClaimValidationOptions(
                reference_time_seconds=1600000061.0,
                clock_tolerance_seconds=60.0,
            )
        )


@pytest.mark.parametrize(
    ("token_text", "key_hex", "expected_algorithm", "message"),
    SPOOFED_TOKENS,
    ids=["tampered-signature", "wrong-key", "algorithm-mismatch"],
)
def test_appendix_a6_signature_verification(
    token_text: str,
    key_hex: str,
    expected_algorithm: int | None,
    message: str,
) -> None:
    """
    付録 A.6 の署名検証が vector どおりの結果になることを確認する。

    改竄された署名、誤った鍵、期待するアルゴリズムとの不一致はすべて
    `ValueError` になる。
    """
    token = CatToken.decode(token_text)
    options = (
        None if expected_algorithm is None else VerifyOptions(expected_algorithm=expected_algorithm)
    )

    if options is None:
        with pytest.raises(ValueError, match=message):
            token.verify(CoseKey.symmetric(hex_bytes(key_hex)))
    else:
        with pytest.raises(ValueError, match=message):
            token.verify_with(CoseKey.symmetric(hex_bytes(key_hex)), options)


def test_non_finite_claim_is_rejected() -> None:
    """
    NaN や無限大の数値クレームが検証で拒否されることを確認する。

    非有限値は期限判定を素通りさせるため、decode と validate の両方で拒否する。
    """
    claims = CatToken.decode(TOKEN_HMAC_FULL).claims
    claims.expiration = float("nan")

    with pytest.raises(ValueError, match="exp must be finite"):
        claims.validate(ClaimValidationOptions(reference_time_seconds=1700000000.0))

    claims.expiration = None
    claims.moqt_reval = float("inf")
    with pytest.raises(ValueError, match="moqt-reval must be finite"):
        claims.validate(ClaimValidationOptions(reference_time_seconds=1700000000.0))


def test_decode_rejects_non_finite_claim() -> None:
    """
    非有限値の数値クレームを持つ CBOR がデコードの時点で拒否されることを確認する。

    CBOR の float64 の無限大は `fb 7f f0 00 00 00 00 00` である。
    """
    payload = hex_bytes("a104fb7ff0000000000000")

    with pytest.raises(ValueError, match="exp must be finite"):
        c4m.CatClaims.decode(c4m.decode_cbor(payload))


def test_build_compact_round_trip() -> None:
    """
    `CatTokenBuilder` が発行した compact トークンが検証と認可に通ることを確認する。

    HMAC-SHA256 の発行には RFC 9053 の HMAC 256/256 (5) を使い、ドラフトの
    別名 (-4) は使わない。
    """
    builder = CatTokenBuilder()
    builder.issuer("https://auth.example.com")
    builder.subject("user:alice")
    builder.audience("https://relay.example.com")
    builder.expiration(1700086400.0)
    builder.not_before(1700000000.0)
    builder.issued_at(1700000000.0)
    builder.cwt_id(b"vector-003")
    builder.moqt(moqt_claim_for_publish())
    builder.moqt_reval(300.0)
    builder.jwk_thumbprint(b"\x01" * 32)
    builder.catdpop(300.0, True)

    token_text = builder.build_compact(hmac_key())
    token = CatToken.decode(token_text)

    assert token.format == TokenFormat.COMPACT
    assert token.header.algorithm == Algorithm.HMAC_SHA256
    assert token.header.algorithm_identifier == 5
    assert token.header.key_id is None
    assert token.claims == builder.claims
    assert token.claims.cwt_id == b"vector-003"
    assert token.claims.moqt_reval == 300.0
    assert token.claims.confirmation is not None
    assert token.claims.confirmation.jkt() == b"\x01" * 32
    assert token.claims.catdpop is not None
    assert token.claims.catdpop.window_seconds_or(60.0) == 300.0
    assert token.claims.catdpop.honors_jti()

    token.verify(hmac_key())
    assert token.claims.authorize(MoqtAction.PUBLISH, (b"example.com",), b"video-hd")
    assert not token.claims.authorize(MoqtAction.PUBLISH, (b"example.com",), b"audio-main")


def test_build_cose_sign1_round_trip() -> None:
    """
    `CatTokenBuilder` が発行した COSE_Sign1 形式のトークンが検証に通ることを確認する。

    COSE 形式は CWT タグ (61) と COSE タグ (18) を付与し、署名対象は
    Sig_structure である。
    """
    builder = CatTokenBuilder()
    builder.issuer("https://auth.example.com")
    builder.audience("https://relay.example.com")
    builder.expiration(1700086400.0)
    builder.moqt(moqt_claim_for_publish())
    builder.algorithm = Algorithm.ES256
    builder.key_id = b"key-1"
    builder.typ = "CAT"

    token_bytes = builder.build_cose(es256_key())
    token = CatToken.decode(token_bytes)

    assert token.format == TokenFormat.COSE_SIGN1
    assert token.header.algorithm == Algorithm.ES256
    assert token.header.key_id == b"key-1"
    assert token.unprotected_header == []
    token.verify(es256_public_key())
    token.verify_with(es256_public_key(), VerifyOptions(expected_type=c4m.CAT_CONTENT_TYPE))
    assert token.claims.authorize(MoqtAction.PUBLISH, (b"example.com",), b"video-hd")


def test_build_cose_mac0_round_trip() -> None:
    """
    `CatTokenBuilder` が発行した COSE_Mac0 形式のトークンが検証に通ることを確認する。

    HMAC は COSE_Mac0 (タグ 17) になり、`signature` が MAC を表す。
    """
    builder = CatTokenBuilder()
    builder.issuer("https://auth.example.com")
    builder.expiration(1700086400.0)
    builder.moqt(moqt_claim_for_publish())

    token_bytes = builder.build_cose(hmac_key())
    token = CatToken.decode(token_bytes)

    assert token.format == TokenFormat.COSE_MAC0
    assert token.header.algorithm == Algorithm.HMAC_SHA256
    token.verify(hmac_key())


def test_cose_encoding_options_control_tags() -> None:
    """
    COSE 形式のタグの付与をオプションで制御できることを確認する。

    タグ無しで発行したトークンは CWT タグも COSE タグも持たない。
    """
    builder = CatTokenBuilder()
    builder.issuer("https://auth.example.com")
    builder.expiration(1700086400.0)

    options = CoseEncodingOptions(cose_tag=False, cwt_tag=False)
    token_bytes = builder.build_cose_with(hmac_key(), options)
    decoded = c4m.decode_cbor(token_bytes)

    # タグ無しの場合、最上位は 4 要素の配列である
    assert decoded.kind == "array"
    token = CatToken.decode(token_bytes)
    assert token.format == TokenFormat.COSE_MAC0
    assert token.claims.issuer == "https://auth.example.com"


def test_builder_claims_can_be_replaced() -> None:
    """
    ビルダーのクレームセットをデコード済みのクレームで置き換えられることを確認する。

    ゲッターは複製を返し、セッターは置き換えである。
    """
    decoded = CatToken.decode(TOKEN_HMAC_FULL).claims
    builder = CatTokenBuilder()
    builder.claims = decoded

    token = CatToken.decode(builder.build_compact(hmac_key()))

    assert token.claims == decoded


def test_builder_rejects_raw_typed_claim() -> None:
    """
    型付きフィールドを持つ claim key を raw へ置くと encode が拒否されることを確認する。

    `iss` を `claim` で追加した場合、型付きフィールドとの解釈のずれを防ぐため
    `ValueError` になる。
    """
    builder = CatTokenBuilder()
    builder.claim(c4m.CLAIM_ISSUER, CborValue.text_string("https://auth.example.com"))

    with pytest.raises(ValueError, match="duplicate claim key"):
        builder.build_compact(hmac_key())


def test_builder_signs_with_default_algorithm_per_key_type() -> None:
    """
    署名アルゴリズムを明示しない場合に鍵の種別から選ばれることを確認する。

    対称鍵は HMAC-SHA256、EC2 の P-256 は ES256 になる。
    """
    assert c4m.default_signing_algorithm(hmac_key()) == Algorithm.HMAC_SHA256
    assert c4m.default_signing_algorithm(es256_key()) == Algorithm.ES256

    builder = CatTokenBuilder()
    builder.expiration(1700086400.0)
    assert CatToken.decode(builder.build_cose(es256_key())).header.algorithm == Algorithm.ES256


def test_sign_and_verify_hmac() -> None:
    """
    HMAC の署名と検証が往復することを確認する。

    メッセージを変えると検証が失敗する。
    """
    key = hmac_key()
    message = b"message"
    signature = c4m.sign(Algorithm.HMAC_SHA256, key, message)

    assert len(signature) == 32
    c4m.verify(Algorithm.HMAC_SHA256, key, message, signature)

    with pytest.raises(ValueError, match="signature verification failed"):
        c4m.verify(Algorithm.HMAC_SHA256, key, b"other", signature)


def test_digest_vectors() -> None:
    """
    SHA-256 / SHA-384 / SHA-512 のハッシュが既知の値と一致することを確認する。

    入力は空メッセージである。
    """
    assert c4m.digest("sha256", b"").hex() == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    assert c4m.digest("sha384", b"").hex() == (
        "38b060a751ac96384cd9327eb1b1e36a21fdb71114be07434c0cc7bf63f6e1da"
        "274edebfe76f65fbd51ad2f14898b95b"
    )
    assert c4m.digest("sha512", b"").hex() == (
        "cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce"
        "47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e"
    )

    with pytest.raises(ValueError, match="unknown digest algorithm"):
        c4m.digest("md5", b"")


def test_sign_rejects_unsupported_algorithm() -> None:
    """
    対応していないアルゴリズムの識別子が拒否されることを確認する。

    RSA のアルゴリズムは未対応である。
    """
    with pytest.raises(ValueError, match="unsupported COSE algorithm"):
        c4m.sign(-257, hmac_key(), b"message")


def test_sign_requires_private_key() -> None:
    """
    秘密鍵を持たない鍵での署名が拒否されることを確認する。

    検証だけなら公開鍵で行える。
    """
    with pytest.raises(ValueError, match="private key is required for signing"):
        c4m.sign(Algorithm.ES256, es256_public_key(), b"message")

    key = es256_key()
    signature = c4m.sign(Algorithm.ES256, key, b"message")
    assert len(signature) == 64
    c4m.verify(Algorithm.ES256, es256_public_key(), b"message", signature)


def test_ed25519_sign_and_verify() -> None:
    """
    Ed25519 の署名と検証が往復することを確認する。

    OKP 鍵の秘密鍵は種 (32 バイト) である。
    """
    # RFC 8032 §7.1 のテストベクタ 1 の種と公開鍵
    seed = hex_bytes("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
    public_key = hex_bytes("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    key = CoseKey.ed25519_with_private_key(public_key, seed)
    signature = c4m.sign(Algorithm.EDDSA, key, b"")

    assert (
        signature.hex() == "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
        "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
    )
    c4m.verify(Algorithm.EDDSA, CoseKey.ed25519(public_key), b"", signature)
    assert c4m.default_signing_algorithm(key) == Algorithm.EDDSA


def test_jwk_thumbprint_matches_appendix_a4() -> None:
    """
    付録 A.4 の JWK の正規化 JSON と JWK サムプリントが vector と一致することを確認する。

    RFC 7638 §3.2 の正規化 JSON は必須メンバーを辞書順に並べ、空白を入れない。
    """
    jwk = es256_jwk()

    assert jwk.canonical_json() == (
        '{"crv":"P-256","kty":"EC","x":"YP7UuiVanTHJYet0xjVtaMBJuJI7Yfps5mliLmDyn7Y",'
        '"y":"eQP-EAi4vJmkGunpVii8ZPLxsgwtfp9Rd6PClNRGIpk"}'
    )
    assert jwk.thumbprint_sha256().hex() == (
        "0cebf1bc9880748a95588905b79843b42ba75cb174055e3e246bf87fe00b4a6d"
    )
    assert jwk.matches_public_key(es256_key())
    assert jwk.to_cose_key() == es256_public_key()


def test_jwk_normalizes_padded_base64url() -> None:
    """
    パディング付きの base64url を持つ JWK が正規化されることを確認する。

    `canonical_json` はパディング無しに正規化した値を返す。
    """
    jwk = Jwk.decode('{"kty":"EC","crv":"P-256","x":"AQ==","y":"AQ=="}')

    assert jwk.canonical_json() == '{"crv":"P-256","kty":"EC","x":"AQ","y":"AQ"}'


def test_jwk_rejects_private_members() -> None:
    """
    秘密鍵のメンバーを含む JWK が拒否されることを確認する。

    RFC 9449 §4.3 は DPoP proof の `jwk` に秘密鍵を含めることを禁止する。
    """
    with pytest.raises(ValueError, match="must not contain a private key: d"):
        Jwk.decode('{"kty":"EC","crv":"P-256","x":"AQ","y":"AQ","d":"AQ"}')


def test_jwk_rejects_duplicate_members() -> None:
    """
    `kty` が重複する JWK が拒否されることを確認する。

    RFC 7517 §4 はメンバー名の重複を許さない。
    """
    with pytest.raises(ValueError, match="duplicate JWK member"):
        Jwk.decode('{"kty":"EC","kty":"EC","crv":"P-256","x":"AQ","y":"AQ"}')


def test_rsa_jwk_cannot_be_converted_to_cose_key() -> None:
    """
    RSA の JWK が COSE の鍵表現へ変換できないことを確認する。

    COSE の鍵表現は RSA を持たず、RSA は未対応である。
    """
    jwk = Jwk.rsa("AQ", "AQ")

    assert jwk.kty == "RSA"
    with pytest.raises(ValueError, match="operation is not supported"):
        jwk.to_cose_key()


def test_cose_message_decode_and_reencode() -> None:
    """
    COSE 形式のトークンが COSE メッセージとしてデコード・再エンコードされることを確認する。

    再エンコードはタグを含めてバイト単位で一致する。
    """
    builder = CatTokenBuilder()
    builder.issuer("https://auth.example.com")
    builder.expiration(1700086400.0)
    token_bytes = builder.build_cose(hmac_key())

    message = CoseMessage.decode(token_bytes)

    assert message.kind == "mac0"
    assert message.cose_tagged
    assert message.cwt_tagged
    assert message.payload is not None
    assert message.header().algorithm == Algorithm.HMAC_SHA256
    assert message.encode() == token_bytes
    # 署名対象は MAC_structure である (RFC 9052 §6.3)
    assert message.signing_input().startswith(b"\x84dMAC0")


def test_cose_message_sign1_construction() -> None:
    """
    `CoseMessage.sign1` で組み立てたメッセージが署名と検証に使えることを確認する。

    protected ヘッダは `CoseHeader` からエンコードし、署名対象は Sig_structure に
    なる。
    """
    header = CoseHeader()
    header.algorithm = Algorithm.ES256
    header.typ = CborValue.text_string("CAT")

    unsigned = CoseMessage.sign1(protected=c4m.encode_cbor(header.encode()), payload=b"payload")
    assert unsigned.kind == "sign1"
    assert unsigned.signature == b""
    assert unsigned.signing_input().startswith(b"\x84\x6aSignature1")

    signature = c4m.sign(Algorithm.ES256, es256_key(), unsigned.signing_input())
    signed = CoseMessage.sign1(
        protected=unsigned.protected,
        payload=unsigned.payload,
        signature=signature,
    )
    encoded = signed.encode()

    decoded = CoseMessage.decode(encoded)
    assert decoded.kind == "sign1"
    c4m.verify(Algorithm.ES256, es256_public_key(), decoded.signing_input(), decoded.signature)


def test_cose_header_crit_rules() -> None:
    """
    `crit` のヘッダパラメータの規則が守られることを確認する。

    `crit` が指すラベルは同じ protected ヘッダに実在する必要がある
    (RFC 9052 §3.1)。
    """
    header = CoseHeader()
    header.algorithm = Algorithm.HMAC_SHA256
    header.critical = [CborValue.integer(c4m.HEADER_KEY_ID)]

    with pytest.raises(ValueError, match="crit lists a header parameter that is not in"):
        header.encode()


def test_cose_header_rejects_unprotected_typ() -> None:
    """
    unprotected ヘッダの `typ` が拒否されることを確認する。

    RFC 9596 §2 は `typ` を unprotected ヘッダに置かないことを MUST とする。
    """
    value = c4m.decode_cbor(hex_bytes("a11063434154"))

    with pytest.raises(ValueError, match="typ must not be in the unprotected header"):
        CoseHeader.decode_unprotected(value)


def test_jws_verify_and_header_errors() -> None:
    """
    JWS compact の検証とヘッダのエラー経路を確認する。

    `alg` は JOSE の名前から COSE の識別子へ変換する。`crit` を持つ JWS は
    拡張ヘッダを解釈しないため拒否する (RFC 7515 §4.1.11)。
    """
    proof_text = DpopProofBuilder(
        "id-1",
        1700000000.0,
        AuthorizationContext(
            context_type="moqt",
            action="PUB",
            track_namespace="example.2ecom",
            track_name="live",
        ),
    ).build(es256_key(), es256_jwk())
    jws = JwsCompact.decode(proof_text)

    assert jws.header.algorithm == Algorithm.ES256
    assert jws.header.typ == c4m.DPOP_PROOF_JWT_TYPE
    assert jws.header.jwk == es256_jwk()
    assert jws.header.key_id is None
    jws.verify(es256_public_key())

    with pytest.raises(ValueError, match="unsupported JWT algorithm"):
        JwsHeader.decode('{"alg":"none"}')
    with pytest.raises(ValueError, match="crit lists an extension header"):
        JwsHeader.decode('{"alg":"ES256","crit":["exp"]}')
    with pytest.raises(ValueError, match="duplicate JWT member"):
        JwsHeader.decode('{"alg":"ES256","alg":"ES256"}')


def test_dpop_proof_build_and_verify() -> None:
    """
    DPoP proof の発行と一連の検証が往復することを確認する。

    署名、鍵バインディング、Authorization Context、鮮度の順に検証する。
    """
    context = AuthorizationContext(
        context_type=c4m.MOQT_AUTHORIZATION_CONTEXT_TYPE,
        action=MoqtAction.PUBLISH_NAMESPACE.authorization_context,
        track_namespace="example.2ecom-alice",
        track_name="live",
        resource="moqt://relay.example.com?tns=example.2ecom-alice&tn=live",
    )
    builder = DpopProofBuilder("id-1", 1700000000.0, context)
    builder.key_id = "key-1"
    proof_text = builder.build(es256_key(), es256_jwk())
    proof = DpopProof.decode(proof_text)

    assert proof.header.typ == c4m.DPOP_PROOF_JWT_TYPE
    assert proof.header.algorithm == Algorithm.ES256
    assert proof.header.key_id == "key-1"
    assert proof.claims.jti == "id-1"
    assert proof.claims.issued_at == 1700000000.0
    # デコードした actx は生 JSON を持つため、型付きフィールドを比較する
    decoded_context = proof.claims.authorization_context
    assert decoded_context.context_type == context.context_type
    assert decoded_context.action == context.action
    assert decoded_context.track_namespace == context.track_namespace
    assert decoded_context.track_name == context.track_name
    assert decoded_context.resource == context.resource
    assert decoded_context.raw != ""
    assert proof.claims.nonce is None

    proof.verify_signature()
    proof.verify_authorization_context(
        MoqtAction.PUBLISH_NAMESPACE, (b"example.com", b"alice"), b"live"
    )
    proof.verify_freshness(1700000060.0, 60.0)

    confirmation = Confirmation()
    confirmation.jwk_thumbprint = es256_jwk().thumbprint_sha256()
    proof.verify_key_binding(confirmation)


def test_authorization_context_accepts_serialized_names() -> None:
    """
    `moqt.msf` の正規シリアライズ結果を `tns` / `tn` へそのまま渡せることを確認する。

    Track Namespace の `.` と Track 名の `-` はリテラルでないためエスケープが要る
    (draft-ietf-moq-transport-21 §8.8 (Representing Namespace and Track Names))。生の
    名前を渡すと `verify_target` が一致しないため、変換関数を通す。
    """
    namespace = [b"example.com"]
    track_name = b"video-hd"
    context = AuthorizationContext(
        context_type=c4m.MOQT_AUTHORIZATION_CONTEXT_TYPE,
        action=MoqtAction.PUBLISH.authorization_context,
        track_namespace=msf.serialize_namespace(namespace),
        track_name=msf.serialize_track_name(track_name),
    )

    assert context.track_namespace == "example.2ecom"
    assert context.track_name == "video.2dhd"
    context.verify_action(MoqtAction.PUBLISH)
    context.verify_target(namespace, track_name)

    # 生の名前を渡した場合は一致しない
    with pytest.raises(ValueError, match="does not match the target"):
        AuthorizationContext(
            context_type=c4m.MOQT_AUTHORIZATION_CONTEXT_TYPE,
            action=MoqtAction.PUBLISH.authorization_context,
            track_namespace="example.com",
            track_name="video-hd",
        ).verify_target(namespace, track_name)


def test_dpop_proof_freshness_errors() -> None:
    """
    DPoP proof の `iat` がウィンドウの外にある場合に拒否されることを確認する。
    """
    proof_text = DpopProofBuilder(
        "id-1",
        1700000000.0,
        AuthorizationContext(
            context_type="moqt",
            action="PUB",
            track_namespace="example.2ecom",
            track_name="live",
        ),
    ).build(es256_key(), es256_jwk())
    proof = DpopProof.decode(proof_text)

    with pytest.raises(ValueError, match="DPoP proof is too old"):
        proof.verify_freshness(1700000061.0, 60.0)
    with pytest.raises(ValueError, match="DPoP proof is issued in the future"):
        proof.verify_freshness(1699999939.0, 60.0)
    with pytest.raises(ValueError, match="freshness window must be finite"):
        proof.verify_freshness(1700000000.0, float("nan"))


def test_dpop_proof_rejects_symmetric_algorithm() -> None:
    """
    対称鍵アルゴリズムの DPoP proof が拒否されることを確認する。

    DPoP proof の署名は非対称アルゴリズムだけで行う。
    """
    with pytest.raises(ValueError, match="DPoP proof must use an asymmetric algorithm"):
        DpopProofBuilder(
            "id-1",
            1700000000.0,
            AuthorizationContext(
                context_type="moqt",
                action="PUB",
                track_namespace="example.2ecom",
                track_name="live",
            ),
        ).build(hmac_key(), es256_jwk())


def test_dpop_proof_rejects_key_mismatch() -> None:
    """
    署名鍵と埋め込む JWK が別の公開鍵である場合に拒否されることを確認する。

    公開鍵の取り違えを発行時に検出する。
    """
    other_jwk = Jwk.okp(
        "Ed25519",
        "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo",
    )

    with pytest.raises(ValueError, match="signing key does not match the embedded JWK"):
        DpopProofBuilder(
            "id-1",
            1700000000.0,
            AuthorizationContext(
                context_type="moqt",
                action="PUB",
                track_namespace="example.2ecom",
                track_name="live",
            ),
        ).build(es256_key(), other_jwk)


def test_dpop_proof_rejects_invalid_type() -> None:
    """
    `typ` が `"dpop-proof+jwt"` でない JWT が拒否されることを確認する。
    """
    header = hex_bytes("7b22616c67223a224553323536222c22747970223a226f74686572227d")
    payload = b"{}"
    token = (
        binascii.b2a_base64(header)[:-1].rstrip(b"=").decode()
        + "."
        + binascii.b2a_base64(payload)[:-1].rstrip(b"=").decode()
        + "."
    )

    with pytest.raises(ValueError, match="invalid DPoP typ"):
        DpopProof.decode(token)


def test_dpop_verify_against_cat_token_with_replay_cache() -> None:
    """
    CAT トークンに束縛した DPoP proof の一括検証を確認する。

    `catdpop` が jti の処理を要求する場合、リプレイキャッシュが必須であり、
    同じ jti の再送は拒否される。
    """
    builder = CatTokenBuilder()
    builder.issuer("https://auth.example.com")
    builder.expiration(1700086400.0)
    builder.moqt(moqt_claim_for_publish())
    builder.jwk_thumbprint(es256_jwk().thumbprint_sha256())
    builder.catdpop(60.0, True)
    token = CatToken.decode(builder.build_compact(hmac_key()))

    context = AuthorizationContext(
        context_type="moqt",
        action=MoqtAction.PUBLISH.authorization_context,
        # Track Name の `-` は §8.8 の正規シリアライズで `.2d` になる
        track_namespace="example.2ecom",
        track_name="video.2dhd",
    )
    proof_text = DpopProofBuilder("id-1", 1700000000.0, context).build(es256_key(), es256_jwk())
    proof = DpopProof.decode(proof_text)

    cache = DpopReplayCache()

    # ath が無い proof をアクセストークン付きで検証すると拒否される
    with pytest.raises(ValueError, match="ath is required"):
        proof.verify_against_cat_token(
            token,
            MoqtAction.PUBLISH,
            (b"example.com",),
            b"video-hd",
            1700000060.0,
            60.0,
            cache,
        )

    # ath を付けて発行すると一括検証が通る
    digest = c4m.digest("sha256", token.raw_token)
    ath = binascii.b2a_base64(digest)[:-1].rstrip(b"=").decode().replace("+", "-").replace("/", "_")
    builder = DpopProofBuilder("id-1", 1700000000.0, context)
    builder.access_token_hash = ath
    proof_text = builder.build(es256_key(), es256_jwk())
    proof = DpopProof.decode(proof_text)
    proof.verify_against_cat_token(
        token,
        MoqtAction.PUBLISH,
        (b"example.com",),
        b"video-hd",
        1700000060.0,
        60.0,
        cache,
    )
    assert len(cache) == 1

    # 同じ jti の再送は拒否される
    replay = DpopProof.decode(proof_text)
    with pytest.raises(ValueError, match="jti was already used"):
        replay.verify_against_cat_token(
            token,
            MoqtAction.PUBLISH,
            (b"example.com",),
            b"video-hd",
            1700000060.0,
            60.0,
            cache,
        )


def test_dpop_verify_against_token_without_access_token() -> None:
    """
    アクセストークンを伴わない DPoP proof を `DpopVerification` で検証できることを確認する。

    token endpoint など、アクセストークンを伴わない proof では `access_token` に
    `None` を渡す。
    """
    builder = CatTokenBuilder()
    builder.issuer("https://auth.example.com")
    builder.expiration(1700086400.0)
    builder.jwk_thumbprint(es256_jwk().thumbprint_sha256())
    builder.catdpop(60.0, False)
    token = CatToken.decode(builder.build_compact(hmac_key()))

    context = AuthorizationContext(
        context_type="moqt",
        action=MoqtAction.PUBLISH.authorization_context,
        track_namespace="example.2ecom",
        # Track Name の `-` は §8.8 の正規シリアライズで `.2d` になる
        track_name="video.2dhd",
    )
    proof = DpopProof.decode(
        DpopProofBuilder("id-1", 1700000000.0, context).build(es256_key(), es256_jwk())
    )
    request = DpopVerification(
        token.claims,
        MoqtAction.PUBLISH,
        (b"example.com",),
        b"video-hd",
        1700000060.0,
        60.0,
    )

    assert request.action == MoqtAction.PUBLISH
    assert request.track_name == b"video-hd"
    assert request.access_token is None
    proof.verify_against_token(request)

    # アクセストークンを渡すと ath が必須になる
    request_with_token = DpopVerification(
        token.claims,
        MoqtAction.PUBLISH,
        (b"example.com",),
        b"video-hd",
        1700000060.0,
        60.0,
        access_token=token.raw_token,
    )
    with pytest.raises(ValueError, match="ath is required"):
        proof.verify_against_token(request_with_token)


def test_access_token_hash_verification() -> None:
    """
    `ath` の照合がハッシュの一致で行われることを確認する。

    `ath` が proof に無い場合は何も行わない。
    """
    context = AuthorizationContext(
        context_type="moqt",
        action="PUB",
        track_namespace="example.2ecom",
        track_name="live",
    )
    digest = c4m.digest("sha256", b"token-abc")
    ath = binascii.b2a_base64(digest)[:-1].rstrip(b"=").decode().replace("+", "-").replace("/", "_")
    builder = DpopProofBuilder("id-1", 1700000000.0, context)
    builder.access_token_hash = ath
    proof = DpopProof.decode(builder.build(es256_key(), es256_jwk()))

    assert proof.claims.access_token_hash == ath
    proof.verify_access_token_hash("token-abc")
    proof.verify_access_token_hash_bytes(b"token-abc")
    with pytest.raises(ValueError, match="ath does not match the access token"):
        proof.verify_access_token_hash("other")


def test_replay_cache_expires_old_entries() -> None:
    """
    リプレイキャッシュがウィンドウ外の古い記録を破棄することを確認する。

    同じ jti でもウィンドウを過ぎれば再び受理される。
    """
    cache = DpopReplayCache()
    cache.check_and_record("id-1", 1700000000.0, 60.0, 1700000000.0)

    assert len(cache) == 1
    with pytest.raises(ValueError, match="jti was already used"):
        cache.check_and_record("id-1", 1700000000.0, 60.0, 1700000030.0)

    # ウィンドウを過ぎた記録は破棄される
    cache.check_and_record("id-1", 1700000000.0, 60.0, 1700000061.0)
    assert len(cache) == 1


def test_appendix_a4_dpop_binding_claims() -> None:
    """
    付録 A.4 の DPoP バインディングのトークンの `cnf` と `catdpop` を確認する。

    1 つ目は confirmation key 3 (ドラフトのベクタ) の `jkt` と jti のリプレイ保護、
    2 つ目はウィンドウ 300 秒と jti の無効化、
    3 つ目は confirmation key 3 の `jkt` と catdpop のウィンドウだけを持つ。
    """
    binding = CatToken.decode(TOKEN_DPOP_JWK_BINDING).claims

    assert binding.confirmation is not None
    assert binding.confirmation.jkt() == hex_bytes(
        "a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1"
    )
    assert binding.confirmation.jwk_thumbprint is None
    assert binding.catdpop is not None
    assert binding.catdpop.window_seconds_or(0.0) == 60.0
    assert binding.catdpop.honors_jti()

    no_jti = CatToken.decode(TOKEN_DPOP_NO_JTI).claims
    assert no_jti.catdpop is not None
    assert no_jti.catdpop.window_seconds_or(0.0) == 300.0
    assert not no_jti.catdpop.honors_jti()

    es256 = CatToken.decode(TOKEN_DPOP_ES256).claims
    assert es256.confirmation is not None
    assert es256.confirmation.jkt() == es256_jwk().thumbprint_sha256()
    assert es256.catdpop is not None
    assert es256.catdpop.window_seconds_or(0.0) == 120.0
    assert not es256.catdpop.honors_jti()


def test_authorization_context_decode_and_errors() -> None:
    """
    Authorization Context の JSON のデコードと整合検証を確認する。

    `resource` が与えられている場合は `tns` / `tn` と整合する必要がある
    (draft-ietf-moq-c4m-01 §3.1.3)。
    """
    context = AuthorizationContext.decode(
        '{"type":"moqt","action":"PUB_NS","tns":"example.2ecom","tn":"live",'
        '"resource":"moqt://relay.example.com?tns=example.2ecom&tn=live"}'
    )

    assert context.context_type == "moqt"
    assert context.action == "PUB_NS"
    assert context.track_namespace == "example.2ecom"
    assert context.track_name == "live"
    context.verify_context_type(c4m.MOQT_AUTHORIZATION_CONTEXT_TYPE)
    context.verify_action(MoqtAction.PUBLISH_NAMESPACE)
    context.verify_target((b"example.com",), b"live")
    context.verify_resource_consistency()

    with pytest.raises(ValueError, match=r"actx\.type does not match"):
        context.verify_context_type("other")
    with pytest.raises(ValueError, match=r"actx\.action does not match"):
        context.verify_action(MoqtAction.SUBSCRIBE)
    with pytest.raises(ValueError, match=r"actx\.tns or actx\.tn does not match"):
        context.verify_target((b"other.example",), b"live")
    with pytest.raises(ValueError, match="duplicate DPoP member"):
        AuthorizationContext.decode('{"type":"moqt","type":"moqt"}')


def test_match_and_namespace_match_api() -> None:
    """
    `Match` と `NamespaceMatch` の構築・判定・CBOR 往復を確認する。

    prefix と suffix は match-type を伴う配列としてエンコードされる。
    """
    exact = Match.exact(b"example.com")
    prefix = Match.prefix(b"video-")
    suffix = Match.suffix(b"-audio")
    end = NamespaceMatch.end()
    matched = NamespaceMatch.match(prefix)

    assert exact.kind == "exact"
    assert prefix.kind == "prefix"
    assert suffix.kind == "suffix"
    assert exact.matches(b"example.com")
    assert not exact.matches(b"example")
    assert prefix.matches(b"video-hd")
    assert not prefix.matches(b"audio")
    assert suffix.matches(b"stream-audio")
    assert not suffix.matches(b"audio-stream")
    assert end.kind == "end"
    assert end.matcher is None
    assert matched.matcher == prefix
    assert matched.kind == "match"

    assert c4m.encode_cbor(prefix.encode()) == hex_bytes("820146766964656f2d")
    assert Match.decode(prefix.encode()) == prefix
    assert Match.decode(exact.encode()) == exact


def test_moqt_scope_round_trip_and_allows() -> None:
    """
    `MoqtScope` の CBOR 往復と認可判定を確認する。

    アクション無し、末尾以外の `nil`、名前空間無しのトラックマッチは encode で
    拒否される。
    """
    scope = MoqtScope([MoqtAction.PUBLISH, MoqtAction.FETCH])
    scope.namespace_match(NamespaceMatch.match(Match.exact(b"example.com")))
    scope.namespace_end()
    scope.track = Match.prefix(b"video-")

    encoded = scope.encode()
    decoded = MoqtScope.decode(encoded)

    assert decoded == scope
    assert decoded.actions == [6, 7]
    assert decoded.track == Match.prefix(b"video-")
    assert decoded.allows(MoqtAction.PUBLISH, (b"example.com",), b"video-hd")
    assert not decoded.allows(MoqtAction.PUBLISH, (b"example.com", b"alice"), b"video-hd")
    assert not decoded.allows(MoqtAction.SUBSCRIBE, (b"example.com",), b"video-hd")

    empty = MoqtScope([])
    with pytest.raises(ValueError, match="moqt-scope has no actions"):
        empty.encode()

    nil_not_last = MoqtScope([MoqtAction.PUBLISH])
    nil_not_last.namespace_end()
    nil_not_last.namespace_match(NamespaceMatch.match(Match.exact(b"example.com")))
    with pytest.raises(ValueError, match="nil must be the last"):
        nil_not_last.encode()

    track_without_namespace = MoqtScope([MoqtAction.PUBLISH])
    track_without_namespace.track = Match.exact(b"video")
    with pytest.raises(ValueError, match="track match without a namespace match"):
        track_without_namespace.encode()


def test_moqt_claim_round_trip() -> None:
    """
    `MoqtClaim` の CBOR 往復と複数スコープの認可を確認する。

    いずれかのスコープが認可すれば許可になり、評価順は問わない。
    """
    claim = MoqtClaim()
    claim.scope(moqt_claim_for_publish().scopes[0])
    other = MoqtScope([MoqtAction.SUBSCRIBE])
    other.namespace_end()
    claim.scope(other)

    decoded = MoqtClaim.decode(claim.encode())

    assert decoded == claim
    assert len(decoded.scopes) == 2
    assert decoded.authorize(MoqtAction.PUBLISH, (b"example.com",), b"video-hd")
    # 2 つ目のスコープは名前空間の末尾を nil で固定しているため、空の名前空間だけに一致する
    assert decoded.authorize(MoqtAction.SUBSCRIBE, (), b"audio")
    assert not decoded.authorize(MoqtAction.SUBSCRIBE, (b"anything",), b"audio")


def test_catdpop_round_trip_and_unknown_labels() -> None:
    """
    `CatDpop` の CBOR 往復と未知の label の保持を確認する。

    label 0 はウィンドウ、label 1 は jti の扱いであり、それ以外は raw に残る。
    """
    catdpop = c4m.CatDpop(120.0, False)
    catdpop.raw = [(2, CborValue.text_string("extension"))]

    decoded = c4m.CatDpop.decode(catdpop.encode())

    assert decoded == catdpop
    assert decoded.window_seconds == 120.0
    assert decoded.honor_jti is False
    assert decoded.honors_jti() is False
    assert decoded.raw == [(2, CborValue.text_string("extension"))]


def test_cbor_value_api() -> None:
    """
    `CborValue` の variant ごとの取り出しを確認する。

    `kind` と `as_*` の対応、マップのキー参照、タグの取り出しを検証する。
    """
    assert CborValue.unsigned(1).kind == "unsigned"
    assert CborValue.integer(-1).as_int() == -1
    assert CborValue.integer(-1).kind == "negative"
    assert CborValue.byte_string(b"x").as_bytes() == b"x"
    assert CborValue.text_string("x").as_text() == "x"
    assert CborValue.boolean(True).as_bool() is True
    assert CborValue.null().kind == "null"
    assert CborValue.undefined().kind == "undefined"
    assert CborValue.float_value(1.5).as_number() == 1.5
    assert CborValue.simple(16).as_simple() == 16
    assert CborValue.unsigned(1).as_number() == 1.0

    array = CborValue.array([CborValue.unsigned(1), CborValue.text_string("x")])
    assert array.as_array() == [CborValue.unsigned(1), CborValue.text_string("x")]

    mapping = CborValue.map([(CborValue.unsigned(1), CborValue.text_string("one"))])
    assert mapping.map_get(CborValue.unsigned(1)) == CborValue.text_string("one")
    assert mapping.map_get(CborValue.unsigned(2)) is None

    tagged = CborValue.tag(61, CborValue.null())
    assert tagged.as_tag() == (61, CborValue.null())
    assert tagged.kind == "tag"


def test_cbor_decode_limits() -> None:
    """
    CBOR のデコードの制限を確認する。

    末尾の余分なバイト、予約された単純値、重複したマップのキーは拒否される。
    `decode_cbor_partial` は先頭のデータ項目だけを消費する。
    """
    value, consumed = c4m.decode_cbor_partial(b"\x01\x02")
    assert value == CborValue.unsigned(1)
    assert consumed == 1

    with pytest.raises(ValueError, match="trailing bytes after the data item"):
        c4m.decode_cbor(b"\x01\x02")
    with pytest.raises(ValueError, match="invalid simple value"):
        c4m.decode_cbor(b"\xf8\x18")
    with pytest.raises(ValueError, match="duplicate map key"):
        c4m.decode_cbor(b"\xa2\x01\x01\x01\x02")


def test_cbor_indefinite_length_is_accepted() -> None:
    """
    indefinite 長の配列とバイト文字列が受理されることを確認する。

    再 encode は definite 長の最短形になる。
    """
    # (`_` で終端する indefinite 長の配列 `[1, 2]`)
    value = c4m.decode_cbor(b"\x9f\x01\x02\xff")

    assert value.as_array() == [CborValue.unsigned(1), CborValue.unsigned(2)]
    assert c4m.encode_cbor(value) == b"\x82\x01\x02"

    # (`_` で終端する indefinite 長のバイト文字列のチャンク)
    chunks = c4m.decode_cbor(b"\x5f\x41a\x41b\xff")
    assert chunks.as_bytes() == b"ab"


def test_cbor_depth_limit() -> None:
    """
    ネスト深度の上限を超えた CBOR が拒否されることを確認する。

    上限は `CBOR_MAX_DEPTH` である。
    """
    nested = b"\x81" * (c4m.CBOR_MAX_DEPTH + 1) + b"\x00"

    with pytest.raises(ValueError, match="nesting depth exceeds"):
        c4m.decode_cbor(nested)


def test_moqt_action_and_algorithm_enums() -> None:
    """
    `MoqtAction` と `Algorithm` の補助 API を確認する。

    値は wire 上の識別子と一致し、Authorization Context や JOSE の名前へ変換できる。
    """
    assert MoqtAction.from_key(6) == MoqtAction.PUBLISH
    assert MoqtAction.PUBLISH.authorization_context == "PUBLISH"
    assert MoqtAction.CLIENT_SETUP.authorization_context == "SETUP"
    assert MoqtAction.SERVER_SETUP.matches_authorization_context("SETUP")
    assert not MoqtAction.PUBLISH.matches_authorization_context("SUBSCRIBE")

    with pytest.raises(ValueError, match="is not a valid MoqtAction"):
        MoqtAction.from_key(99)

    assert Algorithm.from_identifier(5) == Algorithm.HMAC_SHA256
    assert Algorithm.from_identifier_with_c4m_draft_alias(-4) == Algorithm.HMAC_SHA256
    with pytest.raises(ValueError, match="is not a valid Algorithm"):
        Algorithm.from_identifier(-4)

    assert Algorithm.HMAC_SHA256.is_mac
    assert not Algorithm.ES256.is_mac
    assert Algorithm.HMAC_SHA256.jose_name == "HS256"
    assert Algorithm.ES256.jose_name == "ES256"
    assert Algorithm.EDDSA.jose_name == "EdDSA"
    assert Algorithm.ES256.context == "Signature1"
    assert Algorithm.HMAC_SHA256.context == "MAC0"
    assert Algorithm.ES256.tag == c4m.TAG_COSE_SIGN1
    assert Algorithm.HMAC_SHA256.tag == c4m.TAG_COSE_MAC0
    assert Algorithm.from_jose_name("EdDSA") == Algorithm.EDDSA
    with pytest.raises(ValueError, match="unsupported JOSE algorithm"):
        Algorithm.from_jose_name("none")


def test_ec_and_okp_curve_enums() -> None:
    """
    `EcCurve` と `OkpCurve` の座標長と識別子を確認する。

    座標長は ES256 / ES384 / ES512 の署名長の半分である。
    """
    assert EcCurve.P256.coordinate_length == 32
    assert EcCurve.P384.coordinate_length == 48
    assert EcCurve.P521.coordinate_length == 66
    assert OkpCurve.ED25519 == 6
    assert c4m.EcCurve(1) == EcCurve.P256


def test_cose_key_api() -> None:
    """
    `CoseKey` の構築と属性の読み出しを確認する。

    秘密鍵は `repr` に値としては現れない。
    """
    key = es256_key()

    assert key.kind == "ec2"
    assert key.curve == EcCurve.P256
    assert key.x == hex_bytes(ES256_PUBLIC_KEY_X_HEX)
    assert key.y == hex_bytes(ES256_PUBLIC_KEY_Y_HEX)
    assert key.private_key == hex_bytes(ES256_PRIVATE_KEY_HEX)
    assert "private_key_bytes=32" in repr(key)
    assert ES256_PRIVATE_KEY_HEX not in repr(key)

    symmetric = CoseKey.symmetric(b"\x01" * 32)
    assert symmetric.kind == "symmetric"
    assert symmetric.key == b"\x01" * 32
    assert symmetric.curve is None
    assert symmetric.private_key is None


def test_confirmation_api() -> None:
    """
    `Confirmation` の IANA の `jkt` とドラフトの `jkt` の優先順位を確認する。

    `jkt` は confirmation key 323 を優先し、無ければ 3 を返す。
    """
    confirmation = Confirmation()
    confirmation.c4m_draft_jwk_thumbprint = b"\x01" * 32

    assert confirmation.jkt() == b"\x01" * 32

    confirmation.jwk_thumbprint = b"\x02" * 32
    assert confirmation.jwk_thumbprint == b"\x02" * 32
    assert confirmation.c4m_draft_jwk_thumbprint == b"\x01" * 32
    assert confirmation.jkt() == b"\x02" * 32

    decoded = Confirmation.decode(confirmation.encode())
    assert decoded == confirmation


def test_cat_claims_raw_get() -> None:
    """
    型付きで解釈しないクレームが `raw` と `get` で読めることを確認する。

    `catv` などの CAT 固有クレームの値の意味論は評価しない。
    """
    claims = CatToken.decode(TOKEN_HMAC_FULL).claims

    cat_version = claims.get(c4m.CLAIM_CAT_VERSION)
    network_ip = claims.get(c4m.CLAIM_CAT_NETWORK_IP)
    assert cat_version is not None
    assert cat_version.as_text() == "CAT-v1"
    assert network_ip is not None
    assert network_ip.kind == "array"
    assert claims.get(c4m.CLAIM_CAT_METHOD) is None


def test_cat_claims_encode_rejects_typed_raw() -> None:
    """
    型付きフィールドを持つ claim key を raw へ置いた場合の encode が拒否されることを確認する。
    """
    claims = CatClaims()
    claims.raw = [(CborValue.integer(c4m.CLAIM_MOQT), CborValue.array([]))]

    with pytest.raises(ValueError, match="duplicate claim key"):
        claims.encode()


def test_module_exports_are_consistent() -> None:
    """
    `moqt.c4m` の `__all__` の名前がすべて参照できることを確認する。

    公開 API の取りこぼしを検出する。
    """
    for name in c4m.__all__:
        assert hasattr(c4m, name), name
