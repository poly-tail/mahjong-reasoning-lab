from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.main import NAGA_BUTTON_X, NAGA_BUTTON_Y
from ui.table_renderer import (
    ALERT_SOUND_BUTTON_X,
    ALERT_SOUND_BUTTON_Y,
    ALERT_SOUND_DEFAULT_ENABLED,
    ALERT_SOUND_ENABLED_CONFIRMATION_ASSET,
    ALERT_SOUND_ENABLED_CONFIRMATION_TONES,
    HAND_AUTO_BUTTON_OFF_FILL,
    HAND_AUTO_BUTTON_ON_FILL,
    HAND_SELF_ALERT_KIND_NONE,
    HAND_SELF_ALERT_KIND_WARNING,
    PLAYER_ALERT_YELLOW,
    PlayerAlertIndicator,
    SelfHandValueAlertState,
    _alert_sound_is_enabled,
    _play_alert_sound_enabled_confirmation_worker,
    _play_huuuro_alert_sound_if_needed,
    _play_meld_dora_alert_sound_if_needed,
    _play_player_panel_alert_sound_if_needed,
    _play_self_hand_value_alert_sound_if_needed,
    _refresh_alert_sound_button_widget,
    _resolve_alert_sound_button_presentation,
    _toggle_alert_sound,
)


class _ButtonStub:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}

    def configure(self, **options: object) -> None:
        self.options.update(options)


