"""
Python から `import moqt._native` される拡張モジュール。
"""

from _typeshed import Incomplete
from collections.abc import Sequence
from typing import Any, final

@final
class Accessibility:
    """
    MSF の accessibility 記述子 (draft-ietf-moq-msf-01 §5.2.44 (Accessibility))。
    
    [`Track::accessibility`] に設定する。
    
    この仕様は draft 由来であり、将来の改訂で変更される可能性がある。
    """
    def __eq__(self, other: object, /) -> bool: ...
    def __new__(cls, /, scheme: str, value: str) -> Accessibility:
        """
        accessibility 記述子を組み立てる。
        """
    def __repr__(self, /) -> str: ...
    @property
    def scheme(self, /) -> str:
        """
        記述子 scheme。
        """
    @scheme.setter
    def scheme(self, /, value: str) -> None:
        """
        記述子 scheme。
        """
    @property
    def value(self, /) -> str:
        """
        記述子値。
        """
    @value.setter
    def value(self, /, value: str) -> None:
        """
        記述子値。
        """

@final
class AuthInfo:
    """
    MSF の認可情報エントリ (draft-ietf-moq-msf-01 §5.2.42 (Authorization Info))。
    
    [`Track::auth_info`] に設定する。`value` は scheme 固有の JSON 値そのものであり、
    UTF-8 の生 JSON バイト列として渡す。単独の JSON 値でない場合は encode 時に
    `ValueError` になる。
    
    この仕様は draft 由来であり、将来の改訂で変更される可能性がある。
    """
    def __eq__(self, other: object, /) -> bool: ...
    def __new__(cls, /, scheme: str, value: Sequence[int]) -> AuthInfo:
        """
        認可情報エントリを組み立てる。
        """
    def __repr__(self, /) -> str: ...
    @property
    def scheme(self, /) -> str:
        """
        認可 scheme 名。
        """
    @scheme.setter
    def scheme(self, /, value: str) -> None:
        """
        認可 scheme 名。
        """
    @property
    def value(self, /) -> bytes:
        """
        scheme 固有値の生 JSON。
        """
    @value.setter
    def value(self, /, value: Sequence[int]) -> None:
        """
        scheme 固有値の生 JSON。
        """

@final
class AuthorizationContext:
    """
    DPoP proof の Authorization Context (draft-nandakumar-moq-generic-dpop-proof-00
    §4.2 / §5.1)。
    
    `tns` / `tn` は draft-ietf-moq-transport-21 §8.8 の正規シリアライズを使う。
    リテラルでないバイトは `.` と 16 進 2 桁へエスケープされるため、`tns` には
    `moqt.msf.serialize_namespace`、`tn` には `moqt.msf.serialize_track_name` の結果を
    渡す。生の名前を渡すと `verify_target` などで一致しない。
    
    `raw` にしか無い拡張フィールド (`parameters` など) は発行時に出力されない。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __new__(cls, /, context_type: str |None = None, action: str |None = None, track_namespace: str |None = None, track_name: str |None = None, resource: str |None = None, raw: str |None = None) -> AuthorizationContext:
        """
        Authorization Context を組み立てる。
        
        省略したフィールドは空文字列 (`track_name` / `resource` は `None`) になる。
        """
    def __repr__(self, /) -> str: ...
    @property
    def action(self, /) -> str:
        """
        `action`。
        """
    @action.setter
    def action(self, /, value: str) -> None:
        """
        `action` を設定する。
        """
    @property
    def context_type(self, /) -> str:
        """
        `type`。
        """
    @context_type.setter
    def context_type(self, /, value: str) -> None:
        """
        `type` を設定する。
        """
    @staticmethod
    def decode(text: str) -> AuthorizationContext:
        """
        Authorization Context の JSON をデコードする。
        
        メンバー名が重複している場合は `ValueError` になる。
        """
    @property
    def raw(self, /) -> str:
        """
        actx の生 JSON。
        """
    @raw.setter
    def raw(self, /, value: str) -> None:
        """
        actx の生 JSON を設定する。
        """
    @property
    def resource(self, /) -> str |None:
        """
        `resource`。
        """
    @resource.setter
    def resource(self, /, value: str |None) -> None:
        """
        `resource` を設定する。
        """
    @property
    def track_name(self, /) -> str |None:
        """
        `tn` (track name のシリアライズ文字列)。
        """
    @track_name.setter
    def track_name(self, /, value: str |None) -> None:
        """
        `tn` を設定する。
        """
    @property
    def track_namespace(self, /) -> str:
        """
        `tns` (namespace のシリアライズ文字列)。
        """
    @track_namespace.setter
    def track_namespace(self, /, value: str) -> None:
        """
        `tns` を設定する。
        """
    def verify_action(self, /, action: int) -> None:
        """
        `action` がアクションと一致するかどうかを検証する (C4M Table 2)。
        """
    def verify_context_type(self, /, expected: str) -> None:
        """
        `type` が期待どおりかどうかを検証する。
        """
    def verify_resource_consistency(self, /) -> None:
        """
        `resource` が指定されている場合に `tns` / `tn` と整合するかどうかを検証する。
        
        `resource` は `moqt://<relay-endpoint>?tns=<namespace>&tn=<track>` の形式
        (draft-ietf-moq-c4m-01 §3.1.3) を前提とし、クエリパラメータを文字列として
        比較する。パーセントエンコーディングは解釈しない。
        """
    def verify_target(self, /, namespace: Sequence[Sequence[int]], track_name: bytes) -> None:
        """
        `tns` / `tn` が対象の Full Track Name と一致するかどうかを検証する。
        
        `tn` が proof に無い場合は `ValueError` になる (draft-ietf-moq-c4m-01 §3.1.2 は
        `tn` を必須としている)。
        """

@final
class Buffers:
    """
    MSF のターゲットバッファ (draft-ietf-moq-msf-01 §5.2.9 (Buffers))。
    
    [`Track::buffers`] に設定する。draft は target / min / max を省略可能な
    フィールドとして定義する。
    
    この仕様は draft 由来であり、将来の改訂で変更される可能性がある。
    """
    def __eq__(self, other: object, /) -> bool: ...
    def __new__(cls, /, target: int |None = None, min: int |None = None, max: int |None = None) -> Buffers:
        """
        バッファを組み立てる。
        """
    def __repr__(self, /) -> str: ...
    @property
    def max(self, /) -> int |None:
        """
        最大バッファ (ms)。
        """
    @max.setter
    def max(self, /, value: int |None) -> None:
        """
        最大バッファ (ms)。
        """
    @property
    def min(self, /) -> int |None:
        """
        最小バッファ (ms)。
        """
    @min.setter
    def min(self, /, value: int |None) -> None:
        """
        最小バッファ (ms)。
        """
    @property
    def target(self, /) -> int |None:
        """
        目標バッファ (ms)。
        """
    @target.setter
    def target(self, /, value: int |None) -> None:
        """
        目標バッファ (ms)。
        """

@final
class CatClaims:
    """
    CAT のクレームセット (CWT のクレーム + CAT / C4M のクレーム)。
    
    型付きで解釈しないクレームは `raw` にそのまま保持する。CAT 固有のクレーム
    (`catu` / `catnip` など) はクレームキーの定数だけを公開し、値の意味論は評価しない。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __new__(cls, /) -> CatClaims:
        """
        空のクレームセットを組み立てる。
        """
    def __repr__(self, /) -> str: ...
    @property
    def audience(self, /) -> list[str]:
        """
        `aud`。単一のテキストと配列の両方を受ける。
        """
    @audience.setter
    def audience(self, /, value: Sequence[str]) -> None:
        """
        `aud` を設定する。
        """
    def authorize(self, /, action: int, namespace: Sequence[Sequence[int]], track_name: bytes) -> bool:
        """
        `moqt` クレームによりアクションが認可されるかどうかを返す。
        
        `moqt` クレームが無い場合は常に `False` を返す (§2 の「明示的に許可された
        アクション以外はブロックする」)。評価するのは `moqt` クレームだけで、`catu`
        などの CAT 固有クレームは評価しない。
        """
    @property
    def catdpop(self, /) -> CatDpop |None:
        """
        `catdpop` (draft-ietf-moq-c4m-01 §3.1.1)。
        """
    @catdpop.setter
    def catdpop(self, /, value: CatDpop |None) -> None:
        """
        `catdpop` を設定する。
        """
    @property
    def confirmation(self, /) -> Confirmation |None:
        """
        `cnf`。
        """
    @confirmation.setter
    def confirmation(self, /, value: Confirmation |None) -> None:
        """
        `cnf` を設定する。
        """
    @property
    def cwt_id(self, /) -> bytes |None:
        """
        `cti`。バイト文字列とテキスト文字列の両方を受ける。
        """
    @cwt_id.setter
    def cwt_id(self, /, value: Sequence[int] |None) -> None:
        """
        `cti` を設定する。
        """
    @staticmethod
    def decode(value: CborValue) -> CatClaims:
        """
        クレームセットの CBOR のデータ項目をデコードする。
        
        非有限値 (NaN / 無限大) の数値クレームはこの時点で `ValueError` になる。
        """
    def encode(self, /) -> CborValue:
        """
        クレームセットを CBOR のデータ項目へエンコードする。
        
        型付きフィールドを持つ claim key を `raw` に置いた場合と、非有限値の数値
        クレームは `ValueError` になる。
        """
    @property
    def expiration(self, /) -> float |None:
        """
        `exp` (UNIX 秒)。
        """
    @expiration.setter
    def expiration(self, /, value: float |None) -> None:
        """
        `exp` (UNIX 秒) を設定する。
        """
    def get(self, /, key: int) -> CborValue |None:
        """
        整数キーのクレームを取り出す。
        
        型付きフィールドとして解釈しなかったクレーム、および未知のクレームが対象で
        ある。`catv` / `catu` / `cath` などの値の意味論は評価しない。
        """
    @property
    def issued_at(self, /) -> float |None:
        """
        `iat` (UNIX 秒)。
        """
    @issued_at.setter
    def issued_at(self, /, value: float |None) -> None:
        """
        `iat` (UNIX 秒) を設定する。
        """
    @property
    def issuer(self, /) -> str |None:
        """
        `iss`。
        """
    @issuer.setter
    def issuer(self, /, value: str |None) -> None:
        """
        `iss` を設定する。
        """
    @property
    def moqt(self, /) -> MoqtClaim |None:
        """
        `moqt` クレーム (draft-ietf-moq-c4m-01 §2.1)。
        """
    @moqt.setter
    def moqt(self, /, value: MoqtClaim |None) -> None:
        """
        `moqt` クレームを設定する。
        """
    @property
    def moqt_reval(self, /) -> float |None:
        """
        `moqt-reval` (再検証間隔、秒) (draft-ietf-moq-c4m-01 §2.2)。
        
        このライブラリは Sans-I/O のため再検証を実行しない。拒否の判断は利用側が
        行う。
        """
    @moqt_reval.setter
    def moqt_reval(self, /, value: float |None) -> None:
        """
        `moqt-reval` (再検証間隔、秒) を設定する。
        """
    @property
    def not_before(self, /) -> float |None:
        """
        `nbf` (UNIX 秒)。
        """
    @not_before.setter
    def not_before(self, /, value: float |None) -> None:
        """
        `nbf` (UNIX 秒) を設定する。
        """
    @property
    def raw(self, /) -> list[tuple[CborValue, CborValue]]:
        """
        型付きで解釈しなかったクレーム。
        """
    @raw.setter
    def raw(self, /, value: Sequence[tuple[CborValue, CborValue]]) -> None:
        """
        型付きで解釈しなかったクレームを設定する。
        """
    @property
    def subject(self, /) -> str |None:
        """
        `sub`。
        """
    @subject.setter
    def subject(self, /, value: str |None) -> None:
        """
        `sub` を設定する。
        """
    def validate(self, /, options: ClaimValidationOptions) -> None:
        """
        時刻と期待値に対するクレームの検証を行う。
        
        `exp` / `nbf` / `iss` / `aud` を検証する。署名の検証は [`CatToken::verify`] が
        行う。
        """

@final
class CatDpop:
    """
    `catdpop` クレーム (CTA-5007-B / draft-ietf-moq-c4m-01 §3.1.1)。
    
    DPoP proof の処理設定を持つ。label 0 が受理ウィンドウ (秒)、label 1 が jti による
    リプレイ保護を行うかどうかを表す。解釈しなかった設定は `raw` に保持する。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __new__(cls, /, window_seconds: float, honor_jti: bool) -> CatDpop:
        """
        ウィンドウと jti の扱いを指定して組み立てる。
        """
    def __repr__(self, /) -> str: ...
    @staticmethod
    def decode(value: CborValue) -> CatDpop:
        """
        `catdpop` の CBOR のデータ項目をデコードする。
        
        ウィンドウは整数と浮動小数点の両方、jti の扱いは真偽値と整数 (0 / 1) の両方を
        受ける。
        """
    def encode(self, /) -> CborValue:
        """
        `catdpop` を CBOR のデータ項目へエンコードする。
        
        label 1 はドラフトの例に合わせて整数 (1 / 0) で書く。ウィンドウが有限でない
        場合は `ValueError` になる。
        """
    @property
    def honor_jti(self, /) -> bool |None:
        """
        jti によるリプレイ保護を行うかどうか。
        """
    @honor_jti.setter
    def honor_jti(self, /, value: bool |None) -> None:
        """
        jti によるリプレイ保護を行うかどうかを設定する。
        """
    def honors_jti(self, /) -> bool:
        """
        jti によるリプレイ保護を行うかどうかを返す。
        
        未指定の場合は `False` を返す。
        """
    @property
    def raw(self, /) -> list[tuple[int, CborValue]]:
        """
        解釈しなかった設定。
        """
    @raw.setter
    def raw(self, /, raw: Sequence[tuple[int, CborValue]]) -> None:
        """
        解釈しなかった設定を置き換える。
        """
    @property
    def window_seconds(self, /) -> float |None:
        """
        DPoP proof を受理する時間ウィンドウ (秒)。
        """
    @window_seconds.setter
    def window_seconds(self, /, value: float |None) -> None:
        """
        DPoP proof を受理する時間ウィンドウ (秒) を設定する。
        """
    def window_seconds_or(self, /, default: float) -> float:
        """
        ウィンドウを返す (未指定の場合は `default` を返す)。
        """

@final
class CatToken:
    """
    CAT のトークン。
    
    生トークン (bearer クレデンシャル) と署名は `repr` では長さだけを表示する。
    デコードしたトークンは不変であり、書き換えはできない。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __repr__(self, /) -> str: ...
    @property
    def claims(self, /) -> CatClaims:
        """
        クレーム。
        """
    @staticmethod
    def decode(data: Any) -> CatToken:
        """
        トークンをデコードする。
        
        `.` で区切られた 3 分割の compact 形式、COSE 形式の CBOR、COSE 形式を
        base64url または標準 Base64 で包んだテキストの順に判別する。`data` には
        `bytes` と `str` のどちらも渡せる。
        """
    @staticmethod
    def decode_compact(text: str) -> CatToken:
        """
        compact 形式 (`base64url(protected).base64url(claims).base64url(signature)`)
        をデコードする。
        """
    @staticmethod
    def decode_cose(data: bytes) -> CatToken:
        """
        COSE 形式 (CBOR) をデコードする。
        """
    @staticmethod
    def decode_moqt_auth_token(token_type: int, value: Any) -> CatToken:
        """
        MOQT の Auth Token Type と Token Value からデコードする
        (draft-ietf-moq-c4m-01 §7.1)。
        
        Token Type が `MOQT_AUTH_TOKEN_TYPE_CAT` (0x01) 以外の場合は `ValueError` に
        なる。`value` には `bytes` と `str` のどちらも渡せる。
        """
    @property
    def format(self, /) -> str:
        """
        直列化の形式を表す文字列。
        
        `compact` / `cose_sign1` / `cose_mac0` のいずれかである。
        """
    @property
    def header(self, /) -> CoseHeader:
        """
        protected / unprotected を統合したヘッダ。
        """
    @property
    def payload(self, /) -> bytes:
        """
        クレームセットの CBOR バイト列。
        """
    @property
    def protected_header(self, /) -> bytes:
        """
        protected ヘッダの CBOR バイト列。
        """
    @property
    def raw_token(self, /) -> bytes:
        """
        `decode` に渡された生バイト。
        
        compact 形式では ASCII のトークン文字列、COSE 形式では CBOR のバイト列、
        base64url で包んだ入力を渡した場合はそのテキストである。DPoP の `ath` は
        このバイト列をハッシュする。
        """
    @property
    def signature(self, /) -> bytes:
        """
        署名または MAC。
        """
    @property
    def signing_input(self, /) -> bytes:
        """
        署名対象のバイト列。
        """
    @property
    def unprotected_header(self, /) -> list[tuple[CborValue, CborValue]]:
        """
        COSE 形式の場合の unprotected ヘッダ。
        """
    def verify(self, /, key: CoseKey) -> None:
        """
        トークンの署名 / MAC を検証する。
        
        トークンの `alg` と鍵の種別が一致しない場合、および署名が一致しない場合は
        `ValueError` になる。
        """
    def verify_with(self, /, key: CoseKey, options: VerifyOptions |None = None) -> None:
        """
        期待するアルゴリズムと `typ` を指定してトークンの署名 / MAC を検証する。
        """

@final
class CatTokenBuilder:
    """
    CAT のトークンを作るビルダー。
    
    発行 (署名) には秘密鍵が必要である。署名アルゴリズムは鍵の種別から自動選択し、
    `algorithm` で明示もできる。
    """
    def __eq__(self, other: object, /) -> bool: ...
    def __new__(cls, /) -> CatTokenBuilder:
        """
        空のビルダーを組み立てる。
        """
    def __repr__(self, /) -> str: ...
    @property
    def algorithm(self, /) -> int |None:
        """
        署名アルゴリズムの識別子。
        """
    @algorithm.setter
    def algorithm(self, /, value: int |None) -> None:
        """
        署名アルゴリズムを設定する。
        """
    def audience(self, /, audience: str) -> None:
        """
        `aud` を追加する。
        """
    def build_compact(self, /, key: CoseKey) -> str:
        """
        compact 形式 (draft-ietf-moq-c4m-01 付録 A) のトークンを発行する。
        
        HMAC-SHA256 のアルゴリズム識別子は RFC 9053 の HMAC 256/256 (5) を使う。
        ドラフト付録 A のベクタは -4 を使うが、IANA の COSE Algorithms レジストリでは
        -4 は A192KW であり発行には使わない。
        """
    def build_cose(self, /, key: CoseKey) -> bytes:
        """
        COSE 形式 (CWT + COSE_Sign1 / COSE_Mac0) のトークンを発行する。
        
        CWT タグ (61) と COSE タグ (17 / 18) を付与する。
        """
    def build_cose_with(self, /, key: CoseKey, options: CoseEncodingOptions |None = None) -> bytes:
        """
        タグの付与を指定して COSE 形式のトークンを発行する。
        """
    def c4m_draft_jwk_thumbprint(self, /, thumbprint: Sequence[int]) -> None:
        """
        `cnf` の `jkt` を draft-ietf-moq-c4m-01 のベクタが使う key 3 で設定する。
        """
    def catdpop(self, /, window_seconds: float, honor_jti: bool) -> None:
        """
        `catdpop` を設定する。
        """
    def claim(self, /, key: int, value: CborValue) -> None:
        """
        任意のクレームを追加する。
        
        型付きフィールドを持つ claim key (`iss` / `moqt` / `catdpop` など) には専用の
        設定メソッドを使うこと。型付きキーをここへ渡した場合は、encode 時に
        `ValueError` になる。
        """
    @property
    def claims(self, /) -> CatClaims:
        """
        発行するクレームセット。
        
        ゲッターは複製を返すため、返した値を変更してもビルダーには反映されない。
        変更を反映する場合はセッターに渡すこと。
        """
    @claims.setter
    def claims(self, /, value: CatClaims) -> None:
        """
        発行するクレームセットを置き換える。
        """
    def cwt_id(self, /, cwt_id: Sequence[int]) -> None:
        """
        `cti` をバイト文字列として設定する。
        """
    def expiration(self, /, expiration: float) -> None:
        """
        `exp` (UNIX 秒) を設定する。
        """
    def issued_at(self, /, issued_at: float) -> None:
        """
        `iat` (UNIX 秒) を設定する。
        """
    def issuer(self, /, issuer: str) -> None:
        """
        `iss` を設定する。
        """
    def jwk_thumbprint(self, /, thumbprint: Sequence[int]) -> None:
        """
        `cnf` の `jkt` を IANA 登録の confirmation key 323 で設定する。
        """
    @property
    def key_id(self, /) -> Any |None:
        """
        `kid` を返す。
        """
    @key_id.setter
    def key_id(self, /, value: Any |None) -> None:
        """
        `kid` を設定する。
        """
    def moqt(self, /, moqt: MoqtClaim) -> None:
        """
        `moqt` クレームを設定する。
        """
    def moqt_reval(self, /, seconds: float) -> None:
        """
        `moqt-reval` (再検証間隔、秒) を設定する。
        """
    def not_before(self, /, not_before: float) -> None:
        """
        `nbf` (UNIX 秒) を設定する。
        """
    def subject(self, /, subject: str) -> None:
        """
        `sub` を設定する。
        """
    @property
    def typ(self, /) -> str |None:
        """
        `typ` を返す。
        """
    @typ.setter
    def typ(self, /, value: str |None) -> None:
        """
        `typ` を設定する。
        """

