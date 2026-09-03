# 天鳳補助ツール

天鳳の局面をローカル GUI で可視化し、危険度、押し引き、pystyle 推奨、Nodocchi 成績、NAGA 段位ポイント分析、Tenhou UI Bridge 操作をまとめて扱う支援ツール。

## 主要ドキュメント

- [ドキュメント索引](docs/README.md)
- [要件定義 現行版](docs/requirements/current.md)
- [仕様書 現行版](docs/specs/current.md)
- [画面仕様書 現行版](docs/screen_specs/current.md)
- [変更履歴](docs/changelog.md)
- [Codex / agent 作業ルール](AGENTS.md)

## 最近の主な仕様

- 河は差分描画。変わった捨て牌だけ更新し、`P` マーク追加も対象牌だけ差し替える。
- 河の赤/茶/紫/思考時間色は通常牌画像 + Canvas overlay で描画する。
- プレイヤーパネルの `SUMMARY` と `ALERT` は remain 色基準を統一する。
- 河の Push `P` は各席の1段目（捨て牌 local index 0〜5）には表示せず、2段目以降だけ表示する。
- 各席の2段目以降では、`Push` 音声と河 `P` を同じ更新で反映する。
- panel に出ない自分側 alert は音声対象にしない。
- Nodocchi `STATUS` は和了率・副露率・リーチ率だけ赤字、その他は白字。
- 南2以降は下部に NAGA 段位ポイント分析の主要 pt 変化を自動表示する。
- DB分析でプレイヤー別の 1〜3 シャンテン思考時間相関と所属卓を出力する。

## セットアップ

```powershell
python -m pip install -r requirements.txt
```

NAGA 分析を使う場合は `naga-ptev-analyzer/` の setup と Playwright login state が必要。

## 起動例

```powershell
python src/tenhou_hojo.py --mock
python src/tenhou_hojo.py --mock 2
python src/tenhou_hojo.py --test sample.pcapng
python src/tenhou_hojo.py --xml-url https://...
python src/tenhou_hojo.py --tshark-interface 2
python src/tenhou_hojo.py --disable-tenhou-ui-bridge
```

## 分析

```powershell
python scripts/analyze_player_shanten_thinking.py
```

出力先:

- `reports/player_shanten_thinking/`

## テスト

```powershell
$env:PYTHONPATH='src'
python -m pytest tests -q
```

## source ZIP

```powershell
python scripts/package_workspace.py
```

既定の `source` profile は、秘密情報、ログ、runtime CSV DB、pcap、分析出力、既存ZIPを除外する。runtime data の退避は `--profile runtime-backup --include-runtime-data <path>` で明示する。

## 関連

- [Tenhou UI Bridge](docs/integrations/tenhou_ui_bridge.md)
- [Nodocchi STATUS](docs/integrations/nodocchi_status.md)
- [NAGA 段位ポイント分析](docs/integrations/naga_ptev_analyzer.md)
- [性能ホットスポット](docs/analysis/performance_hotspots.md)
