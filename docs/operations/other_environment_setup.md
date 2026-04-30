# 他環境セットアップ

この文書は、別 PC や別ユーザー環境でワークスペースを再実行するための最小手順です。

## 1. 必要なもの

- Python 3.11 以降を推奨
- `pip`
- Wireshark 付属の `tshark`
- Chrome 系ブラウザ
- グラフ再生成を行う場合は `mmdc` または `Node.js + npx`

## 2. Python 依存の導入

```powershell
python -m pip install -r requirements.txt
```

現行の必須依存は `Pillow` です。

## 3. 起動確認

```powershell
python src/tenhou_hojo.py --mock
```

まずは `--mock` で GUI が開くことを確認します。

## 4. live capture / replay

- live capture と `.pcapng` リプレイの両方で `tshark` が必要
- 必要に応じて `--tshark-interface` を指定
- TLS 復号が必要な replay では `--tls-keylog` を渡す

## 5. Bridge 連携

1. `extension/` を Chrome に読み込む
2. app を起動する
3. 天鳳ページを開くか再読込する
4. `SYNC` で bridge 状態を確認する

## 6. ドキュメント再生成

```powershell
python scripts/render_docs_graphs.py
```

## 7. ワークスペース保存

```powershell
python scripts/package_workspace.py
```

`dist/` 配下に ZIP を出力します。