@final
class Catalog:
    """
    MSF カタログ。
    
    draft-ietf-moq-msf-01 §5 (Catalog) の完全カタログである。delta 更新は
    [`DeltaUpdate`] で読み込み、[`Catalog::apply_delta`] で適用する。
    """
    def __eq__(self, other: object, /) -> bool: ...
    def __new__(cls, /) -> Catalog:
        """
        空のカタログを作成する。
        
        version は対応する MSF バージョン、tracks / publishTracks / initDataList は
        空になる。
        """
    def __repr__(self, /) -> str: ...
    def add_init_data(self, /, init_data: InitData) -> None:
        """
        初期化データを `initDataList` へ追加する
        (draft-ietf-moq-msf-01 §5.1.7 (Initialization Data List))。
        
        トラックの `init_ref` が指す id をここで登録する。登録の無い id を指す
        `init_ref` は encode 時に `ValueError` になる。
        """
    def add_publish_track(self, /, track: Track) -> None:
        """
        トラックを `publishTracks` へ追加する
        (draft-ietf-moq-msf-01 §5.1.5 (Publish tracks))。
        """
    def add_track(self, /, track: Track) -> None:
        """
        トラックを `tracks` へ追加する。
        
        draft の MUST に照らした検証は encode 時に行う。`packaging` が draft
        §5.2.4 の許容値でない場合と、トラックのフィールドの型が合わない場合は
        この時点で `ValueError` になる。
        """
    def apply_delta(self, /, text: str, namespace: str |None = None) -> None:
        """
        delta 更新をこのカタログへ適用する。
        
        `namespace` はカタログトラック自身のネームスペースであり、トラックが
        namespace を省略した場合の継承先として使う (draft-ietf-moq-msf-01 §5.2.2)。
        
        操作は配列順に適用される。適用は原子的であり、途中で失敗した場合は
        `ValueError` を送出してこのカタログを呼び出し前の状態に保つ
        (draft-ietf-moq-msf-01 §5.1.6)。
        """
    def apply_delta_update(self, /, delta: DeltaUpdate, namespace: str |None = None) -> None:
        """
        [`DeltaUpdate`] が組み立てた delta 更新をこのカタログへ適用する。
        
        適用規則は [`Catalog::apply_delta`] と同じである。JSON 文字列を経由せずに
        組み立てた操作を適用する場合に使う。
        """
    @staticmethod
    def decode(data: bytes) -> Catalog:
        """
        JSON バイト列からカタログを読み込む。
        
        draft の MUST に違反する文書は `ValueError` になる。delta 更新の文書を
        渡した場合は [`DeltaUpdate`] を使うよう促す `ValueError` になる。
        """
    def encode(self, /) -> bytes:
        """
        カタログを JSON バイト列へ書き出す。
        
        書き出す前に draft の MUST を検証する。手組みの不正な値は `ValueError` になる。
        """
    @property
    def generated_at(self, /) -> int |None:
        """
        カタログ生成時刻 (ms) (draft-ietf-moq-msf-01 §5.1.2)。
        """
    @generated_at.setter
    def generated_at(self, /, value: int |None) -> None:
        """
        カタログ生成時刻 (ms) を設定する (draft-ietf-moq-msf-01 §5.1.2)。
        """
    @property
    def init_data_list(self, /) -> Any:
        """
        初期化データ一覧 (draft-ietf-moq-msf-01 §5.1.7)。
        """
    @property
    def is_complete(self, /) -> bool:
        """
        ブロードキャストが完了しているか (draft-ietf-moq-msf-01 §5.1.3)。
        """
    @is_complete.setter
    def is_complete(self, /, value: bool) -> None:
        """
        ブロードキャストが完了しているかを設定する (draft-ietf-moq-msf-01 §5.1.3)。
        
        真にすると、それ以降の delta 更新によるトラックの追加と複製が拒否される。
        """
    @staticmethod
    def parse(text: str) -> Catalog:
        """
        JSON 文字列からカタログを読み込む。
        """
    @property
    def publish_tracks(self, /) -> Any:
        """
        publish track 一覧 (draft-ietf-moq-msf-01 §5.1.5)。
        """
    @property
    def tracks(self, /) -> Any:
        """
        トラック一覧 (draft-ietf-moq-msf-01 §5.1.4)。
        
        draft のフィールド名を持つ辞書のリストとして返す。
        """
    @property
    def version(self, /) -> str:
        """
        MSF バージョン (draft-ietf-moq-msf-01 §5.1.1)。
        """

@final
class CborValue:
    """
    CBOR のデータ項目 (RFC 8949 §3)。
    
    variant は `kind` で区別する。`kind` は `unsigned` / `negative` / `byte_string` /
    `text_string` / `array` / `map` / `tag` / `bool` / `null` / `undefined` / `float` /
    `simple` のいずれかである。
    
    デコードで得た値も、静的メソッドで組み立てた値も同じクラスで表す。値は不変であり、
    組み立てた後の書き換えはできない。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __repr__(self, /) -> str: ...
    @staticmethod
    def array(values: Sequence[CborValue]) -> CborValue:
        """
        配列 (major type 4) を組み立てる。
        """
    def as_array(self, /) -> list[CborValue] |None:
        """
        配列として取り出す。
        """
    def as_bool(self, /) -> bool |None:
        """
        真偽値として取り出す。
        """
    def as_bytes(self, /) -> bytes |None:
        """
        バイト文字列として取り出す。
        """
    def as_int(self, /) -> int |None:
        """
        `int` の範囲に収まる整数として取り出す。
        """
    def as_map(self, /) -> list[tuple[CborValue, CborValue]] |None:
        """
        マップとして取り出す。
        
        デコードでは入力の順序、encode 後の wire では決定論的な順序になる。
        """
    def as_number(self, /) -> float |None:
        """
        整数または浮動小数点数の数値として取り出す。
        
        負の整数は 1 回だけ丸めて `float` へ変換する (2 段階の丸めで 2^53 を超える値が
        ずれないようにするため)。
        """
    def as_simple(self, /) -> int |None:
        """
        単純値として取り出す。
        """
    def as_tag(self, /) -> tuple[int, CborValue] |None:
        """
        タグ付きデータ項目の `(タグ, 値)` として取り出す。
        """
    def as_text(self, /) -> str |None:
        """
        テキスト文字列として取り出す。
        """
    def as_unsigned(self, /) -> int |None:
        """
        符号なし整数として取り出す。
        """
    @staticmethod
    def boolean(value: bool) -> CborValue:
        """
        真偽値 (major type 7 の 20 / 21) を組み立てる。
        """
    @staticmethod
    def byte_string(value: bytes) -> CborValue:
        """
        バイト文字列 (major type 2) を組み立てる。
        """
    @staticmethod
    def float_value(value: float) -> CborValue:
        """
        浮動小数点数 (major type 7 の 25 / 26 / 27) を組み立てる。
        """
    @staticmethod
    def integer(value: int) -> CborValue:
        """
        `int` を整数のデータ項目 (major type 0 / 1) として組み立てる。
        
        負の値は major type 1 になる。
        """
    @property
    def kind(self, /) -> str:
        """
        variant を表す文字列。
        """
    @staticmethod
    def map(entries: Sequence[tuple[CborValue, CborValue]]) -> CborValue:
        """
        マップ (major type 5) を組み立てる。
        """
    def map_get(self, /, key: CborValue) -> CborValue |None:
        """
        マップからキーに対応する値を取り出す。
        
        マップ以外では常に `None` を返す。
        """
    @staticmethod
    def negative(value: int) -> CborValue:
        """
        負の整数 (major type 1) を組み立てる。
        
        引数はエンコードされた大きさであり、表す値は `-1 - value` である
        (RFC 8949 §3.1)。通常は [`CborValue::integer`] を使う。
        """
    @staticmethod
    def null() -> CborValue:
        """
        null (major type 7 の 22) を組み立てる。
        """
    @staticmethod
    def simple(value: int) -> CborValue:
        """
        上記以外の単純値 (major type 7 の 0 〜 19 と 32 〜 255) を組み立てる。
        """
    @staticmethod
    def tag(tag: int, value: CborValue) -> CborValue:
        """
        タグ付きデータ項目 (major type 6) を組み立てる。
        """
    @staticmethod
    def text_string(value: str) -> CborValue:
        """
        テキスト文字列 (major type 3) を組み立てる。
        """
    @staticmethod
    def undefined() -> CborValue:
        """
        undefined (major type 7 の 23) を組み立てる。
        """
    @staticmethod
    def unsigned(value: int) -> CborValue:
        """
        符号なし整数 (major type 0) を組み立てる。
        """

@final
class ClaimValidationOptions:
    """
    クレームの検証オプション。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __new__(cls, /, reference_time_seconds: float = 0.0, clock_tolerance_seconds: float = 0.0, expected_issuers: Sequence[str] |None = None, expected_audiences: Sequence[str] |None = None) -> ClaimValidationOptions:
        """
        検証オプションを組み立てる。
        
        現在時刻と許容ずれの既定値は 0、期待する `iss` / `aud` の既定値は空である。
        """
    def __repr__(self, /) -> str: ...
    @property
    def clock_tolerance_seconds(self, /) -> float:
        """
        `exp` / `nbf` に許容するずれ (秒)。
        """
    @clock_tolerance_seconds.setter
    def clock_tolerance_seconds(self, /, value: float) -> None:
        """
        `exp` / `nbf` に許容するずれ (秒)。
        """
    @property
    def expected_audiences(self, /) -> list[str]:
        """
        期待する `aud` の一覧。空の場合は検証しない。
        """
    @expected_audiences.setter
    def expected_audiences(self, /, value: Sequence[str]) -> None:
        """
        期待する `aud` の一覧。空の場合は検証しない。
        """
    @property
    def expected_issuers(self, /) -> list[str]:
        """
        期待する `iss` の一覧。空の場合は検証しない。
        """
    @expected_issuers.setter
    def expected_issuers(self, /, value: Sequence[str]) -> None:
        """
        期待する `iss` の一覧。空の場合は検証しない。
        """
    @property
    def reference_time_seconds(self, /) -> float:
        """
        検証に使う現在時刻 (UNIX 秒)。
        """
    @reference_time_seconds.setter
    def reference_time_seconds(self, /, value: float) -> None:
        """
        検証に使う現在時刻 (UNIX 秒)。
        """

@final
class CloneTrack:
    """
    MSF の delta 更新が複製するトラック定義
    (draft-ietf-moq-msf-01 §5.1.6 (Delta update) の clone 操作)。
    
    親トラックの属性を継承し、再定義した属性だけを上書きする。指定しなかった属性は
    親から継承されるため、[`Track`] と違ってすべての属性が省略可能である。
    
    この仕様は draft 由来であり、将来の改訂で変更される可能性がある。
    """
    def __eq__(self, other: object, /) -> bool: ...
    def __new__(cls, /, name: str, parent_name: str) -> CloneTrack:
        """
        複製するトラックを組み立てる。
        
        `name` と `parent_name` だけが必須であり、残りは属性で設定する。設定しなかった
        属性は親トラックから継承される。
        """
    def __repr__(self, /) -> str: ...
    @property
    def accessibility(self, /) -> list[Accessibility] |None:
        """
        accessibility 記述子 (draft-ietf-moq-msf-01 §5.2.44 (Accessibility))。
        """
    @accessibility.setter
    def accessibility(self, /, value: Sequence[Accessibility] |None) -> None:
        """
        accessibility 記述子 (draft-ietf-moq-msf-01 §5.2.44 (Accessibility))。
        """
    @property
    def alt_group(self, /) -> int |None:
        """
        オルタネートグループ (draft-ietf-moq-msf-01 §5.2.12 (Alternate group))。
        """
    @alt_group.setter
    def alt_group(self, /, value: int |None) -> None:
        """
        オルタネートグループ (draft-ietf-moq-msf-01 §5.2.12 (Alternate group))。
        """
    @property
    def auth_info(self, /) -> list[AuthInfo] |None:
        """
        認可情報 (draft-ietf-moq-msf-01 §5.2.42 (Authorization Info))。
        """
    @auth_info.setter
    def auth_info(self, /, value: Sequence[AuthInfo] |None) -> None:
        """
        認可情報 (draft-ietf-moq-msf-01 §5.2.42 (Authorization Info))。
        """
    @property
    def avg_bitrate(self, /) -> int |None:
        """
        平均ビットレート (bps) (draft-ietf-moq-msf-01 §5.2.23 (Average Bitrate))。
        """
    @avg_bitrate.setter
    def avg_bitrate(self, /, value: int |None) -> None:
        """
        平均ビットレート (bps) (draft-ietf-moq-msf-01 §5.2.23 (Average Bitrate))。
        """
    @property
    def bitrate(self, /) -> int |None:
        """
        最大ビットレート (bps) (draft-ietf-moq-msf-01 §5.2.22 (Maximum Bitrate))。
        """
    @bitrate.setter
    def bitrate(self, /, value: int |None) -> None:
        """
        最大ビットレート (bps) (draft-ietf-moq-msf-01 §5.2.22 (Maximum Bitrate))。
        """
    @property
    def buffers(self, /) -> Buffers |None:
        """
        ターゲットバッファ (draft-ietf-moq-msf-01 §5.2.9 (Buffers))。
        """
    @buffers.setter
    def buffers(self, /, value: Buffers |None) -> None:
        """
        ターゲットバッファ (draft-ietf-moq-msf-01 §5.2.9 (Buffers))。
        """
    @property
    def channel_config(self, /) -> str |None:
        """
        チャンネル設定 (draft-ietf-moq-msf-01 §5.2.29 (Channel configuration))。
        """
    @channel_config.setter
    def channel_config(self, /, value: str |None) -> None:
        """
        チャンネル設定 (draft-ietf-moq-msf-01 §5.2.29 (Channel configuration))。
        """
    @property
    def cipher_suite(self, /) -> str |None:
        """
        暗号スイート (draft-ietf-moq-msf-01 §5.2.39 (Cipher Suite))。
        """
    @cipher_suite.setter
    def cipher_suite(self, /, value: str |None) -> None:
        """
        暗号スイート (draft-ietf-moq-msf-01 §5.2.39 (Cipher Suite))。
        """
    @property
    def codec(self, /) -> str |None:
        """
        コーデック (draft-ietf-moq-msf-01 §5.2.18 (Codec))。
        """
    @codec.setter
    def codec(self, /, value: str |None) -> None:
        """
        コーデック (draft-ietf-moq-msf-01 §5.2.18 (Codec))。
        """
    @property
    def connection_uri(self, /) -> str |None:
        """
        接続先 URI (draft-ietf-moq-msf-01 §5.2.36 (Connection URI))。
        """
    @connection_uri.setter
    def connection_uri(self, /, value: str |None) -> None:
        """
        接続先 URI (draft-ietf-moq-msf-01 §5.2.36 (Connection URI))。
        """
    @property
    def depends(self, /) -> list[str] |None:
        """
        依存トラック名 (draft-ietf-moq-msf-01 §5.2.14 (Dependencies))。省略時は親から継承する。
        """
    @depends.setter
    def depends(self, /, value: Sequence[str] |None) -> None:
        """
        依存トラック名 (draft-ietf-moq-msf-01 §5.2.14 (Dependencies))。省略時は親から継承する。
        """
    @property
    def display_height(self, /) -> int |None:
        """
        表示高さ (px) (draft-ietf-moq-msf-01 §5.2.31 (Display height))。
        """
    @display_height.setter
    def display_height(self, /, value: int |None) -> None:
        """
        表示高さ (px) (draft-ietf-moq-msf-01 §5.2.31 (Display height))。
        """
    @property
    def display_width(self, /) -> int |None:
        """
        表示幅 (px) (draft-ietf-moq-msf-01 §5.2.30 (Display width))。
        """
    @display_width.setter
    def display_width(self, /, value: int |None) -> None:
        """
        表示幅 (px) (draft-ietf-moq-msf-01 §5.2.30 (Display width))。
        """
    @property
    def encryption_scheme(self, /) -> str |None:
        """
        暗号化方式 (draft-ietf-moq-msf-01 §5.2.38 (Encryption Scheme))。
        """
    @encryption_scheme.setter
    def encryption_scheme(self, /, value: str |None) -> None:
        """
        暗号化方式 (draft-ietf-moq-msf-01 §5.2.38 (Encryption Scheme))。
        """
    @property
    def event_type(self, /) -> str |None:
        """
        イベントタイムラインタイプ (draft-ietf-moq-msf-01 §5.2.5 (Event timeline type))。
        """
    @event_type.setter
    def event_type(self, /, value: str |None) -> None:
        """
        イベントタイムラインタイプ (draft-ietf-moq-msf-01 §5.2.5 (Event timeline type))。
        """
    @property
    def framerate(self, /) -> float |None:
        """
        フレームレート (fps) (draft-ietf-moq-msf-01 §5.2.20 (Framerate))。
        """
    @framerate.setter
    def framerate(self, /, value: float |None) -> None:
        """
        フレームレート (fps) (draft-ietf-moq-msf-01 §5.2.20 (Framerate))。
        """
    @property
    def height(self, /) -> int |None:
        """
        エンコード高さ (px) (draft-ietf-moq-msf-01 §5.2.27 (Height))。
        """
    @height.setter
    def height(self, /, value: int |None) -> None:
        """
        エンコード高さ (px) (draft-ietf-moq-msf-01 §5.2.27 (Height))。
        """
    @property
    def init_ref(self, /) -> str |None:
        """
        初期化データ参照 (draft-ietf-moq-msf-01 §5.2.13 (Initialization reference))。
        """
    @init_ref.setter
    def init_ref(self, /, value: str |None) -> None:
        """
        初期化データ参照 (draft-ietf-moq-msf-01 §5.2.13 (Initialization reference))。
        """
    @property
    def is_live(self, /) -> bool |None:
        """
        ライブフラグ (draft-ietf-moq-msf-01 §5.2.7 (Is Live))。省略時は親から継承する。
        """
    @is_live.setter
    def is_live(self, /, value: bool |None) -> None:
        """
        ライブフラグ (draft-ietf-moq-msf-01 §5.2.7 (Is Live))。省略時は親から継承する。
        """
    @property
    def key_id(self, /) -> str |None:
        """
        鍵識別子 (draft-ietf-moq-msf-01 §5.2.40 (Key ID))。
        """
    @key_id.setter
    def key_id(self, /, value: str |None) -> None:
        """
        鍵識別子 (draft-ietf-moq-msf-01 §5.2.40 (Key ID))。
        """
    @property
    def label(self, /) -> str |None:
        """
        トラックラベル (draft-ietf-moq-msf-01 §5.2.10 (Track label))。
        """
    @label.setter
    def label(self, /, value: str |None) -> None:
        """
        トラックラベル (draft-ietf-moq-msf-01 §5.2.10 (Track label))。
        """
    @property
    def lang(self, /) -> str |None:
        """
        言語タグ (draft-ietf-moq-msf-01 §5.2.32 (Language))。
        """
    @lang.setter
    def lang(self, /, value: str |None) -> None:
        """
        言語タグ (draft-ietf-moq-msf-01 §5.2.32 (Language))。
        """
    @property
    def max_gop_duration(self, /) -> int |None:
        """
        最大 GOP 長 (ms) (draft-ietf-moq-msf-01 §5.2.24 (Maximum GOP Duration))。
        """
    @max_gop_duration.setter
    def max_gop_duration(self, /, value: int |None) -> None:
        """
        最大 GOP 長 (ms) (draft-ietf-moq-msf-01 §5.2.24 (Maximum GOP Duration))。
        """
    @property
    def max_group_duration(self, /) -> int |None:
        """
        最大 Group 長 (ms) (draft-ietf-moq-msf-01 §5.2.25 (Maximum Group Duration))。
        """
    @max_group_duration.setter
    def max_group_duration(self, /, value: int |None) -> None:
        """
        最大 Group 長 (ms) (draft-ietf-moq-msf-01 §5.2.25 (Maximum Group Duration))。
        """
    @property
    def mime_type(self, /) -> str |None:
        """
        MIME タイプ (draft-ietf-moq-msf-01 §5.2.19 (Mimetype))。
        """
    @mime_type.setter
    def mime_type(self, /, value: str |None) -> None:
        """
        MIME タイプ (draft-ietf-moq-msf-01 §5.2.19 (Mimetype))。
        """
    @property
    def name(self, /) -> str:
        """
        新しいトラック名 (draft-ietf-moq-msf-01 §5.2.3 (Track name))。必須。
        """
    @name.setter
    def name(self, /, value: str) -> None:
        """
        新しいトラック名 (draft-ietf-moq-msf-01 §5.2.3 (Track name))。必須。
        """
    @property
    def namespace(self, /) -> str |None:
        """
        トラックネームスペース (draft-ietf-moq-msf-01 §5.2.2 (Track namespace))。
        """
    @namespace.setter
    def namespace(self, /, value: str |None) -> None:
        """
        トラックネームスペース (draft-ietf-moq-msf-01 §5.2.2 (Track namespace))。
        """
    @property
    def packaging(self, /) -> str |None:
        """
        パッケージングタイプ (draft-ietf-moq-msf-01 §5.2.4 (Packaging))。省略時は親から継承する。
        """
    @packaging.setter
    def packaging(self, /, value: str |None) -> None:
        """
        パッケージングタイプ (draft-ietf-moq-msf-01 §5.2.4 (Packaging))。省略時は親から継承する。
        """
    @property
    def parent_name(self, /) -> str:
        """
        親トラック名 (draft-ietf-moq-msf-01 §5.2.33 (Parent name))。必須。
        """
    @parent_name.setter
    def parent_name(self, /, value: str) -> None:
        """
        親トラック名 (draft-ietf-moq-msf-01 §5.2.33 (Parent name))。必須。
        """
    @property
    def parent_namespace(self, /) -> str |None:
        """
        親トラックネームスペース (draft-ietf-moq-msf-01 §5.2.34 (Parent namespace))。
        
        省略した場合はカタログのネームスペースを継承したものとして解決される。
        """
    @parent_namespace.setter
    def parent_namespace(self, /, value: str |None) -> None:
        """
        親トラックネームスペース (draft-ietf-moq-msf-01 §5.2.34 (Parent namespace))。
        
        省略した場合はカタログのネームスペースを継承したものとして解決される。
        """
    @property
    def render_group(self, /) -> int |None:
        """
        レンダーグループ (draft-ietf-moq-msf-01 §5.2.11 (Render group))。
        """
    @render_group.setter
    def render_group(self, /, value: int |None) -> None:
        """
        レンダーグループ (draft-ietf-moq-msf-01 §5.2.11 (Render group))。
        """
    @property
    def role(self, /) -> str |None:
        """
        トラックロール (draft-ietf-moq-msf-01 §5.2.6 (Track role))。
        """
    @role.setter
    def role(self, /, value: str |None) -> None:
        """
        トラックロール (draft-ietf-moq-msf-01 §5.2.6 (Track role))。
        """
    @property
    def samplerate(self, /) -> int |None:
        """
        オーディオサンプルレート (Hz) (draft-ietf-moq-msf-01 §5.2.28 (Audio sample rate))。
        """
    @samplerate.setter
    def samplerate(self, /, value: int |None) -> None:
        """
        オーディオサンプルレート (Hz) (draft-ietf-moq-msf-01 §5.2.28 (Audio sample rate))。
        """
    @property
    def spatial_id(self, /) -> int |None:
        """
        スペーシャル ID (draft-ietf-moq-msf-01 §5.2.17 (Spatial ID))。
        """
    @spatial_id.setter
    def spatial_id(self, /, value: int |None) -> None:
        """
        スペーシャル ID (draft-ietf-moq-msf-01 §5.2.17 (Spatial ID))。
        """
    @property
    def target_latency(self, /) -> int |None:
        """
        ターゲットレイテンシ (ms) (draft-ietf-moq-msf-01 §5.2.8 (Target latency))。
        """
    @target_latency.setter
    def target_latency(self, /, value: int |None) -> None:
        """
        ターゲットレイテンシ (ms) (draft-ietf-moq-msf-01 §5.2.8 (Target latency))。
        """
    @property
    def template(self, /) -> Template |None:
        """
        メディアタイムラインテンプレート (draft-ietf-moq-msf-01 §5.2.15 (Template))。
        """
    @template.setter
    def template(self, /, value: Template |None) -> None:
        """
        メディアタイムラインテンプレート (draft-ietf-moq-msf-01 §5.2.15 (Template))。
        """
    @property
    def temporal_id(self, /) -> int |None:
        """
        テンポラル ID (draft-ietf-moq-msf-01 §5.2.16 (Temporal ID))。
        """
    @temporal_id.setter
    def temporal_id(self, /, value: int |None) -> None:
        """
        テンポラル ID (draft-ietf-moq-msf-01 §5.2.16 (Temporal ID))。
        """
    @property
    def timescale(self, /) -> int |None:
        """
        タイムスケール (draft-ietf-moq-msf-01 §5.2.21 (Timescale))。
        """
    @timescale.setter
    def timescale(self, /, value: int |None) -> None:
        """
        タイムスケール (draft-ietf-moq-msf-01 §5.2.21 (Timescale))。
        """
    @property
    def token(self, /) -> str |None:
        """
        認証トークン (draft-ietf-moq-msf-01 §5.2.37 (Token))。
        """
    @token.setter
    def token(self, /, value: str |None) -> None:
        """
        認証トークン (draft-ietf-moq-msf-01 §5.2.37 (Token))。
        """
    @property
    def track_base_key(self, /) -> str |None:
        """
        track 基本鍵 (draft-ietf-moq-msf-01 §5.2.41 (Track Base Key))。
        """
    @track_base_key.setter
    def track_base_key(self, /, value: str |None) -> None:
        """
        track 基本鍵 (draft-ietf-moq-msf-01 §5.2.41 (Track Base Key))。
        """
    @property
    def track_duration(self, /) -> int |None:
        """
        トラック長 (ms) (draft-ietf-moq-msf-01 §5.2.35 (Track duration))。
        """
    @track_duration.setter
    def track_duration(self, /, value: int |None) -> None:
        """
        トラック長 (ms) (draft-ietf-moq-msf-01 §5.2.35 (Track duration))。
        """
    @property
    def width(self, /) -> int |None:
        """
        エンコード幅 (px) (draft-ietf-moq-msf-01 §5.2.26 (Width))。
        """
    @width.setter
    def width(self, /, value: int |None) -> None:
        """
        エンコード幅 (px) (draft-ietf-moq-msf-01 §5.2.26 (Width))。
        """

