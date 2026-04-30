# Tenhou Hojo Helper 仕様書 v1.0

## 1. 概要
- 事前に用意した捨て牌データを用いて卓表示を行う初期版仕様。
- GUI は `tkinter`、画像加工は `Pillow` を用いる。

## 2. モジュール
| モジュール | 役割 | 主な関数 |
|-----------|------|---------|
| `tenhou_hojo.py` | アプリ起動とウィンドウ生成 | `main()` |
| `LoadImage.py` | 牌画像の読み込み、回転、描画 | `initialize_image`, `create_canvas` |
| `TenhouCapture.py` | 将来的に捨て牌データを供給 | `capture()` 予定 |

## 3. データ構造
- `initialize_image` は牌画像テーブルを返す。
- `sutehaiLL` は打牌順をキーに `(tile_id, draw_type)` を保持する。

## 4. 処理フロー
1. `main()` でウィンドウを生成する。
2. `LoadImage.initialize_image` で牌画像を準備する。
3. 捨て牌データを取得する。
4. `create_canvas` で 4 座席分を描画する。
5. `mainloop()` で GUI を維持する。

## 5. レイアウト
- ウィンドウサイズは 670x640。
- 座席位置は下・右・上・左の卓配置に合わせる。
- 捨て牌は 6 枚ごとに折り返す。
