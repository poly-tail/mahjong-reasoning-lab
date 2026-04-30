# 性能ホットスポット

更新日: `2026-04-15`

この文書は現時点のホットスポット順位と、ワーカー / coalescing の現状を残すための履歴ファイルである。

## 現在の順位

### 計算量ベース

1. `live red tint` cold rebuild
2. `live suji` bundle
3. suji profile / weighted line map
4. live snapshot clone
5. actual visible summary
6. awaseuchi provisional/confirm

### UI を止めやすい順

1. state lock を跨ぐ snapshot clone
2. bridge snapshot の重複
3. main thread に残っている renderer 判定

## 現在の緩和策

- `live suji`: 常駐ワーカー
- `live red tint`: 常駐ワーカー
- `inferred visible`: 常駐ワーカー
- `bridge snapshot`: coalescing
- `awaseuchi confirm`: provisional 候補がある時だけキュー投入
- discard tint image:
  - tint base を prewarm
  - thinking-time band だけ後乗せ

## 現在のメモ

- actual visible は軽い
- visible と awaseuchi は分離済み
- `no-temp remain` と tedashi history は差分更新
- red tint は seat-level latch 後かなり軽いが、cold path はまだ上位

## 計測テンプレート

```
date:
command:
result:
ranking:
notes:
```

## 履歴

### 2026-04-15

- `bridge snapshot` は `1 in-flight + pending 1` に変更
- `live suji` は常駐 worker 化
- `live red tint` も常駐 worker 化
- `inferred visible` は常駐 worker のまま維持
- `BG ... xN` は active thread count 表示へ変更
- freeze investigation: turning `table situation` fully OFF did not help, but turning `awaseuchi` OFF stopped the symptom.
- current prime suspect: `awaseuchi provisional/confirm`
  - public-event state update runs on redraw-side
  - result-queue drain runs from both `watch_refresh_token()` and bridge tick
  - cache exists, but live refresh churn can still hit the main thread
- temporary mitigation: keep `AWASEUCHI_MARKERS_ENABLED = False` while isolating the regression.
- follow-up freeze isolation: `inferred visible` runtime was also fully disabled.
  - no worker startup
  - no queue drain in redraw/watch paths
  - no inferred-visible draw or tile-panel UI
  - helper tests still run by enabling the dummy canvas explicitly
- next freeze mitigation: async `live suji` / `live red tint` bundle completion no longer changes the UI refresh token.
  - background bundles still compute
  - completed bundles are picked up on the next capture-driven redraw
  - this removes one redraw loop source while keeping the data path intact
- current bridge-side mitigation: periodic `ui_snapshot` polling is disabled.
  - `SYNC` still works
  - discard/control success still triggers forced follow-up snapshots
  - this removes the last always-on bridge background thread during idle
