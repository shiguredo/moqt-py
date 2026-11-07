//! `moqt` のネイティブ拡張。
//!
//! `moqt-rs` の codec と sans I/O セッション状態機械を PyO3 経由で公開する。
//! Python 側の公開 API は `moqt.moqt` / `moqt.loc` / `moqt.msf` の 3 モジュールであり、
//! この拡張モジュール (`moqt._native`) はその実体である。
//!
//! # 役割分担
//!
//! - Python 側: MOQT のイベントループ、スケジューリング、公開 API の組み立て
//! - Rust 側: MOQT / LOC / MSF の codec、MOQT のプロトコル状態機械、
//!   QUIC / WebTransport / QMux の I/O
//!
//! I/O 層は QUIC と WebTransport と QMux の接続・ストリーム・データグラムだけを
//! 担当し、状態機械が生成したイベントを Python の asyncio へ配送する。

mod c4m;
mod codec;
mod core;
mod errors;
mod fetch_encoder;
mod grease;
mod io;
mod loc;
mod message_parameters;
mod msf;
mod properties;

use pyo3::prelude::*;

/// Python から `import moqt._native` される拡張モジュール。
#[pymodule(gil_used = false, name = "_native")]
mod _native {
    use pyo3::prelude::*;
    use pyo3::types::PyModule;

    use shiguredo_moqt::error::{
        PUBLISH_DONE_EXCESSIVE_LOAD, PUBLISH_DONE_EXPIRED, PUBLISH_DONE_GOING_AWAY,
        PUBLISH_DONE_INTERNAL_ERROR, PUBLISH_DONE_MALFORMED_TRACK, PUBLISH_DONE_TOO_FAR_BEHIND,
        PUBLISH_DONE_TRACK_ENDED, PUBLISH_DONE_UNAUTHORIZED, PUBLISH_DONE_UPDATE_FAILED,
        REQUEST_CONFLICTING_FILTERS, REQUEST_DOES_NOT_EXIST, REQUEST_EXCESSIVE_LOAD,
        REQUEST_EXPIRED_AUTH_TOKEN, REQUEST_GOING_AWAY, REQUEST_INTERNAL_ERROR,
        REQUEST_INVALID_FILTER, REQUEST_INVALID_RANGE, REQUEST_MALFORMED_AUTH_TOKEN,
        REQUEST_MALFORMED_TRACK, REQUEST_NAMESPACE_TOO_LARGE, REQUEST_NOT_SUPPORTED,
        REQUEST_REDIRECT, REQUEST_TIMEOUT, REQUEST_UNAUTHORIZED, REQUEST_UNINTERESTED,
        REQUEST_UNSUPPORTED_EXTENSION, SESSION_AUTH_TOKEN_CACHE_OVERFLOW,
        SESSION_CLOSED_CONTROL_STREAM, SESSION_CONTROL_MESSAGE_TIMEOUT,
        SESSION_DATA_STREAM_TIMEOUT, SESSION_DELTA_ENCODING_OVERFLOW,
        SESSION_DUPLICATE_AUTH_TOKEN_ALIAS, SESSION_DUPLICATE_TRACK_ALIAS,
        SESSION_EXPIRED_AUTH_TOKEN, SESSION_FIELD_LENGTH_EXCEEDED, SESSION_GOAWAY_TIMEOUT,
        SESSION_INTERNAL_ERROR, SESSION_INVALID_AUTHORITY, SESSION_INVALID_FIELD,
        SESSION_INVALID_OBJECT_STATUS, SESSION_INVALID_PARAMETER, SESSION_INVALID_PATH,
        SESSION_INVALID_REQUEST_ID, SESSION_INVALID_STREAM_HEADER, SESSION_LOCAL_DATAGRAM_TIMEOUT,
        SESSION_LOCAL_FILTER_MISMATCH, SESSION_MALFORMED_AUTH_TOKEN, SESSION_MALFORMED_AUTHORITY,
        SESSION_MALFORMED_KEY_VALUE, SESSION_MALFORMED_MESSAGE, SESSION_MALFORMED_OBJECT,
        SESSION_MALFORMED_PATH, SESSION_NO_ERROR, SESSION_PROTOCOL_VIOLATION,
        SESSION_ROLE_VIOLATION, SESSION_TOO_MANY_REQUEST_UPDATES, SESSION_TRUNCATED_OBJECT,
        SESSION_UNAUTHORIZED, SESSION_UNEXPECTED_MESSAGE, SESSION_UNKNOWN_AUTH_TOKEN_ALIAS,
        STREAM_CANCELLED, STREAM_DELIVERY_TIMEOUT, STREAM_EXCESSIVE_LOAD,
        STREAM_EXPIRED_AUTH_TOKEN, STREAM_GOING_AWAY, STREAM_INTERNAL_ERROR,
        STREAM_MALFORMED_TRACK, STREAM_SESSION_CLOSED, STREAM_TOO_FAR_BEHIND,
    };
    use shiguredo_moqt::message_parameter::{
        PARAM_AUTHORIZATION_TOKEN, PARAM_EXPIRES, PARAM_FILL_PARAMETERS, PARAM_FILL_TIMEOUT,
        PARAM_GROUP_ORDER, PARAM_INCLUDE_PROPERTIES, PARAM_LARGEST_OBJECT, PARAM_LOCATION_FILTER,
        PARAM_NEW_GROUP_REQUEST, PARAM_OBJECT_DELIVERY_TIMEOUT, PARAM_OBJECT_PROPERTY_FILTER,
        PARAM_OBJECTID_FILTER, PARAM_PAUSED, PARAM_PRIORITY_FILTER, PARAM_RENDEZVOUS_TIMEOUT,
        PARAM_SUBGROUP_DELIVERY_TIMEOUT, PARAM_SUBGROUP_FILTER, PARAM_SUBSCRIBER_PRIORITY,
        PARAM_TRACK_NAMESPACE_PREFIX, PARAM_TRACK_PROPERTY_FILTER,
    };
    use shiguredo_moqt::parameter::{
        SETUP_OPTION_AUTHORITY, SETUP_OPTION_AUTHORIZATION_TOKEN,
        SETUP_OPTION_MAX_AUTH_TOKEN_CACHE_SIZE, SETUP_OPTION_MAX_FILTER_RANGES,
        SETUP_OPTION_MAX_REQUEST_UPDATES, SETUP_OPTION_MOQT_IMPLEMENTATION, SETUP_OPTION_PATH,
    };
    use shiguredo_moqt::session::core::{
        DEFAULT_PEER_ALIAS_RETENTION_MS, PUBLISH_DONE_STREAM_COUNT_UNKNOWN,
    };
    use shiguredo_moqt::session::types::{
        DEFAULT_PUBLISHER_GROUP_ORDER_ASCENDING, MAX_NEW_SESSION_URI_LENGTH,
        PUBLISHER_PRIORITY_DEFAULT,
    };
    use shiguredo_moqt::stream::{
        FETCH_HEADER_TYPE, OBJECT_STATUS_END_OF_GROUP, OBJECT_STATUS_END_OF_TRACK,
        PADDING_DATAGRAM_TYPE, PADDING_STREAM_TYPE, SETUP_STREAM_TYPE,
    };

