# ソース概要

updated: `2026-04-21`

## モジュール構成

### `src/app/`

- `main.py`: 起動分岐、snapshot 組み立て、Bridge / AI / renderer 連携
- `hand_recommendation_service.py`: AI 推奨リクエストと応答整形
- `tenhou_ui_bridge_*`: Bridge の protocol / server / client / probe

### `src/capture/`

- `state.py`: `CaptureState`, `RoundState`, `Discard`, `Meld`
- `fragment_parser.py`: tag ごとの state 更新
- `tshark_capture.py`, `pcap_replay.py`: 入力経路
- `storage.py`: CSV DB 保存

### `src/logic/`

- `danger_suji.py`: remain / no-temp remain / push / tint
- `hand_analysis.py`: 手牌・待ちの分析

### `src/ui/`

- `table_renderer.py`: 画面描画本体
- `tile_images.py`: 牌画像読み込みとオーバーレイ

### `src/visible_tiles.py`

- actual visible 集計
- inferred visible の基礎データ供給

## 更新メモ

- 自家の `2見え以下字牌` 一覧は `src/ui/table_renderer.py` の専用配置ロジックで自副露帯寄りへ寄せる
- Mermaid 図の正本は `docs/graphs/src/*.mmd`
- SVG 再生成は `scripts/render_docs_graphs.py`
- ZIP 作成は `scripts/package_workspace.py`