@final
class Confirmation:
    """
    `cnf` (confirmation) クレーム (RFC 8747 / CTA-5007-B)。
    
    IANA 登録の `jkt` (confirmation key 323) と、draft-ietf-moq-c4m-01 のベクタが
    使う `jkt` (confirmation key 3) を分けて保持する。検証は 323 を優先する。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __new__(cls, /) -> Confirmation:
        """
        空の confirmation を組み立てる。
        """
    def __repr__(self, /) -> str: ...
    @property
    def c4m_draft_jwk_thumbprint(self, /) -> bytes |None:
        """
        draft-ietf-moq-c4m-01 のベクタが使う `jkt` (confirmation key 3) の値。
        """
    @c4m_draft_jwk_thumbprint.setter
    def c4m_draft_jwk_thumbprint(self, /, value: Sequence[int] |None) -> None:
        """
        draft のベクタが使う `jkt` (confirmation key 3) の値を設定する。
        """
    @staticmethod
    def decode(value: CborValue) -> Confirmation:
        """
        `cnf` の CBOR のデータ項目をデコードする。
        """
    def encode(self, /) -> CborValue:
        """
        `cnf` を CBOR のデータ項目へエンコードする。
        """
    def jkt(self, /) -> bytes |None:
        """
        JWK サムプリントを返す。
        
        IANA 登録の 323 を優先し、無ければドラフトのベクタが使う 3 を返す。
        """
    @property
    def jwk_thumbprint(self, /) -> bytes |None:
        """
        IANA 登録の `jkt` (confirmation key 323) の値。
        """
    @jwk_thumbprint.setter
    def jwk_thumbprint(self, /, value: Sequence[int] |None) -> None:
        """
        IANA 登録の `jkt` (confirmation key 323) の値を設定する。
        """
    @property
    def raw(self, /) -> list[tuple[CborValue, CborValue]]:
        """
        解釈しなかった confirmation の値。
        """
    @raw.setter
    def raw(self, /, value: Sequence[tuple[CborValue, CborValue]]) -> None:
        """
        解釈しなかった confirmation の値を設定する。
        """

@final
class CoseEncodingOptions:
    """
    COSE メッセージのエンコードオプション。
    
    既定では CWT タグ (61) と COSE タグ (17 / 18) の両方を付与する。付与は
    「メッセージがデコード時に持っていたタグ」との OR で決まる。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __new__(cls, /, cose_tag: bool = True, cwt_tag: bool = True) -> CoseEncodingOptions:
        """
        CWT タグと COSE タグの付与を指定して組み立てる。
        
        既定はどちらも `True` である。
        """
    def __repr__(self, /) -> str: ...
    @property
    def cose_tag(self, /) -> bool:
        """
        COSE タグ (17 / 18) を付与する。
        """
    @cose_tag.setter
    def cose_tag(self, /, value: bool) -> None:
        """
        COSE タグ (17 / 18) を付与する。
        """
    @property
    def cwt_tag(self, /) -> bool:
        """
        CWT タグ (61) を付与する。
        """
    @cwt_tag.setter
    def cwt_tag(self, /, value: bool) -> None:
        """
        CWT タグ (61) を付与する。
        """

@final
class CoseHeader:
    """
    COSE の protected / unprotected ヘッダ。
    
    解釈しないパラメータは `raw` に保持し、再エンコード時に決定論的な順序で復元する。
    `crit` のラベルは protected ヘッダに実在し、理解できる必要がある
    (RFC 9052 §3.1)。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __new__(cls, /) -> CoseHeader:
        """
        空のヘッダを組み立てる。
        """
    def __repr__(self, /) -> str: ...
    @property
    def algorithm(self, /) -> int |None:
        """
        アルゴリズム (`alg`)。
        
        ヘッダに書かれた識別子を解釈した結果であり、生の識別子は
        `algorithm_identifier` で参照できる。
        """
    @algorithm.setter
    def algorithm(self, /, value: int |None) -> None:
        """
        アルゴリズム (`alg`) を設定する。
        """
    @property
    def algorithm_identifier(self, /) -> int |None:
        """
        ヘッダに書かれていたアルゴリズムの生の識別子。
        """
    @algorithm_identifier.setter
    def algorithm_identifier(self, /, value: int |None) -> None:
        """
        ヘッダに書かれていたアルゴリズムの生の識別子を設定する。
        """
    @property
    def content_type(self, /) -> CborValue |None:
        """
        ペイロードのコンテンツタイプ (`content type`、ラベル 3)。
        """
    @content_type.setter
    def content_type(self, /, value: CborValue |None) -> None:
        """
        ペイロードのコンテンツタイプ (`content type`) を設定する。
        """
    @property
    def critical(self, /) -> list[CborValue]:
        """
        必ず理解しなければならないヘッダパラメータ (`crit`)。
        """
    @critical.setter
    def critical(self, /, value: Sequence[CborValue]) -> None:
        """
        必ず理解しなければならないヘッダパラメータ (`crit`) を設定する。
        """
    @staticmethod
    def decode_protected(value: CborValue) -> CoseHeader:
        """
        protected ヘッダの CBOR のデータ項目をデコードする。
        """
    @staticmethod
    def decode_unprotected(value: CborValue) -> CoseHeader:
        """
        unprotected ヘッダの CBOR のデータ項目をデコードする。
        
        RFC 9052 §3.1 は `crit` を、RFC 9596 §2 は `typ` を unprotected ヘッダに
        置くことを禁止するため、どちらも `ValueError` になる。
        """
    def encode(self, /) -> CborValue:
        """
        ヘッダを CBOR のマップへエンコードする。
        """
    @property
    def key_id(self, /) -> Any |None:
        """
        鍵識別子 (`kid`)。
        
        RFC 9052 §3.1 はバイト文字列とするが、CAT の実装にはテキスト文字列を使う
        ものもあるため、どちらの表記もそのまま保持する。
        """
    @key_id.setter
    def key_id(self, /, value: Any |None) -> None:
        """
        鍵識別子 (`kid`) を設定する。
        """
    @property
    def raw(self, /) -> list[tuple[CborValue, CborValue]]:
        """
        解釈しなかったヘッダパラメータ。
        """
    @raw.setter
    def raw(self, /, value: Sequence[tuple[CborValue, CborValue]]) -> None:
        """
        解釈しなかったヘッダパラメータを設定する。
        """
    @property
    def typ(self, /) -> CborValue |None:
        """
        完全な COSE オブジェクトのコンテンツタイプ (`typ`、ラベル 16)。
        """
    @typ.setter
    def typ(self, /, value: CborValue |None) -> None:
        """
        完全な COSE オブジェクトのコンテンツタイプ (`typ`) を設定する。
        """

@final
class CoseKey:
    """
    COSE Key (RFC 9052 §7) と JWK (RFC 7517) を共通に扱う鍵表現。
    
    `kind` は `symmetric` / `ec2` / `okp` のいずれかである。秘密鍵は署名にだけ使い、
    検証では公開鍵の部分だけを参照する。`repr` は秘密鍵の値を伏せ、長さだけを表示する。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __repr__(self, /) -> str: ...
    @property
    def curve(self, /) -> int |None:
        """
        EC2 鍵の曲線の識別子。
        """
    @staticmethod
    def ec2(curve: int, x: bytes, y: bytes) -> CoseKey:
        """
        公開鍵だけの EC2 鍵 (`kty` = EC2) を組み立てる。
        
        `curve` は COSE の `crv` の識別子 (P-256 = 1 / P-384 = 2 / P-521 = 3) である。
        `x` / `y` はビッグエンディアンの固定長の座標である。
        """
    @staticmethod
    def ec2_with_private_key(curve: int, x: bytes, y: bytes, private_key: bytes) -> CoseKey:
        """
        秘密鍵付きの EC2 鍵を組み立てる。
        
        `private_key` はビッグエンディアンの固定長のスカラーである。
        """
    @staticmethod
    def ed25519(public_key: bytes) -> CoseKey:
        """
        公開鍵だけの Ed25519 鍵 (`kty` = OKP) を組み立てる。
        """
    @staticmethod
    def ed25519_with_private_key(public_key: bytes, private_key: bytes) -> CoseKey:
        """
        秘密鍵付きの Ed25519 鍵を組み立てる。
        
        `private_key` は Ed25519 の種 (32 バイト) である。
        """
    @property
    def key(self, /) -> bytes |None:
        """
        対称鍵のバイト列。
        """
    @property
    def kind(self, /) -> str:
        """
        鍵の種別を表す文字列。
        """
    @property
    def private_key(self, /) -> bytes |None:
        """
        秘密鍵 (EC2 のスカラー / Ed25519 の種)。
        """
    @property
    def public_key(self, /) -> bytes |None:
        """
        OKP 鍵の公開鍵。
        """
    @staticmethod
    def symmetric(key: bytes) -> CoseKey:
        """
        対称鍵 (`kty` = Symmetric) を組み立てる。
        """
    @property
    def x(self, /) -> bytes |None:
        """
        EC2 鍵の x 座標 (ビッグエンディアンの固定長)。
        """
    @property
    def y(self, /) -> bytes |None:
        """
        EC2 鍵の y 座標 (ビッグエンディアンの固定長)。
        """

@final
class CoseMessage:
    """
    COSE のメッセージ (COSE_Sign1 / COSE_Mac0)。
    
    `kind` は `sign1` / `mac0` のいずれかである。MAC では `signature` が MAC (tag) を
    表す。CWT タグ (61) は COSE のタグ付きオブジェクトにだけ前置できる
    (RFC 8392 §6)。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __repr__(self, /) -> str: ...
    @property
    def cose_tagged(self, /) -> bool:
        """
        COSE タグ (17 / 18) が付いていたかどうか。
        """
    @property
    def cwt_tagged(self, /) -> bool:
        """
        CWT タグ (61) が付いていたかどうか。
        """
    @staticmethod
    def decode(data: bytes) -> CoseMessage:
        """
        CBOR のバイト列からデコードする。
        
        CWT タグ (61) と COSE タグ (17 / 18) を許容する。タグが無い場合は protected
        ヘッダのアルゴリズム種別から COSE_Sign1 / COSE_Mac0 を判別する。
        """
    @staticmethod
    def decode_value(value: CborValue) -> CoseMessage:
        """
        CBOR のデータ項目からデコードする。
        """
    def encode(self, /, options: CoseEncodingOptions |None = None) -> bytes:
        """
        COSE メッセージをエンコードする。
        
        タグの付与はデコード時に持っていたタグと `options` の OR で決まる。CWT タグを
        付ける場合は COSE タグも必要になる (RFC 8392 §6)。
        """
    def header(self, /) -> CoseHeader:
        """
        protected / unprotected を統合したヘッダを返す。
        
        `alg` は protected ヘッダに必須であり、同じラベルが両方のバケットにある場合は
        `ValueError` になる。
        """
    @property
    def kind(self, /) -> str:
        """
        メッセージの種別を表す文字列。
        
        `sign1` / `mac0` のいずれかである。
        """
    @staticmethod
    def mac0(protected: bytes |None = None, unprotected: Sequence[tuple[CborValue, CborValue]] |None = None, payload: bytes |None = None, tag: bytes |None = None, cose_tagged: bool = False, cwt_tagged: bool = False) -> CoseMessage:
        """
        COSE_Mac0 を組み立てる。
        
        MAC は `tag` で受ける。`payload` を省略すると detached payload を表す。
        """
    @property
    def payload(self, /) -> bytes |None:
        """
        ペイロード。`None` は detached payload を表す。
        """
    @property
    def protected(self, /) -> bytes:
        """
        protected ヘッダの CBOR バイト列 (bstr の中身)。
        """
    @staticmethod
    def sign1(protected: bytes |None = None, unprotected: Sequence[tuple[CborValue, CborValue]] |None = None, payload: bytes |None = None, signature: bytes |None = None, cose_tagged: bool = False, cwt_tagged: bool = False) -> CoseMessage:
        """
        COSE_Sign1 を組み立てる。
        
        `payload` を省略すると detached payload を表す。`cose_tagged` / `cwt_tagged` は
        デコード時に持っていたタグを再現するために使う。
        """
    @property
    def signature(self, /) -> bytes:
        """
        署名または MAC。
        """
    def signing_input(self, /) -> bytes:
        """
        署名 / MAC の対象バイト列を組み立てる。
        
        COSE_Sign1 は `Sig_structure`、COSE_Mac0 は `MAC_structure` を返す
        (RFC 9052 §4.4 / §6.3)。external_aad は空のバイト文字列である。detached
        payload は扱わないため、その場合は `ValueError` になる。
        """
    @property
    def unprotected(self, /) -> list[tuple[CborValue, CborValue]]:
        """
        unprotected ヘッダのマップ。
        """

@final
class DeltaUpdate:
    """
    MSF の delta 更新。
    
    draft-ietf-moq-msf-01 §5.1.6 (Delta update) の文書である。JSON から読み込むほかに、
    [`DeltaUpdate::add_tracks`] / [`DeltaUpdate::remove_tracks`] /
    [`DeltaUpdate::clone_tracks`] で操作列を組み立てられる。
    """
    def __eq__(self, other: object, /) -> bool: ...
    def __new__(cls, /) -> DeltaUpdate:
        """
        空の delta 更新を作成する。
        
        操作を持たない delta 更新は draft §5.3 が許さないため、そのまま encode すると
        `ValueError` になる。少なくとも 1 つの操作を追加すること。
        """
    def __repr__(self, /) -> str: ...
    def add_tracks(self, /, tracks: Sequence[Track]) -> None:
        """
        トラックを追加する操作 ("add") を操作列の末尾へ追加する
        (draft-ietf-moq-msf-01 §5.1.6 (Delta update))。
        
        操作は配列順に適用されるため、追加した順が適用順になる。
        """
    def clone_tracks(self, /, tracks: Sequence[CloneTrack]) -> None:
        """
        トラックを複製する操作 ("clone") を操作列の末尾へ追加する
        (draft-ietf-moq-msf-01 §5.1.6 (Delta update))。
        
        複製は親トラックの属性を継承し、再定義した属性だけを上書きする。
        """
    @staticmethod
    def decode(data: bytes) -> DeltaUpdate:
        """
        JSON バイト列から delta 更新を読み込む。
        
        完全カタログの文書を渡した場合は [`Catalog`] を使うよう促す `ValueError` になる。
        """
    def encode(self, /) -> bytes:
        """
        delta 更新を JSON バイト列へ書き出す。
        
        書き出す前に draft の MUST を検証する。手組みの不正な値は `ValueError` になる。
        """
    @property
    def generated_at(self, /) -> int |None:
        """
        カタログ生成時刻 (ms) (draft-ietf-moq-msf-01 §5.1.6)。
        """
    @generated_at.setter
    def generated_at(self, /, value: int |None) -> None:
        """
        カタログ生成時刻 (ms) を設定する (draft-ietf-moq-msf-01 §5.1.6)。
        """
    @property
    def operations(self, /) -> Any:
        """
        操作列 (draft-ietf-moq-msf-01 §5.1.6)。
        
        draft のフィールド名を持つ辞書のリストとして返す。操作は配列順に適用される。
        """
    @staticmethod
    def parse(text: str) -> DeltaUpdate:
        """
        JSON 文字列から delta 更新を読み込む。
        """
    def remove_tracks(self, /, tracks: Sequence[RemoveTrack]) -> None:
        """
        トラックを削除する操作 ("remove") を操作列の末尾へ追加する
        (draft-ietf-moq-msf-01 §5.1.6 (Delta update))。
        """

@final
class DpopProof:
    """
    DPoP proof。
    
    `repr` は署名の長さだけを表示する。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __repr__(self, /) -> str: ...
    @property
    def claims(self, /) -> DpopProofClaims:
        """
        クレーム。
        """
    @staticmethod
    def decode(input: str) -> DpopProof:
        """
        DPoP proof の JWT をデコードする。
        
        `typ` が `"dpop-proof+jwt"` でない場合、対称鍵アルゴリズムである場合、`jwk` が
        無い場合は `ValueError` になる。
        """
    @property
    def header(self, /) -> DpopProofHeader:
        """
        ヘッダ。
        """
    @property
    def signature(self, /) -> bytes:
        """
        署名。
        """
    @property
    def signing_input(self, /) -> bytes:
        """
        署名対象のバイト列。
        """
    def verify_access_token_hash(self, /, access_token: str) -> None:
        """
        `ath` をアクセストークン (文字列) と照合する。
        
        `ath` が proof に無い場合は何も行わない。
        """
    def verify_access_token_hash_bytes(self, /, access_token: bytes) -> None:
        """
        `ath` をアクセストークン (バイト列) と照合する。
        """
    def verify_against_cat_token(self, /, token: CatToken, action: int, namespace: Sequence[Sequence[int]], track_name: bytes, reference_time_seconds: float, default_window_seconds: float, replay_cache: DpopReplayCache |None = None) -> None:
        """
        CAT トークンと同時に送られた DPoP proof を一通り検証する。
        
        TOKEN の生バイトを `ath` のアクセストークンとして扱う。署名、`ath`、JWK
        サムプリントのバインディング、Authorization Context、`catdpop` のウィンドウに
        よる鮮度、jti によるリプレイ保護の順に検証する。
        
        `catdpop` が jti の処理を要求している場合は `replay_cache` が必須である。
        """
    def verify_against_token(self, /, request: DpopVerification, replay_cache: DpopReplayCache |None = None) -> None:
        """
        CAT トークンに束縛された DPoP proof を一通り検証する。
        
        [`DpopProof::verify_against_cat_token`] と異なり、アクセストークンの表現を
        呼び出し側が指定する。`DpopVerification` の `access_token` を渡すと `ath` の
        検証が必須になる (draft-nandakumar-moq-generic-dpop-proof-00 §4.3.2)。
        """
    def verify_authorization_context(self, /, action: int, namespace: Sequence[Sequence[int]], track_name: bytes) -> None:
        """
        Authorization Context (actx) を検証する。
        
        `type` が "moqt"、`action` が一致し、`tns` / `tn` が対象と一致し、`resource`
        が与えられている場合は `tns` / `tn` と整合することを確認する。
        """
    def verify_freshness(self, /, reference_time_seconds: float, window_seconds: float) -> None:
        """
        `iat` が現在時刻からウィンドウ内にあるかどうかを検証する。
        
        未来方向のずれも同じウィンドウで制限する。
        """
    def verify_key_binding(self, /, confirmation: Confirmation) -> None:
        """
        proof の JWK がトークンの `cnf` の JWK サムプリントと一致するか検証する。
        
        `cnf` の confirmation key 323 (IANA 登録の `jkt`) を優先し、323 が無い場合だけ
        3 (ドラフトのベクタが使う値) と比較する。
        """
    def verify_signature(self, /) -> None:
        """
        proof の署名を埋め込みの JWK で検証する。
        """

