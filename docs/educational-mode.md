# Educational Mode

## 何を測っているか

reading actionがどの枝にどう効き、utilityがなぜ高い/低いのかを自然言語で説明します。中級者以上向けに、`distribution shape`、`concentration`、`ambiguity`、`resolution`、`projection margin` を一貫した用語として使います。

## なぜ必要か

このツールは研究用であると同時に、ロジックや確率的思考を身につけるための教育支援にも使います。判断結果よりも、差分が出た理由を追えることを重視します。

## どう解釈するか

説明は `teaching_log` と `reading_utility` から生成またはseedされます。高utilityの読みは上位確率質量、ambiguity reduction、projection margin のいずれかに効いていることが多く、低utilityの読みは狭いtailや低impactに留まることがあります。

## 何をやってはいけないか

自然言語説明をブラックボックスの結論として使いません。説明は必ずbefore/after diff、concentration metrics、influence ambiguityと一緒に読む必要があります。

## 将来 pruning-ui とどう接続するか

`reasoning_lab.teaching_logs` を pruning-ui の操作ログ説明、training case、レビューコメントに渡します。将来は pruning-ui 側の実操作から teaching log を逆生成できるようにします。
