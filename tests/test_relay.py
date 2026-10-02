"""`TEST_MOQT_URI` が指す実 relay に対する E2E テスト。

環境変数 `TEST_MOQT_URI` が設定されている場合だけ実行する。moqt-py の CI では
repository secrets の `TEST_MOQT_URI` を環境変数として渡す。

relay を挟んだ publisher と subscriber の相互接続を確認する。映像と音声は実コーデックで
符号化せず、LOC (draft-ietf-moq-loc-04) のプロパティを付けた固定のダミーペイロードを
使う。確認するのは relay を経由した object の配送と、購読側で参照できる LOC プロパティと
MSF カタログである。
"""

import asyncio
import contextlib
import os
from typing import TYPE_CHECKING

import pytest
from moqt import loc, moqt, msf
from moqt.moq import Client, MOQTObject, Publication, Subscription, Transport

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
# 衝突しないようにするためである。
NAMESPACE = (b"moqt-py", b"e2e-" + os.urandom(4).hex().encode())

VIDEO_TRACK_NAME = b"video"
AUDIO_TRACK_NAME = b"audio"
CATALOG_TRACK_NAME = b"catalog"

# Track Alias は publisher が Track ごとに決める (draft-ietf-moq-transport-21 §9.5)。
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
) -> tuple[Publication, Subscription]:
    """relay を挟んで Track の配信を確立する。

    PUBLISH の応答を受けてから SUBSCRIBE し、SUBSCRIBE_OK を待つ。relay が購読の確立前に
    届いた object を保持するとは限らないため、object は購読が確立してから送る。
    """
    publication = await publisher.publish(NAMESPACE, track_name, track_alias)
    subscription = await subscriber.subscribe(NAMESPACE, track_name)
    return publication, subscription


async def _take_object(subscription: Subscription) -> MOQTObject:
    """購読から object を 1 件取り出す。"""
    return await asyncio.wait_for(anext(subscription.objects()), OBJECT_TIMEOUT)


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
    (draft-ietf-moq-transport-21 §3.2 (Fetch))。
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

    データグラムは再送されないため (draft-ietf-moq-transport-21 §11.2 (Object
    Datagrams))、同じサンプルを複数件送り、最初に届いた 1 件だけを確認する。受信側では
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
@pytest.mark.timeout(30)
async def test_relay_accepts_a_native_quic_connection() -> None:
    """
    QUIC 直接接続 (native QUIC) で relay へ接続できることを確認する。

    QUIC では AUTHORITY と PATH を SETUP で通知し、ALPN は `moqt-21` を使う
    (draft-ietf-moq-transport-21 §6.2.2 (Native QUIC))。WebTransport と違い
    ストリームの多重化に HTTP/3 を挟まないため、経路が別である。
    """
    client = Client(url=_require_uri(), transport=Transport.Quic, verify_peer=VERIFY_PEER)
    await client.connect(timeout=CONNECT_TIMEOUT)
    try:
        assert client.established
    finally:
        await client.close()
