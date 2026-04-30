from __future__ import annotations

import shutil
import sys
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
TEST_TMP_ROOT = WORKSPACE_ROOT / "tmp_test_player_profiles"
SRC_DIR = WORKSPACE_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from capture.state import CaptureState
from capture.storage import CsvDatabase


class PlayerProfileStorageTest(unittest.TestCase):
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
            yield temp_dir
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

    def test_upsert_player_profile_preserves_source_url_when_updating_memo(self) -> None:
        with self._temporary_db_dir() as temp_dir:
            database = CsvDatabase(db_dir=temp_dir, bootstrap_logical_tables=("player_profiles",))
            self.addCleanup(database.close)

            database.upsert_player_profile(
                "opp-a",
                source_url="https://tenhou.net/0/?log=test-log",
            )
            database.upsert_player_profile(
                "opp-a",
                user_memo="メモ更新",
            )

            profile = database.get_player_profile("opp-a")

        self.assertEqual(profile["user_memo"], "メモ更新")
        self.assertEqual(profile["source_url"], "https://tenhou.net/0/?log=test-log")

    def test_ensure_player_profiles_keeps_existing_source_url(self) -> None:
        with self._temporary_db_dir() as temp_dir:
            database = CsvDatabase(db_dir=temp_dir, bootstrap_logical_tables=("player_profiles",))
            self.addCleanup(database.close)

            database.upsert_player_profile(
                "opp-b",
                source_url="https://tenhou.net/0/?log=existing-log",
            )
            state = CaptureState()
            state.players[0].name = "self"
            state.players[1].name = "opp-b"
            state.players[2].name = "opp-c"
            state.players[3].name = "opp-d"

            database._ensure_player_profiles(state, None)

            profile = database.get_player_profile("opp-b")

        self.assertEqual(profile["source_url"], "https://tenhou.net/0/?log=existing-log")

    def test_import_xml_discard_hands_writes_source_url_to_all_player_profiles(self) -> None:
        with self._temporary_db_dir() as temp_dir:
            database = CsvDatabase(db_dir=temp_dir)
            self.addCleanup(database.close)

            database._store("hanchan_master").upsert(
                {
                    "hanchan_id": "20260422010101",
                    "room_class_label": "",
                    "seat0_player_name": "self",
                    "seat1_player_name": "opp-a",
                    "seat2_player_name": "opp-b",
                    "seat3_player_name": "opp-c",
                    "source_url": "",
                }
            )
            state = CaptureState()
            state.seat_mapping_resolved = True
            state.game_id = "20260422gm-0009-0000-test0000"
            state.players[0].name = "self"
            state.players[1].name = "opp-a"
            state.players[2].name = "opp-b"
            state.players[3].name = "opp-c"

            with patch(
                "capture.storage.load_xml_discard_snapshots",
                return_value=(state, []),
            ):
                database.import_xml_discard_hands(
                    "<xml />",
                    hanchan_date_override="20260422",
                    source_url="https://tenhou.net/0/?log=imported-log",
                )

            profiles = {
                player_name: database.get_player_profile(player_name)
                for player_name in ("self", "opp-a", "opp-b", "opp-c")
            }

        self.assertEqual(
            profiles["self"]["source_url"],
            "https://tenhou.net/0/?log=imported-log",
        )
        self.assertEqual(
            profiles["opp-a"]["source_url"],
            "https://tenhou.net/0/?log=imported-log",
        )
        self.assertEqual(
            profiles["opp-b"]["source_url"],
            "https://tenhou.net/0/?log=imported-log",
        )
        self.assertEqual(
            profiles["opp-c"]["source_url"],
            "https://tenhou.net/0/?log=imported-log",
        )


if __name__ == "__main__":
    unittest.main()
