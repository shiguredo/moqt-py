"""C4M (Common Access Token for MoQ) の codec と認可。

draft-ietf-moq-c4m-01 の `moqt` / `moqt-reval` クレームと、その基盤となる
CBOR (RFC 8949) / COSE (RFC 9052) / CWT (RFC 8392) / CAT (CTA-5007-B) の
トークンを扱う。JWK (RFC 7517) / JWS compact (RFC 7515) / DPoP proof
(draft-nandakumar-moq-generic-dpop-proof-00) も公開する。

- クレーム: `MoqtAction` / `Match` / `NamespaceMatch` / `MoqtScope` / `MoqtClaim` /
  `CatDpop`
- CBOR: `CborValue` と `encode_cbor` / `decode_cbor` / `decode_cbor_partial`
- COSE: `CoseHeader` / `CoseMessage` / `CoseEncodingOptions`
- 鍵と暗号: `CoseKey` / `EcCurve` / `OkpCurve` と `sign` / `verify` / `digest`
- CAT: `CatToken` / `CatClaims` / `Confirmation` / `CatTokenBuilder` と検証オプション
- JWK / JWT: `Jwk` / `JwsHeader` / `JwsCompact`
- DPoP: `DpopProof` / `DpopProofBuilder` / `AuthorizationContext` / `DpopReplayCache`

署名と検証の暗号実装は aws-lc-rs に固定する。moqt-rs の `CoseCrypto` trait に
相当する抽象は公開せず、`sign` / `verify` / `digest` が aws-lc-rs を直接呼ぶ。

整数の識別子を持つ enum (`MoqtAction` / `Algorithm` / `EcCurve` / `OkpCurve`) は
`enum.IntEnum` として公開する。値は wire 上の識別子と同じであり、native 側の
関数は整数を受け取るため、enum のメンバーをそのまま渡せる。

Track Namespace は `tuple[bytes, ...]`、Track Name は `bytes` で扱う。デコードと
検証の失敗は `ValueError` になる。

C4M は draft 由来であり、将来の改訂で変更される可能性がある。
"""

import enum

from moqt import _native
from moqt._native import (
    AuthorizationContext,
    CatClaims,
    CatDpop,
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
    DpopProofClaims,
    DpopProofHeader,
    DpopReplayCache,
    DpopVerification,
    Jwk,
    JwsCompact,
    JwsHeader,
    Match,
    MoqtClaim,
    MoqtScope,
    NamespaceMatch,
    VerifyOptions,
    decode_cbor,
    decode_cbor_partial,
    default_signing_algorithm,
    digest,
    encode_cbor,
    sign,
    verify,
)

# `moqt` / `moqt-reval` の claim key (draft-ietf-moq-c4m-01 §2)
CLAIM_MOQT: int = _native.CLAIM_MOQT
"""`moqt` クレームの claim key (付録 A.5 のベクタが使う 327)。"""

CLAIM_MOQT_REVAL: int = _native.CLAIM_MOQT_REVAL
"""`moqt-reval` クレームの claim key (付録 A.5 のベクタが使う 328)。"""

# `bin-match` の match-type (draft-ietf-moq-c4m-01 §2.1)
MATCH_TYPE_PREFIX: int = _native.MATCH_TYPE_PREFIX
"""`bin-match` の前方一致を表す match-type。"""

MATCH_TYPE_SUFFIX: int = _native.MATCH_TYPE_SUFFIX
"""`bin-match` の後方一致を表す match-type。"""

# CBOR のネスト深度の上限 (RFC 8949)
CBOR_MAX_DEPTH: int = _native.CBOR_MAX_DEPTH
"""CBOR のデコード / エンコードで許容するネスト深度の上限。"""

# COSE の CBOR タグ (RFC 8392 §6 / RFC 9052 §4.2 / §6.2)
TAG_CWT: int = _native.TAG_CWT
"""CWT の CBOR タグ (61)。"""

TAG_COSE_MAC0: int = _native.TAG_COSE_MAC0
"""COSE_Mac0 の CBOR タグ (17)。"""

