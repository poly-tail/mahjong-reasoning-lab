# 手牌分析仕様

`src/logic/hand_analysis.py` の現在仕様をまとめる。主用途は `discard_fact` の分析列計算であり、打牌時 snapshot からシャンテン数、待ち牌、両面固定判定を求める。

## 1. 入力表現
- concealed hand の正本は raw `tile_136`
- 集計計算は 34 種 counts へ正規化して行う
- open meld 数は打牌前 concealed hand 枚数 `14 / 11 / 8 / 5 / 2` から推定する

## 2. シャンテン計算
- `calculate_shanten_from_tiles_136()` は raw `tile_136` から `ShantenBreakdown` を返す
- `calculate_shanten_from_counts_34()` は 34 種 counts から `ShantenBreakdown` を返す
- `ShantenBreakdown.overall` は `normal`, `chiitoitsu`, `kokushi` のうち有効値の最小を持つ
- 七対子と国士無双は門前時だけ有効とする

## 3. 待ち牌列挙
- `find_tenpai_wait_tiles_34_from_tiles_136()` はテンパイ手牌の待ちを 0..33 で返す
- `find_tenpai_wait_tiles_34_from_counts_34()` は counts ベース版
- 現手牌が `overall != 0` のときは空集合を返す
- 各牌種を 1 枚ずつ加え、`overall == -1` になる牌種だけを待ちとして採用する
- 同一牌種は 4 枚見えている場合には候補へ加えない

## 4. 両面固定判定
- `detect_ryanmen_fixed_discard()` は打牌前 snapshot と打牌牌から、両面固定かどうかを判定する
- 打牌後局所形が `23..78` の 2 連形で、外側に伸びた 3 連形へならない場合だけ `is_ryanmen_fixed=True` とする
- `12` / `89` は penchan のため対象外

## 5. DB 保存時の意味
- `shanten_after_discard` 系は legacy 名だが、値は打牌前 concealed hand snapshot 基準
- `wait_tiles_after_discard_mspz` は実際の打牌後手牌を復元してから待ちを計算する
- snapshot と打牌牌が不整合な場合は待ち列を空欄 fallback する
- 列ごとの説明は `docs/reference/shanten_columns.md` を参照する

## 6. 文字列表現
- DB の待ちは `mspz` grouped text へ変換して保存する
- 例: `36m`, `258p`, `14z`

## 7. 関連文書
- `docs/reference/csv_db_design.md`: `discard_fact` 保存列の定義
- `docs/analysis/db_analysis_rules.md`: DB 分析時の共通除外条件
- `docs/mahjong/hand_analysis_terms.md`: 用語集
- `docs/reference/shanten_columns.md`: シャンテン関連列の意味
