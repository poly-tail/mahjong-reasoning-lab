# ソース概要

updated: `2026-05-24`

## `src/app/`

- `main.py`: 起動、snapshot 構築、Bridge / pystyle / NAGA / renderer 連携。
- `hand_recommendation_service.py`: `AI TOP3` 用 pystyle request と response 整形。
- `nodocchi_stats.py`: Nodocchi 成績取得、cache、表示用整形。
- `naga_analyzer.py`: NAGA ptEV analyzer への query state 構築と response parsing。
- `tenhou_ui_bridge_*`: Chrome extension 経由の天鳳 UI 操作。

## `src/capture/`

- `state.py`: `CaptureState`, `RoundState`, `Discard`, `Meld`。
- `live_river_store.py`: `RoundState` の寿命から独立した live base river 正史。
- `fragment_parser.py`: live / replay / XML tag を state に反映。
- `tshark_capture.py`, `pcap_replay.py`: 入力経路。
- `storage.py`: CSV DB 永続化、legacy CSV 補完、hanchan metadata cache。
- `csv_db_schema.py`: CSV DB の正本 schema。

## `src/logic/`

- `danger_suji.py`: remain / no-temp remain / Push / line ranking / hand danger bar。
- `hand_analysis.py`: シャンテン、待ち、手牌分析。

## `src/ui/`

- `table_renderer.py`: Tk Canvas 画面描画、panel、alert、音声、河差分描画。
- `tile_images.py`: 牌画像読み込み、通常牌画像のスケール/回転。

## `scripts/`

- `analyze_player_shanten_thinking.py`: DB からプレイヤー別の思考時間 x シャンテン相関と所属卓を出力。

## 最近の重点実装

- 河描画は `table_renderer.py` の per-discard signature cache で差分化。
- discard tint は `PhotoImage` 合成ではなく Canvas overlay。
- panel alert 音声は panel 表示に出た他家 alert だけを対象にする。
- NAGA 自動表示は `main.py` が DTO を作り、renderer は下部 strip だけを描く。
- 所属卓分析は `hanchan_master` の座席名と `room_class_label` を正本にする。

## 関連

- [../specs/current.md](../specs/current.md)
- [../screen_specs/river_display.md](../screen_specs/river_display.md)
- [../analysis/performance_hotspots.md](../analysis/performance_hotspots.md)
