"""`TEST_MOQT_URI` が指す実 relay に対する E2E テスト。

環境変数 `TEST_MOQT_URI` が設定されている場合だけ実行する。moqt-py の CI では
repository secrets の `TEST_MOQT_URI` を環境変数として渡す。

relay を挟んだ publisher と subscriber の相互接続を確認する。映像と音声は実コーデックで
符号化せず、LOC (draft-ietf-moq-loc-04) のプロパティを付けた固定のダミーペイロードを
使う。確認するのは relay を経由した object の配送、購読側で参照できる LOC プロパティと
MSF カタログ、複数 Track の同時購読、複数 Group と End of Group、PUBLISH_DONE、
PAUSED による停止と再開、Group 範囲を指定した FETCH である。
"""

import asyncio
import contextlib
import os
from collections.abc import Callable
from typing import TYPE_CHECKING

import pytest
from moqt import loc, moqt, msf
from moqt.moq import Client, Fetch, MOQTObject, Publication, Subscription, Transport

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# 接続先の MOQT URI。未設定の場合は relay のテストを実行しない。
TEST_MOQT_URI: str | None = os.environ.get("TEST_MOQT_URI")

# 接続先の証明書を検証するか。開発用の relay は自己署名証明書を使うため、ローカルで
# 実行するときだけ `TEST_MOQT_VERIFY_PEER=0` を設定する。既定は検証する。
VERIFY_PEER = os.environ.get("TEST_MOQT_VERIFY_PEER", "1") != "0"

# 接続 (SETUP の交換を含む) の待ち合わせの上限秒数。
CONNECT_TIMEOUT = 8.0
# object 1 件の待ち合わせの上限秒数。
OBJECT_TIMEOUT = 5.0


# Track Namespace は実行ごとに変える。relay に前回の実行の state が残っていても
# 衝突しないようにするためである。テストごとにも変え、同じ実行内の別テストが
# 同じ Track を再び PUBLISH して衝突しないようにする。
def _new_namespace() -> tuple[bytes, ...]:
    """relay に残った状態と衝突しない Track Namespace を作る。"""
    return (b"moqt-py", b"e2e-" + os.urandom(4).hex().encode())


NAMESPACE = _new_namespace()

VIDEO_TRACK_NAME = b"video"
AUDIO_TRACK_NAME = b"audio"
CATALOG_TRACK_NAME = b"catalog"

# Track Alias は publisher が Track ごとに決める
# (draft-ietf-moq-transport-23 §3.1.3 (Track Alias))。
VIDEO_TRACK_ALIAS = 1
AUDIO_TRACK_ALIAS = 2
CATALOG_TRACK_ALIAS = 3

# ダミーの映像フレーム。実コーデックのビット列ではなく、配送の確認に必要な長さだけを
# 持つ固定のバイト列である。keyframe と後続フレームの 2 件を送る。
DUMMY_VIDEO_KEYFRAME = bytes.fromhex("12000b000000000000007f")
DUMMY_VIDEO_DELTA_FRAME = bytes.fromhex("32000b000000000000007f")

# ダミーの音声サンプル。Opus のパケットを模した固定のバイト列である。
DUMMY_AUDIO_SAMPLE = bytes.fromhex("f8fffe")

# データグラムで送るダミー音声サンプル。データグラムは再送されないため、同じ内容を
# 複数件送って 1 件でも届くことを確認する。
DUMMY_AUDIO_DATAGRAMS = tuple(bytes([0xF8, 0xFF, index]) for index in range(5))

# relay が object を分割・結合せずに運ぶことを確認するための 32 KiB の固定バイト列。
LARGE_OBJECT_PAYLOAD = bytes(range(256)) * 128

# LOC の Timescale に使う値 (draft-ietf-moq-loc-04 §2.3.1.2)。映像は 90 kHz、
# 音声は 48 kHz のメディア時刻を使う。
VIDEO_TIMESCALE = 90000
AUDIO_TIMESCALE = 48000
# 1 フレーム分のメディア時刻 (30 fps)。
VIDEO_FRAME_DURATION = VIDEO_TIMESCALE // 30


