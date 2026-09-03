# データ構造

updated: `2026-09-03`

この文書は、現行 runtime data structure の正本です。

## 1. Capture / Round

### `CaptureState`

owner: `src/capture/state.py`

主な役割:

- 現在卓の live state
- diagnostics
- live hand / meld / dora snapshot
- CSV DB 連携用の土台

主な fields:

- `current_round`
- `round_id`
- `live_hand_tiles_136`
- `live_meld_tiles_136`
- `live_dora_indicator_tiles_136`
- `diagnostics`

### `RoundState`

主な fields:

- `round_id`
- `kyoku_index`
- `honba`
- `kyotaku`
- `oya_rel`
- `dora_indicators_136`
- `discards`
- `melds`
- `events`
- `result`

### `Discard`

主な fields:

- `tile_136`
- `tile_id`
- `draw_type`
- `called`
- `lagged`
- `lag_delay_ms`
- `thinking_time_ms`
- `thinking_time_before_reach_ms`
- `round_discard_index`
- `event_index`

### `Meld`

主な fields:

- `meld_type`
- `tiles_37`
- `from_player`
- `called_index`
- `is_open`

## 2. Visible Count

### `VisibleTileSummary`

owner: `src/visible_tiles.py`

意味:

- actual visible only

主な fields:

- `visible_counts_34_index`
- `three_visible_tiles`
- `four_visible_tiles`
- `four_visible_tile34_index_set`
- `blocked_sequence_tile34_index_set`

### `VisibleTileInferenceSummary`

owner: `src/visible_tiles.py`

意味:

- actual visible を読み取り専用で参照した推測加算 layer

主な fields:

- `inferred_counts_34_index`
- `adjusted_visible_counts_34_index`
- `inferred_three_visible_tiles`
- `inferred_four_visible_tiles`

### `SujiLineRow` / `SujiLineTable`

owner: `src/logic/danger_suji.py`

意味:

- `SujiLineRow` は萬子・筒子・索子それぞれ 6 本の筋線を固定した 18 行のうち 1 行で、suppressor 適用直後の `raw_count` と rule family 別の名前付き係数、`base_weight`、`concentrated_weight` を分離して保持する
- `SujiLineTable` は 18 行に加え、生の 0/1 集計 `raw_denominator_count` / `raw_tile_numerator_counts_34`、補正後の `base_denominator_count` / `base_tile_numerator_counts_34`、濃度補正後の `concentrated_denominator_count` / `concentrated_tile_numerator_counts_34` を保持する。3 つの numerator 配列は必ず 34 要素とする
- いずれも `frozen=True` の build-local derived state であり、公開 profile や `RoundState` へ格納しない。濃度補正の immutable projection だけは `line_weights + visible_counts_34` の完全値keyで上限付きmemo化する。row単位のmutationやevent invalidationは持たない

`OpponentSujiDangerProfile` は従来の7 dataclass field、positional constructor、`fields()` / `vars()` / `asdict()` / `astuple()` / pickle形状、`line_weights` の直列化順、DB / UI payloadを変更しない。

## 3. Inferred Visible Popup

### `InferredVisibleEntry`

owner: `src/ui/table_renderer.py`

意味:

- self hand 左の popup に出る推測 entry

主な fields:

- `entry_key`
- `tile_37`
- `tile_34_index`
- `reason`
- `candidate_seats`
- `active_candidate_seats`
- `inactive_candidate_seats`

## 4. Nodocchi Player Status

### `NodocchiPlayerStats`

owner: `src/app/nodocchi_stats.py`

意味:

- Nodocchi 鳳凰卓4人打ち成績を renderer がそのまま描画できる形へ整形した payload

主な fields:

- `playerName`
- `mode`
- `table`
- `sourceUrl`
- `fetchedAt`
- `categories`
- `summary`

### `NodocchiStatsCategory`

意味:

- `概要`, `順位`, `アガリ`, `リーチ`, `放銃`, `副露 / 仕掛け`, `役`, `ドラ`, `その他` などの表示グループ

主な fields:

- `title`
- `metrics`

### `NodocchiMetric`

意味:

- 1 つの表示指標

主な fields:

