from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

from sutehai import Player, SutehaiTracker

# Reuse the parsing helpers from the packet capture runner so the logic stays consistent.
from test import parse_line, tile_id_from_tag


# SAMPLE_CAPTURE_LINES の一覧。
SAMPLE_CAPTURE_LINES: List[str] = [
    '1700000000.001\tTLSv1.3 Record Layer: tag":"T05","payload":"sample"}',
    '1700000001.125\tTLSv1.3 Record Layer: tag":"U17","payload":"sample"}',
    '1700000002.310\tTLSv1.3 Record Layer: tag":"V33","payload":"sample"}',
    '1700000002.910\tTLSv1.3 Record Layer: tag":"W11","payload":"sample"}',
    '1700000003.450\tTLSv1.3 Record Layer: tag":"T23","payload":"sample"}',
]


def load_input_lines(path: Optional[Path]) -> Iterator[str]:
    """Return the capture lines either from disk or from the built-in sample."""
    if path is None:
        yield from SAMPLE_CAPTURE_LINES
        return

    with path.open("r", encoding="utf-8") as file:
        yield from file


def run_prototype(lines: Iterable[str]) -> SutehaiTracker:
    """Feed the provided lines through the tracker and return the populated instance."""
    tracker = SutehaiTracker()
    last_timestamp: Optional[float] = None

    for index, raw_line in enumerate(lines, start=1):
        parsed = parse_line(raw_line)
        if not parsed:
            print(f"[SKIP] 行 {index}: 解析対象の tag が見つかりませんでした。")
            continue

        timestamp, tag = parsed
        player_code = tag[0]

        try:
            player = Player.from_code(player_code)
        except ValueError:
            print(f"[SKIP] 行 {index}: 未知のプレイヤーコード {player_code}.")
            continue

        tile_id = tile_id_from_tag(tag)
        if tile_id is None:
            print(f"[SKIP] 行 {index}: タグ {tag} から牌 ID を取得できません。")
            continue

        tsumogiri = player_code == "T"
        tracker.add_discard(
            player,
            tile_id,
            tsumogiri=tsumogiri,
            tag=tag,
            timestamp=timestamp,
        )

        delta = None if last_timestamp is None else timestamp - last_timestamp
        last_timestamp = timestamp

        delta_msg = "N/A" if delta is None else f"{delta:.3f}s"
        print(
            f"[OK ] 行 {index}: {player.name} が牌 {tile_id:02d} "
            f"({'ツモ切り' if tsumogiri else '手出し'}) を捨てました。Δt={delta_msg}"
        )

    return tracker


def format_summary(tracker: SutehaiTracker) -> str:
    """Produce a short textual summary of the captured discards."""
    lines: List[str] = ["\n=== 解析結果サマリー ==="]
    for player in Player:
        discards = tracker.get_discards(player)
        if not discards:
            lines.append(f"- {player.name}: 捨て牌なし")
            continue

        tile_seq = " ".join(f"{discard.tile_id:02d}" for discard in discards)
        lines.append(f"- {player.name}: {len(discards)} 枚 -> {tile_seq}")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="tshark を使わずに仮想キャプチャ入力でトラッカーを動かすプロトタイプ"
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="tshark の想定出力を含むテキストファイル。未指定の場合は組み込みサンプルを使用します。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tracker = run_prototype(load_input_lines(args.input))
    print(format_summary(tracker))


if __name__ == "__main__":
    main()
