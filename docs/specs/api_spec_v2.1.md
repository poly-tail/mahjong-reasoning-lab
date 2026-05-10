# API / 管理仕様 v2.1

更新日: `2026-05-10`

## 1. ランタイムスナップショット

### `LiveTableSnapshot`

- UI 再描画 1 回ぶんの一貫した表示データ
- DB 保存 row ではない
- REINIT 復元用の raw state でもない

主なペイロード:

- hand / discards / melds
- 実見え枚数サマリ
- 推測見え枚数サマリ
- プレイヤーパネル用アラート入力
- 手牌推奨パネル
- 局イベント
- Bridge 状態入力

## 2. 見え枚数構造

### `VisibleTileSummary`

- 実見え枚数のみを保持する
- 担当: `src/visible_tiles.py`

### `VisibleTileInferenceSummary`

- 実見え枚数を読み取り専用で参照する別レイヤ
- 担当: `src/ui/table_renderer.py`
- `adjusted_visible_counts_34_index` は `min(4.0, actual + inferred)`

## 3. 自家字牌ショートリスト

- 対象は `0見え / 1見え / 2見え` の字牌
- 公開枚数判定には `捨て牌 + 晒し牌 + ドラ表示牌` を使う
- 自家の一覧位置は自河の中央固定ではなく、自副露帯側へやや寄せる

## 4. 推奨パネル

`HandRecommendationPanelData.items[*]` は次を持つ。

- `rank`
- `tile_37`
- `tile_text`
- `expected_value`
- `expected_value_text`
- `win_probability`

UI popup は `expected_value_text + win_probability` を表示する。

## 5. Bridge スナップショット

- `ui_snapshot` は poll + follow-up snapshot を使う
- 実行制御は `1 in-flight + pending 1`
- `bridge snapshot` の `xN` は active count であり、起動回数ではない

## 6. ワーカールール

- `live suji`: 常駐ワーカー
- `live red tint`: 常駐ワーカー
- `inferred visible`: キャンバスごとの常駐ワーカー
- `awaseuchi confirm`: 暫定ヒット時だけキュー投入
- `pystyle fetch`: リクエストごとのバックグラウンド取得
- `Nodocchi status fetch`: `STATUS` 押下ごとのバックグラウンド取得。UI 反映は canvas queue 経由

## 7. Nodocchi プレイヤー成績

### Adapter

- owner: `src/app/nodocchi_stats.py`
- public search URL: `https://nodocchi.moe/tenhoulog/#!&name=<encoded player name>`
- JSON endpoint: `https://nodocchi.moe/api/phoenix_status.php?all=1&username=<encoded player name>`
- cache TTL: `NODOCCHI_STATS_CACHE_TTL_SECONDS`

### `NodocchiPlayerStats`

主な fields:

- `playerName`
- `mode`: `4man`
- `table`: `phoenix`
- `sourceUrl`
- `fetchedAt`
- `categories`
- `summary`

### 表示用分類

- `概要`
- `順位`
- `アガリ`
- `リーチ`
- `放銃`
- `副露 / 仕掛け`
- `役`
- `ドラ`
- `その他`

### エラー契約

- プレイヤー名が空なら UI に軽いエラーを出す
- Nodocchi に `s4` が無い、または `totalrecord <= 0` なら `not_found`
- HTTP、JSON、形式不一致は `error`
- いずれの場合も `sourceUrl` を残し、外部ページを開けるようにする

## 8. 再生成・保存

- Mermaid 図は `scripts/render_docs_graphs.py` で再生成する
- ワークスペース ZIP は `scripts/package_workspace.py` で作成する

## 9. 同期先

- 要件: [../requirements/requirements_v2.1.md](../requirements/requirements_v2.1.md)
- 画面仕様: [../screen_specs/screen_spec_v2.1.md](../screen_specs/screen_spec_v2.1.md)
- データ構造: [../architecture/data_structures.md](../architecture/data_structures.md)
- Nodocchi 連携: [../integrations/nodocchi_status.md](../integrations/nodocchi_status.md)
