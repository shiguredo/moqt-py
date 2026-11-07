//! fetch ストリームのエンコーダ。
//!
//! fetch レスポンスストリームのヘッダとエントリは、直前の Object を基準にした差分で
//! 表現される (draft-ietf-moq-transport-23 §11.4.1.1 (Flags) /
//! §11.4.2.1 (ID Decoding))。差分の基準と End of Range / End of Group / End of Track
//! の扱いは状態を持つため、moqt-rs の `FetchStreamEncoder` をそのまま使う。
//!
//! Python 側は、このクラスが返すバイト列をストリームへ書き込むだけである。

use pyo3::prelude::*;
use pyo3::types::PyBytes;

use shiguredo_moqt::stream::encoder::{FetchObjectInput, FetchStreamEncoder};

use crate::errors::codec_error;

/// fetch ストリームのエンコーダ。
#[pyclass(name = "FetchEncoder")]
pub(crate) struct FetchEncoder {
    inner: FetchStreamEncoder,
}

impl FetchEncoder {
    /// エンコード結果を Python の `bytes` にして返す。
    fn bytes(py: Python<'_>, buf: &[u8]) -> Py<PyBytes> {
        PyBytes::new(py, buf).unbind()
    }
}

#[pymethods]
impl FetchEncoder {
    /// エンコーダを作る。
    ///
    /// `group_order` は Ascending (0x01) または Descending (0x02) である
    /// (draft-ietf-moq-transport-23 §9.19.8 (GROUP ORDER Parameter))。
    #[new]
    #[pyo3(signature = (request_id, group_order=1))]
    fn new(request_id: u64, group_order: u8) -> PyResult<Self> {
        let inner = FetchStreamEncoder::new_with_group_order(request_id, group_order)
            .map_err(codec_error)?;
        Ok(Self { inner })
    }

    /// FETCH_HEADER をエンコードする。
    fn header(&self, py: Python<'_>) -> Py<PyBytes> {
        Self::bytes(py, &self.inner.encode_header())
    }

    /// 1 件の Object をエンコードする。
    ///
    /// `properties_data` は Properties Length (vi64) を含む生バイト列である。
    /// `payload` は呼び出し側が続けて書き込む。
    #[pyo3(signature = (
        group_id,
        object_id,
        subgroup_id,
        publisher_priority,
        payload_length,
        properties_data=None,
        datagram_origin=false,
    ))]
    #[expect(clippy::too_many_arguments)]
    fn encode_object(
        &mut self,
        py: Python<'_>,
        group_id: u64,
        object_id: u64,
        subgroup_id: u64,
        publisher_priority: u8,
        payload_length: u64,
        properties_data: Option<Vec<u8>>,
        datagram_origin: bool,
    ) -> PyResult<Py<PyBytes>> {
        let input = FetchObjectInput {
            group_id,
            subgroup_id,
            object_id,
            publisher_priority,
            has_properties: properties_data.is_some(),
            is_datagram_origin: datagram_origin,
            payload_length,
        };
        let mut buf = Vec::new();
        self.inner
            .encode_object(&input, properties_data.as_deref(), &mut buf)
            .map_err(codec_error)?;
        Ok(Self::bytes(py, &buf))
    }

    /// End of Non-Existent Range をエンコードする。
    fn encode_end_of_non_existent_range(
        &mut self,
        py: Python<'_>,
        group_id: u64,
        object_id: u64,
    ) -> PyResult<Py<PyBytes>> {
        let mut buf = Vec::new();
        self.inner
            .encode_end_of_non_existent_range(group_id, object_id, &mut buf)
            .map_err(codec_error)?;
        Ok(Self::bytes(py, &buf))
    }

    /// End of Unknown Range をエンコードする。
    fn encode_end_of_unknown_range(
        &mut self,
        py: Python<'_>,
        group_id: u64,
        object_id: u64,
    ) -> PyResult<Py<PyBytes>> {
        let mut buf = Vec::new();
        self.inner
            .encode_end_of_unknown_range(group_id, object_id, &mut buf)
            .map_err(codec_error)?;
        Ok(Self::bytes(py, &buf))
    }

    /// End of Timed-Out Range をエンコードする。
    fn encode_end_of_timed_out_range(
        &mut self,
        py: Python<'_>,
        group_id: u64,
        object_id: u64,
    ) -> PyResult<Py<PyBytes>> {
        let mut buf = Vec::new();
        self.inner
            .encode_end_of_timed_out_range(group_id, object_id, &mut buf)
            .map_err(codec_error)?;
        Ok(Self::bytes(py, &buf))
    }

    /// End of Gone Range をエンコードする。
    fn encode_end_of_gone_range(
        &mut self,
        py: Python<'_>,
        group_id: u64,
        object_id: u64,
    ) -> PyResult<Py<PyBytes>> {
        let mut buf = Vec::new();
        self.inner
            .encode_end_of_gone_range(group_id, object_id, &mut buf)
            .map_err(codec_error)?;
        Ok(Self::bytes(py, &buf))
    }

    /// End of Group をエンコードする。
    fn encode_end_of_group(&mut self, py: Python<'_>) -> PyResult<Py<PyBytes>> {
        let mut buf = Vec::new();
        self.inner
            .encode_end_of_group(&mut buf)
            .map_err(codec_error)?;
        Ok(Self::bytes(py, &buf))
    }

    /// End of Track をエンコードする。
    fn encode_end_of_track(&mut self, py: Python<'_>) -> PyResult<Py<PyBytes>> {
        let mut buf = Vec::new();
        self.inner
            .encode_end_of_track(&mut buf)
            .map_err(codec_error)?;
        Ok(Self::bytes(py, &buf))
    }
}