- `label`
- `value`
- `percentile`
- `rank`
- `raw`
- `revealed_candidate_seats`
- `seat_adjustments_34_index`
- `total_adjustment`

### Canvas-local selection state

owner: `src/ui/table_renderer.py`

主な state:

- `selected_inferred_visible_tile_37`
- `inferred_visible_candidate_button_specs`
- `selected_inferred_visible_delete_button_specs`
- `inferred_visible_tile_panel_button`

意味:

- 捨て牌 click か 37牌 selector で選んだ tile を header card として保持する
- 赤5の表示は 37種で持ちつつ、count は 34種へ寄せる

## 4. pystyle

### `HandRecommendationEntry`

owner: `src/app/hand_recommendation_service.py`

主な fields:

- `rank`
- `tile_37`
- `tile_text`
- `expected_value`
- `expected_value_text`
- `win_probability`
- `tenpai_probability`

### `HandRecommendationSnapshot`

service 側の thread-safe snapshot

主な fields:

- `items`
- `subtitle_text`
- `status_text`
- `is_loading`
- `hand_key`
- `shanten`
- `turn_index`
- `request_context_key`
- `round_token`

### `HandRecommendationPanelData`

renderer 側の `AI TOP3` popup 用 payload

主な fields:

- `items`
- `hand_key`
- `shanten`
- `round_token`
- `request_context_key`
- `top_expected_value`
- `subtitle_text`
- `status_text`
- `is_loading`

## 5. Snapshot / Panel

### `LiveTableSnapshot`

owner: `src/app/main.py`

意味:

- UI redraw 1 回ぶんの表示 snapshot
- 現在局面の構造 payload と、同一局で最後に完了した heavy suji / 危険度 bundle を持てる。新入力の計算中は後者が表示専用の stale fallback になり得る

主な payload:

- hand / meld / discards
- visible summary
- inferred visible summary
- player panel alert inputs
- hand recommendation panel
- round events
- bridge status inputs
- `suji_analysis_is_current`: snapshot に載せた heavy bundle が現在 input の完了値なら `True`。同一局の表示 fallback、fast snapshot、初回 loading は `False` とし、自動打牌 / alert 音声の新規判定 gate に使う

### `DetailPanelState`

owner: `src/ui/table_renderer.py`

意味:

- 共有 detail area の表示切替状態

### `HandAutoModeState`

owner: `src/ui/table_renderer.py`

主な fields:

- `enabled`
- `mode`
- `in_flight`
- `last_attempt_key`
- `last_error`

## 6. Bridge

### `TenhouUiBridgeStatus`

owner: `src/app/tenhou_ui_bridge_protocol.py`

主な fields:

- `ws_url`
- `visible_controls`
- `toggle_controls`
- `status_text`

### `TenhouUiBridgeControl`

- `control_id`
- `visible`
- `text`
- `label`

### `TenhouUiBridgeToggleControl`

- `control_id`
- `available`
- `active`
- `text`
- `label`

## 7. Worker State

main owner: `src/app/main.py` and `src/ui/table_renderer.py`

主な state:

- `LiveSujiAsyncState`
- `LiveRedTintAsyncState`
- canvas-local `inferred_visible_async_*`
- `bridge_snapshot_in_flight`
- `bridge_snapshot_pending_force`
- thread notice active-count map

`LiveSujiAsyncState.completed_bundle` は同一局で最後に完了した `hand_tiles` と panel / hand danger / Push payload 一式を保持する。pending / in-flight job があっても表示用 completed bundle を空にせず、手牌 danger は保存した `hand_tiles` から現在手牌へ牌 ID と同牌内の出現順で再対応付けし、次 bundle 完了時に一式で置き換える。stale bundle は自動打牌や alert 音声の新規判定には使わず、新局では破棄する。

## 8. Rules

- actual visible と inferred visible は別物
- heavy suji / 危険度の計算中表示と、現在入力に対する判定結果は別物。前者の stale fallback は表示専用とする
- popup manual count は inferred 側だけを増やす
- `LiveTableSnapshot` は DB row ではない
- `HandRecommendationSnapshot` は service 側
- `HandRecommendationPanelData` は renderer 側
