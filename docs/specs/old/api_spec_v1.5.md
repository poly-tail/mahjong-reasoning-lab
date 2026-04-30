# Tenhou Hojo Helper API / 実装仕様 v1.5

## 1. 文書位置づけ

- 本版は `api_spec_v1.4.md` を継承し、2026-04-03 時点の UI 連携・危険度計算・DB 分析前提の更新点を追加する。
- 既存の capture / parser / DB writer の基本仕様は `v1.4` を継承する。

## 2. 追加・更新対象モジュール

- `src/app/main.py`
- `src/app/hand_recommendation_service.py`
- `src/app/pystyle_simulator_protocol.py`
- `src/ui/table_renderer.py`
- `src/visible_tiles.py`
- `src/logic/danger_suji.py`
- `src/logic/hand_analysis.py`
- `src/capture/storage.py`

## 3. 可視枚数から危険度までのパイプライン

### 3.1 可視枚数集計

- `visible_tiles.collect_visible_tile_summary()` は UI 37 種入力から次を返す。
- `three_visible_tiles`
- `four_visible_tiles`
- `visible_counts_34_index`
- `self_hand_counts_34_index`
- 集計対象は `called=False の河`、`自手牌`、`副露牌`、`ドラ表示牌` である。
- `called=True` の河牌は副露側で既に可視化済みのため、河側では二重計上しない。

### 3.2 live 連携

- `app.main.build_live_visible_tile_summary()` は live state から上記 summary を構築する。
- `build_live_hand_danger_metrics()` と `build_live_opponent_suji_panel_summaries()` は同じ summary を共有し、手牌下 danger bar とプレイヤーパネル summary を同じ可視枚数前提で計算する。

### 3.3 筋危険度

- `logic.danger_suji.build_all_opponent_suji_danger_profiles()` は opponent ごとの 34 種危険度 profile を返す。
- line weight の計算順は次で固定する。
- `0本化 / 一時安全処理`
- `matagi 重み付け`
- `chi / 内牌->外牌 / lag の cap・係数`
- `愚形加算`
- `build_hand_tile_suji_danger_metrics()` は手牌 1 枚ごとに seat 別 `TileDangerMetric` を返す。
- `percentage` は描画用の最終危険度、`base_percentage` は筋本数ベース、`ugly_wait_percentage` は愚形加算分とする。

## 4. 愚形加算仕様

- `danger_suji._build_ugly_wait_add_percentages()` は 34 種ごとに総合危険度への加算率を返す。
- 基本パターンは `kanchan`, `shanpon`, `penchan(3/7のみ)` の最大3種類。
- 基本加算は各 `2.0`。
- スペース事情により薄化する場合は `kanchan=0.6`, `shanpon=1.0` とする。
- `4見え` は該当愚形パターンを `0.0` にする。
- `shanpon` は `2見え -> 1.0`, `3見え以上 -> 0.0` とする。
- 自手偏在による濃度補正は `visible=3 and self>=2` または `visible=4 and self>=3` のとき `+1.0` とする。

## 5. AI TOP3 連携

### 5.1 責務分離

- `pystyle_simulator_protocol.py` は request / response の定義、検証、牌変換を持つ。
- `hand_recommendation_service.py` は POST のバックグラウンド取得と不変 snapshot 管理を持つ。
- 巡目インデックスは payload に含めず、`70 - 打牌総数 + チー/ポン回数 - 未打牌ターン数 - カン回数` で求めた山残枚数から `ceil(18 - 山枚数 / 4)` で算出する。
- `table_renderer.py` はボタン状態とパネル描画のみを持つ。

### 5.2 UI 連携仕様

- `HandResponsePanelState.visible` が `False` の間は新規 POST を発行しない。
- `visible=True` の間に手牌 key が変わった場合のみ `hand_recommendation_request_action()` を再実行する。
- POST 成功時は上位3件を `HandRecommendationPanelData` に変換し、`tile_37` と `expected_value_text` を描画側へ渡す。

### 5.3 表示データ

- `HandRecommendationItem` は `rank`, `tile_text`, `tile_37`, `expected_value_text` を持つ。
- 描画は `tile_37` がある場合、縮小牌画像を優先して表示する。

## 6. 打牌前手牌 snapshot と分析

- `capture.state.Discard` は打牌前の concealed hand snapshot を保持する。
- `capture.storage` は `discard_fact` 書き込み時にこの snapshot を `seat*_hand_tiles_136_json` と `seat*_hand_tiles_37_text` へ反映する。
- `logic.hand_analysis` のシャンテン計算と両面固定判定は、上記 snapshot を入力として実行する。
- 互換上、`shanten_after_discard` 系列の列名は維持するが、意味は「打牌前 snapshot に対する値」とする。

## 7. DB 仕様更新

### 7.1 `hanchan_master`

- `source_url` を持つ。
- XML 単発入力と URL リスト入力の両方で、半荘照合が成立した URL を保存する。

### 7.2 `discard_fact`

- `discard_tile_37_text` を持つ。
- `seat0_hand_tiles_136_json` から `seat3_hand_tiles_136_json` の右側に、`seat0_hand_tiles_37_text` から `seat3_hand_tiles_37_text` を並べる。
- 37 種 text 列は CSV セル内で plain text とし、JSON 記法や余計な括弧を持たない。

### 7.3 分析除外

- DB 分析時の共通外れ値除外は `docs/analysis/db_analysis_rules.md` に従う。
- 実装内で固定値を持つ場合も、文書記載値と一致させる。

## 8. 文書運用仕様

- `requirements/current.md`, `specs/current.md`, `screen_specs/current.md` は常に最新 versioned file へ向ける。
- `project_guide.md`, `source_overview.md`, `folder_structure.md`, `src_call_graph.md`, `changelog.md` は、機能追加と同じタイミングで更新する。
- ロジック文書は `docs/mahjong/`、外部連携文書は `docs/integrations/`、分析基準文書は `docs/analysis/`、トラブルシュートは `docs/operations/troubleshooting/` に整理する。
