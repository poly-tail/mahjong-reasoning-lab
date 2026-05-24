# パネルとアラート仕様

updated: `2026-05-24`

## 対象

`AI TOP3`, `SELF`, 他家プレイヤーパネル、Nodocchi `STATUS`, alert 音声、自家字牌一覧、NAGA 下部パネルの表示ルールをまとめる。

## `AI TOP3`

- 最大 3 行を表示する。
- 各行は `pt + 和了率` を表示する。
- 1 位は緑、2 位以下でも `top EV - 50pt` 以内なら緑にする。
- `SELF` alert は `AI TOP3` の期待値とは別のルールで判定する。

## `SELF`

- `LOW EV`, `EV<800`, `HIGH EV` などを表示する。
- `LOW EV` / `EV<800` は短音対象、`HIGH EV` は原則無音。
- 局開始や alert kind 変更で latch を更新する。

## 他家プレイヤーパネル

### `SUMMARY`

- `Remain current/no-temp`
- Line ranking
- Safe hand ranking
- 危険ランク
- SCORE

`SUMMARY` は panel alert の閾値正本でもある。特に `no-temp remain` の黄色・赤・紫基準は `ALERT` と一致させる。

### `ALERT`

主な表示:

- `Remain`
- `Push`
- `Push解除`
- `門前`
- `思考時間聴牌近`
- `染/対々 UP`
- `両面チー3-7`

色基準:

- yellow: 注意
- red: 強い警戒
- purple: no-temp remain の危険域など、赤より別扱いしたい強調
- green: Push解除など緩和

### `Push`

- panel の `Push` と河の `P` は同じ payload を使う。
- 通常は `danger >= 9%`。
- 対象にリーチ者が含まれる成立だけ `danger >= 6%`。
- panel 側は 3巡保持する。
- 手出し現物が出たら `Push解除` に切り替える。

### `STATUS`

Nodocchi 鳳凰卓4人打ち成績を右詳細領域に出す。

- 和了率: 赤字
- 副露率: 赤字
- リーチ率: 赤字
- その他: 白字
- 取得中、成功、失敗、データなしの全状態で `Nodocchiで開く` を残す。
- 同一プレイヤー取得中の連打は多重リクエストにしない。

## 音声

- panel に表示される他家 alert だけを音声対象にする。
- 自分側の remain / push / hidden alert は音声対象外。
- `Remain` は `r-red`, `r-yellow`, `r-purple` 形式の音声 key を使う。
- `Push` 音声は対象捨て牌の `P` marker と同一 redraw で反映する。
- 音声 worker queue が詰まった場合は UI を止めずに skip する。

## 自家 `2見え以下字牌`

- 自家右側、副露帯寄りに表示する。
- 対象は 0見え / 1見え / 2見えの字牌。
- 公開枚数は捨て牌、副露、ドラ表示牌から数える。

## NAGA 下部パネル

- 南2局以降だけ表示する。
- 現状 ptEV、主要和了、主要放銃、流局 best/worst を短く並べる。
- 詳細は NAGA ボタンの popup に残し、下部は常時視認用の要約に留める。
