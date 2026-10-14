"""MOQT セッションの接続方式。"""

from enum import StrEnum

MOQT_PROTOCOL = "moqt-22"
"""MOQT のプロトコル識別子。

QUIC の ALPN、QMux over TLS の ALPN、WebTransport の `WT-Available-Protocols` で使う
(draft-ietf-moq-transport-22 §6.2 (Session establishment) /
draft-nandakumar-moq-qmux-moqt-00 §3.2 (ALPN Identification))。draft 改訂で
値が変わる可能性がある。
"""


class Transport(StrEnum):
    """MOQT セッションの接続方式。"""

    Quic = "quic"
    """QUIC 直接接続 (draft-ietf-moq-transport-22 §6.2.2 (Native QUIC))。"""

    Qmux = "qmux"
    """QMux 直接接続 (draft-nandakumar-moq-qmux-moqt-00)。

    UDP が使えない環境向けに、TCP/TLS 上のストリーム多重化 (QMux) で MOQT を運ぶ
    (draft-ietf-quic-qmux-02 (QMux))。MOQT のストリームは QMux のストリームへ
    そのまま対応する (draft-nandakumar-moq-qmux-moqt-00 §4.1 (Stream Mapping))。
    """

    WebTransportOverHTTP2 = "wt-h2"
    """WebTransport over HTTP/2 (WT-H2)。"""

    WebTransportOverHTTP3 = "wt-h3"
    """WebTransport over HTTP/3 (WT-H3)。"""


__all__ = [
    "MOQT_PROTOCOL",
    "Transport",
]