    use crate::core::{
        SUBGROUP_ID_MODE_EXPLICIT, SUBGROUP_ID_MODE_FIRST_OBJECT_ID, SUBGROUP_ID_MODE_ZERO,
    };

    // I/O 層 (Python の asyncio と接続するトランスポート)
    #[pymodule_export]
    use crate::io::client::IoClient;
    #[pymodule_export]
    use crate::io::event::IoEvent;
    #[pymodule_export]
    use crate::io::server::IoServer;

    // MOQT のプロトコル層 (moqt.moqt)
    #[pymodule_export]
    use crate::codec::{
        Message, classify_data_stream_type, decode_message, decode_parameter, decode_varint,
        decode_varint_prefix, encode_varint, is_padding_datagram, setup_stream_type,
    };
    #[pymodule_export]
    use crate::core::{CoreEvent, CoreSession};
    #[pymodule_export]
    use crate::fetch_encoder::FetchEncoder;

    // GREASE のヘルパー (moqt.moqt)
    #[pymodule_export]
    use crate::grease::{generate, is_grease};

    // Message Parameters の型付きアクセサ (moqt.moqt)
    #[pymodule_export]
    use crate::message_parameters::{LocationFilter, LocationFilterUpdate, MessageParameters};

    // LOC の codec (moqt.loc)
    #[pymodule_export]
    use crate::loc::LocProperties;

    // MOQT の Properties の codec (moqt.moqt)
    #[pymodule_export]
    use crate::properties::{
        ObjectProperties, ObjectPropertiesIterator, TrackProperties, TrackPropertiesIterator,
    };

