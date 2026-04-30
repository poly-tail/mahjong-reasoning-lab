# 操作系と Bridge

updated: `2026-04-21`

この文書は app 側ボタン、browser bridge、右クリック shortcut の正本です。

## アプリ側ボタン

### 下段 toggle 群

- `pystyle`
- `ベタオリ`
- `自動理牌`
- `自動和了`
- `ツモ切り`
- `鳴き無し`

### 自家手牌上部の操作群

- `ロン`
- `ツモ`
- `ポン`
- `チー`
- `カン`
- `鳴き`
- その他 visible control

## 右クリック

- self hand 右クリックは `skip/pass` 系 control を優先する
- visible `skip/pass` が無ければ右端 slot を `ツモ切り` として扱う

## Bridge 状態取得制御

- poll と follow-up snapshot を coalescing する
- 実行制御は `1 in-flight + pending 1`
- visible control, toggle state, ready state の更新にも使う

## Bridge コマンド

- 打牌: `discard_by_index`
- ボタンクリック: `click_control`
- browser 状態取得: `ui_snapshot`
- 接続確認: `ping`