@final
class DpopProofBuilder:
    """
    DPoP proof を発行するビルダー。
    
    署名鍵と埋め込む JWK が同じ公開鍵を表していることを確認してから署名する。
    `iat` が有限でない場合は `ValueError` になる。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __new__(cls, /, jti: str, issued_at: float, authorization_context: AuthorizationContext) -> DpopProofBuilder:
        """
        必須の値を指定して組み立てる。
        """
    def __repr__(self, /) -> str: ...
    @property
    def access_token_hash(self, /) -> str |None:
        """
        `ath` (任意)。
        """
    @access_token_hash.setter
    def access_token_hash(self, /, value: str |None) -> None:
        """
        `ath` を設定する。
        """
    @property
    def authorization_context(self, /) -> AuthorizationContext:
        """
        `actx`。
        """
    @authorization_context.setter
    def authorization_context(self, /, value: AuthorizationContext) -> None:
        """
        `actx` を設定する。
        """
    def build(self, /, key: CoseKey, jwk: Jwk) -> str:
        """
        proof の JWT を発行する。
        
        `jwk` は埋め込む公開鍵で、`key` と同じ公開鍵でなければならない。署名は非対称
        アルゴリズムだけで行う。
        """
    @property
    def issued_at(self, /) -> float:
        """
        `iat` (UNIX 秒)。
        """
    @issued_at.setter
    def issued_at(self, /, value: float) -> None:
        """
        `iat` (UNIX 秒) を設定する。
        """
    @property
    def jti(self, /) -> str:
        """
        `jti`。
        """
    @jti.setter
    def jti(self, /, value: str) -> None:
        """
        `jti` を設定する。
        """
    @property
    def key_id(self, /) -> str |None:
        """
        `kid` (任意)。
        """
    @key_id.setter
    def key_id(self, /, value: str |None) -> None:
        """
        `kid` を設定する。
        """
    @property
    def nonce(self, /) -> str |None:
        """
        `nonce` (任意)。
        """
    @nonce.setter
    def nonce(self, /, value: str |None) -> None:
        """
        `nonce` を設定する。
        """

@final
class DpopProofClaims:
    """
    DPoP proof の JWT ペイロード (draft-nandakumar-moq-generic-dpop-proof-00 §4.3.2)。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __repr__(self, /) -> str: ...
    @property
    def access_token_hash(self, /) -> str |None:
        """
        `ath`。アクセストークンを伴う場合の base64url(SHA-256(token))。
        """
    @property
    def authorization_context(self, /) -> AuthorizationContext:
        """
        `actx`。
        """
    @staticmethod
    def decode(text: str) -> DpopProofClaims:
        """
        ペイロードの JSON をデコードする。
        
        クレーム名が重複している場合は `ValueError` になる。
        """
    @property
    def issued_at(self, /) -> float:
        """
        `iat` (UNIX 秒)。
        """
    @property
    def jti(self, /) -> str:
        """
        `jti`。proof の一意な識別子。
        """
    @property
    def nonce(self, /) -> str |None:
        """
        `nonce`。
        """

@final
class DpopProofHeader:
    """
    DPoP proof の JWT ヘッダ (draft-nandakumar-moq-generic-dpop-proof-00 §4.3.1)。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __repr__(self, /) -> str: ...
    @property
    def algorithm(self, /) -> int:
        """
        `alg` の識別子。非対称署名アルゴリズムでなければならない。
        """
    @property
    def jwk(self, /) -> Jwk:
        """
        `jwk`。proof の検証に使う公開鍵。
        """
    @property
    def key_id(self, /) -> str |None:
        """
        `kid` (任意)。
        """
    @property
    def typ(self, /) -> str:
        """
        `typ`。`"dpop-proof+jwt"` でなければならない。
        """

@final
class DpopReplayCache:
    """
    jti によるリプレイ保護のキャッシュ。
    
    アプリケーションが 1 つの主体 (セッションやアクセストークン) ごとに保持する。
    エントリ数と jti 長の上限は持たないため、アプリケーションが主体ごとのレート制限や
    jti の長さ制限で肥大化を防ぐこと (RFC 9449 §11.1)。
    """
    def __len__(self, /) -> int:
        """
        記録数を返す。
        """
    def __new__(cls, /) -> DpopReplayCache:
        """
        空のキャッシュを組み立てる。
        """
    def __repr__(self, /) -> str: ...
    def check_and_record(self, /, jti: str, issued_at: float, window_seconds: float, reference_time_seconds: float) -> None:
        """
        jti を確認して記録する。
        
        ウィンドウ外の古い記録は破棄する。同じ jti がウィンドウ内に存在する場合は
        `ValueError` になる。
        """
    def is_empty(self, /) -> bool:
        """
        記録が空かどうかを返す。
        """

@final
class DpopVerification:
    """
    DPoP proof を CAT トークンに束縛して検証するための入力。
    
    [`DpopProof::verify_against_token`] に渡す。アクセストークンを渡すと `ath` の検証が
    必須になる。
    """
    def __new__(cls, /, token_claims: CatClaims, action: int, namespace: Sequence[Sequence[int]], track_name: Sequence[int], reference_time_seconds: float, default_window_seconds: float, access_token: Sequence[int] |None = None) -> DpopVerification:
        """
        検証入力を組み立てる。
        
        `namespace` は正規の Track Namespace でなければ `ValueError` になる。
        """
    def __repr__(self, /) -> str: ...
    @property
    def access_token(self, /) -> bytes |None:
        """
        proof と同時に送られたアクセストークン。
        """
    @property
    def action(self, /) -> int:
        """
        要求されたアクションの識別子。
        """
    @property
    def default_window_seconds(self, /) -> float:
        """
        既定のウィンドウ (秒)。
        """
    @property
    def namespace(self, /) -> list:
        """
        対象の Track Namespace のフィールド列。
        """
    @property
    def reference_time_seconds(self, /) -> float:
        """
        検証に使う現在時刻 (UNIX 秒)。
        """
    @property
    def token_claims(self, /) -> CatClaims:
        """
        検証対象の CAT のクレーム。
        """
    @property
    def track_name(self, /) -> bytes:
        """
        対象の Track Name。
        """

@final
class Event:
    """
    sans I/O セッション状態機械が返すイベント。
    
    種別ごとに意味を持つ属性だけが入る。どの属性が有効かは `kind` で決まる。
    """
    def __repr__(self, /) -> str: ...
    @property
    def acceptance(self, /) -> str |None:
        """
        オブジェクトの受理結果 (object イベントのみ)。
        
        `accepted` / `unknown_track_alias` / `discarded` / `filtered_out` のいずれかである。
        """
    @property
    def code(self, /) -> int |None:
        """
        セッション終了コード、またはストリームのエラーコード。
        """
    @property
    def data(self, /) -> bytes |None:
        """
        制御ストリームへ書き込むバイト列 (send_control のみ)。
        """
    @property
    def fin(self, /) -> bool |None:
        """
        メッセージ送信後にストリームを FIN するか。
        """
    @property
    def group_id(self, /) -> int |None:
        """
        受信した data stream の Group ID (object イベントのみ)。
        """
    @property
    def kind(self, /) -> str:
        """
        イベント種別。
        """
    @property
    def message(self, /) -> dict |None:
        """
        送信すべきメッセージ本体。
        """
    @property
    def message_data(self, /) -> bytes |None:
        """
        メッセージの生バイト列 (Type + Length + Message Body)。
        
        受信系イベントでは、そのまま peer へ中継できる形のバイト列になる。
        """
    @property
    def object_id(self, /) -> int |None:
        """
        受信したオブジェクトの Object ID (object イベントのみ)。
        """
    @property
    def parameters(self, /) -> dict |None:
        """
        受信したメッセージのパラメータ。
        """
    @property
    def properties(self, /) -> bytes |None:
        """
        受信したオブジェクトの Properties の生バイト (object イベントのみ)。
        
        `Properties Length (varint) | Properties データ` の形であり、データグラムと
        subgroup のどちらでも同じである。`ObjectProperties.decode` で解釈する。
        """
    @property
    def publisher_priority(self, /) -> int |None:
        """
        受信したデータストリームの Publisher Priority (object イベントのみ)。
        
        `None` は DEFAULT_PRIORITY bit が立ち、購読の優先度を継承することを示す。
        """
    @property
    def reason(self, /) -> str |None:
        """
        セッション終了理由 (close のみ)。
        """
    @property
    def reliable_size(self, /) -> int |None:
        """
        RESET_STREAM の reliable size。
        """
    @property
    def request_id(self, /) -> int |None:
        """
        対象 request の Request ID。
        """
    @property
    def status(self, /) -> int |None:
        """
        受信したオブジェクトの Object Status (object イベントのみ)。
        
        ペイロード長 0 のオブジェクトだけが持ち、非 0 長では `None` になる。
        (draft-ietf-moq-transport-21 §11.1.2 (Object Status))
        """
    @property
    def stream_id(self, /) -> int |None:
        """
        対象データストリームの ID。
        """
    @property
    def subgroup_id(self, /) -> int |None:
        """
        受信したオブジェクトを含む subgroup の Subgroup ID (object イベントのみ)。
        
        ヘッダが Subgroup ID を最初の Object ID として決めるモードでも、最初の
        Object を受信した時点で確定した値が入る
        (draft-ietf-moq-transport-21 §11.3.1 (Subgroup Header))。
        """
    @property
    def track_alias(self, /) -> int |None:
        """
        受信した data stream の Track Alias (object イベントのみ)。
        
        data stream は Request ID ではなく Track Alias で購読を特定するため、
        購読との対応付けに使う。
        """
    @property
    def track_properties(self, /) -> dict |None:
        """
        受信した応答メッセージの Track Properties。
        
        応答が Track Properties を運ぶ場合は型番号をキーにした辞書が入り、運ばない
        応答では空の辞書になる。応答以外のメッセージでは `None` になる
        (draft-ietf-moq-transport-21 §8.4 (Track and Object Properties))。
        """

@final
class EventTimeline:
    """
    MSF イベントタイムライン (draft-ietf-moq-msf-01 §8.1)。
    
    フォーマットは `[{"t"/"l"/"m": ..., "data": ...}, ...]` である。
    """
    def __eq__(self, other: object, /) -> bool: ...
    def __len__(self, /) -> int: ...
    def __new__(cls, /) -> EventTimeline:
        """
        空のイベントタイムラインを作成する。
        """
    def __repr__(self, /) -> str: ...
    def add_location(self, /, group_id: int, object_id: int, data: str) -> None:
        """
        MOQT Location を指すエントリを追加する ('l')。
        """
    def add_media_pts(self, /, pts_ms: int, data: str) -> None:
        """
        メディア PTS (ms) を指すエントリを追加する ('m')。
        """
    def add_wallclock(self, /, wallclock_ms: int, data: str) -> None:
        """
        ウォールクロック (ms) を指すエントリを追加する ('t')。
        """
    @staticmethod
    def decode(data: bytes) -> EventTimeline:
        """
        JSON バイト列からイベントタイムラインを読み込む。
        
        gzip で圧縮された入力は自動的に展開する。
        """
    def encode(self, /, gzip: bool = False) -> bytes:
        """
        イベントタイムラインを JSON バイト列へ書き出す。
        
        各エントリの `data` は単一の JSON object でなければならない。そうでない
        場合は `ValueError` になる。`gzip` が真の場合は gzip で圧縮する。
        """
    @property
    def entries(self, /) -> Any:
        """
        エントリ列を draft のフィールド名を持つ辞書のリストとして返す。
        """

@final
class InitData:
    """
    MSF の初期化データエントリ (draft-ietf-moq-msf-01 §5.1.7 (Initialization Data List))。
    
    [`Catalog::add_init_data`] で登録する。draft が定める `type` は現状 `inline`
    (Base64 [RFC 4648] で符号化した初期化データ) だけであり、JSON へは常に `inline`
    として書き出す。この仕様は draft 由来であり、将来の改訂で変更される可能性がある。
    """
    def __eq__(self, other: object, /) -> bool: ...
    def __new__(cls, /, id: str, data: str) -> InitData:
        """
        初期化データを組み立てる。
        """
    def __repr__(self, /) -> str: ...
    @property
    def data(self, /) -> str:
        """
        Base64 で符号化した初期化データ。
        """
    @data.setter
    def data(self, /, value: str) -> None:
        """
        Base64 で符号化した初期化データ。
        """
    @property
    def id(self, /) -> str:
        """
        カタログ内で一意な id。
        """
    @id.setter
    def id(self, /, value: str) -> None:
        """
        カタログ内で一意な id。
        """

@final
class Jwk:
    """
    JWK (RFC 7517 §4)。
    
    `kty` は `EC` / `OKP` / `RSA` のいずれかである。`x` / `y` / `n` / `e` は
    base64url (パディング無し) の文字列として保持し、デコード時に正規化しない。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __repr__(self, /) -> str: ...
    def canonical_json(self, /) -> str:
        """
        RFC 7638 §3.2 の正規化 JSON を返す。
        
        必須メンバーを辞書順に並べ、空白を入れない。base64url の値はパディング無しに
        正規化する。
        """
    @property
    def curve(self, /) -> str |None:
        """
        `crv` を返す。`kty` が `RSA` の場合は `None` になる。
        """
    @staticmethod
    def decode(text: str) -> Jwk:
        """
        JWK の JSON をデコードする。
        
        メンバー名が重複している場合と、秘密鍵のメンバーを含む場合は `ValueError` に
        なる (RFC 7517 §4 / RFC 9449 §4.3)。
        """
    @property
    def e(self, /) -> str |None:
        """
        `e` を返す。`kty` が `RSA` 以外の場合は `None` になる。
        """
    @staticmethod
    def ec(curve: str, x: str, y: str) -> Jwk:
        """
        EC 公開鍵 (`kty` = "EC") を組み立てる。
        
        `curve` は `P-256` / `P-384` / `P-521`、`x` / `y` は base64url の文字列である。
        """
    @property
    def kty(self, /) -> str:
        """
        `kty` を返す。
        """
    def matches_public_key(self, /, key: CoseKey) -> bool:
        """
        指定した鍵と同じ公開鍵を表すかどうかを返す。
        
        DPoP proof を発行するときに、埋め込む JWK と署名鍵の食い違いを検出するために
        使う。`kty` が `RSA` の場合は `ValueError` になる。
        """
    @property
    def n(self, /) -> str |None:
        """
        `n` を返す。`kty` が `RSA` 以外の場合は `None` になる。
        """
    @staticmethod
    def okp(curve: str, x: str) -> Jwk:
        """
        OKP 公開鍵 (`kty` = "OKP") を組み立てる。
        
        `curve` は `Ed25519`、`x` は base64url の文字列である。
        """
    @staticmethod
    def rsa(n: str, e: str) -> Jwk:
        """
        RSA 公開鍵 (`kty` = "RSA") を組み立てる。
        
        `n` / `e` は base64url の文字列である。RSA は COSE の鍵表現を持たないため、
        `to_cose_key` は `ValueError` になる。
        """
    def thumbprint_sha256(self, /) -> bytes:
        """
        JWK サムプリント (RFC 7638) の SHA-256 を計算する。
        """
    def to_cose_key(self, /) -> CoseKey:
        """
        公開鍵を [`CoseKey`] へ変換する。
        
        `kty` が `RSA` の場合は [`CoseKey`] が表現を持たないため `ValueError` に
        なる。
        """
    @property
    def x(self, /) -> str |None:
        """
        `x` を返す。`kty` が `RSA` の場合は `None` になる。
        """
    @property
    def y(self, /) -> str |None:
        """
        `y` を返す。`kty` が `EC` 以外の場合は `None` になる。
        """

@final
class JwsCompact:
    """
    JWS compact 形式の JWT (RFC 7515 §7.1)。
    
    `header.payload.signature` の 3 分割形式を保持する。`signature` は COSE の固定長
    形式 (ECDSA は `r || s`、Ed25519 は 64 バイト) である。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __repr__(self, /) -> str: ...
    @staticmethod
    def decode(input: str) -> JwsCompact:
        """
        `header.payload.signature` の 3 分割形式をデコードする。
        """
    @property
    def header(self, /) -> JwsHeader:
        """
        ヘッダ。
        """
    @property
    def payload(self, /) -> bytes:
        """
        ペイロードの生バイト列。
        """
    @property
    def signature(self, /) -> bytes:
        """
        署名。
        """
    @property
    def signing_input(self, /) -> bytes:
        """
        署名対象のバイト列 (`base64url(header).base64url(payload)`)。
        """
    def verify(self, /, key: CoseKey) -> None:
        """
        ヘッダの `alg` と鍵で署名を検証する。
        """

@final
class JwsHeader:
    """
    JWS compact のヘッダ (RFC 7515 §4)。
    
    `alg` は JOSE の名前 (ES256 など) から COSE のアルゴリズムの識別子へ変換して
    保持する。`crit` を持つ JWS は、この実装が拡張ヘッダを 1 つも解釈しないため
    拒否する (RFC 7515 §4.1.11)。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __repr__(self, /) -> str: ...
    @property
    def algorithm(self, /) -> int:
        """
        `alg` を COSE のアルゴリズムの識別子として返す。
        """
    @staticmethod
    def decode(text: str) -> JwsHeader:
        """
        ヘッダの JSON をデコードする。
        
        メンバー名が重複している場合と、`crit` を持つ場合は `ValueError` になる。
        """
    @property
    def jwk(self, /) -> Jwk |None:
        """
        `jwk` (DPoP proof が埋め込む公開鍵)。
        """
    @property
    def key_id(self, /) -> str |None:
        """
        `kid`。
        """
    @property
    def typ(self, /) -> str |None:
        """
        `typ`。
        """

@final
class LocProperties:
    """
    LOC プロパティの集合。
    
    ワイヤフォーマットは `Properties Length (vi64) | Key-Value-Pairs...` である。
    encode は prop_id の昇順にソートし、delta encoding で ID を圧縮する。
    (draft-ietf-moq-loc-04 §2.3)
    """
    def __eq__(self, other: object, /) -> bool: ...
    def __len__(self, /) -> int: ...
    def __new__(cls, /) -> LocProperties:
        """
        空のプロパティ集合を作成する。
        """
    def __repr__(self, /) -> str: ...
    def add(self, /, prop_id: int, value: Any) -> None:
        """
        プロパティを 1 件追加する。
        
        偶数 ID は vi64、奇数 ID は長さ付きバイト列で表現する
        (draft-ietf-moq-loc-04 §2.3)。`value` には `int` または `bytes` を渡す。
        
        この時点では ID と値の型の対応を検査しない。対応が取れていないプロパティは
        `encode()` が `ValueError` で拒否する。不正な入力を意図的に組み立てて
        検証したいテストのために、構築時ではなく encode 時に検査する。
        """
    @property
    def audio_config(self, /) -> bytes |None:
        """
        Audio Config (ID=0x0F): 音声コーデックの設定。
        
        (draft-ietf-moq-loc-04 §2.3.3.1)
        """
    @property
    def audio_level(self, /) -> int |None:
        """
        Audio Level (ID=0x0C): RFC 6464 の音声レベル (vi64 の下位 8 bit)。
        
        (draft-ietf-moq-loc-04 §2.3.3.2)
        """
    @staticmethod
    def decode(data: bytes) -> tuple[LocProperties, int]:
        """
        バッファ先頭からプロパティブロックをデコードし `(プロパティ, 消費バイト数)` を返す。
        
        ブロックの後ろに続くバイト列は消費しない。
        """
    def encode(self, /) -> bytes:
        """
        プロパティブロック全体をエンコードする。
        
        空の集合は Properties Length = 0 の 1 バイトになる。
        (draft-ietf-moq-transport-21 §11.3.1 (Subgroup Header))
        """
    @property
    def timescale(self, /) -> int |None:
        """
        Timescale (ID=0x08): Timestamp の単位 (1 秒あたりのユニット数)。
        
        代表的な値は 1000000 (マイクロ秒)、48000、90000 である。
        (draft-ietf-moq-loc-04 §2.3.1.2)
        """
    @property
    def timestamp(self, /) -> int |None:
        """
        Timestamp (ID=0x10): エンコードされたメディアフレームのタイムスタンプ。
        
        Timescale が無い場合は Unix エポック以降のマイクロ秒、ある場合は
        Timescale 単位のメディア時刻として解釈する。
        (draft-ietf-moq-loc-04 §2.3.1.1)
        """
    def to_dict(self, /) -> dict:
        """
        プロパティを `{prop_id: 値}` の辞書へ変換する。
        """
    @property
    def video_config(self, /) -> bytes |None:
        """
        Video Config (ID=0x0D): ビデオコーデックの設定 (extradata)。
        
        (draft-ietf-moq-loc-04 §2.3.2.1)
        """
    @property
    def video_frame_marking(self, /) -> bytes |None:
        """
        Video Frame Marking (ID=0x09): RFC 9626 のビデオフレームフラグ。
        
        内容は解釈せずバイト列として返す。長さは 1-4 バイトである。
        (draft-ietf-moq-loc-04 §2.3.2.2)
        """

