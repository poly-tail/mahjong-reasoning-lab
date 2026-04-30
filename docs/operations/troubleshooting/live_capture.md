# ライブキャプチャのトラブルシュート

live capture が無反応なときの既知原因と確認手順を残す。

通常起動順と開始時確認は [../live_startup_checklist.md](../live_startup_checklist.md) を先に見る。この文書は、そこから外れたときの復旧・切り分けを扱う。

## 用語
- `INIT系`
  - live capture で局面の初期化や再同期に使う初期化系 packet 群を指す
  - 現在この文書では `INIT` / `REINIT` / `INITBYLOG` / `WGC` をまとめて `INIT系` と呼ぶ
  - `INIT` は新局開始の初期化
  - `REINIT` は途中状態の再同期
  - `INITBYLOG` / `WGC` は観戦系 bootstrap / snapshot packet

## 基本方針
- 基本はアプリ reload ではなく、ブラウザ reload によって `INIT系` をもう一度受け取って局面を再同期する
- つまり、通常の初期化解消は「アプリ再起動」より「ブラウザ側で `INIT系` を再発行させる」方が本筋
- ただし browser 側の TLS session と keylog が噛み合っていない場合は、tab reload だけでは足りず browser process の完全再起動が必要になる

## 推奨起動順
- 推奨は `先にアプリを起動し、その後でブラウザで extension が有効なことを確認して天鳳ページを開く/リロードする` 順序とする。
- ブラウザ本体が app より先に起動していても構わない。必須条件は `app 起動後` に天鳳ページを開くかリロードすること。
- 理由は、アプリ起動後の `tshark` / `tls.keylog_file` 設定が有効な状態で browser 側の新しい TLS handshake と websocket 接続を張らせた方が、復号できない既存 session を掴みにくいため。
- すでにブラウザを先に起動していて live capture が無反応な場合は、tab reload だけで直らなければ browser process の完全終了後に、`アプリ起動 -> ブラウザ起動` の順でやり直す。

## TLS 鍵ログの前提
- アプリは browser の TLS 鍵を生成しない。`tshark` に `tls.keylog_file:...` を渡して、そのパスの内容で復号を試みるだけ
- 重要なのは「鍵ファイルが存在すること」ではなく、「今見たい websocket 接続に対応する secret 行がそのファイルに入っていること」
- すでに `C:\tmp\tls.keys` が存在していても、それが過去の別接続の鍵だけなら今の live packet は復号できない
- `tshark` 側は既存ファイルも読むが、browser 側がその接続の鍵をそもそも書いていなければ意味がない
- browser process が `SSLKEYLOGFILE` を見ていない状態で先に起動していた場合、その process 上の既存 TLS session / websocket は後からアプリを起動しても自動では救えない
- その場合は browser reload で新しい handshake を発生させるか、必要なら browser process を完全終了してから起動し直す
- 今回の live 可視化用フラグでは、配牌や自分のツモ牌のような private 情報は `見え枚数増加` に含めない。公開情報として増えた discard / 副露晒し / ドラ表だけが対象

## 2026-04-03 事例
- 症状
  - `py src/tenhou_hojo.py` で GUI は起動するが、牌姿や河が更新されない
  - エラーは出ない
  - `REINIT` が来ているはずなのに表示されない
- 実原因
  - `tshark` command 自体の修正後も、ブラウザが既存 TLS session を握ったままだと新しい keylog と対応せず、WebSocket payload を復号できなかった
  - そのため browser reload で `INIT系` を出していても、そもそも packet を読めず無反応に見えた
- 解決
  - ブラウザ process を完全終了する
  - ブラウザを再起動する
  - その後に天鳳ページを開き直す
  - 新しい TLS handshake が発生して `tls.keys` と一致し、`tshark` が復号できるようになる

## 現在の live tshark コマンド
PowerShell:

```powershell
& "C:\Program Files\Wireshark\tshark" -l -i 5 -o tls.keylog_file:C:\tmp\tls.keys -f "tcp port 443" -Y websocket -T fields -E separator=/t -e frame.time_epoch -e websocket.payload.text -e text
```

`cmd.exe`:

