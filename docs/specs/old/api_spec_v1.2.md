# Tenhou Hojo Helper 仕様書 v1.2

## 1. 概要
- パケット解析、SQLite 記録、`SutehaiTracker` に対応した版の仕様を記述する。

## 2. コンポーネント
| コンポーネント | 役割 | 備考 |
|----------------|------|------|
| `tenhou_hojo` | GUI エントリポイント | `main()` |
| `LoadImage` | 牌画像の読み込みと描画 | `initialize_image`, 各描画ヘルパー |
| `sutehai` | `Player`、`DrawType`、`Discard`、`SutehaiTracker` を提供 | 共通データモデル |
| `test.py` | `tshark` の実行、タグ解析、SQLite 記録 | `run_and_capture()` |

## 3. データモデル
- `Player`: `T/U/V/W` を座席へ変換する列挙型
- `DrawType`: 手出しとツモ切りの列挙型
- `Discard`: 牌 ID、ドロー種別、タグ、時刻などを持つ
- `SutehaiTracker`: 座席ごとの打牌履歴を管理する
- `img_table[Player][DrawType][tile_id] -> PhotoImage`
- `tag_log`、`play_event` の 2 つの SQLite テーブルを持つ

## 4. キャプチャフロー
1. `tshark` を起動する
2. タグを含む行を抽出する
3. タイムスタンプとタグを解析する
4. 座席と牌 ID を求める
5. `SutehaiTracker.add_discard` を呼ぶ
6. デルタ時間を計算して DB に保存する

## 5. 描画フロー
1. 37 種の牌画像を読み込む
2. 手出し・ツモ切り差分と座席回転画像を生成する
3. 4 座席分の捨て牌を描画する
4. `mainloop()` で GUI を維持する