@final
class LocationFilter:
    """
    LOCATION_FILTER (draft-ietf-moq-transport-21 §9.20.10 (LOCATION FILTER Parameter)) の
    型付き表現。
    
    wire 形式は Length-prefixed な optional vi64 群であり、Length (バイト数) で
    フィールド数が決まる。フィールド数と意味の対応は次のとおりである。
    
    - 1 フィールド: StartGroup (Largest Object 相対)
    - 2 フィールド: StartGroup + StartObject (両方 0 なら Next Object、そうでなければ absolute)
    - 3 フィールド: absolute Start + EndGroupDelta (End Group の全 Object を含む)
    - 4 フィールド: absolute Start + EndGroupDelta + EndObject
    
    `kind` は `relative_group` / `next_object` / `absolute_start` / `absolute_range` /
    `absolute_range_with_end` のいずれかであり、種別ごとに必要なフィールドが異なる。
    過不足のあるフィールドを渡すと `ValueError` になる。
    
    この仕様は draft 由来であり、将来の改訂で変更される可能性がある。
    """
    def __eq__(self, other: object, /) -> bool: ...
    def __new__(cls, /, kind: str, start_group: int |None = None, start_object: int |None = None, end_group_delta: int |None = None, end_object: int |None = None) -> LocationFilter:
        """
        LOCATION_FILTER を組み立てる。
        
        `kind` ごとに必要なフィールドは次のとおりである。
        
        - `relative_group`: `start_group`
        - `next_object`: なし
        - `absolute_start`: `start_group` / `start_object`
        - `absolute_range`: `start_group` / `start_object` / `end_group_delta`
        - `absolute_range_with_end`: `start_group` / `start_object` / `end_group_delta` /
          `end_object`
        """
    def __repr__(self, /) -> str: ...
    @staticmethod
    def decode(data: bytes) -> LocationFilter:
        """
        wire format のバイト列から LOCATION_FILTER を読み込む。
        
        フィールド数が 0 または 5 以上の場合と、壊れた vi64 は `ValueError` になる
        (draft-ietf-moq-transport-21 §9.20.10 (LOCATION FILTER Parameter))。
        """
    def encode(self, /) -> bytes:
        """
        LOCATION_FILTER のフィルタ本体をバイト列へ書き出す。
        
        長さプレフィックスを含まないため、パラメータ辞書の値にはそのまま使えない。
        辞書の値にする場合は [`MessageParameters::to_dict`] を使うか、この
        `LocationFilter` をそのまま辞書の値として渡す。
        """
    @property
    def end_group_delta(self, /) -> int |None:
        """
        開始 Group からの End Group の差分 (`absolute_range*` のみ)。
        """
    @property
    def end_object(self, /) -> int |None:
        """
        終端 Group 内の終端 Object ID (`absolute_range_with_end` のみ)。
        """
    @property
    def kind(self, /) -> str:
        """
        フィルタの種別。
        """
    @property
    def start_group(self, /) -> int |None:
        """
        Largest Object からの相対オフセット (`relative_group` のみ)。
        """
    @property
    def start_object(self, /) -> int |None:
        """
        開始 Location の Object ID (`absolute_*` のみ)。
        """

@final
class LocationFilterUpdate:
    """
    LOCATION_FILTER の更新指示 (draft-ietf-moq-transport-21 §3.3.1 (Location Filters))。
    
    REQUEST_UPDATE では Length 0 がフィルタの削除を表す。パラメータの省略 (値の変更なし)
    と区別するために 3 状態で返す。`kind` は `unchanged` / `removed` / `set` のいずれかで
    あり、`set` のときだけ `filter` が入る。
    
    この仕様は draft 由来であり、将来の改訂で変更される可能性がある。
    """
    def __repr__(self, /) -> str: ...
    @property
    def filter(self, /) -> LocationFilter |None:
        """
        `kind` が `set` のときの新しいフィルタ。
        """
    @property
    def kind(self, /) -> str:
        """
        `unchanged` / `removed` / `set` のいずれか。
        """

