# 麻雀ロジック

このフォルダは、ツール実装に接続する麻雀判断ロジックの正本です。牌効率の学習用説明ではなく、「コードがどの前提で何を判定するか」を保守します。

## 文書一覧

- [hand_analysis.md](hand_analysis.md): シャンテン、待ち牌、両面固定判定。
- [mahjong_danger.md](mahjong_danger.md): 筋、裏筋、見え枚数補正、河 marker などの危険度ロジック。
- [opponent_tenpai_readiness.md](opponent_tenpai_readiness.md): 打牌から他家の聴牌近さを読む整理。
- [comparison_trace_reading_engine.md](comparison_trace_reading_engine.md): 比較痕跡ベースの読みエンジン設計。
- [suji_temp_no_temp_logic.md](suji_temp_no_temp_logic.md): temp / no-temp 系の筋ロジック図解。

## 置くもの

- 実装の入力、出力、閾値、例外、fallback。
- `src/logic/`、`src/capture/`、`src/ui/` の判定根拠。
- DB 分析や画面仕様から参照される麻雀判断の正本。

## 置かないもの

- 学習用の牌効率理論: [../theory/](../theory/README.md)
- ルールや用語の基礎定義: [../reference/](../reference/README.md)
- 検証前の長い研究メモ: [../research/](../research/README.md)
