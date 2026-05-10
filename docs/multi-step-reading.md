# Multi-step Reading Chain

## 何を測っているか

観測、仮説分岐、lock、pruning、weight update、direction update、observation request、fallback を時系列で並べ、各stepのbefore/after snapshot diffを追います。

## なぜ必要か

実戦の読みは一発で決まりません。観測、仮説、再観測、再分岐、比較が連鎖するため、最終判断だけでなく途中の分布変化とrationaleを残す必要があります。

## どう解釈するか

stepごとに `delta_mass`、`changed_node_count`、`margin_change`、`dominant_branch_change` を見ます。chain全体では、どのstepが判断を動かし、どのstepが説明や保留に留まったかを確認します。

## 何をやってはいけないか

chain replayを完全な牌譜推論として扱いません。MVPでは一部stepだけがprobability actionに変換され、observationやcompareは説明用snapshotになります。

## 将来 pruning-ui とどう接続するか

`reasoning_lab.reading_chains` を pruning-ui に渡し、確率木編集の操作ログ、教育用リプレイ、A/B scenario比較の入力にします。将来は各stepを pruning-ui の操作DSLへ変換します。
