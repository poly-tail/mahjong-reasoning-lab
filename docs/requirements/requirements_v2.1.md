# 要件定義 v2.1

updated: `2026-05-10`

## 1. コア要件

- live capture / replay / XML import の 3 経路を同じ renderer へ流せること
- Tenhou UI Bridge を使ったブラウザ操作連携を維持すること
- 画面更新を止めやすい処理は常駐 worker または background 実行へ逃がすこと

## 2. 見え枚数

- actual visible は `手牌 + 捨て牌 + 晒し牌 + ドラ表示牌` のみで数える
- actual visible は lag 推測や awaseuchi 推測の影響を受けない
- inferred visible は renderer 側の常駐 worker 1 本で処理する
- inferred visible は actual visible を書き換えない
- UI 上の合算表示は `4見え` を上限とする

## 3. 画面表示

- `AI TOP3` は `pt + 和了率` を表示する
- `AI TOP3` 直下に `総計` 状況表を置く
- `上家 / 対面 / 下家` の状況表は各相手の河と副露の間へ置く
- 自家の `2見え以下字牌` 一覧は、自河の中央固定ではなく自副露帯寄りに少し下げて表示する
- 河の記号は `L`, `Pl`, `P` を使う
- tint 優先順位は `purple > brown > red` とする
- 相手パネルの `STATUS` は、対象プレイヤー名で Nodocchi の鳳凰卓4人打ち成績ビューを開けること
- `STATUS` 成績ビューは取得中、取得成功、取得失敗、データなしの各状態を表示し、常に `Nodocchiで開く` 外部リンクを残すこと

## 4. 外部成績取得

- Nodocchi 成績取得は UI スレッドをブロックしないこと
- 取得・パース・表示整形は renderer から分離した adapter/service に置くこと
- 外部 HTML は直接描画せず、JSON 取得結果を自前 UI に描画すること
- 同一プレイヤー名への取得結果は短時間 cache し、連打で多重リクエストを発生させないこと
- Nodocchi 側の仕様変更や通信失敗時もアプリ全体をクラッシュさせないこと

## 5. 状況表

- `上家 / 対面 / 下家 / 総計` の 4 面を表示する
- 各相手面は `M123, M456, M789, P123, P456, P789, S123, S456, S789, 字` の 10 block を持つ
- manual input の範囲は `-4 .. +4`
- 左 click は `+1`、右 click は `-1`
- `総計` は 3 面平均の read-only 表示とする
- `Σ` は 10 block 合計、`Σ/n` は `0.0` の数牌セル数で割った値とする

## 6. 自動化

- `pystyle ON` 中は `自動和了 ON` / `鳴き無し ON` / `リーチ優先` を守る
- 推奨応答が未到着または失敗時は turn-start 基準の fallback を使う
- Bridge snapshot は `1 in-flight + pending 1` の制御を守る

## 7. ドキュメント同期

変更時は最低でも次を同期する。

- `docs/specs/api_spec_v2.1.md`
- `docs/screen_specs/display_overview.md`
- `docs/screen_specs/river_display.md`
- `docs/screen_specs/alerts_and_panels.md`
- `docs/screen_specs/controls_and_bridge.md`
- `docs/screen_specs/visible_counts_ui.md`
- `docs/architecture/project_guide.md`
- `docs/architecture/src_call_graph.md`
- `docs/architecture/source_overview.md`
- `docs/architecture/folder_structure.md`
- `docs/integrations/nodocchi_status.md`
- `docs/changelog.md`

## 8. ドキュメント配置

- 麻雀ドメイン文書の入口は `docs/mahjong/README.md` とする
- 牌効率・手組み理論は `docs/mahjong/theory/` に置く
- 実装に接続する麻雀ロジックは `docs/mahjong/logic/` に置く
- ルールや用語は `docs/mahjong/reference/` に置く
- 研究メモや未昇格の仮説は `docs/mahjong/research/` に置く

## 9. 配布・保存

- Python 依存は `requirements.txt` で再現できること
- ドキュメントグラフは `scripts/render_docs_graphs.py` で再生成できること
- 状態保存用 ZIP は `scripts/package_workspace.py` で再作成できること
