# 要件定義 v2.2

updated: `2026-09-03`

## 1. 目的

天鳳の live / replay / XML 局面を、補助判断・自動操作・分析へつなげるローカル支援 UI として維持する。v2.2 では、直近で追加した alert 音声、NAGA 自動表示、Nodocchi STATUS、河描画高速化、DB分析の要件を正本化する。

## 2. 表示要件

- 画面は卓、河、他家プレイヤーパネル、自家手牌、詳細領域、Bridge 操作、NAGA 下部パネルで構成する。
- 他家プレイヤーパネルは `SUMMARY`, `ALERT`, `SCORE`, `BUTTONS` を持つ。
- `SUMMARY` の `Remain current/no-temp` と `ALERT` の黄色・赤・紫は同じ no-temp remain 閾値を使う。
- 同一局の heavy suji / 危険度 bundle が計算中の間、他家 side panel、自家手牌の危険度棒、関連する analysis overlay は直前の完了済み bundle を表示専用で保持する。手牌が変わった場合は同じ牌と同牌内の出現順へ危険度を対応付け、対応する旧牌がない新規牌には stale な棒を付けない。完了値がまだない初回計算だけ loading / 危険度棒なしを許容し、新局へは持ち越さない。
- Nodocchi `STATUS` では和了率・副露率・リーチ率を赤字、その他の成績値を白字にする。
- 河は鳴かれた捨て牌の黄色枠、鳴き直後手出しの黄枠、`L`, `Pl`, `P`, 合わせ打ちの `合`、最大思考時間、3見え/4見え、赤/茶/紫 tint を同時に表現できる。
- 河の Push `P` は、各席の捨て牌 local index 0〜5（1段目）には表示せず、index 6 以降（2段目以降）だけ表示する。
- 合わせ打ちは `LiveRiverStore` 由来の全席捨て牌履歴を使い、他家の手出しから数えて5回以内の捨て牌増加で同じ34種牌が切られた場合に表示用フラグを付ける。副露・ドラ表示は起点にも窓の消費にも使わず、ツモ切りは起点にしない。
- 南2局以降は NAGA 段位ポイント分析を自動取得し、主要な放銃・和了・流局の pt 変化を最下部へ短く表示する。

## 3. 音声要件

- 上部操作列に `アラート音 OFF/ON` ボタンを置き、起動時の既定値は OFF とする。ON 切替時は音量確認用の短いチャイムと「サウンド、オン」の言語音声を1回鳴らす。OFF 中は全 alert 音声を鳴らさず、表示と alert 遷移の追跡は継続する。ON へ切り替えた時点で表示済みの過去 alert は遅延再生しない。
- 音声は画面に表示される他家 alert を起点に鳴らす。
- 自分側の残り筋や、プレイヤーパネルに出ない Push / Remain 系 alert は音声対象外とする。
- 最新 event が自家打牌の場合、表示上の他家 `haya` / `oso` timed alert と `dora` discard alert は音声対象外とする。
- 他家の最新打牌が `dora_indicator_tiles` から見たドラ、または赤5の場合は `dora` panel alert と `alert_panel_dora.wav` の音声対象にする。
- 半荘内3局目以降、他家の1段目3〜6打目で現在局平均思考時間が過去局平均より早い場合は、黄色の `早い傾向` panel alert と `alert_panel_fast_trend.wav` の音声対象にする。
- Bridge map 成功、`WGC`、`INITBYLOG` は `alert_huuuro.wav` の音声対象にする。同じ source / live refresh token の再描画では再鳴動しない。
- 複数の音声 alert が同じタイミングで発生した場合は、共有 worker の FIFO queue に積み、古い音を捨てずに順番に再生する。
- 同じ音声 alert job がすでに queue 内にある、または worker が再生処理へ渡している間は、同一 job を再投入しない。
- 同一の global discard index では音声 asset / kind ごとに 1 回だけ鳴らし、`alert_panel_yellow` や `alert_panel_red` など同種音声を同じ捨て牌内で複数回 queue しない。異なる音声 kind は同じ捨て牌でも順番に鳴らしてよい。
- 各席の2段目以降では `Push` 音声と河の `P` マークを同一更新で反映し、音だけ先行しない。
- `Push` 音声は三巡保持中に繰り返さず、Push alert が有効になった最初のタイミングだけ鳴らす。
- `Remain` 音声は no-temp remain が白/通常状態から黄色閾値へ入ったタイミングだけ `remain_yellow` を鳴らす。黄色内、黄色から赤/紫、赤/紫内、赤/紫から黄色へ戻る変化では鳴らさない。閾値外へ戻ったあと再び白から黄色へ入った場合は再度鳴らす。
- 音声再生は専用 worker queue で行い、UI thread を止めない。

## 4. 性能要件

- 河は最大 4人 x 18枚を毎回全描画しない。座席 + 捨て牌 index の表示シグネチャが変化した牌だけ描画し直す。
- 色付き牌のための `PhotoImage` 合成は discard path で行わない。通常牌画像を使い、色は Canvas overlay で重ねる。
- discard path の Canvas item は作成時に `tags=` を付ける。
- `side_panels` と `discards` は slow log に phase breakdown を残し、重い処理のランキングを取れるようにする。
- heavy suji / 危険度 bundle の完了時は async-only partial refresh で side panel / hand / analysis overlay だけを差し替え、base river / table frame を再描画しない。保持中の stale bundle は表示専用とし、自動打牌や alert 音声の新規判定へ使わない。
- full redraw、UI scale 変更、round reset、manual reinit では河描画 cache を明示的に破棄する。

## 5. 分析要件

- `discard_fact_*.csv` と `hanchan_master.csv` から、プレイヤーごとの 1〜3 シャンテン数と思考時間の相関を集計できること。0シャンテンは短時間側の例外として標準レポートの相関対象から除外する。
- 分析結果にはプレイヤー名、サンプル数、シャンテン別中央値、相関、ばらつき、所属卓を含める。
- 所属卓は `hanchan_master` の座席名と `room_class_label` から集計し、discard row 側の卓種は fallback として扱う。
- 出力は CSV / HTML / PNG を `reports/player_shanten_thinking/` 以下へ保存する。

## 6. データ要件

- `hanchan_master` は半荘単位の卓種、プレイヤー名、source URL を保持する。
- `kyoku_master` は各局・各席の1段目平均思考時間を `seat0..3_first_row_avg_thinking_time_ms` として保持する。
- `discard_fact_YYYYMM` は打牌、思考時間、シャンテン、危険度、pystyle top3、agari snapshot を月別に保持する。
- 古い CSV から読める legacy 列は必要に応じて補完するが、現行保存は `room_class_label` を正本とする。

## 7. 運用要件

- 仕様変更時は `docs/requirements/current.md`, `docs/specs/current.md`, `docs/screen_specs/current.md`, `docs/changelog.md` を同期する。
- 画面表示の変更は `docs/screen_specs/*.md` へ、DB分析の変更は `docs/analysis/*.md` へ反映する。
- Push 前提、河 `P` の1段目非表示境界、Remain 閾値、NAGA 自動表示、河描画 cache はテストで固定する。
