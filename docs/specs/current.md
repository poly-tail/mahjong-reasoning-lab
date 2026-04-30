# 仕様書 現行版

> 現行版ファイル: `api_spec_v2.1.md`

## 現行版

- 版: `v2.1`
- 更新日: `2026-04-21`
- 継承元: `old/api_spec_v2.0.md`

## 現在の重点

- `LiveTableSnapshot` を UI 描画専用の一貫スナップショットとして扱う
- `VisibleTileSummary` と `VisibleTileInferenceSummary` の責務を分ける
- Bridge スナップショットの poll / follow-up / coalescing を仕様として固定する
- グラフ再生成とワークスペース ZIP 化の再実行導線を明文化する

## 関連文書

- 仕様本文: [api_spec_v2.1.md](./api_spec_v2.1.md)
- 要件定義 現行版: [../requirements/current.md](../requirements/current.md)
- 画面仕様書 現行版: [../screen_specs/current.md](../screen_specs/current.md)
- データ構造: [../architecture/data_structures.md](../architecture/data_structures.md)
