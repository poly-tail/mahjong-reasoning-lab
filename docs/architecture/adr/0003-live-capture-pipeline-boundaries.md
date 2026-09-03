# ADR-0003: live capture pipelineの責務境界を維持する

## Status

Proposed

## Context

live capture は `tshark` process、packet parser、state mutation、CSV DB保存、UI snapshot、Tk描画をまたぐ。既存実装では `state_lock`、async CSV persist、`AsyncLiveTableSnapshotProvider`、UI差分描画が導入されているが、DB保存用DTOの最小化や計測基盤は追加検証が必要。

## Decision

現時点の方針として、capture thread は packet取得とstate mutationを優先し、DB保存とUI派生計算は可能な限り別threadまたはsnapshot経由へ逃がす。Tk thread上で重いstate複製や派生計算を増やさない。欠落禁止イベントとcoalescing可能な更新を混同しない。

## Alternatives considered

- capture threadでDB保存まで同期実行する: packet処理とUI更新を詰まらせるため不採用。
- UI threadが必要時にlive stateを直接深く読む: Tk thread blockingと途中状態公開のリスクがあるため不採用。
- DB保存用DTOへ全面移行する: 有望だが今回の最小修正範囲を超えるためDeferred。

## Consequences

責務境界は維持されるが、queue長、lock保持時間、snapshot複製時間の継続計測が必要。

## Compatibility

既存CSV schema、UI表示、REINIT復帰、packet順序の互換性を優先する。

## Reconsideration conditions

DB queue遅延、state_lock競合、UI snapshot遅延が実測でP1以上の問題になった場合。

## Related tests

- `tests/test_live_capture_agari_storage.py`
- `tests/test_live_snapshot_cache.py`
- `tests/test_pcap_replay.py`

## Related documents

- `docs/integrations/packet_capture.md`
- `docs/analysis/performance_hotspots.md`
- `docs/operations/troubleshooting/live_capture.md`
