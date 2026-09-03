# 不変条件

この文書は卓UIの `L3: コンポーネント契約` を定義する。差分編集時に守るべき固定条件だけを書く。

## 1. レイアウト不変条件

- `panel.detail` は右端固定とし、`panel.detail.visible3 / visible4 / content` の縦分割を維持する。
- `hand.self` は画面下辺中央基準とし、ツモ牌だけを右へずらす。
- `discard.*` は各席の意味を維持し、最大 `6列 x 3行` の河配置を崩さない。
- `meld.*` は河とは別の専用帯に描画し、河矩形へ食い込ませない。
- `panel.player.toimen` は横長、`panel.player.kamicha / shimocha` は縦長の前提を維持する。
- responsive 時も席方向の意味は変えず、縮小で吸収する。

## 2. コンポーネント不変条件

- `panel.player.*` は `SUMMARY / ALERT / BUTTONS` の3区画構成を維持する。
- `panel.detail.content` は共有詳細表示領域であり、複数ビューを同時常設しない。
- `hand.ai_top3.panel` はフローティング表示とし、`hand.self` の横幅基準を押し広げない。
- `hand.danger_bars` は `上家 / 対面 / 下家` の順序と色対応を維持する。
- 同一局の heavy suji / 危険度計算中は、`panel.player.*`、`hand.danger_bars`、関連する analysis overlay の直前完了表示を空にしない。手牌 danger は同じ牌と同牌内の出現順で現在手牌へ対応付け、対応元のない牌へ stale な棒を転用しない。初回計算と新局は保持対象外とする。
- `round.dora.indicators` と `round.info.text` は `panel.round_center` の中に閉じ込める。

## 3. 差分運用不変条件

- `Layout Fix Mode` では component の責務や DOM 相当の構造を変えない。
- `Style Fix Mode` では矩形配置や表示順を変えない。
- `Structural Refactor Mode` を除き、新しい region id を勝手に増やさない。
- 非対象に書かれた region/component は、見た目改善目的でも変更しない。
- heavy analysis の完了反映は async-only partial refresh とし、base river / table frame を再描画しない。計算中に保持する stale 値は表示専用で、自動打牌や alert 音声の新規判定へ流さない。
- 修正後は、変更した id と変更しなかった主要 id を要約する。
