# 画面仕様書 v2.2

updated: `2026-05-24`

## 1. 画面構成

| 領域 | 内容 |
| --- | --- |
| 卓中央 | 局情報、ドラ、河、鳴き帯 |
| 上部 | `AI TOP3`, `SELF`, Bridge 状態、NAGA ボタン |
| 他家パネル | `SUMMARY`, `ALERT`, `SCORE`, `BUTTONS` |
| 自家手牌 | 手牌、危険度バー、手牌操作、AI 応答 |
| 右詳細 | Visible x3/x4、lag 詳細、memo、Nodocchi STATUS |
| 最下部 | 南2局以降の NAGA 段位 pt 自動要約 |

## 2. 河

河は 4人 x 最大18枚を表示する。v2.2 では全牌再描画を避け、変化した牌だけ更新する。

表示要素:

- 赤枠: 鳴かれた捨て牌
- 黄枠: 鳴き直後の手出し
- `L`: 通常 lag
- `Pl`: pon-lag-likely または複数人 lag
- `P`: Push alert 対象
- 黄丸: 同順合わせ打ち
- 赤ひし形: その局で最長の思考時間
- ピンク丸: 3見え
- 紫 tint: 4見え
- 茶 tint: 4見えで物理否定された 3連形に属する手出し牌
- 赤 tint: remain / no-temp remain / post-call tedashi など危険寄り条件
- 思考時間帯: post-reach と pre-reach を別 band で表示

`Push` 判定で音声が鳴る場合は、同一 redraw で `P` を反映する。

## 3. プレイヤーパネル

### `SUMMARY`

- `Remain current/no-temp`
- Line ranking
- Safe hand ranking
- 危険ランク
- SCORE は自家基準の点差を表示する。

### `ALERT`

- `SUMMARY` と同じ no-temp remain 閾値で黄色・赤・紫を決める。
- `Push` は panel と河の `P` で同じ seat / discard index を参照する。
- `Push解除` は Push 後の手出し現物で緑表示へ切り替える。

### `STATUS`

Nodocchi 鳳凰卓4人打ち成績を右詳細領域に表示する。

- 和了率: 赤字
- 副露率: 赤字
- リーチ率: 赤字
- その他: 白字
- 取得中、取得失敗、データなしでも `Nodocchiで開く` 導線を残す。

## 4. 音声

- 音声対象は panel に表示される他家 alert。
- 自分側の remain / push / hidden alert は鳴らさない。
- `Remain` 音声は `r-red`, `r-yellow`, `r-purple` のように `r` を先頭へ付ける。
- 音声 worker は queue 上限を持ち、UI thread では再生しない。

## 5. NAGA 下部パネル

南2局以降に自動表示する。

- title: `NAGA pt <局名>`
- ready: 現状 ptEV、主要な和了、主要な放銃、流局 best/worst
- loading: `NAGA照会中`
- error: `NAGA取得失敗: ...`
- waiting: 南2局未満または局面未準備では非表示

## 6. Bridge と操作

- `SYNC` は browser-side UI snapshot を取得する。
- `discard_by_index` は自家手牌クリックや AUTO 打牌で使う。
- 右クリックは skip/pass 系 visible control を優先し、なければツモ切り補助として扱う。
- Bridge snapshot は `1 in-flight + pending 1` で coalescing する。

## 7. 性能表示

slow log:

- `UI side_panels slow`
- `UI discards slow`

`UI discards slow` は `drawn`, `skipped`, `changed`, `stale_deleted` を出し、差分描画が効いているか確認できる。

## 8. 互換

- v2.1 以前の `screen_spec_v2.1.md` は前版として残す。
- 現行の正本は本ファイルと `current.md`。
