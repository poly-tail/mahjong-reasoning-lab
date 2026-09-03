# パネルとアラート仕様

updated: `2026-09-03`

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
- `早い傾向`
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
- 河の `P` だけは seat-local index 0〜5（1段目）を表示対象外とし、index 6 以降（2段目以降）に表示する。panel の判定・表示と3巡保持は変更しない。
- 通常は `danger >= 9%`。
- 対象にリーチ者が含まれる成立だけ `danger >= 6%`。
- panel 側は 3巡保持する。
- 手出し現物が出たら `Push解除` に切り替える。

### `早い傾向`

- 対象は他家3人。
- 半荘内3局目以降だけ判定する。5局目では同一半荘の1〜4局目の記録を使う。
- `kyoku_master.csv` の `seat0..3_first_row_avg_thinking_time_ms` に、各局・各席の1段目（席ごとの先頭6打牌）平均思考時間を保存する。
- 現在局では、その席の1段目3打目〜6打目の打牌時に、現在局のここまでの平均思考時間と、過去局の1段目平均思考時間の平均を比較する。
- 現在局平均が過去局平均より早い場合、黄色の `早い傾向` panel alert を出す。

### `STATUS`

Nodocchi 鳳凰卓4人打ち成績を右詳細領域に出す。

- 和了率: 赤字
- 副露率: 赤字
- リーチ率: 赤字
- その他: 白字
- 取得中、成功、失敗、データなしの全状態で `Nodocchiで開く` を残す。
- 同一プレイヤー取得中の連打は多重リクエストにしない。

### heavy suji / 危険度計算中

- 他家 panel の `SUMMARY` / heavy analysis 由来の `ALERT`、自家手牌の危険度棒、関連する河 analysis overlay は、同一局の直前完了済み bundle を一組として表示し続ける。手牌が変わった場合、旧危険度は同じ牌と同牌内の出現順へ再対応付けし、対応元がない牌は棒なしとする。
- 新しい入力の計算中に `Remain: ...` や空の危険度配列へ戻して既表示を消さない。完了済み bundle がまだない初回だけ loading / 危険度棒なしを許容し、新局へ前局値を持ち越さない。
- 新 bundle 完了時は async-only partial refresh で side panel / hand / analysis overlay だけをまとめて差し替え、base river / table frame は再描画しない。
- stale bundle は表示専用とする。自動打牌へ使わず、保持または再表示した alert を新しい音声 transition として扱わない。

## 音声

- 上部操作列の `アラート音 OFF/ON` で self、他家 panel、副露ドラ、Bridge / WGC / INITBYLOG を含む全 alert 音声を一括切替する。起動時は OFF とし、次回起動へ設定を持ち越さない。OFF 中も alert 表示と遷移 latch は更新し、ON 切替時に既に表示中の alert を遅れて鳴らさない。
- `haya`: 他家の最新打牌が `thinking_time_ms <= 2300ms` かつ 3-7 の数牌の場合に panel alert として表示し、`alert_panel_haya.wav` を鳴らす。赤5は 5 として扱い、字牌・1/2/8/9・2300ms 超過は対象外。同じ alert key の再描画では再生しない。最新 event が自家打牌の場合は、表示上 `haya` が残っていても音声は鳴らさない。
- `oso`: 他家の最新打牌が第一打以外で `thinking_time_ms >= 4000ms` かつ 1/2/8/9 の数牌の場合に panel alert として表示し、`alert_panel_oso.wav` を鳴らす。字牌・3-7・第一打・4000ms 未満は対象外。同じ alert key の再描画では再生しない。最新 event が自家打牌の場合は、表示上 `oso` が残っていても音声は鳴らさない。
- `dora`: 他家の最新打牌が `dora_indicator_tiles` から見たドラ、または赤5の場合に panel alert として表示し、`alert_panel_dora.wav` を鳴らす。同じ alert key の再描画では再生しない。最新 event が自家打牌の場合は、表示上 `dora` が残っていても音声は鳴らさない。
- `早い傾向`: 半荘内3局目以降、他家の1段目3〜6打目で現在局平均が過去局平均より早い状態に入った場合に panel alert として表示し、`alert_panel_fast_trend.wav` で「早い傾向」を鳴らす。同じ状態の再描画では再生しない。いったん条件外へ戻ってから再び条件内へ入った場合は再度鳴らす。
- `Bridge` / `WGC` / `INITBYLOG`: Bridge map 成功で live snapshot refresh token が進んだ場合、または live snapshot の最新 raw event が `wgc` / `initbylog` の場合、`alert_huuuro.wav` で「huuuro」を鳴らす。async-only refresh や同じ source / live refresh token の再描画では鳴らし直さず、次の対象 source 受信で再度鳴らす。
- panel に表示される他家 alert だけを音声対象にする。
- 自分側の remain / push / hidden alert は音声対象外。
- `Remain` 音声は no-temp remain が白/通常状態から黄色閾値へ入ったタイミングだけ `remain_yellow` を鳴らす。黄色内、黄色から赤/紫、赤/紫内、赤/紫から黄色へ戻る変化では鳴らさない。閾値外へ戻ったあと再び白から黄色へ入った場合は再度鳴らす。
- `Push` 音声は既存どおり各席の2段目以降だけを対象とし、対象捨て牌の `P` marker と同一 redraw で反映する。panel の `Push` は 3巡保持するが、音声は保持期間の最初の Push 入場時だけ鳴らし、保持中の再描画や Push key 更新では鳴らさない。
- 複数の音声 alert が同じタイミングで発生した場合は、共有 worker の FIFO queue に積み、古い音を捨てずに順番に再生する。WAV asset も worker 上で同期再生し、後続音が前の音を中断しない。
- 同じ音声 alert job がすでに queue 内にある、または worker が再生処理へ渡している間は、同一 job を再投入しない。
- 同一の global discard index では音声 asset / kind ごとに 1 回だけ queue する。`alert_panel_yellow` / `alert_panel_red` のような同種音声は同じ捨て牌内で重ねず、`dora` と `haya` など異なる音声 kind は同じ捨て牌でも順番に鳴らしてよい。

## 自家 `2見え以下字牌`

- 自家右側、副露帯寄りに表示する。
- 対象は 0見え / 1見え / 2見えの字牌。
- 公開枚数は捨て牌、副露、ドラ表示牌から数える。

## NAGA 下部パネル

- 南2局以降だけ表示する。
- 現状 ptEV、主要和了、主要放銃、流局 best/worst を短く並べる。
- 詳細は NAGA ボタンの popup に残し、下部は常時視認用の要約に留める。