class AlertSoundToggleTest(unittest.TestCase):
    def test_alert_sound_button_uses_dedicated_top_left_slot(self) -> None:
        self.assertEqual((ALERT_SOUND_BUTTON_X, ALERT_SOUND_BUTTON_Y), (8, 92))
        self.assertNotEqual(
            (ALERT_SOUND_BUTTON_X, ALERT_SOUND_BUTTON_Y),
            (NAGA_BUTTON_X, NAGA_BUTTON_Y),
        )

    def test_alert_sound_starts_off_and_button_tracks_state(self) -> None:
        self.assertFalse(ALERT_SOUND_DEFAULT_ENABLED)
        self.assertEqual(
            _resolve_alert_sound_button_presentation(False),
            ("アラート音 OFF", HAND_AUTO_BUTTON_OFF_FILL),
        )
        self.assertEqual(
            _resolve_alert_sound_button_presentation(True),
            ("アラート音 ON", HAND_AUTO_BUTTON_ON_FILL),
        )

        button = _ButtonStub()
        canvas = SimpleNamespace(alert_sound_enabled=False, alert_sound_button=button)
        _refresh_alert_sound_button_widget(canvas)
        self.assertEqual(button.options["text"], "アラート音 OFF")
        self.assertEqual(button.options["bg"], HAND_AUTO_BUTTON_OFF_FILL)

        canvas.alert_sound_enabled = True
        _refresh_alert_sound_button_widget(canvas)
        self.assertEqual(button.options["text"], "アラート音 ON")
        self.assertEqual(button.options["bg"], HAND_AUTO_BUTTON_ON_FILL)

    def test_alert_sound_button_toggle_updates_state_and_presentation(self) -> None:
        button = _ButtonStub()
        canvas = SimpleNamespace(alert_sound_enabled=False, alert_sound_button=button)

        with patch("ui.table_renderer.winsound", object()), patch(
            "ui.table_renderer._queue_alert_sound_job",
            return_value=True,
        ) as queue_sound:
            self.assertTrue(_toggle_alert_sound(canvas))
            self.assertTrue(canvas.alert_sound_enabled)
            self.assertEqual(button.options["text"], "アラート音 ON")
            self.assertEqual(button.options["bg"], HAND_AUTO_BUTTON_ON_FILL)

            self.assertFalse(_toggle_alert_sound(canvas))
            self.assertFalse(canvas.alert_sound_enabled)
            self.assertEqual(button.options["text"], "アラート音 OFF")
            self.assertEqual(button.options["bg"], HAND_AUTO_BUTTON_OFF_FILL)

        queue_sound.assert_called_once_with(_play_alert_sound_enabled_confirmation_worker)

    def test_alert_sound_on_confirmation_uses_ascending_beeps(self) -> None:
        class WinsoundStub:
            SND_FILENAME = 0x00020000

            def __init__(self) -> None:
                self.beep_calls: list[tuple[int, int]] = []
                self.play_sound_calls: list[tuple[str, int]] = []

            def Beep(self, frequency_hz: int, duration_ms: int) -> None:
                self.beep_calls.append((frequency_hz, duration_ms))

            def MessageBeep(self) -> None:
                raise AssertionError("MessageBeep should not run when Beep succeeds")

            def PlaySound(self, path: str, flags: int) -> None:
                self.play_sound_calls.append((path, flags))

        winsound_stub = WinsoundStub()
        with patch("ui.table_renderer.winsound", winsound_stub):
            _play_alert_sound_enabled_confirmation_worker()

        self.assertEqual(
            winsound_stub.beep_calls,
            list(ALERT_SOUND_ENABLED_CONFIRMATION_TONES),
        )
        self.assertEqual(len(winsound_stub.play_sound_calls), 1)
        sound_path, flags = winsound_stub.play_sound_calls[0]
        self.assertTrue(sound_path.endswith(f"{ALERT_SOUND_ENABLED_CONFIRMATION_ASSET}.wav"))
        self.assertEqual(flags, WinsoundStub.SND_FILENAME)

    def test_alert_sound_on_confirmation_falls_back_to_canvas_bell(self) -> None:
        button = _ButtonStub()
        canvas = SimpleNamespace(
            alert_sound_enabled=False,
            alert_sound_button=button,
            bell_calls=0,
        )
        canvas.bell = lambda: setattr(canvas, "bell_calls", canvas.bell_calls + 1)

        with patch("ui.table_renderer.winsound", None):
            self.assertTrue(_toggle_alert_sound(canvas))

        self.assertEqual(canvas.bell_calls, 1)

    def test_muted_self_alert_is_not_replayed_when_sound_is_enabled(self) -> None:
        canvas = SimpleNamespace(
            alert_sound_enabled=False,
            last_self_hand_value_alert_kind=HAND_SELF_ALERT_KIND_NONE,
            last_self_low_ev_sound_round_token="",
            last_self_hand_alert_sound_monotonic_s=0.0,
        )
        warning = SelfHandValueAlertState(kind=HAND_SELF_ALERT_KIND_WARNING)

        with patch("ui.table_renderer.winsound", object()), patch(
            "ui.table_renderer._queue_alert_sound_job",
            return_value=True,
        ) as queue_sound:
            _play_self_hand_value_alert_sound_if_needed(canvas, warning)
            self.assertEqual(
                canvas.last_self_hand_value_alert_kind,
                HAND_SELF_ALERT_KIND_WARNING,
            )
            canvas.alert_sound_enabled = True
            _play_self_hand_value_alert_sound_if_needed(canvas, warning)

        queue_sound.assert_not_called()

    def test_muted_huuuro_alert_records_signature_without_playing_it_later(self) -> None:
        canvas = SimpleNamespace(
            alert_sound_enabled=False,
            huuuro_alert_sound_signatures=[],
            last_huuuro_alert_sound_signature=None,
            last_spectator_mode_alert_sound_signature=None,
        )

        with patch("ui.table_renderer.winsound", object()), patch(
            "ui.table_renderer._queue_alert_sound_job",
            return_value=True,
        ) as queue_sound:
            _play_huuuro_alert_sound_if_needed(canvas, "bridge", 1)
            canvas.alert_sound_enabled = True
            _play_huuuro_alert_sound_if_needed(canvas, "bridge", 1)
            _play_huuuro_alert_sound_if_needed(canvas, "bridge", 2)

        queue_sound.assert_called_once()

    def test_muted_panel_alert_tracks_transition_without_playback(self) -> None:
        canvas = SimpleNamespace(
            alert_sound_enabled=False,
            last_player_panel_alert_keys_by_seat={1: (), 2: (), 3: ()},
            last_player_panel_alert_sound_monotonic_s=0.0,
        )
        indicators = {
            1: (
                PlayerAlertIndicator(
                    color=PLAYER_ALERT_YELLOW,
                    label="Remain 11.8",
                    key="remain_yellow",
                ),
            )
        }

        with patch("ui.table_renderer.winsound", object()), patch(
            "ui.table_renderer._queue_alert_sound_job",
            return_value=True,
        ) as queue_sound:
            _play_player_panel_alert_sound_if_needed(
                canvas,
                {1: {"denominator_count": 11.8}},
                {1: {}},
                alert_indicators_by_seat=indicators,
            )
            canvas.alert_sound_enabled = True
            _play_player_panel_alert_sound_if_needed(
                canvas,
                {1: {"denominator_count": 11.8}},
                {1: {}},
                alert_indicators_by_seat=indicators,
            )

        queue_sound.assert_not_called()

    def test_muted_meld_dora_alert_tracks_threshold_without_playback(self) -> None:
        canvas = SimpleNamespace(
            alert_sound_enabled=False,
            last_meld_dora_alert_counts_by_seat={0: 0, 1: 0, 2: 0, 3: 0},
            last_meld_dora_alert_sound_monotonic_s=0.0,
        )
        threshold_counts = {0: 0, 1: 2, 2: 0, 3: 0}

        with patch(
            "ui.table_renderer._meld_dora_counts_by_player",
            return_value=threshold_counts,
        ), patch("ui.table_renderer.winsound", object()), patch(
            "ui.table_renderer._queue_alert_sound_job",
            return_value=True,
        ) as queue_sound:
            _play_meld_dora_alert_sound_if_needed(canvas, {}, ())
            self.assertEqual(canvas.last_meld_dora_alert_counts_by_seat, threshold_counts)
            canvas.alert_sound_enabled = True
            _play_meld_dora_alert_sound_if_needed(canvas, {}, ())

        queue_sound.assert_not_called()

    def test_explicit_canvas_flag_controls_audio_gate(self) -> None:
        self.assertFalse(_alert_sound_is_enabled(SimpleNamespace(alert_sound_enabled=False)))
        self.assertTrue(_alert_sound_is_enabled(SimpleNamespace(alert_sound_enabled=True)))


if __name__ == "__main__":
    unittest.main()
