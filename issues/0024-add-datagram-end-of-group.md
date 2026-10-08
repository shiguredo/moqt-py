# Datagram で END_OF_GROUP を送れるようにする

- Created: 2026-09-16
- Completed:
- Branch: feature/add-datagram-end-of-group
- Polished:

## 目的

Object Datagram で Group の終端を通知できるようにする。

End of Group は Group 内の最後のオブジェクトであることを示す。datagram で送れると、
subgroup ストリームを開かずに Group の区切りを伝えられる。

## 現状

`moq._runtime._encode_object_datagram` は `end_of_group` 引数を持ち、
`draft-ietf-moq-transport-22 §11.2.1` の END_OF_GROUP bit を立てられるが、
呼び出し元の `moq._runtime.Runtime.send_object_datagram` が常に偽を渡しており、
`moq.moq.publisher.Publication.send_datagram` にも指定する口が無い。

moqt-rs の `Session::send_object_datagram` にも `end_of_group` に相当する引数が無いため、
状態機械へ通知する経路が存在しない。moqt-py だけでは実装できない。

## 設計方針

moqt-rs の `Session::send_object_datagram` に END_OF_GROUP を指定する引数が追加されたら、
moqt-py の native と Python 層に同じ引数を通す。

## 完了条件

- `Publication.send_datagram` から END_OF_GROUP を指定できること
- 受信側の `MoqtObject.status` で観測できること

## pending にする理由

moqt-rs の `Session::send_object_datagram` が `end_of_group` を受け取らないため、
moqt-py だけでは状態機械へ通知できない。

END_OF_GROUP の datagram を送るには、moqt-rs 側で
`Session::send_object_datagram` に引数を追加し、datagram のフィルタ評価と
重複 Object 検証へ反映する必要がある。moqt-rs の API が追加された時点で
この issue を reopened にして対応する。

## reopened にする理由

moqt-rs の 0211 (`e195973`) で `Session::send_object_datagram` に `end_of_group: bool` が
追加され、moqt-py の native と Python 層に引数を通せるようになった。STATUS と
END_OF_GROUP の同時指定を拒否する検証も moqt-rs 側に入っている。

あわせて完了条件を実態に合わせて直す。

- 「受信側の `MoqtObject.status` で観測できること」は draft-22 の挙動と合っていない。
  END_OF_GROUP bit は Object Status フィールドではなく Group の終端宣言であり
  (draft-ietf-moq-transport-22 §11.2.1 (Object Datagram))、受信側では Group の終端が
  記録され、宣言位置より大きい Object ID の Object が Malformed Track として拒否される
  (§12.1 (Malformed Tracks))。完了条件をこの挙動に直す

## 完了条件 (reopened 時点)

- `Publication.send_datagram` から END_OF_GROUP を指定できること
- STATUS と END_OF_GROUP の同時指定が拒否されること
- END_OF_GROUP を宣言した Group で、宣言位置より大きい Object ID の Object が受信側で
  Malformed Track として拒否されること
