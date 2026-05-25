# Decision Pipeline

Case Workspace は2つの表示を持ちます。

- 4列モード: 観測 / 仮説 / 条件 / 判断
- 判断プロセスモード: 洗い出し / 重み付け / 加算/合成 / 比較 / 選択 / 反省

schema の `caseLanes` は変更しません。判断プロセスモードは attached nodes、node type、tags、influence edge、lane assignment から派生表示します。

## 派生マッピング

- 洗い出し: `observation`、`question`、`evidence`、`signal`
- 重み付け: `weight_modifier`、`heuristic`、`metric`、influence edgeを持つノード
- 加算/合成: `probability_aggregate`、`metric`、`combine` / `probability_tree` tag
- 比較: `choice_group`、`branch`、`hypothesis`、`scenario`
- 選択: `action`、decision lane、`choose` tag
- 反省: `review` / `teaching` tag、reading utility、反省用 evidence

## 足りない要素

Case Workspace は次の不足を表示します。

- 仮説がない
- metricがない
- choice groupがない
- top-kが未設定
- 判断メモがない
- 反省メモがない
- mixed/unknown influence が残っている
- hard prune されそうだが ambiguity が高い

このパネルは自動採点ではなく、局面整理の抜け漏れを見つけるためのチェックリストです。
