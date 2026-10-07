"""MOQT セッションの接続方式。"""

from enum import StrEnum

MOQT_PROTOCOL = "moqt-22"
"""MOQT のプロトコル識別子。

QUIC の ALPN と WebTransport の `WT-Available-Protocols` で使う
(draft-ietf-moq-transport-22 §6.2 (Session establishment))。draft 改訂で
値が変わる可能性がある。
"""


class Transport(StrEnum):
    """MOQT セッションの接続方式。"""

    Quic = "quic"
    """QUIC 直接接続 (draft-ietf-moq-transport-22 §6.2.2 (Native QUIC))。"""

    WebTransportOverHTTP2 = "wt-h2"
    """WebTransport over HTTP/2 (WT-H2)。"""

    WebTransportOverHTTP3 = "wt-h3"
    """WebTransport over HTTP/3 (WT-H3)。"""


__all__ = [
    "MOQT_PROTOCOL",
    "Transport",
]
