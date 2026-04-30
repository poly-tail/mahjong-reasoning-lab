# プロジェクトガイド

更新日: `2026-04-21`

## 目的

天鳳補助ツールは、live packet capture / replay / XML / Tenhou UI Bridge / AI 推奨を 1 つのデスクトップツールへ統合することを目的とします。

## 主な入口

- `src/tenhou_hojo.py`: 互換エントリ
- `src/app/main.py`: アプリ全体の起動・分岐・連携
- `src/ui/table_renderer.py`: 画面描画本体
- `src/visible_tiles.py`: 実見え枚数の集計
- `src/logic/danger_suji.py`: remain / push / tint のロジック

## 表示と責務

### 実見え枚数

- 担当: `src/visible_tiles.py`
- 入力: 手牌 / 捨て牌 / 晒し牌 / ドラ表示牌

### 推測見え枚数

- 担当: `src/ui/table_renderer.py`
- canvas ごとの常駐ワーカー 1 本で処理
- 実見え枚数は読み取り専用

### 合わせ打ち

- 担当: `src/ui/table_renderer.py`
- 公開イベントのみを使って provisional / confirm を分ける

## 今回の更新点

- 自家の `2見え以下字牌` 一覧を自副露帯寄りへ微調整した
- ドキュメントグラフ再生成を `scripts/render_docs_graphs.py` に統一した
- ワークスペース退避用 ZIP を `scripts/package_workspace.py` で作れるようにした

## 更新時の同期先

- 画面仕様: `docs/screen_specs/`
- 要件 / 仕様: `docs/requirements/`, `docs/specs/`
- グラフ: `docs/graphs/src/`, `docs/graphs/generated/`
- 更新履歴: `docs/changelog.md`