def _require_uri() -> str:
    """接続先の MOQT URI を返す。"""
    assert TEST_MOQT_URI is not None, "TEST_MOQT_URI が設定されていない"
    return TEST_MOQT_URI


def _video_properties(timestamp: int) -> bytes:
    """ダミー映像フレームの LOC プロパティを作る。

    Video Frame Marking (RFC 9626) の先頭バイトは S bit (最上位ビット) がフレームの
    先頭であることを表す。値そのものではなく、relay を経由しても LOC プロパティが
    保たれることを確認するために固定の値を置く。
    """
    properties = loc.Properties()
    properties.add(loc.TIMESTAMP, timestamp)
    properties.add(loc.TIMESCALE, VIDEO_TIMESCALE)
    properties.add(loc.VIDEO_FRAME_MARKING, b"\x80")
    return properties.encode()


def _audio_properties(timestamp: int) -> bytes:
    """ダミー音声サンプルの LOC プロパティを作る。

    Audio Level (RFC 6464) は vi64 の下位 8 bit に音声レベルを置く
    (draft-ietf-moq-loc-04 §2.3.3.2)。
    """
    properties = loc.Properties()
    properties.add(loc.TIMESTAMP, timestamp)
    properties.add(loc.TIMESCALE, AUDIO_TIMESCALE)
    properties.add(loc.AUDIO_LEVEL, 0)
    return properties.encode()


@contextlib.asynccontextmanager
async def _relay_clients() -> AsyncIterator[tuple[Client, Client]]:
    """relay へ接続した publisher と subscriber の client を用意する。

    接続方式は `Client` の既定 (WebTransport over HTTP/3) である。接続先の証明書は
    既定で検証し、`TEST_MOQT_VERIFY_PEER=0` のときだけ検証しない。
    """
    url = _require_uri()
    publisher = Client(url=url, verify_peer=VERIFY_PEER)
    subscriber = Client(url=url, verify_peer=VERIFY_PEER)
    await publisher.connect(timeout=CONNECT_TIMEOUT)
    try:
        await subscriber.connect(timeout=CONNECT_TIMEOUT)
        try:
            yield publisher, subscriber
        finally:
            await subscriber.close()
    finally:
        await publisher.close()


async def _publish_and_subscribe(
    publisher: Client,
    subscriber: Client,
    track_name: bytes,
    track_alias: int,
    namespace: tuple[bytes, ...] = NAMESPACE,
) -> tuple[Publication, Subscription]:
    """relay を挟んで Track の配信を確立する。

    PUBLISH の応答を受けてから SUBSCRIBE し、SUBSCRIBE_OK を待つ。relay が購読の確立前に
    届いた object を保持するとは限らないため、object は購読が確立してから送る。
    テストごとに固有の `namespace` を渡すと、同じ実行内の別テストが PUBLISH した
    Track と衝突しない。
    """
    publication = await publisher.publish(namespace, track_name, track_alias)
    subscription = await subscriber.subscribe(namespace, track_name)
    return publication, subscription


async def _take_object(source: Subscription | Fetch) -> MOQTObject:
    """購読または fetch から object を 1 件取り出す。"""
    return await asyncio.wait_for(anext(source.objects()), OBJECT_TIMEOUT)


