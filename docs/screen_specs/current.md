# 画面仕様書 現行版

> 現行版: `screen_spec_v2.2.md`
> 更新日: `2026-05-24`
> 前版: `screen_spec_v2.1.md`

## 現行画面の要点

- 画面は卓、河、自家手牌、他家プレイヤーパネル、右詳細領域、Bridge 操作、NAGA 下部パネルで構成する。
- 河は `L`, `Pl`, `P`, 同順合わせ打ち、最大思考時間、3見え/4見え、赤/茶/紫 tint を表示する。
- `Push` 音声が鳴る更新では、同じ対象捨て牌へ `P` マークを即時表示する。
- 他家 panel の `SUMMARY` と `ALERT` は同じ remain 閾値を使う。
- Nodocchi `STATUS` は和了率・副露率・リーチ率だけ赤字、その他は白字。
- 南2局以降、下部スペースに NAGA 段位ポイント分析の自動要約を表示する。
- 河は差分描画で、変わった牌だけ更新する。

## 詳細文書

- 画面全体: [display_overview.md](./display_overview.md)
- 河表示: [river_display.md](./river_display.md)
- パネルとアラート: [alerts_and_panels.md](./alerts_and_panels.md)
- 操作と Bridge: [controls_and_bridge.md](./controls_and_bridge.md)
- 見え枚数 UI: [visible_counts_ui.md](./visible_counts_ui.md)
- 版付き画面仕様: [screen_spec_v2.2.md](./screen_spec_v2.2.md)

## 関連文書

- 要件定義: [../requirements/current.md](../requirements/current.md)
- 仕様書: [../specs/current.md](../specs/current.md)
- 性能ホットスポット: [../analysis/performance_hotspots.md](../analysis/performance_hotspots.md)
- NAGA 連携: [../integrations/naga_ptev_analyzer.md](../integrations/naga_ptev_analyzer.md)