    // MSF の codec (moqt.msf)
    #[pymodule_export]
    use crate::msf::{
        Accessibility, AuthInfo, Buffers, Catalog, CloneTrack, DeltaUpdate, EventTimeline,
        InitData, MediaTimeline, RemoveTrack, Template, Track, Uri, parse_fragment_pairs,
        parse_msf_fragment, parse_name, parse_namespace, parse_track_name,
        resolve_catalog_variables, resolve_timeline_template, serialize_name, serialize_namespace,
        serialize_track_name,
    };

    // C4M の codec (moqt.c4m)
    #[pymodule_export]
    use crate::c4m::cat::{
        CatClaims, CatToken, CatTokenBuilder, ClaimValidationOptions, Confirmation, VerifyOptions,
    };
    #[pymodule_export]
    use crate::c4m::cbor::{CborValue, decode_cbor, decode_cbor_partial, encode_cbor};
    #[pymodule_export]
    use crate::c4m::claims::{CatDpop, Match, MoqtClaim, MoqtScope, NamespaceMatch};
    #[pymodule_export]
    use crate::c4m::cose::{CoseEncodingOptions, CoseHeader, CoseMessage};
    #[pymodule_export]
    use crate::c4m::crypto::{CoseKey, default_signing_algorithm_id, digest, sign, verify};
    #[pymodule_export]
    use crate::c4m::dpop::{
        AuthorizationContext, DpopProof, DpopProofBuilder, DpopProofClaims, DpopProofHeader,
        DpopReplayCache, DpopVerification,
    };
    #[pymodule_export]
    use crate::c4m::jwk::Jwk;
    #[pymodule_export]
    use crate::c4m::jwt::{JwsCompact, JwsHeader};

