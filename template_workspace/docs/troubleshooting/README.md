# troubleshooting docs

運用障害、既知不具合、再起動手順、復旧手順などを置く。

## 置くもの
- recurring な障害メモ
- 環境依存のセットアップ注意
- 暫定回避と恒久対応の判断

## 書き方
- 1 事象 1 ファイルを基本にする
- `docs/templates/troubleshooting_note_template.md` を起点にする
- 関連する versioned docs や `docs/changelog.md` へのリンクを残す

## 分け方
- 再利用できる運用知識はここへ置く
- 一回限りの調査ログや raw output は `logs/` や `analysis_output/` に分ける
