# Node Lock / Regime Freeze

## 何を測っているか

ノードや枝集合を固定したとき、残りのchoice groupが壊れずに再正規化されるか、固定部分を平均近似してよいかを見ます。

lock mode:

- `hard_lock`
- `soft_lock`
- `keep_top_k`
- `freeze_ratio`
- `freeze_concentration_band`

## なぜ必要か

分散が小さい部分や判断に効きにくい部分は固定し、揺れの大きい部分に認知資源を集中したいからです。これは局面レビューでも教育でも重要です。

## どう解釈するか

`averaging_safety` が `safe` なら平均近似候補、`caution` は追加確認が必要、`unsafe` は二極化・多峰化・高感度の可能性があります。lock前後の `delta_mass` と `margin_change` を必ず確認します。

## 何をやってはいけないか

lockは真実の確定ではありません。根拠メモなしで固定したり、mixed signが残る枝を固定してpruneしたりしないでください。top-k保持と矛盾するpruneも無効です。

## 将来 pruning-ui とどう接続するか

`locks`、`frozen_nodes`、`top_k_constraints`、`reasoning_lab.averaging_safety` を pruning-ui に渡し、固定された枝を編集不可または警告付きにします。freeze系は比率保持として、hard lockとは別に扱います。