```cmd
"C:\Program Files\Wireshark\tshark" -l -i 5 -o tls.keylog_file:C:\tmp\tls.keys -f "tcp port 443" -Y websocket -T fields -E separator=/t -e frame.time_epoch -e websocket.payload.text -e text
```

## 切り分け手順
1. まず browser reload で `INIT系` を再発行させる
2. `py src/tenhou_hojo.py --debug-tags` で起動する
3. [logs/live_capture.log](../../../logs/live_capture.log) に `capture_start_requested` と `tshark_command_ready` が出るか確認する
4. `C:\tmp\tls.keys` を tail して、browser reload 時に新しい secret 行が追記されるか確認する
5. 上の `tshark` command を単独実行して、timestamp 付き packet 行が流れるか確認する
6. 単独 `tshark` でも何も流れない、または keylog に新規追記が無い場合は、ブラウザを完全終了して再起動する
7. 再起動後に天鳳ページを開き直し、`INIT系` や `D/E/F/G` などの packet が見えるか確認する

## 観測ポイント
- 起動直後の stdout/stderr に `TShark runtime message: Capturing on 'Wi-Fi'` または実通信 adapter 名が出ていない
  - 開始時点で capture interface が怪しい
  - `loopback` / `ETW` が出ていたら、まず interface 選択を疑う
- `logs/live_capture.log` に `snapshot_event` が無い
  - parser の前で止まっている
  - `tshark` が packet を取れていないか、復号できていない可能性が高い
- `src/logs/live_capture.log` に `Capturing on 'Adapter for loopback traffic capture'` または `Event Tracing for Windows (ETW) reader` が出る
  - capture interface が天鳳通信の adapter ではない
  - `tshark -D` で Wi-Fi / Ethernet の index を確認し、`py src/tenhou_hojo.py --tshark-interface 2` のように明示指定する
- `tshark` 単独実行で packet 行が無い
  - アプリ側ではなく capture / decryption 側の問題
- `--debug-tags` で `[debug-tag]` が出ない
  - `parse_fragment()` 以前に止まっている
- `--debug-tags` で `[debug-tag]` は出るが表示されない
  - parser / live state / redraw 側を調べる

## Bridge 状態の見方
- `Bridge connected`
  - Chrome extension の service worker とローカル app の WebSocket がつながっただけ
  - 天鳳ページ準備完了の意味ではない
  - `SYNC` 前の待機表示として出ることがある
- `Bridge globals ctrls=N` / `Bridge canvas_detect ctrls=N` / `Bridge heuristic ctrls=N`
  - `SYNC` 後に `ui_snapshot.tenhouReady = true` になった状態
  - この表示なら天鳳ページ側は bridge 実行可能
  - ただし `Bridge heuristic ctrls=0` は browser 側 snapshot / 座標推定 / visible control 0 個までは確認できるが、live capture 正常や牌表示更新までは保証しない
  - この状態なら bridge 原因で app 再起動を最優先にすることは少ない
  - ただし `tshark` / TLS keylog / capture thread の再初期化や `--tshark-interface` 変更のための app 再起動はまだ有効
- `Bridge tab not ready`
  - 天鳳タブ側の UI 情報がまだ足りない
  - 少し待つか、天鳳タブをリロードしてから `SYNC` を押し直す
- `Bridge ERR ...`
  - `ui_snapshot` または execute が失敗している
  - 表示されている error 文言をそのまま切り分けに使う

## Chrome 再起動時の扱い
- Chrome / 天鳳タブを再起動しても、毎回 `chrome://extensions` で unpacked extension を再読み込みする前提ではない
- まずは `天鳳タブをリロード -> SYNC` を試す
- `Bridge connected` のままなら transport は生きているので、VS Code の DLL error よりも `ui_snapshot` 未実行または tab 未準備を疑う
- それでも `Bridge tab not ready` や `Bridge ERR ...` が続く場合だけ、extension reload や browser 完全再起動まで広げて切り分ける

## 補足
- この事例では Avast 削除は決定打ではなく、最終的な解決は browser 完全再起動だった
- TLS keylog を使う capture では、既に張られている TLS session に後から乗っても復号できないことがある
- reload だけではなく browser process の完全終了が必要な場合がある
