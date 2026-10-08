"""テストから実装の細部を扱うための低レベル API のテスト。

`moqt.moq` の高水準 API (`Client` / `Server`) は、状態機械・生のバイト列・
ストリーム操作を隠さない。ここではそれらをテストから直接扱えることを確認する。
"""

import pytest
from moqt import moqt
from moqt.moq import Client, MOQTError, NativeEvent, Publication, Runtime
from moqt.moq._runtime import (
    _encode_object_datagram,
    _encode_subgroup_header,
    _encode_subgroup_object,
    _properties_blob,
)
from moqt.moq.testing import MOQTPair, SubscriptionRequest, wait_until

# テストで使う Track
NAMESPACE = [b"moqt-py", b"test"]
TRACK_NAME = b"video"
TRACK_ALIAS = 1

# 低レベル API で直接投入するストリームの ID。
# RFC 9000 §2.1 の下位 2 ビット (bit1 が 1 で単方向、bit0 が 0 で client 開始) を満たし、
# 実際の接続が使う ID と衝突しないよう十分に大きい値を選ぶ
_INJECTED_STREAM_ID = 4_000_002


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

    # 観測したイベントは受信順のまま記録されるため、購読も通常どおり成立する。
    # データグラムは再送されないため、配送の確認には subgroup ストリームを使う
    await published[0].send_object(1, 0, b"payload")
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


async def test_malformed_track_cancels_the_subscription_without_failing_the_connection(
    moq_pair: MOQTPair,
) -> None:
    """Malformed Track の cancel が接続エラーにならず、購読単位の終了として届くことを確認する。

    draft-ietf-moq-transport-22 §12.1 (Malformed Tracks) は、購読者が Malformed Track を
    検出したら該当の subscription を取り消す (MUST) が、セッションは閉じないと定める。
    状態機械は request を終端したうえでエラーを返すため、I/O 層はエラーだけを見て接続の
    失敗として扱わず、積まれた終端のイベントを処理する必要がある。
    """
    events: list[NativeEvent] = []

    async def on_event(event: NativeEvent) -> None:
        events.append(event)

    moq_pair.client.on_event(on_event)

    published: list[Publication] = []

    async def on_subscribe(request: SubscriptionRequest) -> None:
        published.append(await request.subscribe_ok(TRACK_ALIAS))

    moq_pair.server.on_subscribe(on_subscribe)

    subscription = await moq_pair.client.subscribe(NAMESPACE, TRACK_NAME)
    request_id = subscription.request_id
    await wait_until(lambda: bool(published))

    # Group ID を超える PRIOR_GROUP_ID_GAP を持つデータグラムは Malformed Track である。
    # 受信を tick に頼らず検証するため、低レベル API で状態機械へ直接投入する
    properties = moqt.ObjectProperties()
    properties.add(moqt.PROP_PRIOR_GROUP_ID_GAP, 2)
    raw = _encode_object_datagram(
        TRACK_ALIAS,
        1,
        0,
        b"malformed",
        None,
        properties_bytes=_properties_blob(properties.encode()),
    )
    await moq_pair.client.runtime.receive_datagram(raw)

    # 終端が同じ受信で処理され、購読が終了する (エラーを返しても取り残さない)
    terminated = [event for event in events if event.kind == "request_terminated"]
    assert len(terminated) == 1
    body = terminated[0].message
    assert body is not None
    assert body.get("request_kind") == "subscribe"
    reason = body.get("reason")
    assert isinstance(reason, dict)
    assert reason.get("kind") == "malformed_track"
    detail = reason.get("reason")
    assert isinstance(detail, str)
    assert "PRIOR_GROUP_ID_GAP exceeds the current group ID" in detail
    assert moq_pair.client.subscription_state(request_id) is None

    # セッションは閉じておらず、接続エラーとして扱われない
    assert moq_pair.client.established is True

    # 同じ接続で購読し直せる
    subscription = await moq_pair.client.subscribe(NAMESPACE, TRACK_NAME)
    await wait_until(lambda: len(published) == 2)
    await published[1].send_object(1, 0, b"after-malformed-track")

    received = await subscription.objects().__anext__()
    assert received.payload == b"after-malformed-track"


async def test_malformed_track_in_a_subgroup_cancels_the_subscription(
    moq_pair: MOQTPair,
) -> None:
    """subgroup 経路の Malformed Track も購読単位の cancel として処理されることを確認する。

    データグラムと同じ検出が subgroup ストリームでも起きるため、どちらの経路でも
    エラーを取り残さず、セッションを閉じない。
    """
    events: list[NativeEvent] = []

    async def on_event(event: NativeEvent) -> None:
        events.append(event)

    moq_pair.client.on_event(on_event)

    published: list[Publication] = []

    async def on_subscribe(request: SubscriptionRequest) -> None:
        published.append(await request.subscribe_ok(TRACK_ALIAS))

    moq_pair.server.on_subscribe(on_subscribe)

    subscription = await moq_pair.client.subscribe(NAMESPACE, TRACK_NAME)
    request_id = subscription.request_id
    await wait_until(lambda: bool(published))

    # Group ID を超える PRIOR_GROUP_ID_GAP を持つ subgroup のオブジェクトは Malformed Track
    properties = moqt.ObjectProperties()
    properties.add(moqt.PROP_PRIOR_GROUP_ID_GAP, 2)
    stream = _encode_subgroup_header(
        TRACK_ALIAS, 1, None, None, has_properties=True
    ) + _encode_subgroup_object(
        0, b"malformed", properties_bytes=_properties_blob(properties.encode())
    )
    # transport を介さず、実際の接続が使わない stream ID へ直接投入する
    await moq_pair.client.runtime.receive_stream(_INJECTED_STREAM_ID, stream)

    terminated = [event for event in events if event.kind == "request_terminated"]
    assert len(terminated) == 1
    body = terminated[0].message
    assert body is not None
    reason = body.get("reason")
    assert isinstance(reason, dict)
    assert reason.get("kind") == "malformed_track"
    assert moq_pair.client.subscription_state(request_id) is None
    assert moq_pair.client.established is True


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
    await published[0].send_object(1, 0, b"after-raw-operations")

    received = await subscription.objects().__anext__()
    assert received.payload == b"after-raw-operations"

    # 開いたままのストリームは reset / STOP_SENDING で終端できる
    idle = await moq_pair.client.open_stream(bidirectional=True)
    await moq_pair.client.stop_sending_stream(idle, moqt.STREAM_CANCELLED)
    await moq_pair.client.reset_stream(idle, moqt.STREAM_CANCELLED)
