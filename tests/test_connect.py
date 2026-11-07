"""`TEST_MOQT_URI` が指す実サーバーへの接続テスト。

環境変数 `TEST_MOQT_URI` が設定されている場合だけ実行する。moqt-py の CI では
repository secrets の `TEST_MOQT_URI` を環境変数として渡す。
"""

import os

import pytest
from moqt.moq import Client

# 接続先の MOQT URI。未設定の場合は接続テストを実行しない。
TEST_MOQT_URI: str | None = os.environ.get("TEST_MOQT_URI")

# 接続先の証明書を検証するか。開発用の relay は自己署名証明書を使うため、ローカルで
# 実行するときだけ `TEST_MOQT_VERIFY_PEER=0` を設定する。既定は検証する。
VERIFY_PEER = os.environ.get("TEST_MOQT_VERIFY_PEER", "1") != "0"

# 接続 (SETUP の交換を含む) の待ち合わせの上限秒数。
CONNECT_TIMEOUT = 8.0


@pytest.mark.skipif(not TEST_MOQT_URI, reason="TEST_MOQT_URI が設定されていないため")
@pytest.mark.timeout(20)
async def test_connect_and_close() -> None:
    """
    `TEST_MOQT_URI` が指す実サーバーへ接続し、SETUP の交換が完了したことを確認して
    から閉じる。

    接続方式は `Client` の既定 (WebTransport over HTTP/3) であり、接続先の証明書は
    検証する (`TEST_MOQT_VERIFY_PEER=0` でだけ検証を切る)。ローカルの server を
    起動する E2E テストと異なり、実環境の TLS とサーバー実装との相互接続を確認する。
    """
    assert TEST_MOQT_URI is not None
    client = Client(url=TEST_MOQT_URI, verify_peer=VERIFY_PEER)

    await client.connect(timeout=CONNECT_TIMEOUT)
    try:
        # SETUP の交換が完了していれば established になり、peer の Setup Option を
        # 参照できる (draft-ietf-moq-transport-23 §9.1 (SETUP))
        assert client.established
        assert client.peer_setup_options is not None
    finally:
        await client.close()


@pytest.mark.skipif(not TEST_MOQT_URI, reason="TEST_MOQT_URI が設定されていないため")
@pytest.mark.timeout(30)
async def test_reconnect_after_close() -> None:
    """
    同じ relay へ接続、close、再接続できることを確認する。

    close の後も relay が新しい接続を受け付け、SETUP の交換が完了することを確認する。
    実 relay の接続状態がテストの後始末で残らないことを確認する。
    """
    assert TEST_MOQT_URI is not None
    for _ in range(2):
        client = Client(url=TEST_MOQT_URI, verify_peer=VERIFY_PEER)
        await client.connect(timeout=CONNECT_TIMEOUT)
        try:
            assert client.established
        finally:
            await client.close()