TAG_COSE_SIGN1: int = _native.TAG_COSE_SIGN1
"""COSE_Sign1 の CBOR タグ (18)。"""

# COSE のヘッダパラメータ (RFC 9052 §3.1 / RFC 9596 §2)
HEADER_ALGORITHM: int = _native.HEADER_ALGORITHM
"""ヘッダパラメータ `alg` (1)。"""

HEADER_CRITICAL: int = _native.HEADER_CRITICAL
"""ヘッダパラメータ `crit` (2)。"""

HEADER_CONTENT_TYPE: int = _native.HEADER_CONTENT_TYPE
"""ヘッダパラメータ `content type` (3)。"""

HEADER_KEY_ID: int = _native.HEADER_KEY_ID
"""ヘッダパラメータ `kid` (4)。"""

HEADER_TYPE: int = _native.HEADER_TYPE
"""ヘッダパラメータ `typ` (16)。"""

C4M_DRAFT_HMAC_SHA256_ALGORITHM_ID: int = _native.C4M_DRAFT_HMAC_SHA256_ALGORITHM_ID
"""draft-ietf-moq-c4m-01 付録 A のベクタが HMAC-SHA256 に使う識別子 (-4)。

検証では HMAC-SHA256 として受理し、発行には使わない。
"""

# CWT の claim key (RFC 8392 §3.1)
CLAIM_ISSUER: int = _native.CLAIM_ISSUER
"""`iss`。"""

CLAIM_SUBJECT: int = _native.CLAIM_SUBJECT
"""`sub`。"""

CLAIM_AUDIENCE: int = _native.CLAIM_AUDIENCE
"""`aud`。"""

CLAIM_EXPIRATION: int = _native.CLAIM_EXPIRATION
"""`exp` (UNIX 秒)。"""

CLAIM_NOT_BEFORE: int = _native.CLAIM_NOT_BEFORE
"""`nbf` (UNIX 秒)。"""

CLAIM_ISSUED_AT: int = _native.CLAIM_ISSUED_AT
"""`iat` (UNIX 秒)。"""

CLAIM_CWT_ID: int = _native.CLAIM_CWT_ID
"""`cti`。"""

CLAIM_CONFIRMATION: int = _native.CLAIM_CONFIRMATION
"""`cnf`。"""

# CAT の claim key (IANA CWT Claims レジストリ / CTA-5007)
CLAIM_CAT_REPLAY: int = _native.CLAIM_CAT_REPLAY
"""`catreplay` (308)。"""

CLAIM_CAT_PROBABILITY_OF_REJECTION: int = _native.CLAIM_CAT_PROBABILITY_OF_REJECTION
"""`catpor` (309)。"""

CLAIM_CAT_VERSION: int = _native.CLAIM_CAT_VERSION
"""`catv` (310)。"""

CLAIM_CAT_NETWORK_IP: int = _native.CLAIM_CAT_NETWORK_IP
"""`catnip` (311)。"""

CLAIM_CAT_URI: int = _native.CLAIM_CAT_URI
"""`catu` (312)。"""

CLAIM_CAT_METHOD: int = _native.CLAIM_CAT_METHOD
"""`catm` (313)。"""

CLAIM_CAT_ALPN: int = _native.CLAIM_CAT_ALPN
"""`catalpn` (314)。"""

CLAIM_CAT_HEADER: int = _native.CLAIM_CAT_HEADER
"""`cath` (315)。"""

CLAIM_CAT_GEO_ISO3166: int = _native.CLAIM_CAT_GEO_ISO3166
"""`catgeoiso3166` (316)。"""

CLAIM_CAT_GEO_COORD: int = _native.CLAIM_CAT_GEO_COORD
"""`catgeocoord` (317)。"""

CLAIM_CAT_GEO_ALT: int = _native.CLAIM_CAT_GEO_ALT
"""`catgeoalt` (318)。"""

