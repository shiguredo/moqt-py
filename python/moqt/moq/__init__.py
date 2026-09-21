"""WebTransport 接続上で MOQT セッションを扱う client。

`webtransport-py` の asyncio API が WebTransport over HTTP/3 の I/O を担当し、
`moqt._native` の MOQT 状態機械と接続する。下位層である `moqt.moqt` の codec や
sans I/O 状態機械を直接扱う必要はない。

公開 API:

- `Client`: 接続を張って MOQT セッションを開始する
- `Transport`: 接続方式 (QUIC / WebTransport over HTTP/2 / WebTransport over HTTP/3)
- `Subscription` / `Fetch` / `TrackStatus`: client 側の要求
- `Publication`: 配信中の Track
- `MOQTObject`: 受信したオブジェクト
- `PeerGoaway`: peer から受信した GOAWAY

server は公開しない。E2E テストで client の相手役として使う server と pytest
fixture は `moqt.moq.testing` が提供する。

relay は含まない。MOQT は draft 由来であり、将来の改訂で変更される可能性がある。
"""

from moqt.moq.client import (
    Client,
    Fetch,
    MOQTObject,
    PeerGoaway,
    Subscription,
    TrackStatus,
)
from moqt.moq.publisher import Publication
from moqt.moq.transport import Transport

# Subgroup Header の Subgroup ID エンコードモード。
# `Publication.send_object` の `subgroup_id_mode` に渡す
# (draft-ietf-moq-transport-21 §11.3.1 (Subgroup Header))。
SUBGROUP_ID_MODE_ZERO = "zero"
SUBGROUP_ID_MODE_FIRST_OBJECT_ID = "first_object_id"
SUBGROUP_ID_MODE_EXPLICIT = "explicit"

__all__ = [
    "SUBGROUP_ID_MODE_EXPLICIT",
    "SUBGROUP_ID_MODE_FIRST_OBJECT_ID",
    "SUBGROUP_ID_MODE_ZERO",
    "Client",
    "Fetch",
    "MOQTObject",
    "PeerGoaway",
    "Publication",
    "Subscription",
    "TrackStatus",
    "Transport",
]