async def _wait_until(
    predicate: Callable[[], bool],
    timeout: float = OBJECT_TIMEOUT,
) -> None:
    """predicate が真になるまで待つ。

    配送の停止・再開のように、object が増えないことを確認するテストでは
    iterator の `anext` をタイムアウトでキャンセルできない。専用タスクで iterator を
    回し、その記録を predicate で確認するための待ち合わせである。
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() >= deadline:
            raise TimeoutError("条件が満たされなかった")
        await asyncio.sleep(0.01)


@pytest.mark.skipif(not TEST_MOQT_URI, reason="TEST_MOQT_URI が設定されていないため")
@pytest.mark.timeout(60)
async def test_relay_delivers_dummy_video() -> None:
    """
    publisher が送ったダミー映像が relay を経由して subscriber へ届くことを確認する。

    keyframe と後続フレームの 2 件を送り、Group ID / Object ID / ペイロードが保たれる
    ことと、購読側で LOC の TIMESTAMP / TIMESCALE / VIDEO_FRAME_MARKING が参照できる
    ことを確認する (draft-ietf-moq-loc-04 §2.3.1 / §2.3.2)。
    """
    async with _relay_clients() as (publisher, subscriber):
        publication, subscription = await _publish_and_subscribe(
            publisher, subscriber, VIDEO_TRACK_NAME, VIDEO_TRACK_ALIAS
        )
        await publication.send_object(
            0, 0, DUMMY_VIDEO_KEYFRAME, properties_data=_video_properties(0)
        )
        await publication.send_object(
            0,
            1,
            DUMMY_VIDEO_DELTA_FRAME,
            properties_data=_video_properties(VIDEO_FRAME_DURATION),
        )

        keyframe = await _take_object(subscription)
        delta = await _take_object(subscription)

        assert (keyframe.group_id, keyframe.object_id) == (0, 0)
        assert keyframe.payload == DUMMY_VIDEO_KEYFRAME
        assert (delta.group_id, delta.object_id) == (0, 1)
        assert delta.payload == DUMMY_VIDEO_DELTA_FRAME

        assert keyframe.properties is not None
        properties = moqt.ObjectProperties.decode(keyframe.properties)[0]
        assert properties.find_varint(loc.TIMESTAMP) == 0
        assert properties.find_varint(loc.TIMESCALE) == VIDEO_TIMESCALE
        assert properties.to_dict()[loc.VIDEO_FRAME_MARKING] == b"\x80"


@pytest.mark.skipif(not TEST_MOQT_URI, reason="TEST_MOQT_URI が設定されていないため")
@pytest.mark.timeout(60)
async def test_relay_delivers_dummy_audio() -> None:
    """
    publisher が送ったダミー音声が relay を経由して subscriber へ届くことを確認する。

    2 件のサンプルを送り、Group ID / Object ID / ペイロードが保たれることと、購読側で
    LOC の TIMESTAMP / TIMESCALE / AUDIO_LEVEL が参照できることを確認する
    (draft-ietf-moq-loc-04 §2.3.1 / §2.3.3)。
    """
    async with _relay_clients() as (publisher, subscriber):
        publication, subscription = await _publish_and_subscribe(
            publisher, subscriber, AUDIO_TRACK_NAME, AUDIO_TRACK_ALIAS
        )
        await publication.send_object(
            0, 0, DUMMY_AUDIO_SAMPLE, properties_data=_audio_properties(0)
        )
        await publication.send_object(
            0, 1, DUMMY_AUDIO_SAMPLE, properties_data=_audio_properties(AUDIO_TIMESCALE // 50)
        )

        first = await _take_object(subscription)
        second = await _take_object(subscription)

        assert (first.group_id, first.object_id) == (0, 0)
        assert first.payload == DUMMY_AUDIO_SAMPLE
        assert (second.group_id, second.object_id) == (0, 1)
        assert second.payload == DUMMY_AUDIO_SAMPLE

        assert first.properties is not None
        properties = moqt.ObjectProperties.decode(first.properties)[0]
        assert properties.find_varint(loc.TIMESTAMP) == 0
        assert properties.find_varint(loc.TIMESCALE) == AUDIO_TIMESCALE
        assert properties.find_varint(loc.AUDIO_LEVEL) == 0


@pytest.mark.skipif(not TEST_MOQT_URI, reason="TEST_MOQT_URI が設定されていないため")
@pytest.mark.timeout(60)
async def test_relay_delivers_the_msf_catalog() -> None:
    """
    MSF カタログを relay 経由で受け取り、同じ内容へ復元できることを確認する。

    カタログは映像と音声の 2 つの Track を告知する完全カタログであり、`catalog` Track の
    object のペイロードとして届く (draft-ietf-moq-msf-01 §5 (Catalog))。
    """
    catalog = msf.Catalog()
    catalog.add_track(msf.Track("video", "loc", True))
    catalog.add_track(msf.Track("audio", "loc", True))
    payload = catalog.encode()

    async with _relay_clients() as (publisher, subscriber):
        publication, subscription = await _publish_and_subscribe(
            publisher, subscriber, CATALOG_TRACK_NAME, CATALOG_TRACK_ALIAS
        )
        await publication.send_object(0, 0, payload)

        received = await _take_object(subscription)

    assert received.payload == payload
    restored = msf.Catalog.parse(received.payload.decode())
    assert [track["name"] for track in restored.tracks] == ["video", "audio"]


@pytest.mark.skipif(not TEST_MOQT_URI, reason="TEST_MOQT_URI が設定されていないため")
@pytest.mark.timeout(60)
async def test_relay_serves_the_msf_catalog_over_fetch() -> None:
    """
    配信中の MSF カタログを FETCH で取得できることを確認する。

    購読で object が relay へ届いたことを確かめてから FETCH する。relay が購読の確立前に
    届いた object を保持するとは限らないため、object を送る前に購読を確立しておく。
    FETCH は購読と同じ Track を対象にするが、届く経路は fetch stream である
    (draft-ietf-moq-transport-23 §3.2 (Fetch))。
    """
    catalog = msf.Catalog()
    catalog.add_track(msf.Track("video", "loc", True))
    catalog.add_track(msf.Track("audio", "loc", True))
    payload = catalog.encode()

    async with _relay_clients() as (publisher, subscriber):
        publication, subscription = await _publish_and_subscribe(
            publisher, subscriber, CATALOG_TRACK_NAME, CATALOG_TRACK_ALIAS
        )
        await publication.send_object(0, 0, payload)
        # 購読で届いた時点で relay が object を保持している
        subscribed = await _take_object(subscription)
        assert subscribed.payload == payload

        fetch = await subscriber.fetch(NAMESPACE, CATALOG_TRACK_NAME)
        fetched = await asyncio.wait_for(anext(fetch.objects()), OBJECT_TIMEOUT)

    assert (fetched.group_id, fetched.object_id) == (0, 0)
    assert fetched.payload == payload
    restored = msf.Catalog.parse(fetched.payload.decode())
    assert [track["name"] for track in restored.tracks] == ["video", "audio"]


@pytest.mark.skipif(not TEST_MOQT_URI, reason="TEST_MOQT_URI が設定されていないため")
@pytest.mark.timeout(60)
async def test_relay_delivers_dummy_audio_as_datagrams() -> None:
    """
    publisher が送ったダミー音声がデータグラムで subscriber へ届くことを確認する。

    データグラムは再送されないため (draft-ietf-moq-transport-23 §11.2 (Datagrams))。
    同じサンプルを複数件送り、最初に届いた 1 件だけを確認する。受信側では
    データストリームを持たないため `MOQTObject.stream_id` が `None` になる。
    """
    async with _relay_clients() as (publisher, subscriber):
        publication, subscription = await _publish_and_subscribe(
            publisher, subscriber, AUDIO_TRACK_NAME, AUDIO_TRACK_ALIAS
        )
        for object_id, payload in enumerate(DUMMY_AUDIO_DATAGRAMS):
            await publication.send_datagram(0, object_id, payload)

        received = await _take_object(subscription)

    assert received.stream_id is None
    assert received.payload in DUMMY_AUDIO_DATAGRAMS


@pytest.mark.skipif(not TEST_MOQT_URI, reason="TEST_MOQT_URI が設定されていないため")
@pytest.mark.timeout(60)
async def test_relay_delivers_concurrent_tracks() -> None:
    """
    同じ relay セッションで映像と音声の 2 Track を同時に購読し、交互に送った object が
    混ざらずに届くことを確認する。

    Track Alias と Track 名の対応が relay を経由しても保たれ、購読ごとに独立した
    object が届くことを確認する (draft-ietf-moq-transport-23 §3.1.3 (Track Alias))。
    """
    async with _relay_clients() as (publisher, subscriber):
        namespace = _new_namespace()
        video_publication, video_subscription = await _publish_and_subscribe(
            publisher, subscriber, VIDEO_TRACK_NAME, VIDEO_TRACK_ALIAS, namespace
        )
        audio_publication, audio_subscription = await _publish_and_subscribe(
            publisher, subscriber, AUDIO_TRACK_NAME, AUDIO_TRACK_ALIAS, namespace
        )

        # 2 つの Track へ交互に送る
        await video_publication.send_object(0, 0, b"video-0")
        await audio_publication.send_object(0, 0, b"audio-0")
        await video_publication.send_object(0, 1, b"video-1")
        await audio_publication.send_object(0, 1, b"audio-1")

        video_objects = [await _take_object(video_subscription) for _ in range(2)]
        audio_objects = [await _take_object(audio_subscription) for _ in range(2)]

    assert [(item.group_id, item.object_id, item.payload) for item in video_objects] == [
        (0, 0, b"video-0"),
        (0, 1, b"video-1"),
    ]
    assert [(item.group_id, item.object_id, item.payload) for item in audio_objects] == [
        (0, 0, b"audio-0"),
        (0, 1, b"audio-1"),
    ]


@pytest.mark.skipif(not TEST_MOQT_URI, reason="TEST_MOQT_URI が設定されていないため")
@pytest.mark.timeout(60)
async def test_relay_delivers_multiple_groups_and_end_of_group() -> None:
    """
    複数の Group、End of Group の status、32 KiB の object が relay を経由して
    保たれることを確認する。

    Group をまたぐ object の配送と、End of Group の status が購読側で観測できることを
    確認する。32 KiB の object は relay の内部バッファで分割・結合されずに届くことを
    確認する (draft-ietf-moq-transport-23 §11.1.1 (Object Status))。
    """
    async with _relay_clients() as (publisher, subscriber):
        namespace = _new_namespace()
        publication, subscription = await _publish_and_subscribe(
            publisher, subscriber, VIDEO_TRACK_NAME, VIDEO_TRACK_ALIAS, namespace
        )
        await publication.send_object(0, 0, b"group-0")
        await publication.send_object(1, 0, b"group-1")
        # End of Group は空のペイロードと status で表現する
        await publication.send_object(1, 1, b"", status=moqt.OBJECT_STATUS_END_OF_GROUP)
        await publication.send_object(2, 0, LARGE_OBJECT_PAYLOAD)

        received = [await _take_object(subscription) for _ in range(4)]

    # Group をまたぐ object は別々の subgroup stream で届くため、到着順ではなく
    # (Group ID, Object ID) の順に並べて比較する
    assert [
        (item.group_id, item.object_id, item.payload, item.status)
        for item in sorted(received, key=lambda item: (item.group_id, item.object_id))
    ] == [
        (0, 0, b"group-0", None),
        (1, 0, b"group-1", None),
        (1, 1, b"", moqt.OBJECT_STATUS_END_OF_GROUP),
        (2, 0, LARGE_OBJECT_PAYLOAD, None),
    ]


@pytest.mark.skipif(not TEST_MOQT_URI, reason="TEST_MOQT_URI が設定されていないため")
@pytest.mark.timeout(60)
async def test_relay_propagates_publish_done() -> None:
    """
    publisher の PUBLISH_DONE が relay を経由して購読へ伝わることを確認する。

    PUBLISH_DONE の受信で購読の iterator が終了し、セッションは維持されることを
    確認する (draft-ietf-moq-transport-23 §9.9 (PUBLISH_DONE))。
    """
    async with _relay_clients() as (publisher, subscriber):
        namespace = _new_namespace()
        publication, subscription = await _publish_and_subscribe(
            publisher, subscriber, VIDEO_TRACK_NAME, VIDEO_TRACK_ALIAS, namespace
        )
        await publication.send_object(0, 0, b"before-done")
        before = await _take_object(subscription)
        assert before.payload == b"before-done"

        await publication.close(moqt.PUBLISH_DONE_TRACK_ENDED, "track ended")

        # PUBLISH_DONE を受けた購読は iterator の終了として観測できる
        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(anext(subscription.objects()), OBJECT_TIMEOUT)
        assert subscriber.established


@pytest.mark.skipif(not TEST_MOQT_URI, reason="TEST_MOQT_URI が設定されていないため")
@pytest.mark.timeout(60)
async def test_relay_pauses_and_resumes_a_subscription() -> None:
    """
    PAUSED で購読の配送が止まり、解除後に再開することを確認する。

    購読中に PAUSED=1 を送り、その間に publisher が送った object が届かないことを
    確認してから PAUSED=0 を送り、新しい object が届くことを確認する
    (draft-ietf-moq-transport-23 §9.19.18 (PAUSED Parameter))。
    """
    async with _relay_clients() as (publisher, subscriber):
        namespace = _new_namespace()
        publication, subscription = await _publish_and_subscribe(
            publisher, subscriber, VIDEO_TRACK_NAME, VIDEO_TRACK_ALIAS, namespace
        )

        received: list[MOQTObject] = []

        async def consume() -> None:
            async for item in subscription.objects():
                received.append(item)

        consumer = asyncio.create_task(consume())
        try:
            await publication.send_object(0, 0, b"before-pause")
            await _wait_until(lambda: len(received) == 1)

            await subscription.request_update({moqt.PARAM_PAUSED: 1})
            await publication.send_object(0, 1, b"while-paused")
            # PAUSED 中は配送されない。relay が object を保持していても、
            # 解除するまで購読へ渡してはならない
            await asyncio.sleep(1.0)
            assert [item.payload for item in received] == [b"before-pause"]

            await subscription.request_update({moqt.PARAM_PAUSED: 0})
            await publication.send_object(0, 2, b"after-resume")
            await _wait_until(lambda: any(item.payload == b"after-resume" for item in received))
            assert subscriber.established
        finally:
            consumer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await consumer


@pytest.mark.skipif(not TEST_MOQT_URI, reason="TEST_MOQT_URI が設定されていないため")
@pytest.mark.timeout(60)
async def test_relay_fetches_a_group_range_and_cancels() -> None:
    """
    Group 範囲を指定した FETCH が relay の保持する object を返し、cancel できることを
    確認する。

    購読で 3 つの Group の object を relay へ届けてから、Group 1 以降を指定して
    FETCH する。Group 0 が返らず、Group 1 と 2 が返ることを確認する。cancel 後は
    状態機械から fetch が回収されることを確認する
    (draft-ietf-moq-transport-23 §3.2 (Fetch) / §3.2.4 (Fetch State Management))。
    """
    async with _relay_clients() as (publisher, subscriber):
        namespace = _new_namespace()
        publication, subscription = await _publish_and_subscribe(
            publisher, subscriber, VIDEO_TRACK_NAME, VIDEO_TRACK_ALIAS, namespace
        )
        for group_id in range(3):
            await publication.send_object(group_id, 0, f"group-{group_id}".encode())

        subscribed = [await _take_object(subscription) for _ in range(3)]
        assert [item.payload for item in sorted(subscribed, key=lambda item: item.group_id)] == [
            b"group-0",
            b"group-1",
            b"group-2",
        ]

        fetch = await subscriber.fetch(
            namespace,
            VIDEO_TRACK_NAME,
            {
                moqt.PARAM_LOCATION_FILTER: moqt.LocationFilter(
                    "absolute_start", start_group=1, start_object=0
                )
            },
        )
        fetched = [await _take_object(fetch) for _ in range(2)]

        await fetch.cancel()
        await _wait_until(lambda: fetch.request_id not in subscriber.fetches())
        assert subscriber.established

    assert [
        (item.group_id, item.object_id, item.payload)
        for item in sorted(fetched, key=lambda item: item.group_id)
    ] == [(1, 0, b"group-1"), (2, 0, b"group-2")]


@pytest.mark.skipif(not TEST_MOQT_URI, reason="TEST_MOQT_URI が設定されていないため")
@pytest.mark.timeout(30)
async def test_relay_accepts_a_native_quic_connection() -> None:
    """
    QUIC 直接接続 (native QUIC) で relay へ接続できることを確認する。

    QUIC では AUTHORITY と PATH を SETUP で通知し、ALPN は `moqt-23` を使う
    (draft-ietf-moq-transport-23 §6.2.2 (Native QUIC))。WebTransport と違い
    ストリームの多重化に HTTP/3 を挟まないため、経路が別である。
    """
    client = Client(url=_require_uri(), transport=Transport.Quic, verify_peer=VERIFY_PEER)
    await client.connect(timeout=CONNECT_TIMEOUT)
    try:
        assert client.established
    finally:
        await client.close()
