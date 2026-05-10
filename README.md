# 天鳳補助ツール

天鳳の対局情報をローカル GUI で可視化し、`tshark` ベースのキャプチャ、`.pcapng` リプレイ、XML 取込、AI 推奨、Tenhou UI Bridge 連携までをまとめて扱うワークスペースです。

## 主要ドキュメント

- [ドキュメント索引](docs/README.md)
- [要件定義 現行版](docs/requirements/current.md)
- [仕様書 現行版](docs/specs/current.md)
- [画面仕様書 現行版](docs/screen_specs/current.md)
- [プロジェクトガイド](docs/architecture/project_guide.md)
- [ソース概要](docs/architecture/source_overview.md)
- [麻雀ドメイン文書](docs/mahjong/README.md)
- [Nodocchi プレイヤー成績連携](docs/integrations/nodocchi_status.md)
- [src コールグラフ](docs/architecture/src_call_graph.md)
- [Tenhou UI Bridge 連携](docs/integrations/tenhou_ui_bridge.md)
- [通常起動チェックリスト](docs/operations/live_startup_checklist.md)
- [他環境セットアップ](docs/operations/other_environment_setup.md)
- [更新履歴](docs/changelog.md)

## セットアップ

### Python 依存

```powershell
python -m pip install -r requirements.txt
```

現行の必須 Python 依存は `Pillow` です。

### 外部ツール

- ライブキャプチャ / `.pcapng` リプレイ: Wireshark 付属の `tshark`
- ドキュメントグラフ再生成: `mmdc` または `Node.js + npx`
- ブラウザ連携: Chrome 系ブラウザ

## 起動例

```powershell
python src/tenhou_hojo.py --mock
python src/tenhou_hojo.py --mock 2
python src/tenhou_hojo.py --test sample.pcapng
python src/tenhou_hojo.py --test sample.pcapng --test-interval-ms 200
python src/tenhou_hojo.py --xml-url https://...
python src/tenhou_hojo.py --tshark-interface 2
python src/tenhou_hojo.py --disable-tenhou-ui-bridge
```

## ドキュメント更新

```powershell
python scripts/render_docs_graphs.py
```

Windows から PowerShell だけで扱いたい場合は、従来の `cli/render_src_call_graph.ps1` も利用できます。

## ワークスペース保存

```powershell
python scripts/package_workspace.py
```

`dist/` 配下に日時付き ZIP を作成します。  
キャッシュ類 (`__pycache__`, `.pytest_cache`) は除外し、読み取れない一時フォルダは警告を出してスキップします。

## Tenhou UI Bridge

`extension/` はローカル GUI とブラウザ上の天鳳 UI をつなぐ Chrome 拡張です。

- `src/app/tenhou_ui_bridge_server.py`: ローカル WebSocket サーバ
- `src/app/tenhou_ui_bridge_client.py`: GUI 側の操作クライアント
- `extension/service-worker.js`: ブラウザ側接続の起点
- `extension/content-bridge.js`: isolated world から MAIN world への橋渡し
- `extension/main-ui-bridge.js`: 天鳳ページ上での UI 実行

起動順は `ローカル app -> 拡張の有効確認 -> 天鳳ページを開く/再読込` です。  
詳細は [通常起動チェックリスト](docs/operations/live_startup_checklist.md) を参照してください。
