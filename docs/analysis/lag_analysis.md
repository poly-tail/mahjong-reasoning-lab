# ラグ分析の前提

`discard_fact` の `lagged` / `lag_delay_ms` を使ってラグ傾向を集計するときの前提をまとめる。

## 目的

- ラグらしく見えるが、実際には通信遅延やアプリ遅延寄りの短時間データを弾く
- ラグ分析の散布図、ヒストグラム、箱ひげ図などで毎回同じ下限を使う
- raw DB の記録値と、分析サンプルの採用条件を混同しない

## 基本前提

- 準備していても、鳴きスキップを `600ms` 未満で安定して行うのは難しいとみなす
- そのため、`lag_delay_ms <= 550` はシステム遅延寄りの値として扱う
  - 例: 通信遅延
  - 例: アプリ遅延
  - 例: capture 観測ずれ
- 新しい DB 運用では、この領域は `lagged = 6` として分離する
- 上記の値は DB にはそのまま保持してよいが、ラグ分析の集計サンプルには入れない

## 推奨フィルタ

ラグ分析では、まず次の条件を掛ける。

```text
lag_delay_ms IS NOT NULL
AND lag_delay_ms > 550
AND player_name NOT IN ('パシフィック', 's6u')
```

必要に応じて、このあとにテーマ別条件を重ねる。

例:

- `lagged = 1` の live 未確定ラグだけを見る
- `lagged = 6` の short system delay だけを別集計する
- `lagged IN (2, 3)` の本ラグ寄りだけを見る
- 鳴き発生局面だけを見る

## 補足

- `550ms` 以下を除外するのは、DB 記録を消すという意味ではない
- あくまで「分析用サンプルから外れ値として除外する」という意味で使う
- 新しいデータでは `lagged = 6` が付くが、旧データ互換のため分析条件は `lag_delay_ms > 550` ベースでも書ける
- `lagged` の意味自体は `docs/reference/csv_db_design.md` と `docs/mahjong/mahjong_call_rules.md` を参照する

## 関連

- 共通分析ルール: `docs/analysis/db_analysis_rules.md`
- 汎用グラフCLI: `docs/analysis/db_graph_tool.md`
- DB schema: `docs/reference/csv_db_design.md`
