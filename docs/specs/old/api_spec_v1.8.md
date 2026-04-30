# Tenhou Hojo Helper API / 実装仕様 v1.8

## 1. 本版の位置づけ
- `api_spec_v1.7.md` を継承し、2026-04-09 時点の `Layout Tuning` direct drag preview と `AI TOP3` history persistence を反映する。
- 主対象モジュールは `src/ui/table_renderer.py`, `src/app/main.py`, `src/capture/state.py`, `src/capture/storage.py` とする。

## 2. 対象ファイル
- `src/ui/table_renderer.py`
- `src/app/main.py`
- `src/capture/state.py`
- `src/capture/storage.py`
- `docs/requirements/requirements_v1.8.md`
- `docs/screen_specs/screen_spec_v1.8.md`

## 3. データモデル

### 3.1 `LayoutTuningSettings`
- `component_offsets: dict[str, tuple[int, int]]` を持つ。
- key は `player_*`, `discard_*`, `meld_*` の draggable component id とする。
- 値は pixel 単位の `(dx, dy)` translation とし、renderer 側で clamp / normalize する。

### 3.2 `LayoutDragState`
- active drag 中の `component_key`, `start_pointer`, `start_offset` を持つ mutable dataclass とする。
- `start_offset` は drag 開始時点で画面上に見えている resolved offset を使う。

### 3.3 `GameState.pystyle_self_history_by_round_hand`
- key は `(round_id, discard_index, normalized_hand_key)` とする。
- value は `pystyle_top1..3_*` 群にそのまま落とせる `dict[str, str]` とする。

## 4. Renderer 仕様
- `_build_layout()` は `drag_components` と `resolved_component_offsets` を返す。
- `_resolve_layout_component_rects()` は board 内 clamp と fixed blocker / sibling component の non-overlap を解決し、actual rect / offset を返す。
- `open_layout_tuning_window()` は window open 中に `canvas.layout_drag_enabled = True` を設定する。
- `_start_layout_component_drag()` は overlay hit 時のみ drag を開始し、開始点は current resolved offset を採用する。
- `_update_layout_component_drag()` は pointer 差分から desired offset を作り、resolved offset を preview と status text へ反映する。
- `_finish_layout_component_drag()` は active drag を終了し、その時点の preview を current session state に残す。
- `Save` は current `LayoutTuningSettings` snapshot をそのまま `csv_db/ui_layout_tuning.json` へ保存する。
- `resolved_component_offsets` は redraw / drag preview 用の runtime state として扱い、再描画で `component_offsets` を自動上書きしない。

## 5. `AI TOP3` 保存仕様
- `app.main.main()` は renderer に `hand_recommendation_history_action` を渡す。
- `_remember_visible_pystyle_history()` は visible panel から top3 を抽出し、`capture.storage.remember_pystyle_self_history()` を呼ぶ。
- `remember_pystyle_self_history()` は 14 枚手牌の自家 current hand だけを履歴対象とし、局 / 打牌順 / 手牌単位の cache へ積む。
- `_pystyle_history_columns_from_state()` は self discard row に対応する cached history を `discard_fact` 用列へ展開する。
- `_merge_preserved_discard_fact_fields()` は既存 row に非空 `pystyle_top*` 列がある場合、blank candidate で消さない。

## 6. 非対象
- `app.hand_recommendation_service.py` の POST / ranking algorithm 自体は本版の主対象外とする。
- `AI TOP3` の取得契機は自家 14 枚手牌表示時に限定し、open meld を含む詳細判定の拡張は本版では扱わない。
