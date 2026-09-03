# 要件定義 現行版

> 現行版: `requirements_v2.2.md`
> 更新日: `2026-09-03`
> 前版: `requirements_v2.1.md`

## 現行スコープ

- live capture / replay / XML import の局面を同一 renderer へ流し、天鳳卓の現在状態を即時可視化する。
- `AI TOP3`, `SELF`, 他家プレイヤーパネル、河、Bridge 操作、NAGA 段位ポイント分析を 1 画面で扱う。
- 押し引き、残り筋、ラグ、合わせ打ち、3見え/4見え、思考時間、Nodocchi 成績を、表示・音声・DB分析で矛盾しないよう揃える。
- 重い UI 処理は段階的に計測し、主に河と side panel の再描画を差分化する。

## 最近の必須要件

- 上部操作列に `アラート音 OFF/ON` ボタンを置き、アプリ起動時は必ず OFF とする。ON 切替時は音量確認用の短いチャイムと「サウンド、オン」の言語音声を1回鳴らす。OFF 中は全 alert 音声を抑止しつつ遷移状態を追跡し、ON 切替時に過去の alert を遅延再生しない。
- 同一局の heavy suji / 危険度 bundle が計算中の間、他家 side panel、自家手牌の危険度棒、関連する analysis overlay は直前の完了済み bundle を表示専用で保持する。手牌が変わった場合は同じ牌と同牌内の出現順へ危険度を対応付け、対応する旧牌がない新規牌には stale な棒を付けない。完了値がまだない初回計算だけ loading / 危険度棒なしを許容し、新局へは持ち越さない。
- 新しい bundle の完了時は async-only partial refresh で side panel / hand / analysis overlay だけを差し替え、base river / table frame を再描画しない。保持中の stale bundle は自動打牌や alert 音声の新規判定へ使わない。
- 河の Push `P` は、各席の捨て牌 local index 0〜5（1段目）には表示せず、index 6 以降（2段目以降）だけ表示する。
- 各席の2段目以降で `Push` 音声が鳴る場合、同じ更新タイミングで対象捨て牌へ `P` マークを表示する。
- `Push` 音声は三巡保持中に繰り返さず、Push alert が有効になった最初のタイミングだけ鳴らす。
- プレイヤーパネルに出ない自分側の残り筋・Push 系 alert は音声対象から除外する。
- 最新 event が自家打牌の場合、表示上の他家 `haya` / `oso` timed alert と `dora` discard alert は音声対象から除外する。
- 他家の最新打牌が `dora_indicator_tiles` から見たドラ、または赤5の場合は `dora` panel alert と `alert_panel_dora.wav` の音声対象にする。
- 半荘内3局目以降、他家の1段目3〜6打目で現在局平均思考時間が過去局平均より早い場合は、黄色の `早い傾向` panel alert と `alert_panel_fast_trend.wav` の音声対象にする。
- Bridge map 成功、`WGC`、`INITBYLOG` は `alert_huuuro.wav` の音声対象にする。同じ source / live refresh token の再描画では再鳴動しない。
- 複数の音声 alert が同じタイミングで発生した場合は、共有 worker の FIFO queue に積み、古い音を捨てずに順番に再生する。
- 同じ音声 alert job がすでに queue 内にある、または worker が再生処理へ渡している間は、同一 job を再投入しない。
- 同一の global discard index では音声 asset / kind ごとに 1 回だけ鳴らし、`alert_panel_yellow` や `alert_panel_red` など同種音声を同じ捨て牌内で複数回 queue しない。異なる音声 kind は同じ捨て牌でも順番に鳴らしてよい。
- `Remain` 系音声は no-temp remain が白/通常状態から黄色閾値へ入ったタイミングだけ `remain_yellow` を鳴らす。黄色内、黄色から赤/紫、赤/紫内、赤/紫から黄色へ戻る変化では鳴らさない。閾値外へ戻ったあと再び白から黄色へ入った場合は再度鳴らす。
- プレイヤーパネルの `SUMMARY` と `Alert` は、黄色・赤・紫の閾値を `SUMMARY` 側の no-temp remain 基準へ統一する。
- Nodocchi `STATUS` 表示では、和了率・副露率・リーチ率だけを赤字、その他の数値は白字で表示する。
- 河の再描画は全牌再生成ではなく、座席 + 捨て牌 index の表示シグネチャが変わった牌だけ再描画する。
- 河の赤/茶/紫/4見え/思考時間色は、色付き `PhotoImage` を都度作らず、通常牌画像 + Canvas overlay で描画する。
- 河の Canvas item は作成時に tag を付け、描画後の `find_all()` 差分タグ付けを discard path では使わない。
- 合わせ打ちは `LiveRiverStore` 由来の全席捨て牌履歴を使い、他家の手出しから数えて5回以内の捨て牌増加で同じ34種牌が切られた場合に表示用フラグを付ける。副露・ドラ表示は起点にも窓の消費にも使わず、ツモ切りは起点にしない。
- 合わせ打ちフラグの捨て牌には、analysis overlayで黄色の `合` を牌画像上へ重ねる。
- 南2局以降は下部スペースに NAGA 段位ポイント分析の主要な放銃・和了・流局の pt 変化を自動表示する。
- DB分析は、思考時間とシャンテン数の相関をプレイヤーごとに集計し、所属卓を `hanchan_master` から併記する。

## 非機能要件

- UI thread で長時間処理を走らせない。NAGA、Nodocchi、pystyle、visible 推定、音声再生は background thread / queue で扱う。
- background thread は用途ごとに上限を持ち、同一処理の多重起動を避ける。
- slow log は `side_panels` と `discards` の phase breakdown を出し、重い処理ランキングを追跡できること。
- full redraw と incremental redraw の cache invalidation を明示し、古い河 item や click spec が残らないこと。
- CSV DB は分析用の正本として扱い、`hanchan_master` の卓種情報を後続分析へ引き継げること。

## 関連文書

- 仕様書: [../specs/current.md](../specs/current.md)
- 画面仕様書: [../screen_specs/current.md](../screen_specs/current.md)
- 河表示: [../screen_specs/river_display.md](../screen_specs/river_display.md)
- パネルとアラート: [../screen_specs/alerts_and_panels.md](../screen_specs/alerts_and_panels.md)
- 性能ホットスポット: [../analysis/performance_hotspots.md](../analysis/performance_hotspots.md)
- プレイヤー別シャンテン思考時間分析: [../analysis/player_shanten_thinking.md](../analysis/player_shanten_thinking.md)
