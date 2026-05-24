# API / 管理仕様 v2.2

更新日: `2026-05-24`

## 1. Runtime snapshot

### `LiveTableSnapshot`

UI 1 回の描画で使う局面 snapshot。DB row ではなく、capture state から renderer へ渡す表示用構造である。

主な内容:

- 手牌、捨て牌、副露、ドラ表示牌
- `VisibleTileSummary`
- `VisibleTileInferenceSummary`
- 他家プレイヤーパネル用 summary / alert payload
- `push_marker_alert_percentages`
- `same_jun_marker_indices_by_seat`
- `table_situation_auto_scores_by_seat`
- `NagaAutoPanelData`

## 2. Alert payload

### `PlayerAlertIndicator`

他家 panel の `ALERT` に出す 1 行。音声判定もこの構造を正本にする。

主な属性:

- `color`: `yellow`, `red`, `purple`, `green` などの意味色
- `label`: UI 表示ラベル
- `key`: 音声重複防止と優先度判定に使う安定キー

音声仕様:

- panel に出ない alert は鳴らさない。
- 自分側の remain / push は鳴らさない。
- `Remain` は `r-red` のような音声 key を生成する。
- `Push` は局後半の対象打牌にだけ鳴らす。

### Push payload

`Push` は seat ごとの payload として renderer へ渡す。

- `seat`
- `tile`
- `discard_index`
- `percentage`
- `threshold_percent`
- `kind`

panel の `Push` と河の `P` は同じ discard index を参照する。

## 3. 河描画 cache

### Canvas cache

`src/ui/table_renderer.py` は Canvas に次を保持する。

- `discard_render_cache_by_key`: `(seat, local_index) -> render_signature`
- `last_discard_render_stats`: `active`, `drawn`, `skipped`, `changed`, `stale_deleted`
- `discard_base_tile_image_cache`: discard scale が変わる場合の通常牌画像 cache

### 表示シグネチャ

表示シグネチャには、少なくとも次を含める。

- 座席、捨て牌 local index、tile id、draw type
- 位置、anchor、画像サイズ、bounds
- called / lag / riichi / thinking time
- tint kind、thinking time band step
- marker 有無、lag marker kind、Push marker 有無
- border kind

シグネチャが一致する牌は再描画しない。ただし click spec と lag marker reference spec は毎回復元する。

### Canvas tags

discard item は作成時に次の tag を持つ。

- `live_async_discards`
- `live_async_discards_<seat>_<local_index>`

差し替え時は個別 tag を `delete()` し、full redraw 時だけ `live_async_discards` 全体を削除する。

## 4. 牌画像と overlay

`_discard_tile_image()` は通常牌画像だけを返す。色付き `PhotoImage` の合成は discard path では行わない。

Canvas overlay:

- red: remain / push 系の危険寄り tint
- brown: 4見えで物理否定された 3連形に属する手出し牌
- four_visible: 牌自身が 4見え
- thinking time band: post-reach / pre-reach の思考時間帯

overlay は seat 回転後の画像 bounds へ矩形として重ねる。

## 5. NAGA 段位ポイント分析

### `NagaAutoPanelData`

renderer へ渡す下部自動表示用 DTO。

- `visible`
- `title_text`
- `lines`
- `status_kind`: `waiting`, `loading`, `ready`, `error`

南2局以降、`src/app/main.py` が `naga-ptev-analyzer` の結果から次を抽出する。

- 現状 ptEV
- 主要な和了候補
- 主要な放銃候補
- 流局候補の best / worst

## 6. Nodocchi STATUS

`src/app/nodocchi_stats.py` が Nodocchi API の取得と整形を担当し、renderer は detail view として表示する。

表示色:

- 和了率: 赤字
- 副露率: 赤字
- リーチ率: 赤字
- その他: 白字

取得は background thread で行い、同一プレイヤーの連打は cache / in-flight set で抑止する。

## 7. DB分析

### `scripts/analyze_player_shanten_thinking.py`

入力:

- `csv_db/discard_fact_*.csv`
- `csv_db/hanchan_master.csv`

主な出力:

- `player_shanten_thinking_summary.csv`
- `player_shanten_thinking_report.html`
- プレイヤー別 scatter / median line の PNG

所属卓:

- `hanchan_master` の `seat0..3_player_name` と `room_class_label` を melt して集計する。
- 同一 `hanchan_id` はプレイヤーごとに重複除去する。
- `hanchan_master` に該当がない場合だけ discard row 側の `room_class_label` を fallback 表示する。

## 8. CSV DB

現行保存の卓種正本は `room_class_label`。legacy の `go_type`, `go_type_hex`, `room_class_code` は読み取り補完対象であり、新規分析では `room_class_label` を優先する。

## 9. 同期対象

この仕様を変えたら、最低限次を同時に更新する。

- [../requirements/current.md](../requirements/current.md)
- [../screen_specs/current.md](../screen_specs/current.md)
- [../screen_specs/river_display.md](../screen_specs/river_display.md)
- [../screen_specs/alerts_and_panels.md](../screen_specs/alerts_and_panels.md)
- [../analysis/performance_hotspots.md](../analysis/performance_hotspots.md)
- [../analysis/player_shanten_thinking.md](../analysis/player_shanten_thinking.md)
- [../changelog.md](../changelog.md)
