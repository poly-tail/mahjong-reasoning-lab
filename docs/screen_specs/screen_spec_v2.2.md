# 画面仕様書 v2.2

updated: `2026-09-03`

## 1. 画面構成

| 領域 | 内容 |
| --- | --- |
| 卓中央 | 局情報、ドラ、河、鳴き帯 |
| 上部 | `AI TOP3`, `SELF`, `アラート音 OFF/ON`, Bridge 状態、NAGA ボタン |
| 他家パネル | `SUMMARY`, `ALERT`, `SCORE`, `BUTTONS` |
| 自家手牌 | 手牌、危険度バー、手牌操作、AI 応答 |
| 右詳細 | Visible x3/x4、lag 詳細、memo、Nodocchi STATUS |
| 最下部 | 南2局以降の NAGA 段位 pt 自動要約 |

## 2. 河

河は 4人 x 最大18枚を表示する。base river layer は full redraw 境界では全削除・全描画し、cached-layout redraw では slot 単位の表示シグネチャと Canvas item tag の存在を確認して変化のない牌を再利用する。analysis overlay だけを別 layer として更新する。ただし副露 `call` event の redraw / async-only refresh 後だけ、配列に残る slot の Canvas image item 欠落を検知する。欠け検出時は同じ refresh 内で差分再実行せず、通常 redraw queue へ戻す。table frame の cache miss では opaque な discard zone が既存牌を覆うため、base river / analysis overlay と描画 cache を invalidate し、同じ redraw 内で frame の後に河を全描画する。

表示要素:

- 黄枠: 鳴かれた捨て牌
- 黄強調: 鳴き直後の手出し
- `L`: 通常 lag
- `Pl`: pon-lag-likely または複数人 lag
- `P`: Push alert 対象のうち、各席の2段目以降にある捨て牌
- `合`: 他家の手出しから5回以内の捨て牌増加で同じ34種牌を切った合わせ打ち
- 赤ひし形: その局で最長の思考時間
- ピンク丸: 3見え
- 紫 tint: 4見え
- 茶 tint: 4見えで物理否定された 3連形に属する手出し牌
- 赤 tint: remain / no-temp remain / post-call tedashi など危険寄り条件
- 思考時間帯: post-reach と pre-reach を別 band で表示

河の `P` は、各席の捨て牌 local index 0〜5（1段目）には描画せず、index 6 以降（2段目以降）だけ描画する。表示対象の `Push` 判定で音声が鳴る場合は、同一 redraw で `P` を反映する。
河は base river layer と analysis overlay layer に分ける。base は牌画像本体、手出し/ツモ切り、思考時間、lag、`called=True` 黄色枠、リーチ棒を描く。analysis overlay は red / brown / four-visible tint、見え枚数 marker、2段目以降の Push `P`、合わせ打ちの `合` を牌画像上へ重ねる。副露や projection 更新では base river を短縮せず、鳴かれた捨て牌は黄色枠で残す。
合わせ打ちの5打牌窓は全席の捨て牌増加だけで数える。途中の対象seat自身の別打牌をまたいでも窓内なら有効で、副露・ドラ表示は起点にも窓消費にも使わず、起点側のツモ切りは対象外とする。

renderer は通常の round cache が reset されても、最後に描けた base river backup を `LiveRiverStore.epoch` 境界まで保持する。snapshot fallback は capture state lock が busy の場合も表示用 stable copy の optimistic read で短い cached snapshot を補強する。`round_identity=None` や短い/空 projection では画面の欠落 slot を backup から復元し、epoch 変更時だけ前局 backup を破棄する。

最新 event が `call`、または `LiveTableSnapshot.recent_event_types` に `call` が残るときに短い `discard_map` を受けた場合、Canvas discard slot を削除した場合、または配列に残る slot の Canvas image item 欠落を検知した場合は `logs/live_capture.log` に UI 側の河診断を残す。

## 3. プレイヤーパネル

### `SUMMARY`

- `Remain current/no-temp`
- Line ranking
- Safe hand ranking
- 危険ランク
- SCORE は自家基準の点差を表示する。

### `ALERT`

- `SUMMARY` と同じ no-temp remain 閾値で黄色・赤・紫を決める。
- `Push` は panel と河の `P` で同じ seat / global discard index を参照する。ただし河 `P` だけは seat-local index 0〜5を表示対象外とする。
- `Push解除` は Push 後の手出し現物で緑表示へ切り替える。
- `早い傾向` は半荘内3局目以降の他家1段目3〜6打目で、現在局平均思考時間が過去局平均より早い場合に黄色表示する。

### `STATUS`

Nodocchi 鳳凰卓4人打ち成績を右詳細領域に表示する。

- 和了率: 赤字
- 副露率: 赤字
- リーチ率: 赤字
- その他: 白字
- 取得中、取得失敗、データなしでも `Nodocchiで開く` 導線を残す。

