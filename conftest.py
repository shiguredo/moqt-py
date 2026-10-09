"""moqt-py 自身のテストで使う pytest 設定。

公開している `moqt.moq.testing` の fixture を、利用者と同じ手順で読み込む。
"""

import pytest
from moqt.moq.transport import Transport

pytest_plugins = ["moqt.moq.testing"]


@pytest.fixture(
    params=[
        Transport.WebTransportOverHTTP2,
        Transport.WebTransportOverHTTP3,
        Transport.Quic,
    ]
)
def moq_transport(request: pytest.FixtureRequest) -> Transport:
    """E2E テストを WT-H2 / WT-H3 / QUIC 直接接続で実行する。"""
    transport = request.param
    assert isinstance(transport, Transport)
    return transport
