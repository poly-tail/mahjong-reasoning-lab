# 差分指示テンプレート

この文書は卓UIの `L4: 差分指示` と `L5: 受け入れ条件` の雛形をまとめる。

## 使い方

- 依頼の先頭で編集モードを宣言する。
- `screen_map.md` の id をそのまま使う。
- 実装前に、対象・非対象・制約の要約を返させる。
- 実装後に、差分サマリを返させる。

## テンプレート

```text
Mode:
- Layout Fix Mode

Page:
- table.board

Target:
- region: panel.detail
- component: hand.ai_top3.button
- component: hand.ai_top3.panel

Goal:
- 手牌右側の補助操作を見やすくし、詳細パネルとの役割衝突を避ける

Change:
- hand.ai_top3.button を hand.self の右端基準に固定
- hand.ai_top3.panel は hand.self の上側にフロート表示
- panel.detail とは重ならない位置関係を維持

Do Not Touch:
- discard.*
- meld.*
- panel.player.*
- panel.round_center

Constraints:
- centered-bottom-hand
- fixed-right-detail
- river-grid-6x3
- shared-detail-area

Acceptance:
- hand.ai_top3.button が常に手牌レーン右端に見える
- hand.ai_top3.panel を開いても panel.detail と河が崩れない
- 非対象 region の矩形と役割が変化しない

Required Output:
- 変更した region/component id の一覧
- 変更していない主要 region の一覧
- 受け入れ条件を満たしたかの自己判定
```

## 先に返させる一文

```text
この修正は局所編集です。対象以外は変更しないでください。
まず、今回の変更対象・非対象・維持すべき制約を箇条書きで要約してください。
その後、その制約を守った最小差分だけを実装してください。
```

## このプロジェクト向けサンプル

```text
Mode:
- Layout Fix Mode

Page:
- table.board

Target:
- region: panel.player.toimen
- component: panel.player.toimen.summary

Goal:
- 対面パネルの SUMMARY を少し広げて line top3 の可読性を上げる

Change:
- SUMMARY 比率だけを広げる
- ALERT と BUTTONS は必要最小限だけ再配分する

Do Not Touch:
- panel.player.kamicha
- panel.player.shimocha
- panel.detail
- hand.self

Constraints:
- seat-anchored
- fixed-right-detail
- river-grid-6x3

Acceptance:
- 対面パネル内だけで調整が閉じる
- 他席パネルと詳細パネルの矩形は変わらない
- line top3 の省略頻度が下がる
```
