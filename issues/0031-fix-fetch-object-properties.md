# FETCH 応答オブジェクトの Properties が受信側で観測できない

- Created: 2026-09-16
- Completed: 2026-09-27
- Branch: feature/fix-fetch-object-properties
- Polished:

## 目的

FETCH で受け取ったオブジェクトの Properties をアプリから参照できるようにする。

subgroup で受け取るオブジェクトは `MOQTObject.properties` から Properties を参照できる。
FETCH でも同じことができるはずで、参照できないと FETCH 経由でしか取得しない場合に
アプリが Properties を扱えない。

## 現状

`moqt.moq.testing` の `FetchResponse.send_object` は Properties を指定して送信できる。

しかし受信側では参照できない。moqt-py の `src/core.rs` は FETCH の
`DecodedFetchEntry::Object` を `CoreEvent` へ変換するときに `properties` を設定して
いないため、`python/moqt/moq/client.py` の `_on_object` が `event.properties` を
`MOQTObject` へ渡しても常に `None` になる。subgroup 経路は
`DecodedSubgroupObject::properties_bytes` を `properties` に載せており、FETCH 経路だけが
非対称である。

`tests/test_e2e.py` の `test_fetch_response_carries_properties_and_datagram_origin` は
送信側が指定した Properties が peer のデコーダで検証されることまでを確認しており、
受信側での参照は確認できていない。

## 設計方針

`DecodedFetchObject::properties_bytes` を subgroup 経路と同じ形
(`Properties Length` の varint + Properties データ) で `CoreEvent.properties` に載せる。
Python 側は `_on_object` が既に `event.properties` を `MOQTObject` へ渡しているため
変更しない。

## 完了条件

- FETCH で受け取ったオブジェクトの Properties を `MOQTObject.properties` から参照できること
- e2e テストで往復を確認できること

## pending にする理由

moqt-rs の `DecodedFetchObject` が Properties を保持しておらず、moqt-py だけでは
実装できない。moqt-rs 側の API 追加待ちである。

## reopened にする理由

moqt-rs の `DecodedFetchObject` に `properties_bytes: Option<Vec<u8>>` が追加され、
`DecodedSubgroupObject::properties_bytes` と同じ表現で Properties を保持するように
なった。pending の理由だった「moqt-rs 側の API 追加待ち」が解消したため reopened に
する。

## 解決方法

`src/core.rs` の FETCH 経路が `DecodedFetchEntry::Object` から `CoreEvent` を作るときに
`properties: object.properties_bytes.clone()` を設定した。表現は subgroup 経路と同じ
`Properties Length (varint) | Properties データ` であり、アプリは
`moqt.ObjectProperties.decode` にそのまま渡せる
(draft-ietf-moq-transport-21 §11.4.1.1 (Flags) / §11.1.3 (Object Properties))。

`tests/test_e2e.py` の
`test_fetch_response_carries_properties_and_datagram_origin` で、送信側が指定した
Properties が受信側の `MOQTObject.properties` から参照でき、`ObjectProperties.decode` で
元の値に戻ることを固定した。Properties を指定せずに送ったオブジェクトは `None` のまま
であることも確認している。

`uv run pytest` は 416 件すべて通り、`cargo fmt` / `cargo clippy` / `ruff` / `ty` も
通ることを確認した。
