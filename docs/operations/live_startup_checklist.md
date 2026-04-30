# 通常起動チェックリスト

live capture と Tenhou UI Bridge を併用する通常運用時の確認順です。

## 1. 事前確認

- `tshark` が使える
- Chrome 拡張 `extension/` を読み込んである
- ローカル app とブラウザを同時に起動できる

## 2. 起動順

1. ローカル app を起動する
2. ブラウザで拡張が有効なことを確認する
3. 天鳳ページを開くか再読込する
4. app 側で `SYNC` を押して bridge 状態を確認する

## 3. 標準出力で見るべき行

- `Tenhou UI Bridge listening on ws://127.0.0.1:8765`
- `Tenhou UI Bridge startup order: app -> confirm extension enabled in browser -> open/reload Tenhou page ...`
- `TShark runtime message: Capturing on 'Wi-Fi'`

`Wi-Fi` や `Ethernet` のような実アダプタ名なら正常です。

## 4. 注意すべき表示

- `Capturing on 'Adapter for loopback traffic capture'`
- `Capturing on 'Event Tracing for Windows (ETW) reader'`
- `0 packets captured`
- `Bridge heuristic ctrls=0`

`Bridge heuristic ctrls=0` はブラウザ側の準備だけでは異常と断定しません。  
capture 側の未準備、天鳳ページ未読込、visible control 不在などでも出ます。

## 5. bridge 状態の見方

- `Bridge connected`: transport 接続のみ確認
- `Bridge globals ctrls=N`: page globals 取得成功
- `Bridge canvas_detect ctrls=N`: canvas 検出モードで取得成功
- `Bridge heuristic ctrls=N`: heuristic での取得結果
- `Bridge tab not ready`: 天鳳ページが準備前
- `Bridge ERR ...`: snapshot か execute が失敗

## 6. capture インターフェースが怪しい時

```powershell
& "C:\Program Files\Wireshark\tshark" -D
python src/tenhou_hojo.py --tshark-interface 2
```

loopback / ETW を掴んでいる場合は、実ネットワーク側の index を明示します。
