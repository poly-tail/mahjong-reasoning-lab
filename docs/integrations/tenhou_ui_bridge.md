# Tenhou UI Bridge 連携

更新日: `2026-04-15`

## 1. 役割

ローカルアプリからブラウザの天鳳タブへ、打牌 / call / toggle / snapshot を送る。

## 2. 構成

- アプリ側 server/client: `src/app/tenhou_ui_bridge_*`
- MV3 service worker: `extension/service-worker.js`
- content bridge: `extension/content-bridge.js`
- main world executor: `extension/main-ui-bridge.js`

## 3. 主なコマンド

- `ping`
- `ui_snapshot`
- `discard_by_index`
- `click_control`

## 4. 現在のスナップショット動作

- poll と action 後 follow-up snapshot を持つ
- action 直後の visible control 変化を拾うために follow-up を入れる
- snapshot 起動は coalescing し、`1 in-flight + pending 1` に抑える

## 5. 現在のブラウザ操作動作

- discard: `discard_by_index`
- chi / pon / kan / ron / tsumo / riichi / skip / toggle:
  - `click_control`
  - browser 側 visible control を優先して通す

## 6. 復旧

- tab receiver 未準備時は再注入で復旧を試みる
- stale page-side bridge を避けるため install flag / channel を version 化する

## 7. UI 連携

- app 側には visible call button 群を出す
- browser toggle 状態は snapshot で読んで `ON/OFF` 表示に反映する
- bridge action はバックグラウンド実行し、右上 `BG bridge ... xN` に active count を出す

## 8. 起動順

- 初回だけ `chrome://extensions` で unpacked extension を読み込む
- 通常運用では `ローカル app -> ブラウザで extension 有効確認 -> 天鳳ページを開く/リロード` を推奨する
- ブラウザ本体が先に起動していてもよいが、必須条件は `app 起動後` に天鳳ページを開くかリロードすること
- Chrome / 天鳳タブ再起動後も、まずは extension reload ではなく `天鳳タブをリロード -> SYNC` を優先する
- 起動直後の stdout/stderr と bridge status の確認手順は `docs/operations/live_startup_checklist.md` を正本とする
