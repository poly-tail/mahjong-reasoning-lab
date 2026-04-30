# Tenhou Hojo Helper API / 実装仕様 v1.7

## 1. 文書の位置づけ
- 本版は `api_spec_v1.6.md` を継承し、2026-04-07 に追加した待ち牌保存と `Layout Tuning` window 2 列化の実装契約を定義する。
- 対象モジュールは主に `src/logic/hand_analysis.py`, `src/capture/storage.py`, `src/capture/csv_db_schema.py`, `src/ui/table_renderer.py` である。

## 2. 対象モジュール
- `src/logic/hand_analysis.py`
- `src/capture/storage.py`
- `src/capture/csv_db_schema.py`
- `src/ui/table_renderer.py`
- `docs/requirements/requirements_v1.7.md`
- `docs/screen_specs/screen_spec_v1.7.md`

## 3. データ構造

### 3.1 `LayoutTuningSettings`
- 卓レイアウトの寸法、余白、scale、player-panel 割合を保持する dataclass とする。
- 少なくとも次を含む。
  - panel 系: `detail_panel_width`, `detail_panel_gap`, `detail_top_margin`, `horizontal_panel_width`, `horizontal_panel_height`, `vertical_panel_width`, `vertical_panel_height`
  - table / hand 系: `main_left_margin`, `panel_table_gap_extra`, `panel_top_margin`, `top_panel_top_margin`, `right_panel_right_margin`, `bottom_margin`, `hand_gap_margin`, `hand_bottom_margin`
  - discard 系: `discard_tile_scale`, `top_bottom_discard_extra_width`, `top_bottom_discard_extra_height`, `side_discard_extra_width`, `side_discard_extra_height`
  - `side_discard_extra_height` の UI label は `Side discard height` として表示し、左右河の高さ調整として扱う
  - meld 系: `meld_tile_scale`, `horizontal_meld_extra_height`, `side_meld_min_width`, `top_meld_min_width`
  - player-panel 系: `player_panel_summary_content_top_offset`, `player_panel_horizontal_summary_ratio`, `player_panel_horizontal_alert_ratio`, `player_panel_vertical_summary_ratio`, `player_panel_vertical_alert_ratio`, `player_panel_tile_rank_scale`, `player_panel_tile_rank_horizontal_row_gap`, `player_panel_tile_rank_vertical_row_gap`

### 3.2 `LayoutTuningControlSpec`
- tuning window の slider 定義を表す immutable dataclass とする。
- `field_name`, `label`, `min_value`, `max_value`, `resolution` を持つ。

### 3.3 `ShantenBreakdown`
- `overall`, `normal`, `chiitoitsu`, `kokushi`, `completed_meld_count` を持つ immutable dataclass とする。
- `overall` は有効な手役族の最小シャンテン値を保持する。

## 4. 手牌分析 API
- `tiles136_to_counts34()` は raw 136 tile ids から 34 種 counts を返す。
- `infer_open_meld_count_from_pre_discard_hand_size()` は打牌前 concealed hand 枚数 `14 / 11 / 8 / 5 / 2` から open meld 数を推定する。
- `calculate_shanten_from_tiles_136()` / `calculate_shanten_from_counts_34()` は通常形、七対子、国士無双のシャンテンを返す。
- `find_tenpai_wait_tiles_34_from_tiles_136()` / `find_tenpai_wait_tiles_34_from_counts_34()` は、現手牌がテンパイのときだけ 0..33 の待ち牌集合を返す。
- `detect_ryanmen_fixed_discard()` は打牌前 snapshot と打牌牌から、両面固定かどうかを返す。

## 5. discard_fact 分析列仕様
- `DISCARD_ANALYSIS_COLUMNS` は `shanten_after_discard` 系、`wait_tiles_after_discard_mspz`, `ryanmen_fixed_flag` を含む。
- `_discard_analysis_columns()` は打牌前 concealed hand snapshot を decode し、open meld 数を推定して `shanten_after_discard` 系と `ryanmen_fixed_flag` を計算する。
- `_post_discard_hand_tiles_136()` は snapshot から実際の打牌牌を 1 枚取り除いた post-discard hand を復元する。
- exact `tile_136` が snapshot に無い場合は同一 `tile_34` の別 copy で fallback し、それも無理なら待ち列は空欄とする。
- `_tile34_indices_to_mspz_text()` は待ち牌集合を `mspz` grouped text へ変換する。
- `wait_tiles_after_discard_mspz` は post-discard hand がテンパイなら保存し、非テンパイまたは復元不能なら空欄とする。
- `csv_db_schema.DISCARD_FACT_COLUMNS` は `wait_tiles_after_discard_mspz` を schema に含める。

## 6. GUI / renderer 連携仕様
- `create_canvas()` は `board_canvas.layout_tuning_settings` を初期化し、`LAYOUT` ボタンと `Ctrl+Shift+L` shortcut を登録する。
- `open_layout_tuning_window()` は `LAYOUT_TUNING_WINDOW_COLUMN_COUNT` に従って controls を 2 列へ分割する。
- 各 control row は `label + slider + current value` で構成する。
- action row は `Save`, `Reset`, `Close`, status text を下段へ固定する。
- slider 変更は `handle_layout_tuning_change()` を通して current session の tuning 値へ反映し、直ちに `redraw()` を呼ぶ。
- `Save` は JSON 永続化、`Reset` は dataclass 既定値への復帰、`Close` は window の破棄のみを行う。

## 7. 互換性
- `shanten_after_discard` 系の column 名は legacy を維持する。
- 旧 CSV を読むときは optional missing column と schema migration で吸収する。
- `TableLayout.region_rects` への新規 region id 追加は本件の必須要件ではない。

## 8. 非対象
- `capture.fragment_parser.py`, `logic.danger_suji.py`, `app.hand_recommendation_service.py` のアルゴリズム契約は本版の主対象ではない。
- 待ち牌列挙は打牌候補の探索 UI ではなく、DB 保存用の補助分析列として扱う。
