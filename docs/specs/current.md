# 仕様書 現行版

> 現行版: `api_spec_v2.2.md`
> 更新日: `2026-05-24`
> 前版: `api_spec_v2.1.md`

## 現行仕様の要点

- `LiveTableSnapshot` は UI 描画用の一貫した局面 snapshot として扱う。
- `NagaAutoPanelData` を renderer へ渡し、南2局以降の NAGA 段位 pt 変化を下部へ表示する。
- `PlayerAlertIndicator` は panel 表示と音声判定の正本であり、panel に出ない自分側 alert は音声へ流さない。
- `Push` alert payload は seat / tile / discard_index / percentage / threshold を持ち、panel と河 `P` marker は同じ payload から決める。
- `Remain` alert は `SUMMARY` と同じ no-temp remain 閾値で色を決める。
- 河描画は `canvas.discard_render_cache_by_key[(seat, local_index)]` に表示シグネチャを持ち、変化した牌だけ Canvas item tag 単位で差し替える。
- `_discard_tile_image()` は通常牌画像だけを返す。赤/茶/紫/4見え/思考時間は Canvas overlay で描画する。
- DB分析 `scripts/analyze_player_shanten_thinking.py` は `discard_fact_*.csv` と `hanchan_master.csv` を読み、プレイヤー別の思考時間 x シャンテン相関と所属卓を出す。

## 関連文書

- 仕様本体: [api_spec_v2.2.md](./api_spec_v2.2.md)
- 要件定義: [../requirements/current.md](../requirements/current.md)
- 画面仕様: [../screen_specs/current.md](../screen_specs/current.md)
- CSV DB: [../reference/csv_db_design.md](../reference/csv_db_design.md)
- 性能ホットスポット: [../analysis/performance_hotspots.md](../analysis/performance_hotspots.md)