@final
class Match:
    """
    `bin-match` (draft-ietf-moq-c4m-01 §2.1)。
    
    バイト文字列は完全一致、prefix / suffix は前方 / 後方一致を表す。マッチは
    バイト単位で行い、正規化はしない。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __repr__(self, /) -> str: ...
    @staticmethod
    def decode(value: CborValue) -> Match:
        """
        `bin-match` の CBOR のデータ項目をデコードする。
        """
    def encode(self, /) -> CborValue:
        """
        `bin-match` を CBOR のデータ項目へエンコードする。
        """
    @staticmethod
    def exact(value: bytes) -> Match:
        """
        完全一致 (`bstr`) を組み立てる。
        """
    @property
    def kind(self, /) -> str:
        """
        マッチの種別を表す文字列。
        
        `exact` / `prefix` / `suffix` のいずれかである。
        """
    def matches(self, /, value: bytes) -> bool:
        """
        値がマッチするかどうかを返す。
        """
    @staticmethod
    def prefix(value: bytes) -> Match:
        """
        前方一致 (`[1, bstr]`) を組み立てる。
        """
    @staticmethod
    def suffix(value: bytes) -> Match:
        """
        後方一致 (`[2, bstr]`) を組み立てる。
        """
    @property
    def value(self, /) -> bytes:
        """
        マッチのパターンのバイト列。
        """

@final
class MediaTimeline:
    """
    MSF メディアタイムライン (draft-ietf-moq-msf-01 §7.1)。
    
    フォーマットは `[[pts_ms, [group_id, object_id], wallclock_ms], ...]` である。
    """
    def __eq__(self, other: object, /) -> bool: ...
    def __len__(self, /) -> int: ...
    def __new__(cls, /) -> MediaTimeline:
        """
        空のメディアタイムラインを作成する。
        """
    def __repr__(self, /) -> str: ...
    def add(self, /, pts_ms: int, group_id: int, object_id: int, wallclock_ms: int) -> None:
        """
        エントリを末尾に追加する。
        
        `wallclock_ms` が不明な場合は 0 を渡す。
        """
    @staticmethod
    def decode(data: bytes) -> MediaTimeline:
        """
        JSON バイト列からメディアタイムラインを読み込む。
        
        gzip で圧縮された入力は自動的に展開する。
        """
    def encode(self, /, gzip: bool = False) -> bytes:
        """
        メディアタイムラインを JSON バイト列へ書き出す。
        
        `gzip` が真の場合は gzip で圧縮する (draft-ietf-moq-msf-01 §7.1)。
        """
    @property
    def entries(self, /) -> list[tuple[int, int, int, int]]:
        """
        エントリ列を `(pts_ms, group_id, object_id, wallclock_ms)` のリストとして返す。
        """

@final
class Message:
    """
    Python 側へ渡す制御メッセージ 1 件。
    
    メッセージ本体は種別ごとに異なる辞書であり、キーは
    [draft-ietf-moq-transport-21 §9 (Control Messages)](https://datatracker.ietf.org/doc/draft-ietf-moq-transport/)
    の各メッセージが運ぶフィールドに対応する。
    """
    def __eq__(self, other: object, /) -> bool: ...
    def __repr__(self, /) -> str: ...
    @property
    def body(self, /) -> dict:
        """
        メッセージ本体。
        """
    @property
    def kind(self, /) -> str:
        """
        メッセージ種別を表す文字列。
        
        `setup` / `goaway` / `request_ok` / `request_error` / `subscribe` /
        `subscribe_ok` / `request_update` / `publish` / `publish_done` /
        `publish_state_notify` / `fetch` / `fetch_ok` / `track_status` /
        `unsupported` のいずれかである。
        
        `unsupported` は draft-ietf-moq-transport-21 §9 Table 5 に定義済みだが
        moqt-rs が実装しない制御メッセージ (relay 専用の namespace 発見・告知機構と
        その応答) であり、本体は生バイト列のまま公開する。`body` は `type_id`
        (メッセージ Type) と `request_id` (`None` の場合もある) と `body`
        (Length の後ろの生バイト列) を持つ。列挙は `moqt.moqt` が扱う制御メッセージの
        全体であり、relay 専用の namespace 発見・告知機構の API は含まない。
        """
    @property
    def parameters(self, /) -> Any:
        """
        メッセージが運ぶパラメータ。
        
        パラメータを持たないメッセージでは空の辞書を返す。
        """
    @property
    def raw(self, /) -> bytes:
        """
        デコードに使った生バイト列 (Type + Length + Message Body)。
        
        そのまま peer へ中継できる形である。
        """
    @property
    def request_id(self, /) -> int |None:
        """
        メッセージが運ぶ Request ID。
        
        応答メッセージはワイヤに Request ID を含まないため `None` を返す。
        (draft-ietf-moq-transport-21 §9.4 (REQUEST_ERROR))
        
        `unsupported` では Request ID (vi64) で始まる型 (PUBLISH_NAMESPACE /
        SUBSCRIBE_NAMESPACE / SUBSCRIBE_TRACKS) のときだけ `Some` になり、
        応答専用の型 (NAMESPACE / NAMESPACE_DONE / PUBLISH_SKIPPED) では `None` になる。
        """
    @property
    def type_id(self, /) -> int:
        """
        wire 上のメッセージ Type (vi64)。
        """

@final
class MessageParameters:
    """
    Message Parameters (draft-ietf-moq-transport-21 §9.20 (Control Message Parameters))。
    
    `Event.parameters` / `Message.parameters` が返す「型番号をキーにしたエンコード済み
    バイト列の辞書」と同じ内容を、draft が定める値の型と意味で読み書きする。
    辞書からは [`MessageParameters::new`] で構築でき、[`MessageParameters::to_dict`] で
    辞書へ戻せる。
    
    この仕様は draft 由来であり、将来の改訂で変更される可能性がある。
    """
    def __eq__(self, other: object, /) -> bool: ...
    def __len__(self, /) -> int: ...
    def __new__(cls, /, parameters: dict |None = None) -> MessageParameters:
        """
        パラメータの集合を作成する。
        
        `parameters` は `Event.parameters` / `Message.parameters` が返す辞書と同じ形式で
        ある。キーはパラメータ型、値はパラメータ 1 件分のエンコード済みバイト列であり、
        `AUTHORIZATION_TOKEN` は複数回出現できるためバイト列のリストで指定する。
        省略した場合は空の集合になる。
        
        `bytes` 以外の値は型ごとの Python 表現としても受け取る。`uint8` と `vi64` の
        パラメータは `int`、`LARGEST_OBJECT` は `(group_id, object_id)`、
        `TRACK_NAMESPACE_PREFIX` は `bytes` のリスト、`FILL_PARAMETERS` は入れ子の辞書、
        `AUTHORIZATION_TOKEN` は `{"kind": ...}` の辞書または
        `(token_type, token_value)` のタプルである。`LOCATION_FILTER`
        には [`LocationFilter`] も渡せる。
        
        `AUTHORIZATION_TOKEN` の辞書は `kind` で `delete` / `register` / `use_alias` /
        `use_value` を選び、キーは種別ごとに異なる。`delete` と `use_alias` は `alias`、
        `register` は `alias` / `token_type` / `token_value`、`use_value` は
        `token_type` / `token_value` を取る
        (draft-ietf-moq-transport-21 §8.9 (Authorization Token Compression))。
        
        長さ付きバイト列のパラメータは、長さプレフィックスを含むエンコード済みの値を
        要求する。長さが合わない値と解釈できない値は `ValueError` になる。
        この節番号・規則は draft 由来であり将来の改訂で変更されうる。
        
        この辞書は `Session.send_subscribe` などの送信経路へそのまま渡せる。形式は
        受信側が返す辞書と同一である。
        """
    def __repr__(self, /) -> str: ...
    def authorization_tokens(self, /) -> list[Any]:
        """
        AUTHORIZATION_TOKEN (type 0x03) の値を出現順に返す
        (draft-ietf-moq-transport-21 §8.9 (Authorization Token Compression))。
        
        各要素は `decode_parameter` が返すものと同じ「`kind` で種別を表す辞書」であり、
        4 種すべてで alias / token_type / token_value が復元される。AUTHORIZATION_TOKEN は
        同一メッセージ内で複数回出現できる。
        """
    @property
    def expires(self, /) -> int |None:
        """
        EXPIRES (type 0x08) の値を返す
        (draft-ietf-moq-transport-21 §9.20.17 (EXPIRES Parameter))。
        
        値が 0 の場合と、パラメータが無い場合はどちらも `None` になる。0 を指定された
        ことを区別するには [`MessageParameters::has_expires`] を使う。
        """
    @property
    def fill_parameters(self, /) -> MessageParameters |None:
        """
        FILL_PARAMETERS (type 0x23) の内側のパラメータ群を返す
        (draft-ietf-moq-transport-21 §9.20.16 (FILL PARAMETERS Parameter))。
        
        内側は外側とは別のパラメータスコープであり、パラメータが無い場合は `None` になる。
        """
    @property
    def fill_timeout(self, /) -> int |None:
        """
        FILL_TIMEOUT (type 0x0A) の値をミリ秒で返す
        (draft-ietf-moq-transport-21 §9.20.6 (FILL TIMEOUT Parameter))。
        """
    @property
    def forward(self, /) -> int |None:
        """
        FORWARD (type 0x10) の値を返す
        (draft-ietf-moq-transport-21 §9.20.19 (FORWARD Parameter))。
        
        0 は転送しない、1 は転送するである。
        """
    @property
    def group_order(self, /) -> int |None:
        """
        GROUP_ORDER (type 0x22) の値を返す
        (draft-ietf-moq-transport-21 §9.20.9 (GROUP ORDER Parameter))。
        """
    @property
    def has_expires(self, /) -> bool:
        """
        EXPIRES (type 0x08) が存在するかを返す。
        
        EXPIRES=0 もパラメータとしては存在するため `True` になる。
        """
    @property
    def has_range_filters(self, /) -> bool:
        """
        Range Filter を 1 つ以上持つかを返す
        (draft-ietf-moq-transport-21 §3.3.2 (Range Filters))。
        """
    @property
    def include_properties(self, /) -> int |None:
        """
        INCLUDE_PROPERTIES (type 0x35) の値を返す
        (draft-ietf-moq-transport-21 §9.20.22 (INCLUDE_PROPERTIES Parameter))。
        
        0 は Properties を送らない、1 は送るである。パラメータが無い場合の既定は 1 で
        あるため、判定する側が既定を補う。
        """
    @property
    def largest_object(self, /) -> tuple[int, int] |None:
        """
        LARGEST_OBJECT (type 0x09) の値を `(group_id, object_id)` として返す
        (draft-ietf-moq-transport-21 §9.20.9 (LARGEST_OBJECT Parameter))。
        """
    @property
    def location_filter(self, /) -> bytes |None:
        """
        LOCATION_FILTER (type 0x21) のフィルタ本体をバイト列として返す。
        
        長さプレフィックスを含まないため、[`LocationFilter::decode`] へそのまま渡せる。
        解釈した値が必要な場合は [`MessageParameters::location_filter_typed`] を使う。
        """
    @property
    def location_filter_typed(self, /) -> LocationFilter |None:
        """
        LOCATION_FILTER (type 0x21) を [`LocationFilter`] として返す。
        
        パラメータが無い場合と Length 0 (no filter) の場合は `None` になる。
        REQUEST_UPDATE での削除指示と省略を区別する場合は
        [`MessageParameters::location_filter_update`] を使う。
        """
    @property
    def location_filter_update(self, /) -> LocationFilterUpdate:
        """
        LOCATION_FILTER (type 0x21) の更新指示を返す
        (draft-ietf-moq-transport-21 §3.3.1 (Location Filters))。
        
        `kind` が `unchanged` なら省略、`removed` なら Length 0 による削除、
        `set` なら `filter` への置き換えである。
        """
    @property
    def new_group_request(self, /) -> int |None:
        """
        NEW_GROUP_REQUEST (type 0x32) の値を返す
        (draft-ietf-moq-transport-21 §9.20.20 (NEW_GROUP_REQUEST Parameter))。
        """
    @property
    def object_delivery_timeout(self, /) -> int |None:
        """
        OBJECT_DELIVERY_TIMEOUT (type 0x02) の値をミリ秒で返す
        (draft-ietf-moq-transport-21 §9.20.2 (OBJECT_DELIVERY_TIMEOUT Parameter))。
        """
    @property
    def range_filter_count(self, /) -> int:
        """
        Range Filter の個数を返す
        (draft-ietf-moq-transport-21 §3.3.2 (Range Filters))。
        """
    def range_filters(self, /, param_type: int) -> list[bytes]:
        """
        指定した Range Filter 型 (0x25-0x29) の全インスタンスのフィルタ本体を出現順に返す
        (draft-ietf-moq-transport-21 §3.3.2 (Range Filters))。
        
        Range Filter は同一 Parameter Type が同一メッセージ内で複数回出現できるため、
        単一の値ではなく列として返す。長さプレフィックスは含まない。Range Filter 型以外を
        渡した場合は空のリストになる。
        """
    def set_largest_object(self, /, group_id: int, object_id: int) -> None:
        """
        LARGEST_OBJECT (type 0x09) を設定する。
        
        既に値がある場合は置き換える。
        """
    @property
    def subgroup_delivery_timeout(self, /) -> int |None:
        """
        SUBGROUP_DELIVERY_TIMEOUT (type 0x06) の値をミリ秒で返す
        (draft-ietf-moq-transport-21 §9.20.4 (SUBGROUP_DELIVERY_TIMEOUT Parameter))。
        """
    @property
    def subscriber_priority(self, /) -> int |None:
        """
        SUBSCRIBER_PRIORITY (type 0x20) の値を返す
        (draft-ietf-moq-transport-21 §9.20.6 (SUBSCRIBER_PRIORITY Parameter))。
        """
    def to_dict(self, /) -> dict:
        """
        同じ内容を「型番号をキーにしたエンコード済みバイト列の辞書」として返す。
        
        `Event.parameters` / `Message.parameters` と同じ形式であり、そのまま
        [`MessageParameters::new`] へ渡して往復させられる。
        """
    @property
    def track_namespace_prefix(self, /) -> list |None:
        """
        TRACK_NAMESPACE_PREFIX (type 0x34) の値を namespace のフィールド列として返す
        (draft-ietf-moq-transport-21 §9.20.21 (TRACK_NAMESPACE_PREFIX Parameter))。
        """

@final
class MoqtClaim:
    """
    `moqt` クレーム (draft-ietf-moq-c4m-01 §2.1)。
    
    アクションスコープの配列を持つ。いずれかのスコープが認可すれば許可となり、評価順は
    問わない (§2.1.2)。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __new__(cls, /) -> MoqtClaim:
        """
        空のクレームを組み立てる。
        
        スコープを持たない状態の encode は `ValueError` になる。
        """
    def __repr__(self, /) -> str: ...
    def authorize(self, /, action: int, namespace: Sequence[Sequence[int]], track_name: bytes) -> bool:
        """
        アクションと Full Track Name が認可されるかどうかを返す。
        
        いずれかのスコープが認可すれば `True` を返す。`moqt` クレームを持たない
        `CatClaims` の認可判定は [`crate::c4m::cat::CatClaims`] を参照。
        """
    @staticmethod
    def decode(value: CborValue) -> MoqtClaim:
        """
        `moqt` クレームの CBOR のデータ項目をデコードする。
        """
    def encode(self, /) -> CborValue:
        """
        `moqt` クレームを CBOR のデータ項目へエンコードする。
        """
    def scope(self, /, scope: MoqtScope) -> None:
        """
        スコープを追加する。
        """
    @property
    def scopes(self, /) -> list[MoqtScope]:
        """
        認可スコープの列。
        """
    @scopes.setter
    def scopes(self, /, scopes: Sequence[MoqtScope]) -> None:
        """
        認可スコープの列を置き換える。
        """

@final
class MoqtScope:
    """
    `moqt-scope` (draft-ietf-moq-c4m-01 §2.1)。
    
    アクションの配列と、省略可能な名前空間マッチの配列 / トラック名マッチを持つ。
    名前空間マッチ無しでトラック名マッチだけを持つスコープは encode できない。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __new__(cls, /, actions: Sequence[int] |None = None) -> MoqtScope:
        """
        スコープを組み立てる。
        
        `actions` はアクションの整数値の列である。省略するとアクション無しになり、
        その状態の encode は `ValueError` になる。
        """
    def __repr__(self, /) -> str: ...
    def action(self, /, action: int) -> None:
        """
        アクションを追加する (draft-ietf-moq-c4m-01 §2.1 Table 1)。
        """
    @property
    def actions(self, /) -> list[int]:
        """
        認可するアクションの整数値の列。
        """
    @actions.setter
    def actions(self, /, actions: Sequence[int]) -> None:
        """
        認可するアクションの整数値の列を置き換える。
        """
    def allows(self, /, action: int, namespace: Sequence[Sequence[int]], track_name: bytes) -> bool:
        """
        アクションと Full Track Name がこのスコープで認可されるかどうかを返す。
        
        `namespace` は Track Namespace のフィールド列、`track_name` は Track Name を
        表す。未知のアクションの識別子は認可されないものとして `False` を返す。
        """
    @staticmethod
    def decode(value: CborValue) -> MoqtScope:
        """
        `moqt-scope` の CBOR のデータ項目をデコードする。
        """
    def encode(self, /) -> CborValue:
        """
        `moqt-scope` を CBOR のデータ項目へエンコードする。
        
        アクションが空の場合、`nil` が末尾以外にある場合、名前空間マッチ無しで
        トラック名マッチだけを持つ場合は `ValueError` になる。
        """
    @property
    def namespace(self, /) -> list[NamespaceMatch]:
        """
        名前空間フィールドのマッチの列。
        """
    @namespace.setter
    def namespace(self, /, namespace: Sequence[NamespaceMatch]) -> None:
        """
        名前空間フィールドのマッチの列を置き換える。
        """
    def namespace_end(self, /) -> None:
        """
        名前空間の末尾を固定する `nil` を追加する。
        """
    def namespace_match(self, /, namespace_match: NamespaceMatch) -> None:
        """
        名前空間フィールドのマッチを追加する。
        """
    @property
    def track(self, /) -> Match |None:
        """
        トラック名のマッチ。
        
        `None` の場合はすべてのトラック名にマッチする。設定すると、そのスコープは
        トラック名のマッチだけを持つ状態になるため、名前空間マッチが無い場合は
        encode が `ValueError` になる。
        """
    @track.setter
    def track(self, /, matcher: Match |None) -> None:
        """
        トラック名のマッチを置き換える。
        """

@final
class NamespaceMatch:
    """
    `moqt-ns-match` (draft-ietf-moq-c4m-01 §2.1)。
    
    名前空間フィールドのマッチ ([`Match`]) と、名前空間の末尾にそれ以上のフィールドが
    無いことを要求する `nil` のいずれかである。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __repr__(self, /) -> str: ...
    @staticmethod
    def end() -> NamespaceMatch:
        """
        名前空間の末尾にだけ現れる `nil` を組み立てる。
        """
    @property
    def kind(self, /) -> str:
        """
        マッチの種別を表す文字列。
        
        `match` / `end` のいずれかである。
        """
    @staticmethod
    def match(value: Match) -> NamespaceMatch:
        """
        `bin-match` による名前空間フィールドのマッチを組み立てる。
        """
    @property
    def matcher(self, /) -> Match |None:
        """
        `bin-match` によるマッチ。`nil` の場合は `None` になる。
        """

@final
class ObjectProperties:
    """
    MOQT の Object Properties。
    
    ワイヤフォーマットは `Properties Length (vi64) | Key-Value-Pairs...` である。
    encode は prop_type の昇順にソートし、delta encoding で型番号を圧縮する。
    (draft-ietf-moq-transport-21 §16.8 (Properties) Table 14)
    """
    def __bytes__(self, /) -> bytes:
        """
        Properties を含むオブジェクトを送信する引数へそのまま渡せるバイト列を返す。
        
        `moqt.moq.Publication.send_object` と `send_datagram` の `properties_data` は
        この形を受け取る。
        """
    def __eq__(self, other: object, /) -> bool: ...
    def __iter__(self, /) -> ObjectPropertiesIterator: ...
    def __len__(self, /) -> int: ...
    def __new__(cls, /) -> ObjectProperties:
        """
        空のプロパティ集合を作成する。
        """
    def __repr__(self, /) -> str: ...
    def add(self, /, prop_type: int, value: Any) -> None:
        """
        プロパティを 1 件追加する。
        
        偶数型は varint として `int` を、奇数型は長さ付きバイト列として `bytes` を渡す。
        この時点では型番号と値の型の対応を検査しない。対応が取れていないプロパティは
        `encode()` が `ValueError` で拒否する。
        """
    @staticmethod
    def decode(data: bytes) -> tuple[ObjectProperties, int]:
        """
        バッファ先頭からプロパティブロックをデコードし `(プロパティ, 消費バイト数)` を返す。
        
        ブロックの後ろに続くバイト列は消費しない。入れ子の IMMUTABLE_PROPERTIES など
        draft の MUST に違反する入力は `ValueError` になる。
        """
    def encode(self, /) -> bytes:
        """
        プロパティブロック全体をエンコードする。
        
        空の集合は Properties Length = 0 の 1 バイトになる。
        """
    def find_varint(self, /, prop_type: int) -> int |None:
        """
        任意の型番号の varint 値を引く。
        
        見つからない場合と、その型番号の値がバイト列である場合は `None` になる。
        draft-ietf-moq-transport-21 §10.7 (Immutable Properties) の「MUST search both」
        に従い IMMUTABLE_PROPERTIES の内側も探索し、外側の値を優先する。
        """
    @property
    def immutable_properties(self, /) -> bytes |None:
        """
        IMMUTABLE_PROPERTIES (0x0B): 途中で変化しないプロパティの入れ子リスト。
        
        内容は解釈せず生バイト列として返す。
        (draft-ietf-moq-transport-21 §10.7 (Immutable Properties))
        """
    def items(self, /) -> list:
        """
        プロパティを保持している順に `(型番号, 値)` として列挙する。
        
        ワイヤ上の型番号の昇順ではなく、`add()` で追加した順に返す。
        `list(properties)` も同じ列を返す。
        """
    @property
    def object_delivery_timeout(self, /) -> int |None:
        """
        OBJECT_DELIVERY_TIMEOUT (0x02): Object の配送期限 (ms)。
        
        (draft-ietf-moq-transport-21 §10.2 (OBJECT_DELIVERY_TIMEOUT))
        """
    @property
    def prior_group_id_gap(self, /) -> int |None:
        """
        PRIOR_GROUP_ID_GAP (0x3C): 直前の存在しない Group の個数。
        
        (draft-ietf-moq-transport-21 §10.8 (Prior Group ID Gap))
        """
    @property
    def prior_object_id_gap(self, /) -> int |None:
        """
        PRIOR_OBJECT_ID_GAP (0x3E): 直前の存在しない Object の個数。
        
        (draft-ietf-moq-transport-21 §10.9 (Prior Object ID Gap))
        """
    @property
    def subgroup_delivery_timeout(self, /) -> int |None:
        """
        SUBGROUP_DELIVERY_TIMEOUT (0x06): Subgroup の配送期限 (ms)。
        
        (draft-ietf-moq-transport-21 §10.1 (SUBGROUP_DELIVERY_TIMEOUT))
        """
    def to_dict(self, /) -> dict:
        """
        プロパティを `{prop_type: 値}` の辞書へ変換する。
        
        未知の型番号も含めてすべて返す。
        """

@final
class ObjectPropertiesIterator:
    """
    Object Properties の `(型番号, 値)` を追加順に列挙するイテレータ。
    
    列挙の途中で元の集合を `add()` で変更しても、列挙中の列は変わらない。
    """
    def __iter__(self, /) -> ObjectPropertiesIterator: ...
    def __next__(self, /) -> Any |None: ...
    def __repr__(self, /) -> str: ...

@final
class RemoveTrack:
    """
    カタログから削除するトラックの参照
    (draft-ietf-moq-msf-01 §5.1.6 (Delta update) の remove 操作)。
    
    draft はトラック名と任意のネームスペースだけを持つ参照を定める。ネームスペースを
    省略した場合はカタログトラックのネームスペースを継承したものとして解決される
    (§5.2.2 (Track namespace))。
    
    この仕様は draft 由来であり、将来の改訂で変更される可能性がある。
    """
    def __eq__(self, other: object, /) -> bool: ...
    def __new__(cls, /, name: str, namespace: str |None = None) -> RemoveTrack:
        """
        削除するトラックの参照を組み立てる。
        """
    def __repr__(self, /) -> str: ...
    @property
    def name(self, /) -> str:
        """
        削除するトラック名。
        """
    @name.setter
    def name(self, /, value: str) -> None:
        """
        削除するトラック名。
        """
    @property
    def namespace(self, /) -> str |None:
        """
        削除するトラックのネームスペース。
        """
    @namespace.setter
    def namespace(self, /, value: str |None) -> None:
        """
        削除するトラックのネームスペース。
        """

@final
class Session:
    """
    1 本の MOQT Transport Session に対応する sans I/O セッション状態機械。
    
    ストリームの実体には触れない。呼び出し側が peer のストリーム種別を判定して
    `receive_*` を呼び、戻り値のイベントに従ってバイト列を送る。
    relay 全体の routing / fan-out / cache / policy は扱わない。
    """
    @staticmethod
    def client(implementation: str = "moqt-py", setup_options: dict |None = None, transport: str = "wt-h3") -> Session:
        """
        client role の MOQT Session を作成する。
        
        `setup_options` は Setup Option Type をキーにした辞書である。偶数型は `int`、
        奇数型は `bytes`、AUTHORIZATION_TOKEN は Token の辞書またはそのリストを渡す。
        MOQT_IMPLEMENTATION は `implementation` 引数が担うため指定できない
        (draft-ietf-moq-transport-21 §16.4 (Setup Options))。
        
        `transport` は `moqt.moq.Transport` の値である。QUIC 直接接続では AUTHORITY と
        PATH を SETUP に載せ、WebTransport では載せてはならない
        (draft-ietf-moq-transport-21 §9.1.1 (AUTHORITY) / §9.1.2 (PATH))。
        """
    def close(self, /, code: int, reason: str = "internal error") -> list[Event]:
        """
        セッションを閉じる。
        
        理由はライブラリが 'static な文字列しか受け取らないため、既知の理由だけを
        そのまま渡し、それ以外は internal error として扱う。
        """
    @property
    def control_message_timeout_ms(self, /) -> int |None:
        """
        制御メッセージの応答待ちタイムアウト (ms) を返す。
        
        無効の場合は `None` を返す
        (draft-ietf-moq-transport-21 §12.2 (Session Termination Codes))。
        draft 由来の値であり、将来の改訂で変更される可能性がある。
        """
    @property
    def data_stream_timeout_ms(self, /) -> int |None:
        """
        データストリームの停止を検出するタイムアウト (ms) を返す。
        
        無効の場合は `None` を返す
        (draft-ietf-moq-transport-21 §12.2 (Session Termination Codes))。
        draft 由来の値であり、将来の改訂で変更される可能性がある。
        """
    @property
    def established(self, /) -> bool:
        """
        SETUP 交換が完了しているかを返す。
        """
    def fetch(self, /, request_id: int) -> dict |None:
        """
        指定 Request ID の fetch の状態を返す。
        
        保持していない Request ID の場合は `None` を返す。
        """
    def fetch_cleanup_ready(self, /, request_id: int) -> bool |None:
        """
        fetch が破棄可能かを返す。
        """
    def fetch_stop_sending_received(self, /, request_id: int) -> list[Event]:
        """
        FETCH の STOP_SENDING を受信したことを通知する。
        """
    def fetches(self, /) -> dict:
        """
        自側が保持する全 fetch の状態を Request ID をキーにした辞書で返す。
        """
    def forget_fetch(self, /, request_id: int) -> bool:
        """
        終了済みの fetch を破棄する。
        """
    def forget_subscription(self, /, request_id: int) -> bool:
        """
        終了済みの subscription を破棄する。
        """
    def forget_track_status(self, /, request_id: int) -> bool:
        """
        応答済みの TRACK_STATUS を破棄する。
        
        応答 (TRACK_STATUS_OK / REQUEST_ERROR) を受信する前の TRACK_STATUS と、保持して
        いない Request ID では破棄しない。応答前に request stream が終端した場合は
        REQUEST_ERROR として記録されるため破棄できる
        (draft-ietf-moq-transport-21 §9.13 (TRACK_STATUS))。
        """
    def goaway_drain_ready(self, /) -> bool:
        """
        GOAWAY の drain が完了しているかを返す。
        
        drain を妨げる request が 1 件も無ければ `True` である
        (draft-ietf-moq-transport-21 §6.6.1 (Graceful Session Migration))。
        draft 由来の仕様であり、将来の改訂で変更される可能性がある。
        """
    def goaway_drain_snapshot(self, /) -> dict:
        """
        GOAWAY の drain を妨げている request を返す。
        
        自側が GOAWAY を送った後、返る Request ID の request がすべて破棄可能に
        なるまで drain は完了しない。キーは
        `blocking_subscription_request_ids` / `blocking_fetch_request_ids` /
        `blocking_track_status_request_ids` であり、値は Request ID のリストである
        (draft-ietf-moq-transport-21 §6.6.1 (Graceful Session Migration) /
        §9.2 (GOAWAY))。draft 由来の仕様であり、将来の改訂で変更される可能性がある。
        """
    @property
    def last_error(self, /) -> str |None:
        """
        状態機械が通知した直近のエラー理由を返す。
        
        プロトコル違反の切り分けに使う診断用の値である。
        """
    def next_local_request_id(self, /) -> int:
        """
        次の request 用 Request ID を予約する。
        """
    def open_outgoing_fill_stream_count(self, /, request_id: int) -> int:
        """
        指定 subscription で open 中の送信 fill fetch stream 数を返す。
        
        1 つの subscription に複数本の fill fetch stream が同時に開くことがある
        (draft-ietf-moq-transport-21 §3.4 (Fill Semantics))。draft 由来の仕様であり、
        将来の改訂で変更される可能性がある。
        """
    @property
    def peer_alias_retention_ms(self, /) -> int:
        """
        キャンセル済み peer publisher alias の保持期間 (ms) を返す。
        
        draft-ietf-moq-transport-21 §3.1.2 (Track Alias) の SHOULD に対応する保持期間であり、
        draft 由来の値であるため将来の改訂で変更される可能性がある。
        """
    @property
    def peer_max_auth_token_cache_size(self, /) -> int:
        """
        peer が SETUP で宣言した MAX_AUTH_TOKEN_CACHE_SIZE を返す。
        
        宣言が無い場合は 0 を返す。SETUP で受け取った値はキャッシュせず、状態機械から
        都度取得する
        (draft-ietf-moq-transport-21 §9.1.3 (MAX_AUTH_TOKEN_CACHE_SIZE))。
        draft 由来の値であり、将来の改訂で変更される可能性がある。
        """
    def peer_setup_options(self, /) -> dict:
        """
        peer が SETUP で宣言した Setup Option を返す。
        
        キーは Setup Option Type、値は偶数型なら `int`、奇数型なら `bytes` である。
        AUTHORIZATION_TOKEN は Token の辞書のリストになる。SETUP を受信していない
        場合は空の辞書を返す。
        (draft-ietf-moq-transport-21 §9.1 (SETUP) / §16.4 (Setup Options))
        """
    def receive_control(self, /, data: bytes) -> list[Event]:
        """
        peer 制御ストリームの断片を投入し、発生したイベントを返す。
        """
    def receive_control_stream_closed(self, /, reset: bool = False, error_code: int |None = None) -> list[Event]:
        """
        peer 制御ストリームが終端したことを通知する。
        
        `reset` が真の場合は RESET_STREAM、偽の場合は FIN として扱う。`error_code` から
        終端の種類を推測しない。`reset` が真で `error_code` が `None` の場合は
        「アプリケーションエラーコード無しのリセット」である
        (draft-ietf-webtrans-http3-16 §4.4 (Resetting Data Streams))。
        """
    def receive_data_stream(self, /, stream_id: int, data: bytes, stream_type: int |None = None) -> tuple[list[tuple[int, int, int, str]], list[Event]]:
        """
        peer の data stream の断片を投入し、発生したイベントを返す。
        
        最初の断片に含まれる stream type を状態機械へ通知し、種別に応じたデコーダで
        ヘッダとオブジェクトをデコードする。オブジェクトのペイロードはイベントの
        `data` にそのまま入る。
        
        返り値は `(オブジェクトの受理結果, イベント列)` の組である。受理結果は
        デコードしたオブジェクトごとに `(stream_id, object_id, payload_length, 受理結果)`
        を並べたリストである。
        """
    def receive_data_stream_closed(self, /, stream_id: int, reset: bool = False, error_code: int |None = None, reliable_size: int |None = None) -> list[Event]:
        """
        peer の data stream が終端したことを通知する。
        
        `reset` が真の場合は RESET_STREAM、偽の場合は FIN として扱う。`error_code` から
        終端の種類を推測しない。`reset` が真で `error_code` が `None` の場合は
        「アプリケーションエラーコード無しのリセット」である
        (draft-ietf-webtrans-http3-16 §4.4 (Resetting Data Streams))。
        """
    def receive_datagram(self, /, data: bytes) -> list[Event]:
        """
        peer のデータグラムを投入し、発生したイベントを返す。
        
        オブジェクトを受理した場合は、その内容を `object` イベントとして返す。
        """
    def receive_request_stream(self, /, stream_id: int, data: bytes, role: str = "local") -> list[Event]:
        """
        request stream の断片を投入し、発生したイベントを返す。
        
        `role` はストリームをどちら側が開始したかを表す。
        
        - `"local"`: 自側が開始した request への応答である
        - `"peer"`: peer が開始した request である
        
        応答メッセージはワイヤに Request ID を含まないため、この区別は I/O 層
        (Python 側) が保持する。
        """
    def receive_request_stream_closed(self, /, stream_id: int, reset: bool = False, error_code: int |None = None, reliable_size: int |None = None) -> list[Event]:
        """
        peer の request stream が終端したことを通知する。
        
        `reset` が真の場合は RESET_STREAM、偽の場合は FIN として扱う。`error_code` から
        終端の種類を推測しない。`reset` が真で `error_code` が `None` の場合は
        「アプリケーションエラーコード無しのリセット」である
        (draft-ietf-webtrans-http3-16 §4.4 (Resetting Data Streams))。
        """
    def recv_data_stream_stop_sending(self, /, stream_id: int) -> list[Event]:
        """
        peer が受信ストリームへ STOP_SENDING を送ったことを通知する。
        """
    def register_local_request_stream(self, /, stream_id: int, request_id: int) -> None:
        """
        自側が開始した request stream を登録する。
        
        MOQT の応答メッセージはワイヤに Request ID を含まないため、Python 側が
        `send_request` イベントでストリームを開いた直後にこの対応を登録する。
        """
    def report_mid_object_fin(self, /, stream_id: int) -> list[Event]:
        """
        オブジェクトの受信途中でストリームが終端したことを通知する。
        """
    def reset_outgoing_data_stream(self, /, stream_id: int, error_code: int, reliable_size: int |None = None) -> list[Event]:
        """
        送信済みのデータストリームを reset する。
        
        `reliable_size` を渡すと RESET_STREAM_AT になり、先頭 `reliable_size` バイトは
        peer へ確実に届ける (draft-ietf-moq-transport-21 §11.3.2 (Subgroup Object))。
        省略した場合は RESET_STREAM になり、未達のデータは破棄される。
        """
    def retry_pending_data_streams(self, /) -> list[Event]:
        """
        購読が確定する前に届いたデータストリームを再試行する。
        
        ヘッダを受理できずに保留したストリームを購読の確定後に回し直し、発生した
        イベントを返す。購読を登録した直後と定期処理から呼ぶ。保留がなければ
        空のリストを返す。
        """
    def role(self, /) -> str:
        """
        自側の役割を返す。
        """
    def send_data_stream_closed(self, /, stream_id: int, reset: bool = False, error_code: int |None = None, reliable_size: int |None = None) -> list[Event]:
        """
        送信済みのデータストリームを終了する。
        
        `reset` が真の場合は RESET_STREAM、偽の場合は FIN になる。`reset` が真で
        `error_code` が `None` の場合はアプリケーションエラーコード無しのリセットに
        なる。`reset` が偽のときに `error_code` か `reliable_size` を指定すると
        `ValueError` になる。
        """
    def send_data_stream_stop_sending(self, /, stream_id: int) -> list[Event]:
        """
        自側が受信ストリームへ STOP_SENDING を送ったことを通知する。
        """
    def send_fetch(self, /, namespace: Sequence[Sequence[int]], track_name: Sequence[int], parameters: Any) -> list[Event]:
        """
        FETCH を送信する。
        """
    def send_fetch_data_stream_closed(self, /, stream_id: int) -> list[Event]:
        """
        fetch ストリームを終了する。
        """
    def send_fetch_header(self, /, stream_id: int, request_id: int) -> list[Event]:
        """
        送信する fetch ストリームを登録する。
        """
    def send_fetch_object(self, /, stream_id: int) -> list[Event]:
        """
        fetch ストリームへオブジェクトを書き込むことを通知する。
        """
    def send_fetch_ok(self, /, request_id: int, end_of_track: bool, end_location: tuple[int, int], parameters: Any, track_properties: Any) -> list[Event]:
        """
        FETCH_OK を送信する。
        """
    def send_fetch_stop_sending(self, /, request_id: int) -> list[Event]:
        """
        FETCH の STOP_SENDING を送信する。
        """
    def send_fill_fetch_header(self, /, stream_id: int, request_id: int) -> list[Event]:
        """
        送信する fill fetch ストリームを登録する。
        """
    def send_goaway(self, /, new_session_uri: Sequence[int], timeout: int) -> list[Event]:
        """
        GOAWAY を送信する。
        """
    def send_goaway_on_request_stream(self, /, request_id: int, new_session_uri: Sequence[int], timeout: int) -> list[Event]:
        """
        request stream 上に GOAWAY を送信する。
        """
    def send_object_datagram(self, /, request_id: int, group_id: int, object_id: int, properties_data: Sequence[int] |None = None, status: int |None = None) -> tuple[bool, list[Event]]:
        """
        オブジェクトデータグラムを送信することを通知する。
        
        フィルタで破棄される場合は `False` を返す。その場合 Python 側は
        データグラムを送信してはならない。
        """
    def send_padding_datagram(self, /, length: int) -> list[Event]:
        """
        パディングデータグラムの送信を要求する。
        """
    def send_padding_stream(self, /, length: int) -> list[Event]:
        """
        パディングストリームの送信を要求する。
        """
    def send_publish(self, /, namespace: Sequence[Sequence[int]], track_name: Sequence[int], track_alias: int, parameters: Any, track_properties: Any) -> list[Event]:
        """
        PUBLISH を送信する。
        """
    def send_publish_done(self, /, request_id: int, status_code: int, stream_count: int, reason: str) -> list[Event]:
        """
        PUBLISH_DONE を送信する。
        """
    def send_publish_done_for_subscription(self, /, request_id: int, status_code: int, reason: str) -> list[Event]:
        """
        自側が受け持つ subscription の応答を処理する。
        
        REQUEST_UPDATE に対して FORWARD などを変更する場合に使う。
        """
    def send_publish_state_notify(self, /, request_id: int, parameters: Any) -> list[Event]:
        """
        PUBLISH_STATE_NOTIFY を送信する。
        """
    def send_request_error(self, /, request_id: int, error_code: int, retry_interval: int, reason: str, redirect: tuple[Sequence[int], Sequence[Sequence[int]], Sequence[int]] |None = None) -> list[Event]:
        """
        REQUEST_ERROR を送信する。
        
        `redirect` は `(connect_uri, track_namespace, track_name)` のタプルである。
        """
    def send_request_ok(self, /, request_id: int, parameters: Any, track_properties: Any) -> list[Event]:
        """
        REQUEST_OK を送信する。
        """
    def send_request_update(self, /, request_id: int, parameters: Any) -> list[Event]:
        """
        REQUEST_UPDATE を送信する。
        """
    def send_subgroup_header(self, /, stream_id: int, request_id: int, track_alias: int, group_id: int, subgroup_id: int |None = None, subgroup_id_mode: str = "zero", publisher_priority: int |None = None, has_properties: bool = False, end_of_group: bool = False, first_object: bool = False) -> list[Event]:
        """
        送信する subgroup ストリームを登録する。
        
        実際のバイト列は Python 側が組み立てるため、ここでは状態機械へ登録だけを行う。
        
        `subgroup_id_mode` は Subgroup ID のエンコードモードであり、`"zero"` /
        `"first_object_id"` / `"explicit"` のいずれかである。Subgroup ID を最初の
        Object ID として決めるモードでは `subgroup_id` を渡さない
        (draft-ietf-moq-transport-21 §11.3.1 (Subgroup Header))。
        """
    def send_subgroup_object(self, /, stream_id: int, object_id: int, properties_data: Sequence[int] |None = None) -> tuple[bool, list[Event]]:
        """
        subgroup ストリームへオブジェクトを書き込むことを通知する。
        
        フィルタで破棄される場合は `False` を返す。その場合 Python 側は
        バイト列を送信してはならない。
        """
    def send_subscribe(self, /, namespace: Sequence[Sequence[int]], track_name: Sequence[int], parameters: Any) -> list[Event]:
        """
        SUBSCRIBE を送信する。
        """
    def send_subscribe_ok(self, /, request_id: int, track_alias: int, parameters: Any, track_properties: Any) -> list[Event]:
        """
        SUBSCRIBE_OK を送信する。
        """
    def send_track_status(self, /, namespace: Sequence[Sequence[int]], track_name: Sequence[int], parameters: Any) -> list[Event]:
        """
        TRACK_STATUS を送信する。
        """
    @staticmethod
    def server(implementation: str = "moqt-py", setup_options: dict |None = None, transport: str = "wt-h3") -> Session:
        """
        server role の MOQT Session を作成する。
        
        引数の意味は `client` と同じである。
        """
    def set_control_message_timeout_ms(self, /, timeout_ms: int |None) -> None:
        """
        制御メッセージのタイムアウト (ms) を設定する。
        """
    def set_data_stream_timeout_ms(self, /, timeout_ms: int |None) -> None:
        """
        データストリームのタイムアウト (ms) を設定する。
        """
    def set_peer_alias_retention_ms(self, /, retention_ms: int) -> None:
        """
        キャンセル済み peer publisher alias の保持期間 (ms) を設定する。
        
        0 を設定すると保持は実質無効になる。既に登録済みの保持期限は変わらない。
        """
    def start(self, /) -> bytes:
        """
        自側制御ストリームの stream type prefix と SETUP を返す。
        """
    def state(self, /) -> str:
        """
        現在のセッション状態を返す。
        """
    def stop_sending(self, /, request_id: int) -> list[Event]:
        """
        subscription を終了する (subscriber 側の STOP_SENDING)。
        """
    def subscription(self, /, request_id: int) -> dict |None:
        """
        指定 Request ID の subscription の状態を返す。
        
        保持していない Request ID の場合は `None` を返す。
        """
    def subscription_cleanup_ready(self, /, request_id: int) -> bool |None:
        """
        subscription が破棄可能かを返す。
        """
    def subscription_track_alias(self, /, request_id: int) -> int |None:
        """
        request_id に対応する subscription の track alias を返す。
        
        alias は SUBSCRIBE_OK の受信後に確定する。
        """
    def subscriptions(self, /) -> dict:
        """
        自側が保持する全 subscription の状態を Request ID をキーにした辞書で返す。
        """
    def tick(self, /, now_ms: int) -> list[Event]:
        """
        時間を進めてタイムアウトを判定する。
        """
    def track_status_request(self, /, request_id: int) -> dict |None:
        """
        指定 Request ID の TRACK_STATUS の状態を返す。
        
        保持していない Request ID の場合は `None` を返す。
        """
    def track_status_requests(self, /) -> dict:
        """
        自側が保持する全 TRACK_STATUS の状態を Request ID をキーにした辞書で返す。
        """

@final
class Template:
    """
    MSF のメディアタイムラインテンプレート
    (draft-ietf-moq-msf-01 §5.2.15 (Template) / §7.4.1 (Template Format))。
    
    [`Track::template`] に設定する。8 つの値は JSON では 6 要素の配列であり、
    `[start_media_time, delta_media_time, [start_group_id, start_object_id],
    [delta_group_id, delta_object_id], start_wallclock, delta_wallclock]` の順に並ぶ。
    n 番目のエントリの計算式は群のフィールドから
    [`Template::resolve_entry`] で求める。
    
    この仕様は draft 由来であり、将来の改訂で変更される可能性がある。
    """
    def __eq__(self, other: object, /) -> bool: ...
    def __new__(cls, /, start_media_time: int, delta_media_time: int, start_group_id: int, start_object_id: int, delta_group_id: int, delta_object_id: int, start_wallclock: int, delta_wallclock: int) -> Template:
        """
        テンプレートを組み立てる。
        """
    def __repr__(self, /) -> str: ...
    @property
    def delta_group_id(self, /) -> int:
        """
        Group ID の増分。
        """
    @delta_group_id.setter
    def delta_group_id(self, /, value: int) -> None:
        """
        Group ID の増分。
        """
    @property
    def delta_media_time(self, /) -> int:
        """
        メディア時刻の増分 (ms)。
        """
    @delta_media_time.setter
    def delta_media_time(self, /, value: int) -> None:
        """
        メディア時刻の増分 (ms)。
        """
    @property
    def delta_object_id(self, /) -> int:
        """
        Object ID の増分。
        """
    @delta_object_id.setter
    def delta_object_id(self, /, value: int) -> None:
        """
        Object ID の増分。
        """
    @property
    def delta_wallclock(self, /) -> int:
        """
        ウォールクロックの増分 (ms)。
        """
    @delta_wallclock.setter
    def delta_wallclock(self, /, value: int) -> None:
        """
        ウォールクロックの増分 (ms)。
        """
    def resolve_entry(self, /, n: int) -> tuple[int, int, int, int] |None:
        """
        n 番目 (0 始まり) のエントリを `(pts_ms, group_id, object_id, wallclock_ms)` として返す。
        
        draft-ietf-moq-msf-01 §7.4.1 の計算式に従う。4 系列のいずれかが overflow する
        場合は `None` を返す。この仕様は draft 由来であり、将来の改訂で変更される
        可能性がある。
        """
    @property
    def start_group_id(self, /) -> int:
        """
        開始 Group ID。
        """
    @start_group_id.setter
    def start_group_id(self, /, value: int) -> None:
        """
        開始 Group ID。
        """
    @property
    def start_media_time(self, /) -> int:
        """
        開始メディア時刻 (ms)。
        """
    @start_media_time.setter
    def start_media_time(self, /, value: int) -> None:
        """
        開始メディア時刻 (ms)。
        """
    @property
    def start_object_id(self, /) -> int:
        """
        開始 Object ID。
        """
    @start_object_id.setter
    def start_object_id(self, /, value: int) -> None:
        """
        開始 Object ID。
        """
    @property
    def start_wallclock(self, /) -> int:
        """
        開始ウォールクロック (ms)。
        """
    @start_wallclock.setter
    def start_wallclock(self, /, value: int) -> None:
        """
        開始ウォールクロック (ms)。
        """

@final
class Track:
    """
    MSF のトラックオブジェクト (draft-ietf-moq-msf-01 §5.2 (Track Object Fields))。
    
    カタログの `tracks` / `publishTracks` と、delta 更新の add 操作が運ぶトラック 1 件で
    ある。JSON のフィールド名を snake_case にした属性を持つ。
    
    `packaging` は draft §5.2.4 (Packaging) が定める `loc` / `mediatimeline` /
    `eventtimeline` / `moqlog` / `moqmetrics` のいずれかである。それ以外の値を
    [`Catalog::add_track`] や [`DeltaUpdate::add_tracks`] へ渡すと `ValueError` になる。
    draft の MUST 違反 (eventType と packaging の組み合わせ、targetLatency と buffers の
    共存、mediatimeline / eventtimeline の depends と mimeType など) は encode 時に
    `ValueError` になる。
    
    この仕様は draft 由来であり、将来の改訂で変更される可能性がある。
    """
    def __eq__(self, other: object, /) -> bool: ...
    def __new__(cls, /, name: str, packaging: str, is_live: bool) -> Track:
        """
        トラックを組み立てる。
        
        `name` / `packaging` / `is_live` だけが必須であり、残りは属性で設定する。
        """
    def __repr__(self, /) -> str: ...
    @property
    def accessibility(self, /) -> list[Accessibility]:
        """
        accessibility 記述子 (draft-ietf-moq-msf-01 §5.2.44 (Accessibility))。
        """
    @accessibility.setter
    def accessibility(self, /, value: Sequence[Accessibility]) -> None:
        """
        accessibility 記述子 (draft-ietf-moq-msf-01 §5.2.44 (Accessibility))。
        """
    @property
    def alt_group(self, /) -> int |None:
        """
        オルタネートグループ (draft-ietf-moq-msf-01 §5.2.12 (Alternate group))。
        """
    @alt_group.setter
    def alt_group(self, /, value: int |None) -> None:
        """
        オルタネートグループ (draft-ietf-moq-msf-01 §5.2.12 (Alternate group))。
        """
    @property
    def auth_info(self, /) -> list[AuthInfo] |None:
        """
        認可情報 (draft-ietf-moq-msf-01 §5.2.42 (Authorization Info))。
        """
    @auth_info.setter
    def auth_info(self, /, value: Sequence[AuthInfo] |None) -> None:
        """
        認可情報 (draft-ietf-moq-msf-01 §5.2.42 (Authorization Info))。
        """
    @property
    def avg_bitrate(self, /) -> int |None:
        """
        平均ビットレート (bps) (draft-ietf-moq-msf-01 §5.2.23 (Average Bitrate))。
        """
    @avg_bitrate.setter
    def avg_bitrate(self, /, value: int |None) -> None:
        """
        平均ビットレート (bps) (draft-ietf-moq-msf-01 §5.2.23 (Average Bitrate))。
        """
    @property
    def bitrate(self, /) -> int |None:
        """
        最大ビットレート (bps) (draft-ietf-moq-msf-01 §5.2.22 (Maximum Bitrate))。
        """
    @bitrate.setter
    def bitrate(self, /, value: int |None) -> None:
        """
        最大ビットレート (bps) (draft-ietf-moq-msf-01 §5.2.22 (Maximum Bitrate))。
        """
    @property
    def buffers(self, /) -> Buffers |None:
        """
        ターゲットバッファ (draft-ietf-moq-msf-01 §5.2.9 (Buffers))。
        
        `target_latency` と同時には指定できない。
        """
    @buffers.setter
    def buffers(self, /, value: Buffers |None) -> None:
        """
        ターゲットバッファ (draft-ietf-moq-msf-01 §5.2.9 (Buffers))。
        
        `target_latency` と同時には指定できない。
        """
    @property
    def channel_config(self, /) -> str |None:
        """
        チャンネル設定 (draft-ietf-moq-msf-01 §5.2.29 (Channel configuration))。
        """
    @channel_config.setter
    def channel_config(self, /, value: str |None) -> None:
        """
        チャンネル設定 (draft-ietf-moq-msf-01 §5.2.29 (Channel configuration))。
        """
    @property
    def cipher_suite(self, /) -> str |None:
        """
        暗号スイート (draft-ietf-moq-msf-01 §5.2.39 (Cipher Suite))。
        """
    @cipher_suite.setter
    def cipher_suite(self, /, value: str |None) -> None:
        """
        暗号スイート (draft-ietf-moq-msf-01 §5.2.39 (Cipher Suite))。
        """
    @property
    def codec(self, /) -> str |None:
        """
        コーデック (draft-ietf-moq-msf-01 §5.2.18 (Codec))。
        """
    @codec.setter
    def codec(self, /, value: str |None) -> None:
        """
        コーデック (draft-ietf-moq-msf-01 §5.2.18 (Codec))。
        """
    @property
    def connection_uri(self, /) -> str |None:
        """
        接続先 URI (draft-ietf-moq-msf-01 §5.2.36 (Connection URI))。
        """
    @connection_uri.setter
    def connection_uri(self, /, value: str |None) -> None:
        """
        接続先 URI (draft-ietf-moq-msf-01 §5.2.36 (Connection URI))。
        """
    @property
    def depends(self, /) -> list[str]:
        """
        依存トラック名 (draft-ietf-moq-msf-01 §5.2.14 (Dependencies))。
        """
    @depends.setter
    def depends(self, /, value: Sequence[str]) -> None:
        """
        依存トラック名 (draft-ietf-moq-msf-01 §5.2.14 (Dependencies))。
        """
    @property
    def display_height(self, /) -> int |None:
        """
        表示高さ (px) (draft-ietf-moq-msf-01 §5.2.31 (Display height))。
        """
    @display_height.setter
    def display_height(self, /, value: int |None) -> None:
        """
        表示高さ (px) (draft-ietf-moq-msf-01 §5.2.31 (Display height))。
        """
    @property
    def display_width(self, /) -> int |None:
        """
        表示幅 (px) (draft-ietf-moq-msf-01 §5.2.30 (Display width))。
        """
    @display_width.setter
    def display_width(self, /, value: int |None) -> None:
        """
        表示幅 (px) (draft-ietf-moq-msf-01 §5.2.30 (Display width))。
        """
    @property
    def encryption_scheme(self, /) -> str |None:
        """
        暗号化方式 (draft-ietf-moq-msf-01 §5.2.38 (Encryption Scheme))。
        """
    @encryption_scheme.setter
    def encryption_scheme(self, /, value: str |None) -> None:
        """
        暗号化方式 (draft-ietf-moq-msf-01 §5.2.38 (Encryption Scheme))。
        """
    @property
    def event_type(self, /) -> str |None:
        """
        イベントタイムラインタイプ (draft-ietf-moq-msf-01 §5.2.5 (Event timeline type))。
        """
    @event_type.setter
    def event_type(self, /, value: str |None) -> None:
        """
        イベントタイムラインタイプ (draft-ietf-moq-msf-01 §5.2.5 (Event timeline type))。
        """
    @property
    def framerate(self, /) -> float |None:
        """
        フレームレート (fps) (draft-ietf-moq-msf-01 §5.2.20 (Framerate))。
        """
    @framerate.setter
    def framerate(self, /, value: float |None) -> None:
        """
        フレームレート (fps) (draft-ietf-moq-msf-01 §5.2.20 (Framerate))。
        """
    @property
    def height(self, /) -> int |None:
        """
        エンコード高さ (px) (draft-ietf-moq-msf-01 §5.2.27 (Height))。
        """
    @height.setter
    def height(self, /, value: int |None) -> None:
        """
        エンコード高さ (px) (draft-ietf-moq-msf-01 §5.2.27 (Height))。
        """
    @property
    def init_ref(self, /) -> str |None:
        """
        初期化データ参照 (draft-ietf-moq-msf-01 §5.2.13 (Initialization reference))。
        """
    @init_ref.setter
    def init_ref(self, /, value: str |None) -> None:
        """
        初期化データ参照 (draft-ietf-moq-msf-01 §5.2.13 (Initialization reference))。
        """
    @property
    def is_live(self, /) -> bool:
        """
        ライブフラグ (draft-ietf-moq-msf-01 §5.2.7 (Is Live))。必須。
        """
    @is_live.setter
    def is_live(self, /, value: bool) -> None:
        """
        ライブフラグ (draft-ietf-moq-msf-01 §5.2.7 (Is Live))。必須。
        """
    @property
    def key_id(self, /) -> str |None:
        """
        鍵識別子 (draft-ietf-moq-msf-01 §5.2.40 (Key ID))。
        """
    @key_id.setter
    def key_id(self, /, value: str |None) -> None:
        """
        鍵識別子 (draft-ietf-moq-msf-01 §5.2.40 (Key ID))。
        """
    @property
    def label(self, /) -> str |None:
        """
        トラックラベル (draft-ietf-moq-msf-01 §5.2.10 (Track label))。
        """
    @label.setter
    def label(self, /, value: str |None) -> None:
        """
        トラックラベル (draft-ietf-moq-msf-01 §5.2.10 (Track label))。
        """
    @property
    def lang(self, /) -> str |None:
        """
        言語タグ (draft-ietf-moq-msf-01 §5.2.32 (Language))。
        """
    @lang.setter
    def lang(self, /, value: str |None) -> None:
        """
        言語タグ (draft-ietf-moq-msf-01 §5.2.32 (Language))。
        """
    @property
    def max_gop_duration(self, /) -> int |None:
        """
        最大 GOP 長 (ms) (draft-ietf-moq-msf-01 §5.2.24 (Maximum GOP Duration))。
        """
    @max_gop_duration.setter
    def max_gop_duration(self, /, value: int |None) -> None:
        """
        最大 GOP 長 (ms) (draft-ietf-moq-msf-01 §5.2.24 (Maximum GOP Duration))。
        """
    @property
    def max_group_duration(self, /) -> int |None:
        """
        最大 Group 長 (ms) (draft-ietf-moq-msf-01 §5.2.25 (Maximum Group Duration))。
        """
    @max_group_duration.setter
    def max_group_duration(self, /, value: int |None) -> None:
        """
        最大 Group 長 (ms) (draft-ietf-moq-msf-01 §5.2.25 (Maximum Group Duration))。
        """
    @property
    def mime_type(self, /) -> str |None:
        """
        MIME タイプ (draft-ietf-moq-msf-01 §5.2.19 (Mimetype))。
        """
    @mime_type.setter
    def mime_type(self, /, value: str |None) -> None:
        """
        MIME タイプ (draft-ietf-moq-msf-01 §5.2.19 (Mimetype))。
        """
    @property
    def name(self, /) -> str:
        """
        トラック名 (draft-ietf-moq-msf-01 §5.2.3 (Track name))。必須。
        """
    @name.setter
    def name(self, /, value: str) -> None:
        """
        トラック名 (draft-ietf-moq-msf-01 §5.2.3 (Track name))。必須。
        """
    @property
    def namespace(self, /) -> str |None:
        """
        トラックネームスペース (draft-ietf-moq-msf-01 §5.2.2 (Track namespace))。
        """
    @namespace.setter
    def namespace(self, /, value: str |None) -> None:
        """
        トラックネームスペース (draft-ietf-moq-msf-01 §5.2.2 (Track namespace))。
        """
    @property
    def packaging(self, /) -> str:
        """
        パッケージングタイプ (draft-ietf-moq-msf-01 §5.2.4 (Packaging))。必須。
        """
    @packaging.setter
    def packaging(self, /, value: str) -> None:
        """
        パッケージングタイプ (draft-ietf-moq-msf-01 §5.2.4 (Packaging))。必須。
        """
    @property
    def render_group(self, /) -> int |None:
        """
        レンダーグループ (draft-ietf-moq-msf-01 §5.2.11 (Render group))。
        """
    @render_group.setter
    def render_group(self, /, value: int |None) -> None:
        """
        レンダーグループ (draft-ietf-moq-msf-01 §5.2.11 (Render group))。
        """
    @property
    def role(self, /) -> str |None:
        """
        トラックロール (draft-ietf-moq-msf-01 §5.2.6 (Track role))。
        """
    @role.setter
    def role(self, /, value: str |None) -> None:
        """
        トラックロール (draft-ietf-moq-msf-01 §5.2.6 (Track role))。
        """
    @property
    def samplerate(self, /) -> int |None:
        """
        オーディオサンプルレート (Hz) (draft-ietf-moq-msf-01 §5.2.28 (Audio sample rate))。
        """
    @samplerate.setter
    def samplerate(self, /, value: int |None) -> None:
        """
        オーディオサンプルレート (Hz) (draft-ietf-moq-msf-01 §5.2.28 (Audio sample rate))。
        """
    @property
    def spatial_id(self, /) -> int |None:
        """
        スペーシャル ID (draft-ietf-moq-msf-01 §5.2.17 (Spatial ID))。
        """
    @spatial_id.setter
    def spatial_id(self, /, value: int |None) -> None:
        """
        スペーシャル ID (draft-ietf-moq-msf-01 §5.2.17 (Spatial ID))。
        """
    @property
    def target_latency(self, /) -> int |None:
        """
        ターゲットレイテンシ (ms) (draft-ietf-moq-msf-01 §5.2.8 (Target latency))。
        
        `buffers` と同時には指定できない。
        """
    @target_latency.setter
    def target_latency(self, /, value: int |None) -> None:
        """
        ターゲットレイテンシ (ms) (draft-ietf-moq-msf-01 §5.2.8 (Target latency))。
        
        `buffers` と同時には指定できない。
        """
    @property
    def template(self, /) -> Template |None:
        """
        メディアタイムラインテンプレート (draft-ietf-moq-msf-01 §5.2.15 (Template))。
        """
    @template.setter
    def template(self, /, value: Template |None) -> None:
        """
        メディアタイムラインテンプレート (draft-ietf-moq-msf-01 §5.2.15 (Template))。
        """
    @property
    def temporal_id(self, /) -> int |None:
        """
        テンポラル ID (draft-ietf-moq-msf-01 §5.2.16 (Temporal ID))。
        """
    @temporal_id.setter
    def temporal_id(self, /, value: int |None) -> None:
        """
        テンポラル ID (draft-ietf-moq-msf-01 §5.2.16 (Temporal ID))。
        """
    @property
    def timescale(self, /) -> int |None:
        """
        タイムスケール (draft-ietf-moq-msf-01 §5.2.21 (Timescale))。
        """
    @timescale.setter
    def timescale(self, /, value: int |None) -> None:
        """
        タイムスケール (draft-ietf-moq-msf-01 §5.2.21 (Timescale))。
        """
    @property
    def token(self, /) -> str |None:
        """
        認証トークン (draft-ietf-moq-msf-01 §5.2.37 (Token))。
        """
    @token.setter
    def token(self, /, value: str |None) -> None:
        """
        認証トークン (draft-ietf-moq-msf-01 §5.2.37 (Token))。
        """
    @property
    def track_base_key(self, /) -> str |None:
        """
        track 基本鍵 (draft-ietf-moq-msf-01 §5.2.41 (Track Base Key))。
        """
    @track_base_key.setter
    def track_base_key(self, /, value: str |None) -> None:
        """
        track 基本鍵 (draft-ietf-moq-msf-01 §5.2.41 (Track Base Key))。
        """
    @property
    def track_duration(self, /) -> int |None:
        """
        トラック長 (ms) (draft-ietf-moq-msf-01 §5.2.35 (Track duration))。
        
        `is_live` が真の場合は指定できない。
        """
    @track_duration.setter
    def track_duration(self, /, value: int |None) -> None:
        """
        トラック長 (ms) (draft-ietf-moq-msf-01 §5.2.35 (Track duration))。
        
        `is_live` が真の場合は指定できない。
        """
    @property
    def width(self, /) -> int |None:
        """
        エンコード幅 (px) (draft-ietf-moq-msf-01 §5.2.26 (Width))。
        """
    @width.setter
    def width(self, /, value: int |None) -> None:
        """
        エンコード幅 (px) (draft-ietf-moq-msf-01 §5.2.26 (Width))。
        """

@final
class TrackProperties:
    """
    MOQT の Track Properties。
    
    Track 単位で決まるプロパティである。SUBSCRIBE_OK / FETCH_OK / PUBLISH が運ぶ
    (draft-ietf-moq-transport-21 §16.8 (Properties) Table 14)。
    """
    def __eq__(self, other: object, /) -> bool: ...
    def __iter__(self, /) -> TrackPropertiesIterator: ...
    def __len__(self, /) -> int: ...
    def __new__(cls, /) -> TrackProperties:
        """
        空のプロパティ集合を作成する。
        """
    def __repr__(self, /) -> str: ...
    def add(self, /, prop_type: int, value: Any) -> None:
        """
        プロパティを 1 件追加する。
        
        偶数型は varint として `int` を、奇数型は長さ付きバイト列として `bytes` を渡す。
        """
    @staticmethod
    def decode(data: bytes) -> TrackProperties:
        """
        バッファ全体を Track Properties としてデコードする。
        
        長さプレフィックスが無いためバッファ末尾まで読む。空のバッファは空の集合になる。
        型番号の重複など draft の MUST に違反する入力は `ValueError` になる。
        """
    @property
    def default_publisher_group_order(self, /) -> int |None:
        """
        DEFAULT_PUBLISHER_GROUP_ORDER (0x22): 既定の Group Order。
        
        省略時は `None` になる。draft の既定値 Ascending (0x1) は適用しない
        (draft-ietf-moq-transport-21 §10.5 (Default Publisher Group Order))。
        """
    @property
    def default_publisher_priority(self, /) -> int |None:
        """
        DEFAULT_PUBLISHER_PRIORITY (0x0E): 既定の Publisher Priority。
        
        省略時は `None` になる。draft の既定値 128 は適用しない
        (draft-ietf-moq-transport-21 §10.4 (Default Publisher Priority))。
        """
    @property
    def dynamic_groups(self, /) -> int |None:
        """
        DYNAMIC_GROUPS (0x30): Group が動的に決まるか。
        
        (draft-ietf-moq-transport-21 §10.6 (Dynamic Groups))
        """
    def encode(self, /) -> bytes:
        """
        プロパティ列をエンコードする。
        
        Object Properties と異なり長さプレフィックスを付けない。カウントプレフィックスを
        持たない KVP 列そのものになり、空の集合は 0 バイトになる
        (draft-ietf-moq-transport-21 §8.4 (Track and Object Properties))。
        subscription を送る引数へ埋め込むバイト列がこれである。
        """
    def find_varint(self, /, prop_type: int) -> int |None:
        """
        任意の型番号の varint 値を引く。
        
        見つからない場合と、その型番号の値がバイト列である場合は `None` になる。
        IMMUTABLE_PROPERTIES の内側も探索し、外側の値を優先する
        (draft-ietf-moq-transport-21 §10.7 (Immutable Properties))。
        """
    @property
    def has_unknown_mandatory(self, /) -> bool:
        """
        未知の必須プロパティを含むか。
        
        必須の範囲は `MANDATORY_TRACK_PROPERTY_MIN` から `MANDATORY_TRACK_PROPERTY_MAX`
        である (draft-ietf-moq-transport-21 §16.8 (Properties) Table 14)。未知の必須
        プロパティを含む Track は扱えないため、アプリは購読を拒否できる。
        """
    def items(self, /) -> list:
        """
        プロパティを保持している順に `(型番号, 値)` として列挙する。
        
        ワイヤ上の型番号の昇順ではなく、`add()` で追加した順に返す。
        `list(properties)` も同じ列を返す。
        """
    @property
    def object_delivery_timeout(self, /) -> int |None:
        """
        OBJECT_DELIVERY_TIMEOUT (0x02): Object の配送期限 (ms)。
        """
    @property
    def subgroup_delivery_timeout(self, /) -> int |None:
        """
        SUBGROUP_DELIVERY_TIMEOUT (0x06): Subgroup の配送期限 (ms)。
        """
    def to_dict(self, /) -> dict:
        """
        プロパティを `{prop_type: 値}` の辞書へ変換する。
        
        辞書は Session の `send_*` に渡す `track_properties` 引数と同じ形である。
        未知の型番号も含めてすべて返す。
        """

@final
class TrackPropertiesIterator:
    """
    Track Properties の `(型番号, 値)` を追加順に列挙するイテレータ。
    
    列挙の途中で元の集合を `add()` で変更しても、列挙中の列は変わらない。
    """
    def __iter__(self, /) -> TrackPropertiesIterator: ...
    def __next__(self, /) -> Any |None: ...
    def __repr__(self, /) -> str: ...

@final
class Uri:
    """
    パース済みの MSF URI (draft-ietf-moq-msf-01 §11.1)。
    
    `moqt://` URI の fragment (`msf:...`) をパースした結果である。percent-decode は
    行わず、値をそのまま保持する。
    """
    def __eq__(self, other: object, /) -> bool: ...
    def __repr__(self, /) -> str: ...
    @property
    def authority(self, /) -> str:
        """
        authority (host + 任意の port)。
        """
    def c4m_tokens(self, /) -> list[str]:
        """
        c4m パラメータの値を出現順に返す。
        """
    def connection_types(self, /) -> list[str]:
        """
        connection パラメータが要求する接続種別を出現順に返す。
        
        値は `quic` または `webtransport` である。
        """
    def location_ranges(self, /) -> list[dict]:
        """
        location-range パラメータを辞書のリストとして返す。
        
        各辞書は `start_group_id` / `start_object_id` / `end_group_id` /
        `end_object_id` を持つ。省略された要素は `None` になる。
        """
    def mediatime_ranges(self, /) -> list[tuple[int, int |None]]:
        """
        mediatime-range パラメータを `(開始 ms, 終了 ms)` のリストとして返す。
        """
    @property
    def namespace(self, /) -> list:
        """
        track-identifier を分解したネームスペース。
        """
    def parameter_values(self, /, name: str) -> list[str]:
        """
        指定名のパラメータ値を出現順に返す。
        """
    @property
    def parameters(self, /) -> list[tuple[str, str]]:
        """
        fragment パラメータ列を `(名前, 値)` のリストとして返す。出現順である。
        """
    @staticmethod
    def parse(uri: str) -> Uri:
        """
        MSF URI をパースする。
        
        draft-ietf-moq-msf-01 §11.1 の
        `msf-uri = "moqt://" authority path-abempty [ "?" query ] "#" msf-fragment`
        に従う。scheme は case-insensitive である。
        """
    @property
    def path(self, /) -> str:
        """
        path (先頭の `/` を含む。無い場合は空文字列)。
        """
    @property
    def query(self, /) -> str |None:
        """
        query (`?` 以降。無い場合は `None`)。
        """
    @property
    def track_name(self, /) -> bytes:
        """
        track-identifier を分解した Track 名。
        """
    def wallclock_ranges(self, /) -> list[tuple[int, int |None]]:
        """
        wallclock-range パラメータを `(開始 ms, 終了 ms)` のリストとして返す。
        
        終了が省略された open range の終了は `None` になる。
        """

@final
class VerifyOptions:
    """
    署名検証のオプション。
    """
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __new__(cls, /, expected_algorithm: int |None = None, expected_type: str |None = None) -> VerifyOptions:
        """
        検証オプションを組み立てる。
        """
    def __repr__(self, /) -> str: ...
    @property
    def expected_algorithm(self, /) -> int |None:
        """
        トークンの `alg` に期待するアルゴリズムの識別子。
        """
    @expected_algorithm.setter
    def expected_algorithm(self, /, value: int |None) -> None:
        """
        トークンの `alg` に期待するアルゴリズムの識別子。
        """
    @property
    def expected_type(self, /) -> str |None:
        """
        トークンの `typ` に期待する値。
        
        CAT では `CAT_CONTENT_TYPE` (`"CAT"`) を指定する。未指定の場合は `typ` を
        検証しない。
        """
    @expected_type.setter
    def expected_type(self, /, value: str |None) -> None:
        """
        トークンの `typ` に期待する値。
        
        CAT では `CAT_CONTENT_TYPE` (`"CAT"`) を指定する。未指定の場合は `typ` を
        検証しない。
        """

def classify_data_stream_type(type_id: int) -> str |None:
    """
    stream type の varint が制御ストリームかデータストリームかを判定する。
    
    データストリームの場合は種別を表す文字列を返す。制御ストリームと未知の値は
    `None` を返す。
    
    (draft-ietf-moq-transport-21 §6.4.1 (Unidirectional Streams) Table 3)
    """

def decode_cbor(data: bytes) -> CborValue:
    """
    CBOR のデータ項目をデコードする。
    
    入力の全バイトをデータ項目として消費する。末尾に余分なバイトがある場合は
    `ValueError` になる。複数のデータ項目を続けて読む場合は
    [`decode_cbor_partial`] を使う。
    """

def decode_cbor_partial(data: bytes) -> tuple[CborValue, int]:
    """
    CBOR のデータ項目をデコードし `(値, 消費バイト数)` を返す。
    
    ブロックの後ろに続くバイト列は消費しない。
    """

def decode_message(data: bytes) -> tuple[Message, int]:
    """
    制御メッセージを 1 件デコードする。
    
    返り値は `(メッセージ, 消費バイト数)` である。`data` の先頭が制御メッセージの
    途中で切れている場合と、メッセージとして不正な場合は `ValueError` を送出する。
    
    制御メッセージは Type (vi64) + Length (u16 big-endian) + Message Body で構成される
    (draft-ietf-moq-transport-21 §9 (Control Messages))。
    """

def decode_parameter(param_type: int, value: bytes) -> Any:
    """
    パラメータの値部分をデコードして Python の値へ変換する。
    
    `Event.parameters` と `Message.parameters` が返す辞書の値は、パラメータ 1 件分の
    エンコード済みバイト列である。この関数で型に応じた値へ解釈する。
    偶数型は `int`、長さ付きバイト列は `bytes`、`LARGEST_OBJECT` は
    `(group_id, object_id)`、`AUTHORIZATION_TOKEN` は辞書、
    `FILL_PARAMETERS` は入れ子の辞書になる。
    
    `AUTHORIZATION_TOKEN` の辞書は `kind` で種別を表し、キーは種別ごとに異なる
    (draft-ietf-moq-transport-21 §8.9 (Authorization Token Compression))。
    
    - `delete` / `use_alias`: `alias`
    - `register`: `alias` / `token_type` / `token_value`
    - `use_value`: `token_type` / `token_value`
    
    解釈できないバイト列は `ValueError` になる。この節番号・規則は draft 由来であり
    将来の改訂で変更されうる。
    (draft-ietf-moq-transport-21 §9.20 (Control Message Parameters))
    """

def decode_varint(data: bytes) -> tuple[int, int]:
    """
    先頭の vi64 をデコードし `(値, 消費バイト数)` を返す。
    
    非最小エンコーディングも受理する。バイト列が途中で切れている場合は
    `ValueError` を送出する。
    """

def decode_varint_prefix(data: bytes) -> tuple[int, int] |None:
    """
    先頭の vi64 をデコードし `(値, 消費バイト数)` を返す。
    
    バイト列が途中で切れている場合は `None` を返し、続きの到着を待つ。
    非最小エンコーディングも受理する。
    """

def default_signing_algorithm(key: CoseKey) -> int:
    """
    鍵の種別から既定の署名アルゴリズムの識別子を返す。
    
    対称鍵は HMAC-SHA256、EC2 は曲線に対応する ES256 / ES384 / ES512、OKP は
    EdDSA になる。
    """

def digest(algorithm: str, message: bytes) -> bytes:
    """
    メッセージのハッシュを計算する。
    
    `algorithm` は `sha256` / `sha384` / `sha512` のいずれかである。JWK サムプリント
    (RFC 7638) など、署名以外でハッシュが必要な処理に使う。
    """

def encode_cbor(value: CborValue) -> bytes:
    """
    CBOR のデータ項目をエンコードする。
    
    RFC 8949 §4.2 の決定論的エンコードに従う。マップのキーはキーのエンコード済み
    バイト列の昇順に並び、浮動小数点数は値を保つ最短の幅になる。
    """

def encode_varint(value: int) -> bytes:
    """
    vi64 をエンコードする (draft-ietf-moq-transport-21 §8.1 (Variable-Length Integers))。
    
    最小バイト数の表現を返す。
    """

def generate(source: Any |None = None) -> int:
    """
    GREASE 値を生成する。
    
    `source` は `stop` を 1 つだけ受け取り、`[0, stop)` の整数を返す呼び出し可能
    オブジェクトである (`random.Random.randrange` と同じ形)。省略した場合は
    標準ライブラリの `random.randrange` を使う。テストから決定的な値を渡せるように
    引数で受け取る。
    """

def is_grease(value: int) -> bool:
    """
    与えられた値が GREASE 値かどうかを返す。
    
    上限 `GREASE_MAX` を超えた値も、値の並びに合致すれば `True` になる。受信側は
    将来 draft の上限が広がった場合にも未知値として無視できる必要があるためである。
    """

def is_padding_datagram(data: bytes) -> bool:
    """
    データグラムの種別がパディングかを判定する。
    
    データグラムは stream type を持たないため、先頭の varint で判定する。
    """

def parse_fragment_pairs(fragment: str) -> list[tuple[str, str]]:
    """
    fragment を `&` 区切りのパラメータ列へ分解する
    (draft-ietf-moq-msf-01 §11.1)。
    
    `msf:` prefix の検証は行わず、`&` 区切りの `名前=値` を取り出すだけである。
    """

def parse_msf_fragment(fragment: str) -> tuple[Any, bytes, list[tuple[str, str]]]:
    """
    MSF fragment (`msf:` prefix 付き) を namespace と Track 名とパラメータへ分解する
    (draft-ietf-moq-msf-01 §11.1 (URL construction and interpretation))。
    
    `Uri.parse` を通さない入力を扱う。返り値は
    `(namespace, track_name, [(名前, 値), ...])` である。
    """

def parse_name(text: str) -> tuple[Any, bytes]:
    """
    MSF の Track 識別子 (`namespace--track` 形式) を namespace と Track 名へ分解する
    (draft-ietf-moq-transport-21 §8.8 (Representing Namespace and Track Names))。
    
    分解できない場合は `ValueError` を送出する。メッセージには moqt-rs の
    `NameParseError` の `Display` 表現 (失敗した規則の説明) をそのまま使う。
    """

def parse_namespace(text: str) -> list:
    """
    namespace の正規表現をタプルへパースする。
    
    `serialize_namespace` の逆変換であり、§8.8.1 (Parsing Serialized Names) の MUST を
    適用する。空文字列は 0 フィールドの namespace になる。パースできない場合は
    `ValueError` を送出し、メッセージには moqt-rs の `NameParseError` の `Display` 表現を
    そのまま使う。
    """

def parse_track_name(text: str) -> bytes:
    """
    Track 名の正規表現をバイト列へパースする。
    
    `serialize_track_name` の逆変換であり、§8.8.1 (Parsing Serialized Names) の MUST を
    適用する。パースできない場合は `ValueError` を送出し、メッセージには moqt-rs の
    `NameParseError` の `Display` 表現をそのまま使う。
    """

def resolve_catalog_variables(document: bytes, fragment: str) -> bytes:
    """
    カタログの変数参照を fragment の値で解決する
    (draft-ietf-moq-msf-01 §5.4 (Catalog variables))。
    """

def resolve_timeline_template(template: list, n: int) -> tuple[int, int, int, int] |None:
    """
    MSF の media timeline template から n 番目のエントリを計算する
    (draft-ietf-moq-msf-01 §7.4.1)。
    
    `template` は `Catalog.tracks` の `template` 配列である。値が負の整数または
    配列でない場合は `ValueError` になる。計算が overflow する場合は `None` を返す。
    型付きで組み立てた [`Template`] からは [`Template::resolve_entry`] で同じ計算ができる。
    """

def serialize_name(namespace: Sequence[Sequence[int]], track_name: bytes) -> str:
    """
    namespace と Track 名を MSF の Track 識別子 (`namespace--track` 形式) へ変換する。
    """

def serialize_namespace(namespace: Sequence[Sequence[int]]) -> str:
    """
    namespace を draft-ietf-moq-transport-21 §8.8 (Representing Namespace and Track Names)
    の正規表現へ変換する。
    
    各フィールドを `-` で連結し、リテラル (`a-z` / `A-Z` / `0-9` / `_`) でないバイトは
    `.` と 16 進 2 桁へエスケープする。0 フィールドの namespace は空文字列になる。
    DPoP の Authorization Context の `tns` へそのまま渡せる
    (draft-nandakumar-moq-generic-dpop-proof-00 §5.1.3)。
    """

def serialize_track_name(track_name: bytes) -> str:
    """
    Track 名を draft-ietf-moq-transport-21 §8.8 (Representing Namespace and Track Names)
    の正規表現へ変換する。
    
    単体の Track 名を表す関数であり、Full Track Name の長さ制約 (§8.7) は適用しない。
    `-` は namespace の区切りと衝突するため `.2d` へエスケープされる。DPoP の
    Authorization Context の `tn` へそのまま渡せる
    (draft-nandakumar-moq-generic-dpop-proof-00 §5.1.3)。
    """

def setup_stream_type() -> int:
    """
    制御ストリームの stream type を返す。
    """

def sign(algorithm: int, key: CoseKey, message: bytes) -> bytes:
    """
    メッセージに署名または MAC を付ける。
    
    対称鍵の場合は MAC を返す。EC2 / OKP の場合は COSE の固定長形式 (ECDSA は
    `r || s`) の署名を返す。`algorithm` は COSE のアルゴリズム識別子であり、
    draft-ietf-moq-c4m-01 付録 A のベクタが HMAC-SHA256 に使う `-4` も受理する。
    
    対応するアルゴリズムは HMAC 256/384/512、ES256/384/512、EdDSA (Ed25519) である。
    """

def verify(algorithm: int, key: CoseKey, message: bytes, signature: bytes) -> None:
    """
    署名または MAC を検証する。
    
    検証に失敗した場合は `ValueError` になる。埋め込みの JWK を検証する場合は
    [`crate::c4m::jwk::Jwk::to_cose_key`] で公開鍵へ変換して渡す。
    """

def __getattr__(name: str) -> Incomplete: ...
