# 要件定義 現行版

> 現行版: `requirements_v2.2.md`
> 更新日: `2026-05-24`
> 前版: `requirements_v2.1.md`

## 現行スコープ

- live capture / replay / XML import の局面を同一 renderer へ流し、天鳳卓の現在状態を即時可視化する。
- `AI TOP3`, `SELF`, 他家プレイヤーパネル、河、Bridge 操作、NAGA 段位ポイント分析を 1 画面で扱う。
- 押し引き、残り筋、ラグ、同順合わせ打ち、3見え/4見え、思考時間、Nodocchi 成績を、表示・音声・DB分析で矛盾しないよう揃える。
- 重い UI 処理は段階的に計測し、主に河と side panel の再描画を差分化する。

## 最近の必須要件

- `Push` 判定で音が鳴る場合、同じ更新タイミングで対象捨て牌へ `P` マークを表示する。
- プレイヤーパネルに出ない自分側の残り筋・Push 系 alert は音声対象から除外する。
- `Remain` 系音声は色名だけでなく `r-red`, `r-yellow`, `r-purple` のように先頭へ `r` 読みを付ける。
- プレイヤーパネルの `SUMMARY` と `Alert` は、黄色・赤・紫の閾値を `SUMMARY` 側の no-temp remain 基準へ統一する。
- Nodocchi `STATUS` 表示では、和了率・副露率・リーチ率だけを赤字、その他の数値は白字で表示する。
- 河の再描画は全牌再生成ではなく、座席 + 捨て牌 index の表示シグネチャが変わった牌だけ再描画する。
- 河の赤/茶/紫/4見え/思考時間色は、色付き `PhotoImage` を都度作らず、通常牌画像 + Canvas overlay で描画する。
- 河の Canvas item は作成時に tag を付け、描画後の `find_all()` 差分タグ付けを discard path では使わない。
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