CLAIM_CAT_TLS_PUBLIC_KEY: int = _native.CLAIM_CAT_TLS_PUBLIC_KEY
"""`cattpk` (319)。"""

CLAIM_CAT_IF_DATA: int = _native.CLAIM_CAT_IF_DATA
"""`catifdata` (320)。"""

CLAIM_CAT_DPOP: int = _native.CLAIM_CAT_DPOP
"""`catdpop` (321)。"""

CLAIM_CAT_IF: int = _native.CLAIM_CAT_IF
"""`catif` (322)。"""

CLAIM_CAT_RENEWAL: int = _native.CLAIM_CAT_RENEWAL
"""`catr` (323)。"""

# `cnf` の `jkt` の confirmation key
CONFIRMATION_JWK_THUMBPRINT: int = _native.CONFIRMATION_JWK_THUMBPRINT
"""IANA 登録の `jkt` の confirmation key (323)。"""

CONFIRMATION_C4M_DRAFT_JWK_THUMBPRINT: int = _native.CONFIRMATION_C4M_DRAFT_JWK_THUMBPRINT
"""draft-ietf-moq-c4m-01 のベクタが使う `jkt` の confirmation key (3)。"""

# MOQT の Auth Token Type (draft-ietf-moq-c4m-01 §7.1)
MOQT_AUTH_TOKEN_TYPE_CAT: int = _native.MOQT_AUTH_TOKEN_TYPE_CAT
"""CAT の Auth Token Type (0x01)。"""

CAT_CONTENT_TYPE: str = _native.CAT_CONTENT_TYPE
"""CAT の COSE ヘッダの `typ` の値 (`"CAT"`)。"""

# DPoP (draft-nandakumar-moq-generic-dpop-proof-00)
DPOP_PROOF_JWT_TYPE: str = _native.DPOP_PROOF_JWT_TYPE
"""DPoP proof の JWT の `typ` (`"dpop-proof+jwt"`、§4.3.1)。"""

MOQT_AUTHORIZATION_CONTEXT_TYPE: str = _native.MOQT_AUTHORIZATION_CONTEXT_TYPE
"""MOQT の Authorization Context の `type` (`"moqt"`、§5.1)。"""


class MoqtAction(enum.IntEnum):
    """`moqt` クレームのアクション (draft-ietf-moq-c4m-01 §2.1 Table 1)。

    メンバー名は MOQT のメッセージ名と同じである。値は `moqt-actions` の識別子で
    あり、`MoqtScope.actions` と `CatClaims.authorize` にそのまま渡せる。
    """

    CLIENT_SETUP = 0
    SERVER_SETUP = 1
    PUBLISH_NAMESPACE = 2
    SUBSCRIBE_NAMESPACE = 3
    SUBSCRIBE = 4
    REQUEST_UPDATE = 5
    PUBLISH = 6
    FETCH = 7
    TRACK_STATUS = 8

    @classmethod
    def from_key(cls, key: int) -> MoqtAction:
        """アクションの識別子からアクションを返す。

        未知の識別子の場合は `ValueError` になる。
        """
        return cls(key)

    @property
    def authorization_context(self) -> str:
        """DPoP の Authorization Context で使うアクション識別子 (Table 2)。"""
        return _MOQT_AUTHORIZATION_CONTEXTS[self]

    def matches_authorization_context(self, value: str) -> bool:
        """DPoP の Authorization Context のアクション識別子と一致するか返す。

        CLIENT_SETUP と SERVER_SETUP はどちらも `"SETUP"` を使う (Table 2)。
        """
        return self.authorization_context == value


