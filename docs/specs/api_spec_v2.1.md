# API / 管理仕様 v2.1

更新日: `2026-04-21`

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

## 7. 再生成・保存

- Mermaid 図は `scripts/render_docs_graphs.py` で再生成する
- ワークスペース ZIP は `scripts/package_workspace.py` で作成する

## 8. 同期先

- 要件: [../requirements/requirements_v2.1.md](../requirements/requirements_v2.1.md)
- 画面仕様: [../screen_specs/screen_spec_v2.1.md](../screen_specs/screen_spec_v2.1.md)
- データ構造: [../architecture/data_structures.md](../architecture/data_structures.md)
