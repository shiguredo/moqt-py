"""moqt.moq.Client の接続方式選択の単体テスト。"""

import pytest
from moqt import moqt
from moqt.moq import Client, Transport
from webtransport import Client as WebTransportClient
from webtransport import HTTPVersion, quic


def test_url_scheme_must_be_moqt() -> None:
    """
    `moqt://` 以外の URL を拒否することを確認する。

    MOQT の URI は `moqt://` である
    (draft-ietf-moq-transport-22 §6.1 (MOQT URI Scheme))。
    """
    with pytest.raises(ValueError, match="use moqt://"):
        Client(url="https://127.0.0.1:4433/webtransport")


def test_default_transport_is_webtransport_over_http3() -> None:
    """
    `transport` を省略した場合に WT-H3 になり、https URI へ接続することを確認する。

    WebTransport では moqt URI のスキームを https に置き換えた URI へ
    extended CONNECT を送る (draft-ietf-moq-transport-22 §6.2.1 (WebTransport))。
    接続方式は統一 API の `HTTPVersion` で選ぶ。
    """
    client = Client(url="moqt://127.0.0.1:4433/webtransport")
    assert client.transport is Transport.WebTransportOverHTTP3
    transport = client._transport
    assert isinstance(transport, WebTransportClient)
    assert transport.http_version is HTTPVersion.HTTP3
    assert transport.h3 is not None
    assert transport.h2 is None
    assert transport.url == "https://127.0.0.1:4433/webtransport"


def test_webtransport_over_http2_uses_the_https_uri() -> None:
    """
    WT-H2 が https URI へ接続することを確認する。
    """
    client = Client(
        url="moqt://127.0.0.1:4433/webtransport",
        transport=Transport.WebTransportOverHTTP2,
    )
    assert client.transport is Transport.WebTransportOverHTTP2
    transport = client._transport
    assert isinstance(transport, WebTransportClient)
    assert transport.http_version is HTTPVersion.HTTP2
    assert transport.h2 is not None
    assert transport.h3 is None
    assert transport.url == "https://127.0.0.1:4433/webtransport"


def test_webtransport_over_http2_rejects_ca_file() -> None:
    """
    WT-H2 では `ca_file` を指定できないことを確認する。

    webtransport-py の WT-H2 client は `ca_file` を受け取らない。
    """
    with pytest.raises(ValueError, match="ca_file is not supported"):
        Client(
            url="moqt://127.0.0.1:4433/webtransport",
            transport=Transport.WebTransportOverHTTP2,
            ca_file="ca.pem",
        )


def test_quic_connects_to_the_uri_authority() -> None:
    """
    QUIC 直接接続が URI の authority へ接続することを確認する。

    authority の host と port (省略時は 443) へ QUIC 接続する
    (draft-ietf-moq-transport-22 §6.2.2 (Native QUIC))。
    """
    client = Client(url="moqt://example.com:4433/live", transport=Transport.Quic)
    assert client.transport is Transport.Quic
    transport = client._transport
    assert isinstance(transport, quic.Client)
    assert (transport.host, transport.port) == ("example.com", 4433)

    # port を省略した場合は 443 になる (§6.2 (Session establishment))
    default_port = Client(url="moqt://example.com", transport=Transport.Quic)
    default_transport = default_port._transport
    assert isinstance(default_transport, quic.Client)
    assert default_transport.port == 443


def test_quic_sets_authority_and_path_setup_options() -> None:
    """
    QUIC 直接接続で AUTHORITY と PATH が SETUP に載ることを確認する。

    authority、path-abempty、query を Setup Option で通知しなければならない。
    path には query を `?` で連結し、path が無い場合は `/` にする
    (draft-ietf-moq-transport-22 §6.2.2 (Native QUIC) / §9.1.1 (AUTHORITY) /
    §9.1.2 (PATH))。
    """
    client = Client(url="moqt://example.com:4433/live?token=1", transport=Transport.Quic)
    assert client._setup_options == {
        moqt.SETUP_OPTION_AUTHORITY: b"example.com:4433",
        moqt.SETUP_OPTION_PATH: b"/live?token=1",
    }

    # path を省略した場合は `/` になる
    default_path = Client(url="moqt://example.com:4433", transport=Transport.Quic)
    assert default_path._setup_options == {
        moqt.SETUP_OPTION_AUTHORITY: b"example.com:4433",
        moqt.SETUP_OPTION_PATH: b"/",
    }


def test_webtransport_rejects_authority_and_path_setup_options() -> None:
    """
    WebTransport では AUTHORITY と PATH を拒否することを確認する。

    どちらも WebTransport では送ってはならない
    (draft-ietf-moq-transport-22 §9.1.1 (AUTHORITY) / §9.1.2 (PATH))。
    """
    with pytest.raises(ValueError, match="only valid for QUIC connections"):
        Client(
            url="moqt://127.0.0.1:4433/webtransport",
            setup_options={moqt.SETUP_OPTION_PATH: b"/live"},
        )
