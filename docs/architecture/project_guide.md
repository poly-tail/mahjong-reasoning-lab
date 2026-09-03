# プロジェクトガイド

更新日: `2026-09-03`

## 目的

天鳳補助ツールは、live packet capture / replay / XML / Tenhou UI Bridge / pystyle / Nodocchi / NAGA 分析を 1 つのローカル UI へ統合する。

## 主な入口

- `src/tenhou_hojo.py`: 起動 entry point
- `src/app/main.py`: アプリ全体の起動、snapshot 構築、外部連携
- `src/ui/table_renderer.py`: 画面描画、panel、alert、音声、河差分描画
- `src/logic/danger_suji.py`: remain / push / line ranking / danger bar
- `src/capture/storage.py`: CSV DB 永続化
- `scripts/analyze_player_shanten_thinking.py`: DB分析

## 直近の重点

- `Push` は panel、音声、河 `P` で同じ payload を参照する。panel は判定時から表示し、音声と河 `P` は各席の2段目以降だけ同じタイミングで反映する。
- panel に出ない自分側 alert は音声対象にしない。
- `SUMMARY` と `ALERT` の remain 色基準は同一にする。
- 同一局の heavy suji / 危険度計算中は直前完了 bundle を side panel / hand / analysis overlay の表示専用 fallback として保持し、完了時は async-only partial refresh で差し替える。初回と新局は保持対象外で、stale 値を自動打牌や alert 音声の新規判定へ使わない。
- 河は全描画せず、表示シグネチャ単位で差分更新する。
- NAGA は南2以降に下部自動要約を出す。
- 所属卓分析は `hanchan_master` を正本にする。

## 変更時の同期先

- 要件: `docs/requirements/current.md`
- 仕様: `docs/specs/current.md`
- 画面仕様: `docs/screen_specs/current.md`
- 性能: `docs/analysis/performance_hotspots.md`
- DB分析: `docs/analysis/player_shanten_thinking.md`
- 変更履歴: `docs/changelog.md`

## テスト

```powershell
$env:PYTHONPATH='src'
python -m pytest tests -q
```
