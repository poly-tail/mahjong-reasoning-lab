from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Iterable, Literal, Sequence

# CSV_DB_DIRNAME の定義。
CSV_DB_DIRNAME: Final = "csv_db"
# INITBYLOG_HANCHAN_ID_SUFFIX の定義。
INITBYLOG_HANCHAN_ID_SUFFIX: Final = "k"

# HANCHAN_MASTER_FILENAME の定義。
HANCHAN_MASTER_FILENAME: Final = "hanchan_master.csv"
# KYOKU_MASTER_FILENAME の定義。
KYOKU_MASTER_FILENAME: Final = "kyoku_master.csv"
# PLAYER_PROFILES_FILENAME の定義。
PLAYER_PROFILES_FILENAME: Final = "player_profiles.csv"
# DISCARD_FACT_FILENAME_GLOB の定義。
DISCARD_FACT_FILENAME_GLOB: Final = "discard_fact_*.csv"
# DISCARD_CONTEXT_FILENAME_GLOB の定義。
DISCARD_CONTEXT_FILENAME_GLOB: Final = "discard_context_*.csv"
AGARI_FACT_FILENAME_GLOB: Final = "agari_fact_*.csv"
# LEGACY_REMOVED_FILENAME_GLOBS の並びを定義する。
LEGACY_REMOVED_FILENAME_GLOBS: Final[tuple[str, ...]] = ("discard_hands_*.csv",)

# RELATIVE_SEAT_NAME_COLUMNS の並びを定義する。
RELATIVE_SEAT_NAME_COLUMNS: Final[tuple[str, ...]] = (
    "seat0_player_name",
    "seat1_player_name",
    "seat2_player_name",
    "seat3_player_name",
)


# CsvTableSpec クラスを定義する。
@dataclass(frozen=True)
class CsvTableSpec:
    # logical_name を保持する。
    logical_name: str
    # filename_pattern を保持する。
    filename_pattern: str
    # key_columns の並びを保持する。
    key_columns: tuple[str, ...]
    # columns の並びを保持する。
    columns: tuple[str, ...]
    # split_mode を保持する。
    split_mode: Literal["single_file", "monthly"]


# HANCHAN_MASTER_COLUMNS の並びを定義する。
HANCHAN_MASTER_COLUMNS: Final[tuple[str, ...]] = (
    "hanchan_id",
    "room_class_label",
    *RELATIVE_SEAT_NAME_COLUMNS,
    "source_url",
)

# KYOKU_MASTER_COLUMNS の並びを定義する。
KYOKU_MASTER_COLUMNS: Final[tuple[str, ...]] = (
    "kyoku_id",
    "hanchan_id",
    "room_class_label",
    "honba",
    "kyotaku",
    "oya_rel",
    *RELATIVE_SEAT_NAME_COLUMNS,
    "oya_player_name",
    "seat0_first_row_avg_thinking_time_ms",
    "seat1_first_row_avg_thinking_time_ms",
    "seat2_first_row_avg_thinking_time_ms",
    "seat3_first_row_avg_thinking_time_ms",
)

# DISCARD_FACT_COLUMNS の並びを定義する。
DISCARD_FACT_COLUMNS: Final[tuple[str, ...]] = (
    "discard_id",
    "kyoku_id",
    "hanchan_id",
    "room_class_label",
    "player_rel_seat",
    "player_name",
    "discard_tile_136",
    "discard_tile_37_text",
    "tsumogiri_flag",
    "discard_epoch_s",
    "thinking_time_ms",
    "thinking_time_before_reach_ms",
    "lagged",
    "lag_delay_ms",
    "seat0_hand_tiles_136_json",
    "seat1_hand_tiles_136_json",
    "seat2_hand_tiles_136_json",
    "seat3_hand_tiles_136_json",
    "seat0_hand_tiles_37_text",
    "seat1_hand_tiles_37_text",
    "seat2_hand_tiles_37_text",
    "seat3_hand_tiles_37_text",
    "shanten_after_discard",
    "shanten_normal_after_discard",
    "shanten_chiitoitsu_after_discard",
    "wait_tiles_after_discard_mspz",
    "ryanmen_fixed_flag",
    "pystyle_top1_tile_37_text",
    "pystyle_top1_expected_value_text",
    "pystyle_top2_tile_37_text",
    "pystyle_top2_expected_value_text",
    "pystyle_top3_tile_37_text",
    "pystyle_top3_expected_value_text",
)

# DISCARD_CONTEXT_COLUMNS の並びを定義する。
DISCARD_CONTEXT_COLUMNS: Final[tuple[str, ...]] = (
    "discard_id",
    "kyoku_id",
    "scores_json",
    "reach_state_json",
    "dora_indicators_136_json",
    "melds_by_seat_json",
    "rivers_by_seat_136_json",
    "visible_tile_counts_34_json",
)

# PLAYER_PROFILES_COLUMNS の並びを定義する。
AGARI_FACT_COLUMNS: Final[tuple[str, ...]] = (
    "agari_id",
    "kyoku_id",
    "hanchan_id",
    "room_class_label",
    "agari_epoch_s",
    "winner_rel_seat",
    "winner_name",
    "from_rel_seat",
    "from_name",
    "is_tsumo",
    "winning_tile_136",
    "winning_tile_37_text",
    "deal_in_discard_id",
    "deal_in_round_discard_index",
    "estimated_danger_percent",
    "danger_estimate_source",
    "agari_state_snapshot_json",
)

PLAYER_PROFILES_COLUMNS: Final[tuple[str, ...]] = (
    "player_name",
    "user_memo",
    "analysis_memo",
    "source_url",
)

