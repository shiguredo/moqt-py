"""MSF (MOQT Streaming Format) のカタログとタイムライン。

draft-ietf-moq-msf-01 のカタログ・メディアタイムライン・イベントタイムライン・
URI を扱う。いずれも JSON 文書であり、Rust 側が draft の MUST に照らした検証と
delta 更新の適用を担う。

カタログは ``catalog`` という Track 名で配信する (draft-ietf-moq-msf-01 §5 (Catalog))。
``CATALOG_TRACK_NAME`` がその名前である。

カタログと delta 更新は JSON 文字列を経由せずに組み立てられる。``Track`` /
``CloneTrack`` / ``RemoveTrack`` が操作の対象であり、``Catalog.add_track`` と
``DeltaUpdate`` の各メソッドがそれらを取り込む。追加した内容が draft の MUST に
違反する場合は encode 時に ``ValueError`` になる。

Track 識別子 (``namespace--track``) と、その構成要素である namespace と Track 名の
正規表現 (draft-ietf-moq-transport-22 §8.8) の相互変換も扱う。``parse_name`` /
``serialize_name`` が識別子全体、``parse_namespace`` / ``serialize_namespace`` と
``parse_track_name`` / ``serialize_track_name`` が構成要素である。``moqt.c4m`` の
``AuthorizationContext`` が要求する ``tns`` / ``tn`` は後者の表現である。

MSF は draft 由来であり、将来の改訂で変更される可能性がある。
"""

from moqt import _native
from moqt._native import (
    Accessibility,
    AuthInfo,
    Buffers,
    Catalog,
    CloneTrack,
    DeltaUpdate,
    EventTimeline,
    InitData,
    MediaTimeline,
    RemoveTrack,
    Template,
    Track,
    Uri,
    parse_fragment_pairs,
    parse_msf_fragment,
    parse_name,
    parse_namespace,
    parse_track_name,
    resolve_catalog_variables,
    resolve_timeline_template,
    serialize_name,
    serialize_namespace,
    serialize_track_name,
)

MSF_VERSION: str = _native.MSF_VERSION
"""このライブラリが対応する MSF のバージョン (draft-ietf-moq-msf-01 §5.1.1)。"""

CATALOG_TRACK_NAME: bytes = _native.MSF_CATALOG_TRACK_NAME
"""カタログを配信する Track 名 (draft-ietf-moq-msf-01 §5 (Catalog))。"""

__all__ = [
    "CATALOG_TRACK_NAME",
    "MSF_VERSION",
    "Accessibility",
    "AuthInfo",
    "Buffers",
    "Catalog",
    "CloneTrack",
    "DeltaUpdate",
    "EventTimeline",
    "InitData",
    "MediaTimeline",
    "RemoveTrack",
    "Template",
    "Track",
    "Uri",
    "parse_fragment_pairs",
    "parse_msf_fragment",
    "parse_name",
    "parse_namespace",
    "parse_track_name",
    "resolve_catalog_variables",
    "resolve_timeline_template",
    "serialize_name",
    "serialize_namespace",
    "serialize_track_name",
]