class Algorithm(enum.IntEnum):
    """COSE のアルゴリズム (RFC 9053 §2 / §3 のレジストリ値)。

    対応するのは HMAC 256/384/512、ES256/384/512、EdDSA (Ed25519) である。
    RSA は未対応である。
    """

    HMAC_SHA256 = 5
    HMAC_SHA384 = 6
    HMAC_SHA512 = 7
    ES256 = -7
    ES384 = -35
    ES512 = -36
    EDDSA = -8

    @classmethod
    def from_identifier(cls, identifier: int) -> Algorithm:
        """COSE のアルゴリズム識別子からアルゴリズムを返す。

        ドラフトの別名 (`-4` を HMAC-SHA256 とする) は含めない。別名を解決する
        場合は `from_identifier_with_c4m_draft_alias` を使う。
        """
        return cls(identifier)

    @classmethod
    def from_identifier_with_c4m_draft_alias(cls, identifier: int) -> Algorithm:
        """ドラフトの別名を含めてアルゴリズム識別子を解決する。

        `C4M_DRAFT_HMAC_SHA256_ALGORITHM_ID` (`-4`) を HMAC-SHA256 として受理する。
        """
        if identifier == C4M_DRAFT_HMAC_SHA256_ALGORITHM_ID:
            return cls.HMAC_SHA256
        return cls(identifier)

    @classmethod
    def from_jose_name(cls, name: str) -> Algorithm:
        """JOSE の `alg` 名 (ES256 など) からアルゴリズムを返す。

        対応していない名前の場合は `ValueError` になる。
        """
        try:
            return _JOSE_ALGORITHMS[name]
        except KeyError:
            raise ValueError(f"unsupported JOSE algorithm: {name}") from None

    @property
    def is_mac(self) -> bool:
        """MAC アルゴリズムかどうか。"""
        return self in _MAC_ALGORITHMS

    @property
    def jose_name(self) -> str:
        """JOSE の `alg` 名 (RFC 7518 §3.1 / RFC 8037 §3.1)。"""
        return _JOSE_NAMES[self]

    @property
    def context(self) -> str:
        """署名対象バイト列のコンテキスト文字列 (RFC 9052 §4.4 / §6.3)。"""
        return "MAC0" if self.is_mac else "Signature1"

    @property
    def tag(self) -> int:
        """COSE の構造の CBOR タグ (RFC 9052 §4.2 / §6.2)。"""
        return TAG_COSE_MAC0 if self.is_mac else TAG_COSE_SIGN1


class EcCurve(enum.IntEnum):
    """COSE の楕円曲線 (RFC 9053 §7)。"""

    P256 = 1
    P384 = 2
    P521 = 3

    @property
    def coordinate_length(self) -> int:
        """座標と秘密鍵のバイト長。"""
        return _EC_COORDINATE_LENGTHS[self]


class OkpCurve(enum.IntEnum):
    """COSE の OKP (Octet Key Pair) の曲線 (RFC 9053 §7)。"""

    ED25519 = 6


class TokenFormat(enum.StrEnum):
    """CAT のトークンの直列化の形式。

    `CatToken.format` はこの値と同じ文字列を返す。
    """

    COMPACT = "compact"
    COSE_SIGN1 = "cose_sign1"
    COSE_MAC0 = "cose_mac0"


# アクションと Authorization Context のアクション識別子の対応 (Table 2)
_MOQT_AUTHORIZATION_CONTEXTS: dict[MoqtAction, str] = {
    MoqtAction.CLIENT_SETUP: "SETUP",
    MoqtAction.SERVER_SETUP: "SETUP",
    MoqtAction.PUBLISH_NAMESPACE: "PUB_NS",
    MoqtAction.SUBSCRIBE_NAMESPACE: "SUB_NS",
    MoqtAction.SUBSCRIBE: "SUBSCRIBE",
    MoqtAction.REQUEST_UPDATE: "REQ_UPDATE",
    MoqtAction.PUBLISH: "PUBLISH",
    MoqtAction.FETCH: "FETCH",
    MoqtAction.TRACK_STATUS: "TRK_STATUS",
}

# MAC アルゴリズム (COSE_Mac0 を使うもの)
_MAC_ALGORITHMS: frozenset[Algorithm] = frozenset(
    (Algorithm.HMAC_SHA256, Algorithm.HMAC_SHA384, Algorithm.HMAC_SHA512)
)

