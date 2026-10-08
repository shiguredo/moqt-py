"""テストから実装の細部を扱うための低レベル API のテスト。

`moqt.moq` の高水準 API (`Client` / `Server`) は、状態機械・生のバイト列・
ストリーム操作を隠さない。ここではそれらをテストから直接扱えることを確認する。
"""

import pytest
from moqt import moqt
from moqt.moq import Client, MOQTError, NativeEvent, Publication, Runtime
from moqt.moq.testing import MOQTPair, SubscriptionRequest, wait_until

# テストで使う Track
NAMESPACE = [b"moqt-py", b"test"]
TRACK_NAME = b"video"
TRACK_ALIAS = 1


def test_runtime_and_session_are_exposed(moq_pair: MOQTPair) -> None:
    """接続後に Runtime と native の状態機械へ直接アクセスできることを確認する。

    テストは状態機械のイベント列やタイムアウトを直接扱う必要があるため、
    接続が保持するランタイムと状態機械を隠さない。
    """
    runtime = moq_pair.client.runtime

    assert isinstance(runtime, Runtime)
    # Client.session は Runtime.session と同じものを返す
    assert moq_pair.client.session is runtime.session
    assert moq_pair.client.session.established


def test_runtime_is_not_exposed_before_connect() -> None:
    """接続前に Runtime を取得しようとするとエラーになることを確認する。"""
    client = Client(url="moqt://example.com:4433/live")

    with pytest.raises(MOQTError, match="client is not connected"):
        _ = client.runtime


async def test_on_event_observes_send_and_receive_events(moq_pair: MOQTPair) -> None:
    """すべてのイベントが送信系も含めて観測できることを確認する。

    種類ごとのコールバックは受信イベントしか運ばないため、`send_request` や
    `finish_request_stream` のような送信系のイベントは `on_event` でだけ観測できる。
    """
    kinds: list[str] = []

    async def on_event(event: NativeEvent) -> None:
        kinds.append(event.kind)

    moq_pair.client.on_event(on_event)

    published: list[Publication] = []

    async def on_subscribe(request: SubscriptionRequest) -> None:
        published.append(await request.subscribe_ok(TRACK_ALIAS))

    moq_pair.server.on_subscribe(on_subscribe)

    subscription = await moq_pair.client.subscribe(NAMESPACE, TRACK_NAME)
    await wait_until(lambda: bool(published))

    # 送信系のイベントが観測できる
    assert "send_request" in kinds
    # 受信系のイベントも同じフックで観測できる
    assert "request_ok" in kinds

    # 観測したイベントは受信順のまま記録されるため、購読も通常どおり成立する
    await published[0].send_datagram(1, 0, b"payload")
    received = await subscription.objects().__anext__()
    assert received.payload == b"payload"
    assert "object" in kinds


async def test_server_on_event_observes_events(moq_pair: MOQTPair) -> None:
    """server 側でもすべてのイベントを接続とともに観測できることを確認する。

    server は 1 つのコールバックで複数接続を扱うため、イベントはランタイムと
    組にして渡される。
    """
    observed: list[tuple[Runtime, str]] = []

    async def on_event(runtime: Runtime, event: NativeEvent) -> None:
        observed.append((runtime, event.kind))

    moq_pair.server.on_event(on_event)

    published: list[Publication] = []

    async def on_subscribe(request: SubscriptionRequest) -> None:
        published.append(await request.subscribe_ok(TRACK_ALIAS))

    moq_pair.server.on_subscribe(on_subscribe)

    await moq_pair.client.subscribe(NAMESPACE, TRACK_NAME)
    await wait_until(lambda: bool(published))

    kinds = [kind for _, kind in observed]
    # 受信した SUBSCRIBE と、応答の送信を観測できる
    assert "subscribe" in kinds
    assert "send_on_stream" in kinds
    # イベントは server 側のランタイムと組で渡される
    assert all(runtime is moq_pair.session.runtime for runtime, _ in observed)


async def test_raw_stream_and_datagram_operations(moq_pair: MOQTPair) -> None:
    """生のストリーム操作とデータグラム送信が使えることを確認する。

    状態機械を介さない操作でも接続が壊れないことを、PADDING ストリームと
    PADDING データグラム (受信側が読み飛ばす) で確認する。
    """
    # 単方向ストリームを開き、PADDING ストリームとして読み飛ばされる生のバイト列を送る
    stream_id = await moq_pair.client.open_stream()
    assert stream_id >= 0
    await moq_pair.client.send_stream_data(
        stream_id,
        moqt.encode_varint(moqt.PADDING_STREAM_TYPE) + bytes(8),
        fin=True,
    )

    # PADDING データグラムもそのまま送れる
    await moq_pair.client.send_datagram(moqt.encode_varint(moqt.PADDING_DATAGRAM_TYPE) + bytes(8))

    # 生の操作の後もセッションは通常どおり動く
    published: list[Publication] = []

    async def on_subscribe(request: SubscriptionRequest) -> None:
        published.append(await request.subscribe_ok(TRACK_ALIAS))

    moq_pair.server.on_subscribe(on_subscribe)

    subscription = await moq_pair.client.subscribe(NAMESPACE, TRACK_NAME)
    await wait_until(lambda: bool(published))
    await published[0].send_datagram(1, 0, b"after-raw-operations")

    received = await subscription.objects().__anext__()
    assert received.payload == b"after-raw-operations"

    # 開いたままのストリームは reset / STOP_SENDING で終端できる
    idle = await moq_pair.client.open_stream(bidirectional=True)
    await moq_pair.client.stop_sending_stream(idle, moqt.STREAM_CANCELLED)
    await moq_pair.client.reset_stream(idle, moqt.STREAM_CANCELLED)