    /// モジュール定数を登録する。
    #[pymodule_init]
    fn init(module: &Bound<'_, PyModule>) -> PyResult<()> {
        // ストリーム種別 (draft-ietf-moq-transport-23 §6.4.1 (Unidirectional Streams) Table 2)
        module.add("SETUP_STREAM_TYPE", SETUP_STREAM_TYPE)?;
        module.add("FETCH_HEADER_TYPE", FETCH_HEADER_TYPE)?;
        module.add("PADDING_STREAM_TYPE", PADDING_STREAM_TYPE)?;
        module.add("PADDING_DATAGRAM_TYPE", PADDING_DATAGRAM_TYPE)?;

        // Message Parameters (draft-ietf-moq-transport-23 §9.19 (Control Message Parameters))
        module.add(
            "PARAM_OBJECT_DELIVERY_TIMEOUT",
            PARAM_OBJECT_DELIVERY_TIMEOUT,
        )?;
        module.add("PARAM_AUTHORIZATION_TOKEN", PARAM_AUTHORIZATION_TOKEN)?;
        module.add("PARAM_RENDEZVOUS_TIMEOUT", PARAM_RENDEZVOUS_TIMEOUT)?;
        module.add(
            "PARAM_SUBGROUP_DELIVERY_TIMEOUT",
            PARAM_SUBGROUP_DELIVERY_TIMEOUT,
        )?;
        module.add("PARAM_EXPIRES", PARAM_EXPIRES)?;
        module.add("PARAM_LARGEST_OBJECT", PARAM_LARGEST_OBJECT)?;
        module.add("PARAM_FILL_TIMEOUT", PARAM_FILL_TIMEOUT)?;
        module.add("PARAM_PAUSED", PARAM_PAUSED)?;
        module.add("PARAM_SUBSCRIBER_PRIORITY", PARAM_SUBSCRIBER_PRIORITY)?;
        module.add("PARAM_LOCATION_FILTER", PARAM_LOCATION_FILTER)?;
        module.add("PARAM_GROUP_ORDER", PARAM_GROUP_ORDER)?;
        module.add("PARAM_FILL_PARAMETERS", PARAM_FILL_PARAMETERS)?;
        module.add("PARAM_SUBGROUP_FILTER", PARAM_SUBGROUP_FILTER)?;
        module.add("PARAM_OBJECTID_FILTER", PARAM_OBJECTID_FILTER)?;
        module.add("PARAM_PRIORITY_FILTER", PARAM_PRIORITY_FILTER)?;
        module.add("PARAM_OBJECT_PROPERTY_FILTER", PARAM_OBJECT_PROPERTY_FILTER)?;
        module.add("PARAM_TRACK_PROPERTY_FILTER", PARAM_TRACK_PROPERTY_FILTER)?;
        module.add("PARAM_NEW_GROUP_REQUEST", PARAM_NEW_GROUP_REQUEST)?;
        module.add("PARAM_TRACK_NAMESPACE_PREFIX", PARAM_TRACK_NAMESPACE_PREFIX)?;
        module.add("PARAM_INCLUDE_PROPERTIES", PARAM_INCLUDE_PROPERTIES)?;

        // SETUP オプション (draft-ietf-moq-transport-23 §9.1 (SETUP))
        module.add("SETUP_OPTION_PATH", SETUP_OPTION_PATH)?;
        module.add("SETUP_OPTION_AUTHORITY", SETUP_OPTION_AUTHORITY)?;
        module.add(
            "SETUP_OPTION_AUTHORIZATION_TOKEN",
            SETUP_OPTION_AUTHORIZATION_TOKEN,
        )?;
        module.add(
            "SETUP_OPTION_MAX_AUTH_TOKEN_CACHE_SIZE",
            SETUP_OPTION_MAX_AUTH_TOKEN_CACHE_SIZE,
        )?;
        module.add(
            "SETUP_OPTION_MAX_FILTER_RANGES",
            SETUP_OPTION_MAX_FILTER_RANGES,
        )?;
        module.add(
            "SETUP_OPTION_MAX_REQUEST_UPDATES",
            SETUP_OPTION_MAX_REQUEST_UPDATES,
        )?;
        module.add(
            "SETUP_OPTION_MOQT_IMPLEMENTATION",
            SETUP_OPTION_MOQT_IMPLEMENTATION,
        )?;

        // REQUEST_ERROR のコード (draft-ietf-moq-transport-23 §12.3)
        module.add("REQUEST_INTERNAL_ERROR", REQUEST_INTERNAL_ERROR)?;
        module.add("REQUEST_UNAUTHORIZED", REQUEST_UNAUTHORIZED)?;
        module.add("REQUEST_TIMEOUT", REQUEST_TIMEOUT)?;
        module.add("REQUEST_NOT_SUPPORTED", REQUEST_NOT_SUPPORTED)?;
        module.add("REQUEST_MALFORMED_AUTH_TOKEN", REQUEST_MALFORMED_AUTH_TOKEN)?;
        module.add("REQUEST_EXPIRED_AUTH_TOKEN", REQUEST_EXPIRED_AUTH_TOKEN)?;
        module.add("REQUEST_GOING_AWAY", REQUEST_GOING_AWAY)?;
        module.add("REQUEST_EXCESSIVE_LOAD", REQUEST_EXCESSIVE_LOAD)?;
        module.add("REQUEST_DOES_NOT_EXIST", REQUEST_DOES_NOT_EXIST)?;
        module.add("REQUEST_INVALID_RANGE", REQUEST_INVALID_RANGE)?;
        module.add("REQUEST_MALFORMED_TRACK", REQUEST_MALFORMED_TRACK)?;
        module.add("REQUEST_UNINTERESTED", REQUEST_UNINTERESTED)?;
        module.add("REQUEST_NAMESPACE_TOO_LARGE", REQUEST_NAMESPACE_TOO_LARGE)?;
        module.add(
            "REQUEST_UNSUPPORTED_EXTENSION",
            REQUEST_UNSUPPORTED_EXTENSION,
        )?;
        module.add("REQUEST_REDIRECT", REQUEST_REDIRECT)?;
        module.add("REQUEST_CONFLICTING_FILTERS", REQUEST_CONFLICTING_FILTERS)?;
        module.add("REQUEST_INVALID_FILTER", REQUEST_INVALID_FILTER)?;

        // PUBLISH_DONE のコード (draft-ietf-moq-transport-23 §12.4)
        module.add("PUBLISH_DONE_INTERNAL_ERROR", PUBLISH_DONE_INTERNAL_ERROR)?;
        module.add("PUBLISH_DONE_UNAUTHORIZED", PUBLISH_DONE_UNAUTHORIZED)?;
        module.add("PUBLISH_DONE_TRACK_ENDED", PUBLISH_DONE_TRACK_ENDED)?;
        module.add("PUBLISH_DONE_GOING_AWAY", PUBLISH_DONE_GOING_AWAY)?;
        module.add("PUBLISH_DONE_TOO_FAR_BEHIND", PUBLISH_DONE_TOO_FAR_BEHIND)?;
        module.add("PUBLISH_DONE_EXPIRED", PUBLISH_DONE_EXPIRED)?;
        module.add("PUBLISH_DONE_UPDATE_FAILED", PUBLISH_DONE_UPDATE_FAILED)?;
        module.add("PUBLISH_DONE_EXCESSIVE_LOAD", PUBLISH_DONE_EXCESSIVE_LOAD)?;
        module.add("PUBLISH_DONE_MALFORMED_TRACK", PUBLISH_DONE_MALFORMED_TRACK)?;

        // ストリーム reset のコード (draft-ietf-moq-transport-23 §12.5)
        module.add("STREAM_INTERNAL_ERROR", STREAM_INTERNAL_ERROR)?;
        module.add("STREAM_CANCELLED", STREAM_CANCELLED)?;
        module.add("STREAM_DELIVERY_TIMEOUT", STREAM_DELIVERY_TIMEOUT)?;
        module.add("STREAM_SESSION_CLOSED", STREAM_SESSION_CLOSED)?;
        module.add("STREAM_GOING_AWAY", STREAM_GOING_AWAY)?;
        module.add("STREAM_TOO_FAR_BEHIND", STREAM_TOO_FAR_BEHIND)?;
        module.add("STREAM_EXPIRED_AUTH_TOKEN", STREAM_EXPIRED_AUTH_TOKEN)?;
        module.add("STREAM_EXCESSIVE_LOAD", STREAM_EXCESSIVE_LOAD)?;
        module.add("STREAM_MALFORMED_TRACK", STREAM_MALFORMED_TRACK)?;

        // Session Termination のコード (draft-ietf-moq-transport-23 §12.2)
        module.add("SESSION_NO_ERROR", SESSION_NO_ERROR)?;
        module.add("SESSION_INTERNAL_ERROR", SESSION_INTERNAL_ERROR)?;
        module.add("SESSION_UNAUTHORIZED", SESSION_UNAUTHORIZED)?;
        module.add("SESSION_PROTOCOL_VIOLATION", SESSION_PROTOCOL_VIOLATION)?;
        module.add("SESSION_INVALID_REQUEST_ID", SESSION_INVALID_REQUEST_ID)?;
        module.add(
            "SESSION_DUPLICATE_TRACK_ALIAS",
            SESSION_DUPLICATE_TRACK_ALIAS,
        )?;
        module.add("SESSION_MALFORMED_KEY_VALUE", SESSION_MALFORMED_KEY_VALUE)?;
        module.add(
            "SESSION_INVALID_OBJECT_STATUS",
            SESSION_INVALID_OBJECT_STATUS,
        )?;
        module.add(
            "SESSION_INVALID_STREAM_HEADER",
            SESSION_INVALID_STREAM_HEADER,
        )?;
        module.add("SESSION_MALFORMED_OBJECT", SESSION_MALFORMED_OBJECT)?;
        module.add("SESSION_TRUNCATED_OBJECT", SESSION_TRUNCATED_OBJECT)?;
        module.add("SESSION_MALFORMED_MESSAGE", SESSION_MALFORMED_MESSAGE)?;
        module.add("SESSION_INVALID_FIELD", SESSION_INVALID_FIELD)?;
        module.add("SESSION_UNEXPECTED_MESSAGE", SESSION_UNEXPECTED_MESSAGE)?;
        module.add("SESSION_ROLE_VIOLATION", SESSION_ROLE_VIOLATION)?;
        module.add("SESSION_INVALID_PARAMETER", SESSION_INVALID_PARAMETER)?;
        module.add(
            "SESSION_CLOSED_CONTROL_STREAM",
            SESSION_CLOSED_CONTROL_STREAM,
        )?;
        module.add(
            "SESSION_DELTA_ENCODING_OVERFLOW",
            SESSION_DELTA_ENCODING_OVERFLOW,
        )?;
        module.add(
            "SESSION_FIELD_LENGTH_EXCEEDED",
            SESSION_FIELD_LENGTH_EXCEEDED,
        )?;
        module.add("SESSION_INVALID_PATH", SESSION_INVALID_PATH)?;
        module.add("SESSION_MALFORMED_PATH", SESSION_MALFORMED_PATH)?;
        module.add("SESSION_GOAWAY_TIMEOUT", SESSION_GOAWAY_TIMEOUT)?;
        module.add(
            "SESSION_CONTROL_MESSAGE_TIMEOUT",
            SESSION_CONTROL_MESSAGE_TIMEOUT,
        )?;
        module.add("SESSION_DATA_STREAM_TIMEOUT", SESSION_DATA_STREAM_TIMEOUT)?;
        module.add(
            "SESSION_AUTH_TOKEN_CACHE_OVERFLOW",
            SESSION_AUTH_TOKEN_CACHE_OVERFLOW,
        )?;
        module.add(
            "SESSION_DUPLICATE_AUTH_TOKEN_ALIAS",
            SESSION_DUPLICATE_AUTH_TOKEN_ALIAS,
        )?;
        module.add("SESSION_MALFORMED_AUTH_TOKEN", SESSION_MALFORMED_AUTH_TOKEN)?;
        module.add(
            "SESSION_UNKNOWN_AUTH_TOKEN_ALIAS",
            SESSION_UNKNOWN_AUTH_TOKEN_ALIAS,
        )?;
        module.add("SESSION_EXPIRED_AUTH_TOKEN", SESSION_EXPIRED_AUTH_TOKEN)?;
        module.add("SESSION_INVALID_AUTHORITY", SESSION_INVALID_AUTHORITY)?;
        module.add("SESSION_MALFORMED_AUTHORITY", SESSION_MALFORMED_AUTHORITY)?;
        module.add(
            "SESSION_TOO_MANY_REQUEST_UPDATES",
            SESSION_TOO_MANY_REQUEST_UPDATES,
        )?;
        module.add(
            "SESSION_LOCAL_FILTER_MISMATCH",
            SESSION_LOCAL_FILTER_MISMATCH,
        )?;
        module.add(
            "SESSION_LOCAL_DATAGRAM_TIMEOUT",
            SESSION_LOCAL_DATAGRAM_TIMEOUT,
        )?;

        // Object Status (draft-ietf-moq-transport-23 §11.1.1 (Object Status))
        module.add("OBJECT_STATUS_END_OF_GROUP", OBJECT_STATUS_END_OF_GROUP)?;
        module.add("OBJECT_STATUS_END_OF_TRACK", OBJECT_STATUS_END_OF_TRACK)?;

        // Subgroup ID のエンコードモード (draft-ietf-moq-transport-23 §11.3.1 (Subgroup Header))
        // SUBGROUP_ID_MODE は Type Flags の bits 1-2 (mask 0x06) の 2 bit である。
        // 0b11 は将来のために予約されている
        module.add("SUBGROUP_ID_MODE_ZERO", SUBGROUP_ID_MODE_ZERO)?;
        module.add(
            "SUBGROUP_ID_MODE_FIRST_OBJECT_ID",
            SUBGROUP_ID_MODE_FIRST_OBJECT_ID,
        )?;
        module.add("SUBGROUP_ID_MODE_EXPLICIT", SUBGROUP_ID_MODE_EXPLICIT)?;

        // 既定値
        module.add("PUBLISHER_PRIORITY_DEFAULT", PUBLISHER_PRIORITY_DEFAULT)?;
        module.add(
            "DEFAULT_PUBLISHER_GROUP_ORDER_ASCENDING",
            DEFAULT_PUBLISHER_GROUP_ORDER_ASCENDING,
        )?;
        module.add(
            "DEFAULT_PEER_ALIAS_RETENTION_MS",
            DEFAULT_PEER_ALIAS_RETENTION_MS,
        )?;

        // GOAWAY の New Session URI の最大長 (draft-ietf-moq-transport-23 §9.2 (GOAWAY))
        // Rust 側はバイト列の長さなので usize である。Python の int へは u64 として渡す
        // (既知の小さな定数なので桁落ちは起きない)
        module.add(
            "MAX_NEW_SESSION_URI_LENGTH",
            MAX_NEW_SESSION_URI_LENGTH as u64,
        )?;

        // PUBLISH_DONE の STREAM_COUNT が不明であることを示す番兵
        // (draft-ietf-moq-transport-23 §9.9 (PUBLISH_DONE))
        module.add(
            "PUBLISH_DONE_STREAM_COUNT_UNKNOWN",
            PUBLISH_DONE_STREAM_COUNT_UNKNOWN,
        )?;

        // LOC と MSF の定数
        crate::loc::register_constants(module)?;
        crate::msf::register_constants(module)?;
        crate::properties::register_constants(module)?;
        crate::grease::register_constants(module)?;

        // C4M の定数 (moqt.c4m)
        crate::c4m::register_constants(module)?;
        Ok(())
    }
}
