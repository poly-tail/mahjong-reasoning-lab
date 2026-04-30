# 画面仕様書テンプレート

## 1. 文書の位置づけ
- 前版: `screen_spec_v***.md`
- current pointer: `docs/screen_specs/current.md`
- 今回の追加 / 変更対象: `*** SCREEN`, `*** PANEL`, `*** TUNING WINDOW`
- 共通 UI ルール: `docs/screen_specs/ui_principles.md`, `docs/screen_specs/screen_map.md`
- 旧版の扱い: 旧版ファイルは残し、`current.md` だけ最新 pointer へ差し替える

## 2. 画面要素
### 2.1 主要ボタン / 入口
- 表示位置: `main canvas top-left`, `toolbar right edge`, `detail footer`
- 見た目: `40x20 button`, `label = ***`, `active fill = #***`
- 役割: `*** window` を開く、`*** mode` を切り替える、`*** save` を実行する
- shortcut: `Ctrl+Shift+***`, `F***`, `Escape`

### 2.2 補助 window / panel
- 種別: `Toplevel window`, `floating panel`, `shared detail area`
- 役割: `*** controls`, `*** preview`, `*** memo editor`
- 再オープン時の挙動: `last session state を維持` / `default へ戻す`

## 3. 構成
- 説明文: `*** の設定を調整し、preview を見ながら保存できる`
- control area: `2 columns`, `label + slider + value`, `section header = ***`
- action row: `Save`, `Reset`, `Close`, `status text`
- status / helper text: `Saved to ***`, `Preview only`, `Legacy value migrated`

## 4. 操作対象
- control 群: `panel size`, `discard area`, `meld area`, `detail area`, `text scale`
- 表示対象: `*** panel`, `*** tiles`, `*** graph`, `*** placeholder`
- 非表示条件: `data unavailable`, `window too small`, `mode != ***`

## 5. 挙動
- 即時反映: `slider move`, `button click`, `drag end`
- session 維持: `window close` 後も current session では保持する
- 保存: `csv_db/***_tuning.json` または `player_profiles.csv` に保存する
- reset: `LayoutTuningDefaults` / `*** defaults` へ戻す
- close: 状態は保持しつつ window だけ閉じる

## 6. 影響範囲
- 変わるもの: `panel rect`, `tile scale`, `button state`, `status text`
- 変わらないもの: `core capture flow`, `DB schema`, `analysis pipeline`
- 非対象: `network request body`, `external API`, `legacy replay parser`

## 7. 文書管理メモ
- 版上げ時に更新する `current.md`: `docs/screen_specs/current.md`
- 旧版として残す画面仕様: `docs/screen_specs/screen_spec_v***.md`
- 併せて見直す共通 UI 文書: `ui_principles.md`, `screen_map.md`, `invariants.md`
- 変更履歴: `docs/changelog.md`