# アルゴリズムと JOSE の `alg` 名の対応
_JOSE_NAMES: dict[Algorithm, str] = {
    Algorithm.HMAC_SHA256: "HS256",
    Algorithm.HMAC_SHA384: "HS384",
    Algorithm.HMAC_SHA512: "HS512",
    Algorithm.ES256: "ES256",
    Algorithm.ES384: "ES384",
    Algorithm.ES512: "ES512",
    Algorithm.EDDSA: "EdDSA",
}

# JOSE の `alg` 名とアルゴリズムの対応
_JOSE_ALGORITHMS: dict[str, Algorithm] = {
    name: algorithm for algorithm, name in _JOSE_NAMES.items()
}

# 楕円曲線と座標のバイト長の対応
_EC_COORDINATE_LENGTHS: dict[EcCurve, int] = {
    EcCurve.P256: 32,
    EcCurve.P384: 48,
    EcCurve.P521: 66,
}

__all__ = [
    "C4M_DRAFT_HMAC_SHA256_ALGORITHM_ID",
    "CAT_CONTENT_TYPE",
    "CBOR_MAX_DEPTH",
    "CLAIM_AUDIENCE",
    "CLAIM_CAT_ALPN",
    "CLAIM_CAT_DPOP",
    "CLAIM_CAT_GEO_ALT",
    "CLAIM_CAT_GEO_COORD",
    "CLAIM_CAT_GEO_ISO3166",
    "CLAIM_CAT_HEADER",
    "CLAIM_CAT_IF",
    "CLAIM_CAT_IF_DATA",
    "CLAIM_CAT_METHOD",
    "CLAIM_CAT_NETWORK_IP",
    "CLAIM_CAT_PROBABILITY_OF_REJECTION",
    "CLAIM_CAT_RENEWAL",
    "CLAIM_CAT_REPLAY",
    "CLAIM_CAT_TLS_PUBLIC_KEY",
    "CLAIM_CAT_URI",
    "CLAIM_CAT_VERSION",
    "CLAIM_CONFIRMATION",
    "CLAIM_CWT_ID",
    "CLAIM_EXPIRATION",
    "CLAIM_ISSUED_AT",
    "CLAIM_ISSUER",
    "CLAIM_MOQT",
    "CLAIM_MOQT_REVAL",
    "CLAIM_NOT_BEFORE",
    "CLAIM_SUBJECT",
    "CONFIRMATION_C4M_DRAFT_JWK_THUMBPRINT",
    "CONFIRMATION_JWK_THUMBPRINT",
    "DPOP_PROOF_JWT_TYPE",
    "HEADER_ALGORITHM",
    "HEADER_CONTENT_TYPE",
    "HEADER_CRITICAL",
    "HEADER_KEY_ID",
    "HEADER_TYPE",
    "MATCH_TYPE_PREFIX",
    "MATCH_TYPE_SUFFIX",
    "MOQT_AUTHORIZATION_CONTEXT_TYPE",
    "MOQT_AUTH_TOKEN_TYPE_CAT",
    "TAG_COSE_MAC0",
    "TAG_COSE_SIGN1",
    "TAG_CWT",
    "Algorithm",
    "AuthorizationContext",
    "CatClaims",
    "CatDpop",
    "CatToken",
    "CatTokenBuilder",
    "CborValue",
    "ClaimValidationOptions",
    "Confirmation",
    "CoseEncodingOptions",
    "CoseHeader",
    "CoseKey",
    "CoseMessage",
    "DpopProof",
    "DpopProofBuilder",
    "DpopProofClaims",
    "DpopProofHeader",
    "DpopReplayCache",
    "DpopVerification",
    "EcCurve",
    "Jwk",
    "JwsCompact",
    "JwsHeader",
    "Match",
    "MoqtAction",
    "MoqtClaim",
    "MoqtScope",
    "NamespaceMatch",
    "OkpCurve",
    "TokenFormat",
    "VerifyOptions",
    "decode_cbor",
    "decode_cbor_partial",
    "default_signing_algorithm",
    "digest",
    "encode_cbor",
    "sign",
    "verify",
]