# CSV_TABLE_SPECS の並びを定義する。
CSV_TABLE_SPECS: Final[tuple[CsvTableSpec, ...]] = (
    CsvTableSpec(
        logical_name="hanchan_master",
        filename_pattern=HANCHAN_MASTER_FILENAME,
        key_columns=("hanchan_id",),
        columns=HANCHAN_MASTER_COLUMNS,
        split_mode="single_file",
    ),
    CsvTableSpec(
        logical_name="kyoku_master",
        filename_pattern=KYOKU_MASTER_FILENAME,
        key_columns=("kyoku_id",),
        columns=KYOKU_MASTER_COLUMNS,
        split_mode="single_file",
    ),
    CsvTableSpec(
        logical_name="discard_fact",
        filename_pattern=DISCARD_FACT_FILENAME_GLOB,
        key_columns=("discard_id",),
        columns=DISCARD_FACT_COLUMNS,
        split_mode="monthly",
    ),
    CsvTableSpec(
        logical_name="discard_context",
        filename_pattern=DISCARD_CONTEXT_FILENAME_GLOB,
        key_columns=("discard_id",),
        columns=DISCARD_CONTEXT_COLUMNS,
        split_mode="monthly",
    ),
    CsvTableSpec(
        logical_name="agari_fact",
        filename_pattern=AGARI_FACT_FILENAME_GLOB,
        key_columns=("agari_id",),
        columns=AGARI_FACT_COLUMNS,
        split_mode="monthly",
    ),
    CsvTableSpec(
        logical_name="player_profiles",
        filename_pattern=PLAYER_PROFILES_FILENAME,
        key_columns=("player_name",),
        columns=PLAYER_PROFILES_COLUMNS,
        split_mode="single_file",
    ),
)


def build_kyoku_info(kyoku_index: int | None, honba: int | None) -> str | None:
    """Return the 4-character round code `seed[0]seed[1]` with zero padding."""

    if kyoku_index is None or honba is None:
        return None
    if not 0 <= kyoku_index <= 99:
        raise ValueError(f"kyoku_index must be in 0..99: {kyoku_index}")
    if not 0 <= honba <= 99:
        raise ValueError(f"honba must be in 0..99: {honba}")
    return f"{kyoku_index:02d}{honba:02d}"


def build_kyoku_id(hanchan_id: str, kyoku_info: str) -> str:
    """Return the round identifier composed from hanchan id plus `_` plus 4-digit round code."""

    if not hanchan_id:
        raise ValueError("hanchan_id must not be empty")
    if len(kyoku_info) != 4:
        raise ValueError(f"kyoku_info must be 4 characters: {kyoku_info}")
    return f"{hanchan_id}_{kyoku_info}"


def build_discard_id(kyoku_id: str, discard_index: int) -> str:
    """Return a stable discard identifier scoped under one round."""

    if discard_index < 0:
        raise ValueError(f"discard_index must be >= 0: {discard_index}")
    return f"{kyoku_id}_{discard_index:03d}"


def build_same_day_player_signature(
    hanchan_date: str,
    player_names_by_rel_seat: Sequence[str | None],
) -> str:
    """Return the same-day signature used to deduplicate INITBYLOG-based hanchan ids."""

    if len(hanchan_date) != 8 or not hanchan_date.isdigit():
        raise ValueError(f"hanchan_date must be YYYYMMDD: {hanchan_date}")
    if len(player_names_by_rel_seat) != 4:
        raise ValueError(
            "player_names_by_rel_seat must contain exactly four relative-seat entries"
        )
    normalized_names = [
        (name or "").replace("|", "/").strip()
        for name in player_names_by_rel_seat
    ]
    return (
        f"{hanchan_date}"
        f"|0={normalized_names[0]}"
        f"|1={normalized_names[1]}"
        f"|2={normalized_names[2]}"
        f"|3={normalized_names[3]}"
    )


def build_hanchan_id(
    hanchan_date: str,
    start_hms: str,
    *,
    use_initbylog_fallback: bool = False,
) -> str:
    """Return the canonical hanchan id.

    Normal ids are `YYYYMMDDHHMMSS`.
    INITBYLOG fallback ids keep the total width at 14 characters by replacing the last second digit
    with `k`, for example `2026040212345k`.
    """

    if len(hanchan_date) != 8 or not hanchan_date.isdigit():
        raise ValueError(f"hanchan_date must be YYYYMMDD: {hanchan_date}")
    if len(start_hms) != 6 or not start_hms.isdigit():
        raise ValueError(f"start_hms must be HHMMSS: {start_hms}")
    if use_initbylog_fallback:
        return f"{hanchan_date}{start_hms[:5]}{INITBYLOG_HANCHAN_ID_SUFFIX}"
    return f"{hanchan_date}{start_hms}"


def monthly_chunk_token_from_hanchan_id(hanchan_id: str) -> str:
    """Return the `YYYYMM` token used by monthly CSV chunk files."""

    if len(hanchan_id) < 6 or not hanchan_id[:6].isdigit():
        raise ValueError(f"hanchan_id must start with YYYYMM: {hanchan_id}")
    return hanchan_id[:6]


def resolve_table_paths(db_dir: Path, spec: CsvTableSpec) -> list[Path]:
    """Return every CSV path that belongs to one logical table."""

    if spec.split_mode == "single_file":
        return [db_dir / spec.filename_pattern]
    return sorted(db_dir.glob(spec.filename_pattern))


def iter_all_table_paths(db_dir: Path) -> Iterable[Path]:
    """Yield every configured CSV file path in the DB directory."""

    for spec in CSV_TABLE_SPECS:
        yield from resolve_table_paths(db_dir, spec)
