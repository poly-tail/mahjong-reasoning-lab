from __future__ import annotations

import json
import shutil
import sys
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
TEST_TMP_ROOT = WORKSPACE_ROOT / "tmp_test_live_capture"
SRC_DIR = WORKSPACE_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from capture.state import CaptureState, Discard, Event, Meld, RoundState
from capture.storage import CsvDatabase, HanchanContext, _snapshot_capture_state_for_async_persist
from logic.danger_suji import (
    OpponentSujiDangerProfile,
    OpponentSujiPanelSummary,
    PlayerPushAlertSummary,
)


class LiveCaptureAgariStorageTest(unittest.TestCase):
    def _sample_hanchan(self) -> HanchanContext:
        return HanchanContext(
            hanchan_id="20260417123543",
            hanchan_date="20260417",
            hanchan_start_hms="123543",
            hanchan_start_epoch_ms=1776396943,
            hanchan_id_source="init_timestamp",
            first_init_tag="INIT",
            same_day_player_signature="20260417|self|winner||",
            game_id="2026041712gm-0029-0000-test0000",
            room_class_label="迚ｹ荳雁酷",
            source_kind="player_live",
        )

    @contextmanager
    def _temporary_db_dir(self):
        TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
        temp_dir = TEST_TMP_ROOT / f"case_{time.time_ns()}"
        suffix = 0
        while temp_dir.exists():
            suffix += 1
            temp_dir = TEST_TMP_ROOT / f"case_{time.time_ns()}_{suffix}"
        temp_dir.mkdir()
        try:
            yield str(temp_dir)
        finally:
            for attempt in range(6):
                try:
                    shutil.rmtree(temp_dir)
                    break
                except PermissionError:
                    if attempt == 5:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        break
                    time.sleep(0.05 * (attempt + 1))

    def test_agari_row_falls_back_when_ron_danger_estimate_fails(self) -> None:
        with self._temporary_db_dir() as temp_dir_text:
            database = CsvDatabase(db_dir=Path(temp_dir_text), bootstrap_logical_tables=())
            self.addCleanup(database.close)
            state = CaptureState()
            state.players[0].name = "self"
            state.players[1].name = "winner"
            round_state = RoundState(started_from_init_like=True)
            event = Event(
                timestamp=1776398761.0,
                event_type="agari",
                attrs={"who": 1, "fromWho": 0, "machi": 53, "is_tsumo": False},
            )
            state.events.append(event)

            with patch(
                "capture.storage._build_agari_ron_danger_columns",
                side_effect=TypeError("synthetic agari danger failure"),
            ):
                row = database._agari_fact_row(
                    state,
                    event,
                    self._sample_hanchan(),
                    "20260417123543_0600",
                    "蜊・螻0譛ｬ蝣ｴ",
                    round_state,
                )

        self.assertEqual(row["winner_name"], "winner")
        self.assertEqual(row["from_name"], "self")
        self.assertEqual(row["winning_tile_136"], 53)
        self.assertEqual(row["deal_in_discard_id"], "")
        self.assertEqual(row["deal_in_round_discard_index"], "")
        self.assertEqual(row["estimated_danger_percent"], "")
        self.assertEqual(row["danger_estimate_source"], "")
        self.assertTrue(
            any(
                diagnostic.get("code") == "agari_ron_danger_estimate_failed"
                for diagnostic in state.diagnostics
            )
        )

    def test_hanchan_master_room_class_falls_back_to_live_game_id(self) -> None:
        with self._temporary_db_dir() as temp_dir_text:
            database = CsvDatabase(db_dir=Path(temp_dir_text), bootstrap_logical_tables=())
            self.addCleanup(database.close)
            state = CaptureState()
            state.game_id = "2026052115gm-00a9-0000-627a47cd"
            state.current_round = RoundState(started_from_init_like=True)
            for seat, name in enumerate(("self", "shimo", "toi", "kami")):
                state.players[seat].name = name
            event = Event(timestamp=1779338668.0, event_type="init", raw_tag="INIT")

            database.persist_event(state, event)
            rows = database._store("hanchan_master").iter_rows()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["room_class_label"], "鳳凰卓")

        self.assertEqual(
            rows[0]["source_url"],
            "https://tenhou.net/0/?log=2026052115gm-00a9-0000-627a47cd",
        )

    def test_hanchan_master_source_url_backfills_when_game_id_arrives_after_init(self) -> None:
        with self._temporary_db_dir() as temp_dir_text:
            database = CsvDatabase(db_dir=Path(temp_dir_text), bootstrap_logical_tables=())
            self.addCleanup(database.close)
            state = CaptureState()
            state.current_round = RoundState(started_from_init_like=True)
            for seat, name in enumerate(("self", "shimo", "toi", "kami")):
                state.players[seat].name = name
            init_event = Event(timestamp=1779338668.0, event_type="init", raw_tag="INIT")
            database.persist_event(state, init_event)
            rows = database._store("hanchan_master").iter_rows()
            self.assertEqual(rows[0]["source_url"], "")

            state.game_id = "2026052115gm-00a9-0000-627a47cd"
            go_event = Event(timestamp=1779338669.0, event_type="go", raw_tag="GO")
            database.persist_event(state, go_event)
            rows = database._store("hanchan_master").iter_rows()

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["source_url"],
            "https://tenhou.net/0/?log=2026052115gm-00a9-0000-627a47cd",
        )

    def test_hanchan_master_room_class_updates_when_go_arrives_after_init(self) -> None:
        with self._temporary_db_dir() as temp_dir_text:
            database = CsvDatabase(db_dir=Path(temp_dir_text), bootstrap_logical_tables=())
            self.addCleanup(database.close)
            state = CaptureState()
            state.current_round = RoundState(started_from_init_like=True)
            for seat, name in enumerate(("self", "shimo", "toi", "kami")):
                state.players[seat].name = name
            init_event = Event(timestamp=1779338668.0, event_type="init", raw_tag="INIT")
            database.persist_event(state, init_event)

            state.go_type = 169
            state.room_class_label = "鳳凰卓"
            go_event = Event(timestamp=1779338669.0, event_type="go", raw_tag="GO")
            database.persist_event(state, go_event)
            rows = database._store("hanchan_master").iter_rows()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["room_class_label"], "鳳凰卓")

    def test_kyoku_master_records_first_row_average_thinking_time(self) -> None:
        with self._temporary_db_dir() as temp_dir_text:
            database = CsvDatabase(db_dir=Path(temp_dir_text), bootstrap_logical_tables=())
            self.addCleanup(database.close)
            database.current_hanchan = self._sample_hanchan()
            state = CaptureState()
            for seat, name in enumerate(("self", "shimo", "toi", "kami")):
                state.players[seat].name = name
            round_state = RoundState(
                kyoku_index=0,
                honba=0,
                kyotaku=0,
                oya=0,
                started_from_init_like=True,
            )
            state.current_round = round_state
            state.rounds.append(round_state)
            event = Event(
                timestamp=1776398761.0,
                event_type="discard",
                seat=1,
                tile_136=8,
            )
            state.events.append(event)
            round_state.events.append(event)
            for index, thinking_time_ms in enumerate((1000.0, 2000.0, 3000.0)):
                round_state.discards[1].append(
                    Discard(
                        tile_136=8 + index,
                        round_discard_index=index,
                        thinking_time_ms=thinking_time_ms,
                        event_index=0 if index == 2 else -1,
                    )
                )

            database.persist_event(state, event)
            rows = database._store("kyoku_master").iter_rows()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["seat1_first_row_avg_thinking_time_ms"], "2000.0")
        self.assertEqual(rows[0]["seat0_first_row_avg_thinking_time_ms"], "")

    def test_reinit_snapshot_discards_are_persisted_to_discard_fact(self) -> None:
        with self._temporary_db_dir() as temp_dir_text:
            database = CsvDatabase(db_dir=Path(temp_dir_text), bootstrap_logical_tables=())
            self.addCleanup(database.close)
            state = CaptureState()
            state.game_id = "2026052115gm-00a9-0000-627a47cd"
            for seat, name in enumerate(("self", "shimo", "toi", "kami")):
                state.players[seat].name = name
            round_state = RoundState(
                kyoku_index=0,
                honba=0,
                kyotaku=0,
                oya=0,
                started_from_init_like=True,
            )
            round_state.discards[0].append(
                Discard(
                    tile_136=12,
                    round_discard_index=0,
                    raw_tag="REINIT_KAWA:12",
                )
            )
            round_state.discards[1].append(
                Discard(
                    tile_136=48,
                    round_discard_index=1,
                    raw_tag="REINIT_KAWA:48",
                )
            )
            state.current_round = round_state
            state.rounds.append(round_state)
            event = Event(timestamp=1779338668.0, event_type="reinit", raw_tag="REINIT")
            state.events.append(event)
            round_state.events.append(event)

            database.persist_event(state, event)
            rows = database._store("discard_fact", "202605").iter_rows()

        self.assertEqual([row["discard_tile_136"] for row in rows], ["12", "48"])
        self.assertTrue(all(row["discard_epoch_s"] for row in rows))
        self.assertEqual(rows[0]["room_class_label"], "鳳凰卓")

    def test_async_persist_waits_for_state_lock_instead_of_dropping_event(self) -> None:
        with self._temporary_db_dir() as temp_dir_text:
            database = CsvDatabase(
                db_dir=Path(temp_dir_text),
                bootstrap_logical_tables=(),
                async_persist=True,
            )
            self.addCleanup(database.close)
            state = CaptureState()
            round_state = RoundState(started_from_init_like=True, round_id="round-busy")
            state.current_round = round_state
            state.rounds.append(round_state)
            state.sync_current_round_context()
            event = Event(timestamp=1.0, event_type="discard", seat=0)
            state.events.append(event)
            round_state.events.append(event)

            persisted_call_count = 0

            def count_persist_now(
                self: CsvDatabase,
                snapshot_state: CaptureState,
                snapshot_event: Event,
            ) -> None:
                nonlocal persisted_call_count
                persisted_call_count += 1

            with patch.object(CsvDatabase, "_persist_event_now", new=count_persist_now):
                state.state_lock.acquire()
                persist_done = threading.Event()
                persist_error: list[BaseException] = []

                def run_persist() -> None:
                    try:
                        database.persist_event(state, event)
                    except BaseException as exc:  # noqa: BLE001 - test captures thread errors.
                        persist_error.append(exc)
                    finally:
                        persist_done.set()

                persist_thread = threading.Thread(target=run_persist)
                try:
                    persist_thread.start()
                    self.assertFalse(persist_done.wait(timeout=0.05))
                finally:
                    state.state_lock.release()
                persist_thread.join(timeout=1.0)
                database.wait_for_pending_writes()

        self.assertFalse(persist_error)
        self.assertEqual(persisted_call_count, 1)

    def test_async_persist_skips_non_csv_event_types(self) -> None:
        with self._temporary_db_dir() as temp_dir_text:
            database = CsvDatabase(
                db_dir=Path(temp_dir_text),
                bootstrap_logical_tables=(),
                async_persist=True,
            )
            self.addCleanup(database.close)
            state = CaptureState()
            state.current_round = RoundState(started_from_init_like=True)
            state.rounds.append(state.current_round)
            event = Event(timestamp=1.0, event_type="draw", seat=0)

            with patch.object(CsvDatabase, "_persist_event_now") as persist_now:
                database.persist_event(state, event)
                database.wait_for_pending_writes()

        persist_now.assert_not_called()

    def test_agari_row_includes_suji_snapshot_and_discard_flags(self) -> None:
        with self._temporary_db_dir() as temp_dir_text:
            database = CsvDatabase(db_dir=Path(temp_dir_text), bootstrap_logical_tables=())
            self.addCleanup(database.close)
            state = CaptureState()
            state.players[0].name = "self"
            state.players[1].name = "winner"
            state.players[2].name = "toimen"
            state.players[3].name = "kamicha"
            round_state = RoundState(started_from_init_like=True)
            round_state.discards[1].append(
                Discard(
                    tile_136=16,
                    round_discard_index=0,
                    lagged=6,
                    lag_delay_ms=420.0,
                )
            )
            event = Event(
                timestamp=1776398761.0,
                event_type="agari",
                attrs={"who": 1, "fromWho": 0, "machi": 53, "is_tsumo": False},
            )
            state.events.append(event)

            zero34_float = tuple(0.0 for _ in range(34))
            zero34_int = tuple(0 for _ in range(34))
            fake_profiles = {
                1: OpponentSujiDangerProfile(
                    seat=1,
                    tile_weights_34=zero34_float,
                    corrected_musuji_count=5.5,
                    safe_tile34=frozenset(),
                    line_weights=((0, 1, 4, 1.0), (0, 2, 5, 0.5)),
                    visible_counts_34=zero34_int,
                    ugly_wait_add_percent_34=zero34_float,
                ),
                2: OpponentSujiDangerProfile(
                    seat=2,
                    tile_weights_34=zero34_float,
                    corrected_musuji_count=10.0,
                    safe_tile34=frozenset(),
                    line_weights=((1, 3, 6, 1.0),),
                    visible_counts_34=zero34_int,
                    ugly_wait_add_percent_34=zero34_float,
                ),
                3: OpponentSujiDangerProfile(
                    seat=3,
                    tile_weights_34=zero34_float,
                    corrected_musuji_count=11.0,
                    safe_tile34=frozenset(),
                    line_weights=((2, 2, 5, 1.0),),
                    visible_counts_34=zero34_int,
                    ugly_wait_add_percent_34=zero34_float,
                ),
            }
            fake_panel_summaries = {
                1: OpponentSujiPanelSummary(
                    seat=1,
                    denominator_count=5.5,
                    top_line_labels=("1-4m m1 18%",),
                    denominator_count_without_temporary_safe=12.2,
                    menzen_alert_score=5,
                    hand_pattern_alert_level=1,
                    suit_bias_alert=True,
                    ryanmen_chi_central_tedashi_alert=True,
                    tedashi_thinking_rise_alert=True,
                    tenpai_probability=42.0,
                    top_safe_hand_labels=("1. 1m 0%",),
                    top_tile_rank_labels=("1. 4m 18%",),
                ),
                2: OpponentSujiPanelSummary(
                    seat=2,
                    denominator_count=10.0,
                    top_line_labels=(),
                    tenpai_probability=18.0,
                ),
                3: OpponentSujiPanelSummary(
                    seat=3,
                    denominator_count=11.0,
                    top_line_labels=(),
                    tenpai_probability=21.0,
                ),
            }
            fake_push_alerts = {
                1: PlayerPushAlertSummary(
                    seat=1,
                    percentage=12.3,
                    tile_34=4,
                    tile_label="5m",
                    discard_index=0,
                    is_current=True,
                    target_seats=(0, 2),
                ),
                2: PlayerPushAlertSummary(seat=2),
                3: PlayerPushAlertSummary(seat=3),
            }

            with (
                patch(
                    "capture.storage.build_all_opponent_suji_danger_profiles",
                    return_value=fake_profiles,
                ),
                patch(
                    "capture.storage.build_all_opponent_suji_panel_summaries",
                    return_value=fake_panel_summaries,
                ),
                patch(
                    "capture.storage.build_latest_discard_push_alert_percentages",
                    return_value=fake_push_alerts,
                ),
                patch(
                    "capture.storage.build_discard_red_tint_indices_by_seat",
                    return_value={0: (), 1: (0,), 2: (), 3: ()},
                ),
            ):
                row = database._agari_fact_row(
                    state,
                    event,
                    self._sample_hanchan(),
                    "20260417123543_0600",
                    "蜊・螻0譛ｬ蝣ｴ",
                    round_state,
                )

        payload = json.loads(row["agari_state_snapshot_json"])
        self.assertEqual(payload["suji_by_seat"]["1"]["line_weights"][0]["line"], "1-4m")
        self.assertEqual(
            payload["suji_by_seat"]["1"]["push_alert"]["target_seats"],
            [0, 2],
        )
        self.assertIn(
            "Push 5m 12.3%",
            [item["label"] for item in payload["suji_by_seat"]["1"]["alerts"]],
        )
        self.assertTrue(payload["discards_by_seat"]["1"]["items"][0]["red_tint"])
        self.assertEqual(payload["discards_by_seat"]["1"]["items"][0]["tile_mspz"], "r5m")
        self.assertEqual(payload["discards_by_seat"]["1"]["items"][0]["lagged"], 6)

    def test_async_persist_keeps_old_agari_snapshot_after_live_state_moves_on(self) -> None:
        with self._temporary_db_dir() as temp_dir_text:
            database = CsvDatabase(
                db_dir=Path(temp_dir_text),
                bootstrap_logical_tables=("player_profiles", "hanchan_master", "kyoku_master"),
                async_persist=True,
            )
            self.addCleanup(database.close)
            state = CaptureState()
            state.game_id = "2026041712gm-0029-0000-test0000"
            state.players[0].name = "self-old"
            state.players[1].name = "winner-old"
            round_state = RoundState(
                started_from_init_like=True,
                kyoku_index=6,
                honba=0,
                oya=0,
            )
            state.current_round = round_state
            state.rounds.append(round_state)
            state.sync_current_round_context()
            event = Event(
                timestamp=1776398761.0,
                event_type="agari",
                attrs={"who": 1, "fromWho": 0, "machi": 53, "is_tsumo": False},
            )
            state.events.append(event)
            database.current_hanchan = self._sample_hanchan()
            database.current_game_id = state.game_id

            release_worker = threading.Event()
            original_persist_now = CsvDatabase._persist_event_now
            test_case = self

            def slow_persist_now(
                self: CsvDatabase,
                snapshot_state: CaptureState,
                snapshot_event: Event,
            ) -> None:
                if snapshot_event.event_type == "agari":
                    test_case.assertTrue(release_worker.wait(timeout=2.0))
                original_persist_now(self, snapshot_state, snapshot_event)

            with (
                patch.object(CsvDatabase, "_persist_event_now", new=slow_persist_now),
                patch("capture.storage._build_agari_state_snapshot_json", return_value="{}"),
            ):
                database.persist_event(state, event)
                state.players[0].name = "self-new"
                state.players[1].name = "winner-new"
                state.current_round = RoundState(
                    started_from_init_like=True,
                    kyoku_index=7,
                    honba=1,
                    oya=1,
                )
                state.rounds.append(state.current_round)
                state.sync_current_round_context()
                release_worker.set()
                database.close()

            row = database._store("agari_fact", "202604").get(("20260417123543_0600_agari_000",))

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["winner_name"], "winner-old")
        self.assertEqual(row["from_name"], "self-old")
        self.assertEqual(row["kyoku_id"], "20260417123543_0600")

    def test_async_persist_snapshot_uses_lightweight_copy_for_call_state(self) -> None:
        state = CaptureState()
        state.players[0].name = "self-old"
        state.players[1].name = "caller-old"
        round_state = RoundState(
            started_from_init_like=True,
            kyoku_index=1,
            honba=0,
            oya=0,
            round_id="round-old",
        )
        discard = Discard(
            tile_136=12,
            round_discard_index=0,
            hand_tiles_before_discard_136=[1, 2, 3],
            called=True,
            event_index=0,
        )
        meld = Meld(
            who=1,
            raw_m=51275,
            meld_type="pon",
            consumed_tile_ids=[12, 13],
            called_tile_id=14,
            tiles_136=[12, 13, 14],
            tiles_34=[3, 3, 3],
            tiles_37=[4, 4, 4],
            event_index=1,
        )
        round_state.discards[0].append(discard)
        round_state.melds[1].append(meld)
        state.current_round = round_state
        state.rounds.append(round_state)
        state.sync_current_round_context()
        discard_event = Event(timestamp=1.0, event_type="discard", seat=0)
        call_event = Event(
            timestamp=2.0,
            event_type="call",
            seat=1,
            attrs={"nested": {"tiles": [12, 13, 14]}},
        )
        state.events.extend([discard_event, call_event])
        round_state.events.extend([discard_event, call_event])

        with patch("capture.storage.copy.deepcopy", side_effect=AssertionError("deepcopy used")):
            snapshot = _snapshot_capture_state_for_async_persist(state, call_event)

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        snapshot_state, snapshot_event = snapshot
        self.assertIs(snapshot_event, snapshot_state.events[1])

        state.players[1].name = "caller-new"
        discard.hand_tiles_before_discard_136.append(99)
        discard.called = False
        meld.tiles_136.append(99)
        call_event.attrs["nested"]["tiles"].append(99)

        self.assertEqual(snapshot_state.players[1].name, "caller-old")
        snapshot_discard = snapshot_state.current_round.discards[0][0]
        self.assertEqual(snapshot_discard.hand_tiles_before_discard_136, [1, 2, 3])
        self.assertTrue(snapshot_discard.called)
        snapshot_meld = snapshot_state.current_round.melds[1][0]
        self.assertEqual(snapshot_meld.tiles_136, [12, 13, 14])
        self.assertEqual(snapshot_event.attrs["nested"]["tiles"], [12, 13, 14])

    def test_async_persist_snapshot_can_skip_when_live_state_lock_is_busy(self) -> None:
        state = CaptureState()
        round_state = RoundState(started_from_init_like=True, round_id="round-busy")
        state.current_round = round_state
        state.rounds.append(round_state)
        state.sync_current_round_context()
        event = Event(timestamp=1.0, event_type="discard", seat=0)
        state.events.append(event)
        round_state.events.append(event)

        lock_acquired = threading.Event()
        release_lock = threading.Event()

        def _hold_state_lock() -> None:
            with state.state_lock:
                lock_acquired.set()
                release_lock.wait(timeout=2.0)

        holder_thread = threading.Thread(target=_hold_state_lock, daemon=True)
        holder_thread.start()
        self.assertTrue(lock_acquired.wait(timeout=1.0))
        try:
            snapshot = _snapshot_capture_state_for_async_persist(
                state,
                event,
                blocking=False,
            )
        finally:
            release_lock.set()
            holder_thread.join(timeout=1.0)

        self.assertIsNone(snapshot)


if __name__ == "__main__":
    unittest.main()
