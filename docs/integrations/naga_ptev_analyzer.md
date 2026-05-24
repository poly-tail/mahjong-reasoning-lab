# NAGA 段位ポイント分析連携

更新日: `2026-05-24`

## 目的

NAGA の段位ポイントアナライザをローカル GUI から照会し、局面の ptEV と主要分岐を表示する。v2.2 では南2局以降、最下部に自動要約も表示する。

## 構成

- app 側: `src/app/main.py`
- renderer 側 DTO: `NagaAutoPanelData`
- analyzer package: `naga-ptev-analyzer/`
- raw 出力: analyzer 側の `out/raw/`
- login state: `.secrets/` 配下。Git 管理しない。

## 手動表示

`NAGA段位` ボタンを押すと popup を開く。

popup section:

- 全体
- 3900直撃平均
- 満貫ツモ候補

graph metric:

- 段位 ptEV

## 自動表示

南2局以降に `NAGA_AUTO_REFRESH_MS` 間隔で query state を確認し、未取得の局面なら自動照会する。

下部表示:

- `現状 +x.xpt`
- `和了 ...`
- `放銃 ...`
- `流局 ...`

表示状態:

- `waiting`: 非表示または照会待ち
- `loading`: 照会中
- `ready`: 結果あり
- `error`: 照会失敗

## 失敗時

- ログイン state がない、または期限切れの場合は popup に再ログイン手順を出す。
- 自動表示側は短い error 文に丸めて下部へ表示する。
- NAGA query は background thread で行い、UI thread を止めない。

## 関連

- [../screen_specs/alerts_and_panels.md](../screen_specs/alerts_and_panels.md)
- [../screen_specs/current.md](../screen_specs/current.md)
- [../../naga-ptev-analyzer/README.md](../../naga-ptev-analyzer/README.md)