### 非同期分析中の表示保持

- 同一局の heavy suji / 危険度計算中は、他家 side panel、自家手牌の危険度棒、関連する河 analysis overlay に直前の完了済み bundle を表示し続ける。loading summary や空の危険度配列で既表示を消さない。
- 手牌が変わった場合、旧危険度は同じ牌と同牌内の出現順に再対応付けし、対応する旧牌がない牌には stale な棒を表示しない。
- 同一局に完了済み bundle がまだない初回計算だけ loading / 危険度棒なしを許容し、新局へ前局値を持ち越さない。
- 新 bundle 完了時は async-only partial refresh で side panel / hand / analysis overlay だけをまとめて差し替える。base river / table frame は再描画しない。
- 保持中の stale 値は表示専用であり、自動打牌や alert 音声の新規判定には使わない。

## 4. 音声

- 画面左上の専用段に置く `アラート音 OFF/ON` で全 alert 音声を切り替える。遅れて生成される `NAGA段位` ボタンと座標を共有しない。起動時は OFF、ON 切替時は音量確認用の上昇2音チャイムと「サウンド、オン」音声を1回鳴らし、設定は次回起動へ持ち越さない。OFF 中も画面表示と alert 遷移の追跡は続け、ON 切替時に過去の alert を遅延再生しない。
- 音声対象は panel に表示される他家 alert。
- `haya`: 他家の最新打牌が `thinking_time_ms <= 2300ms` かつ 3-7 の数牌の場合に panel alert として表示し、`alert_panel_haya.wav` を鳴らす。赤5は 5 として扱い、字牌・1/2/8/9・2300ms 超過は対象外。同じ alert key の再描画では再生しない。最新 event が自家打牌の場合は、表示上 `haya` が残っていても音声は鳴らさない。
- `oso`: 他家の最新打牌が第一打以外で `thinking_time_ms >= 4000ms` かつ 1/2/8/9 の数牌の場合に panel alert として表示し、`alert_panel_oso.wav` を鳴らす。字牌・3-7・第一打・4000ms 未満は対象外。同じ alert key の再描画では再生しない。最新 event が自家打牌の場合は、表示上 `oso` が残っていても音声は鳴らさない。
- `dora`: 他家の最新打牌が `dora_indicator_tiles` から見たドラ、または赤5の場合に panel alert として表示し、`alert_panel_dora.wav` を鳴らす。同じ alert key の再描画では再生しない。最新 event が自家打牌の場合は、表示上 `dora` が残っていても音声は鳴らさない。
- `早い傾向`: 半荘内3局目以降、他家の1段目3〜6打目で現在局平均思考時間が過去局平均より早い状態に入った場合に panel alert として表示し、`alert_panel_fast_trend.wav` を鳴らす。同じ状態の再描画では再生せず、条件外へ戻ったあと再入場した場合は再度鳴らす。
- `Bridge` / `WGC` / `INITBYLOG`: Bridge map 成功で live snapshot refresh token が進んだ場合、または live snapshot の最新 raw event が `wgc` / `initbylog` の場合、`alert_huuuro.wav` で「huuuro」を鳴らす。同じ source / live refresh token の再描画では再鳴動しない。
- 自分側の remain / push / hidden alert は鳴らさない。
- `Remain` 音声は no-temp remain が白/通常状態から黄色閾値へ入ったタイミングだけ `remain_yellow` を鳴らす。黄色内、黄色から赤/紫、赤/紫内、赤/紫から黄色へ戻る変化では鳴らさない。閾値外へ戻ったあと再び白から黄色へ入った場合は再度鳴らす。
- `Push` 音声は 3巡保持中に繰り返さず、Push alert が有効になった最初のタイミングだけ鳴らす。
- 複数の音声 alert が同じタイミングで発生した場合は、共有 worker の FIFO queue に積み、古い音を捨てずに順番に再生する。WAV asset も worker 上で同期再生し、後続音が前の音を中断しない。UI thread では再生しない。
- 同じ音声 alert job がすでに queue 内にある、または worker が再生処理へ渡している間は、同一 job を再投入しない。
- 同一の global discard index では同じ音声 asset / kind を 1 回だけ鳴らし、同じ捨て牌内の `alert_panel_yellow` / `alert_panel_red` など同種音声の二重再生を抑制する。異なる音声 kind は同じ捨て牌でも順番に鳴らす。

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

`UI discards slow` は `drawn`, `skipped`, `changed`, `stale_deleted` を出す。cached-layout redraw では変化のない base 牌を skip できるため、通常打牌以外の redraw では `skipped` が増え、`drawn` は新規または変更 slot に寄る。

## 8. 互換

- v2.1 以前の `screen_spec_v2.1.md` は前版として残す。
- 現行の正本は本ファイルと `current.md`。
