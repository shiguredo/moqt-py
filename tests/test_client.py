"""moqt.moq.Client の接続方式選択の単体テスト。"""

import ssl

import pytest
from moqt import moqt
from moqt.moq import Client, Transport
from moqt.moq._runtime import MOQTError
from moqt.moq.transport import MOQT_PROTOCOL
from webtransport import Client as WebTransportClient
from webtransport import HTTPVersion, qmux, quic


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


@pytest.mark.parametrize(
    "transport_kind",
    [Transport.WebTransportOverHTTP2, Transport.WebTransportOverHTTP3],
    ids=["wt-h2", "wt-h3"],
)
def test_webtransport_sends_stop_sending_from_the_unified_client(
    transport_kind: Transport,
) -> None:
    """
    WebTransport の STOP_SENDING が統一 API から送られることを確認する。

    状態機械が cancel で要求するのは STOP_SENDING であり、RESET_STREAM は
    ストリームの破棄である
    (draft-ietf-moq-transport-22 §6.4.2.3 (Request Cancellation and Rejection) /
    §12.2 (Session Termination Codes))。統一 API は選択した HTTP/2 / HTTP/3 の実装へ
    委譲するため、moqt-py は接続方式で分けずに同じ経路を使う。
    """
    client = Client(url="moqt://127.0.0.1:4433/webtransport", transport=transport_kind)
    webtransport = client._transport
    assert isinstance(webtransport, WebTransportClient)

    # 状態機械の STOP_SENDING は統一 API の stop_sending へ繋がる
    ops = client._transport_ops()
    assert ops.stop_sending == webtransport.stop_sending
    # reset による代替ではない
    assert ops.stop_sending != webtransport.reset_stream


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


def test_qmux_connects_to_the_uri_authority() -> None:
    """
    QMux 接続が URI の authority へ接続することを確認する。

    authority の host と port (省略時は 443) へ TCP 接続し、TLS では MOQT の ALPN を
    提示する (draft-nandakumar-moq-qmux-moqt-00 §3.2 (ALPN Identification))。
    """
    client = Client(url="moqt://example.com:4433/live", transport=Transport.Qmux)
    assert client.transport is Transport.Qmux
    transport = client._transport
    assert isinstance(transport, qmux.Client)
    assert (transport.host, transport.port) == ("example.com", 4433)

    # port を省略した場合は 443 になる (§6.2 (Session establishment))
    default_port = Client(url="moqt://example.com", transport=Transport.Qmux)
    default_transport = default_port._transport
    assert isinstance(default_transport, qmux.Client)
    assert default_transport.port == 443


def test_qmux_offers_the_moqt_alpn_protocol() -> None:
    """
    QMux over TLS が MOQT の ALPN を提示することを確認する。

    QMux を TLS で使う場合は ALPN が必須であり、MOQT over QMux は native QUIC と
    同じ値を使う (draft-ietf-quic-qmux-02 §8.1 (Protocol Negotiation) /
    draft-nandakumar-moq-qmux-moqt-00 §3.2 (ALPN Identification))。
    """
    client = Client(
        url="moqt://example.com:4433/live",
        transport=Transport.Qmux,
        verify_peer=False,
    )
    transport = client._transport
    assert isinstance(transport, qmux.Client)
    # ALPN は SSLContext へ設定される (asyncio の接続 API に引数が無いため)
    assert transport._alpn_protocols == [MOQT_PROTOCOL]
    context = transport._ssl
    assert context is not None
    # verify_peer=False では証明書の検証とホスト名の検証を無効にする
    assert context.verify_mode == ssl.CERT_NONE
    assert context.check_hostname is False


def test_qmux_sets_authority_and_path_setup_options() -> None:
    """
    QMux でも AUTHORITY と PATH が SETUP に載ることを確認する。

    QMux は WebTransport ではないため、HTTP 層が URI を運ぶことはない。そのため
    native QUIC と同じく Setup Option で通知する
    (draft-ietf-moq-transport-22 §6.2.2 (Native QUIC) / §9.1.1 (AUTHORITY) /
    §9.1.2 (PATH))。
    """
    client = Client(url="moqt://example.com:4433/live?token=1", transport=Transport.Qmux)
    assert client._setup_options == {
        moqt.SETUP_OPTION_AUTHORITY: b"example.com:4433",
        moqt.SETUP_OPTION_PATH: b"/live?token=1",
    }


def test_webtransport_rejects_authority_and_path_setup_options() -> None:
    """
    WebTransport では AUTHORITY と PATH を拒否することを確認する。

    どちらも WebTransport では送ってはならない
    (draft-ietf-moq-transport-22 §9.1.1 (AUTHORITY) / §9.1.2 (PATH))。
    """
    with pytest.raises(ValueError, match="only valid for QUIC and QMux connections"):
        Client(
            url="moqt://127.0.0.1:4433/webtransport",
            setup_options={moqt.SETUP_OPTION_PATH: b"/live"},
        )


def test_qmux_wires_stream_reset_and_stop_sending() -> None:
    """
    QMux の reset / STOP_SENDING が送出 API へ配線されていることを確認する。

    QMux は RESET_STREAM と STOP_SENDING を QUIC のフレームとして扱い、
    webtransport-py の qmux が `reset_stream` / `stop_sending` を公開している。配線が
    外れると `MOQTError` を送出する実装へ戻るため、同一の関数であることを確認する。
    """
    client = Client(url="moqt://example.com:4433/live", transport=Transport.Qmux)
    transport = client._transport
    assert isinstance(transport, qmux.Client)
    ops = client._transport_ops()
    assert ops.reset_stream == transport.reset_stream
    assert ops.stop_sending == transport.stop_sending


async def test_qmux_reports_unsupported_datagram() -> None:
    """
    QMux が対応していないデータグラムが理由の分かるエラーになることを確認する。

    QMux はデータグラムを規定しているが、dwnx が実装していない
    (draft-ietf-quic-qmux-02 §9.1 (Unreliable Datagram Extension))。黙って捨てずに
    状態機械から呼ばれた時点で失敗させる。
    """
    client = Client(url="moqt://example.com:4433/live", transport=Transport.Qmux)
    ops = client._transport_ops()
    with pytest.raises(MOQTError, match="does not support datagrams"):
        await ops.send_datagram(b"datagram")
