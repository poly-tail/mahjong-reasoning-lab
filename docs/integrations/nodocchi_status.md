# Nodocchi プレイヤー成績連携

updated: `2026-05-10`

この文書は、プレイヤーパネルの `STATUS` から Nodocchi の鳳凰卓4人打ち成績を表示する連携仕様をまとめる。

## 入口

- UI 操作: 相手パネルの `STATUS`
- UI 表示先: 右 shared detail 領域
- 実装入口: `src/ui/table_renderer.py`
- 取得・整形 adapter: `src/app/nodocchi_stats.py`

## URL

外部リンクとして開く検索 URL:

```text
https://nodocchi.moe/tenhoulog/#!&name=<URLエンコード済みプレイヤー名>
```

成績取得に使う JSON endpoint:

```text
https://nodocchi.moe/api/phoenix_status.php?all=1&username=<URLエンコード済みプレイヤー名>
```

`name` は公開ページの URL fragment にあるため、公開ページ HTML を fetch しても検索結果は取得できない。ツール内表示では JSON endpoint の `s4` を鳳凰卓4人打ちの集計として扱う。

## データ整形

`src/app/nodocchi_stats.py` は次を行う。

- プレイヤー名を URL encode する
- JSON endpoint から取得する
- `s4` がない、または `totalrecord <= 0` の場合は not found とする
- `order_top_Z`, `exacta_Z`, `order_last_Z` から 2位率と 3位率を補完する
- 主要指標を日本語ラベルへ変換する
- `概要`, `順位`, `アガリ`, `リーチ`, `放銃`, `副露 / 仕掛け`, `役`, `ドラ`, `その他` に分類する
- 同一プレイヤー名の結果を短時間 cache する

## UI 状態

- `loading`: `成績を取得中...`
- `success`: 取得日時、概要、カテゴリ別指標を表示
- `not_found`: `このプレイヤーの鳳凰卓4人打ち成績が見つかりませんでした`
- `error`: `Nodocchiの成績を取得できませんでした` と短い理由

どの状態でも `Nodocchiで開く` ボタンを残す。

## 実行制御

- 取得は background thread で行う
- 結果は canvas queue へ入れ、UI thread の poll で反映する
- 同一プレイヤー名が取得中なら追加リクエストしない
- side panel render cache の署名に status state を含め、非同期完了時に再描画されるようにする

## 失敗時の扱い

外部サイトの仕様変更、通信失敗、JSON 形式変更があってもアプリ全体は落とさない。UI には失敗理由を短く表示し、ユーザーが Nodocchi 側で直接確認できるよう外部リンクを残す。
