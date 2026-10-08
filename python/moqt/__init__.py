"""MOQT (Media over QUIC Transport) の codec と状態機械を扱う Python ライブラリ。

`moqt-rs` が MOQT (draft-ietf-moq-transport-22) の codec と sans I/O セッション
状態機械を、LOC (draft-ietf-moq-loc-04) / MSF (draft-ietf-moq-msf-01) /
C4M (draft-ietf-moq-c4m-01) の codec を PyO3 経由で提供し、このパッケージが
それらを公開する。

`webtransport-py` と接続する高レベル API は `moqt.moq` が提供する。relay は
どちらの層にも含まない。

公開 API:

- `moqt.moqt`: MOQT の codec と sans I/O セッション状態機械
- `moqt.loc`: LOC プロパティの codec
- `moqt.msf`: MSF のカタログとタイムラインの codec
- `moqt.c4m`: C4M (CAT) のトークンと DPoP proof の codec
- `moqt.moq`: WebTransport 接続上で MOQT セッションを扱う client / server
- `moqt.moq.testing`: 他プロジェクトのテストから使う pytest fixture 群

`moqt.moq` は `moqt._native` を直接使うため、このモジュールから再輸出しない。
利用者は `from moqt.moq import Client` のように `moqt.moq` から取り出す。

MOQT は draft 由来であり、将来の改訂で変更される可能性がある。
"""

from moqt import c4m, loc, moqt, msf

__all__ = [
    "c4m",
    "loc",
    "moqt",
    "msf",
]
