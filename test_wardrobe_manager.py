import unittest
from datetime import datetime, timedelta
import os
from tempfile import NamedTemporaryFile

from wardrobe_manager import (
    WardrobeManager,
    calculate_remaining_time,
    is_valid_operator_number,
    parse_history_line,
)


class TimerCalculationTests(unittest.TestCase):
    def test_operator_number_must_have_exactly_four_characters(self):
        self.assertFalse(is_valid_operator_number("123"))
        self.assertTrue(is_valid_operator_number("1234"))
        self.assertFalse(is_valid_operator_number("12345"))

    def test_confirming_jig_number_focuses_operator_field(self):
        class OperatorEntry:
            def __init__(self):
                self.focused = False

            def focus_set(self):
                self.focused = True

        manager = WardrobeManager.__new__(WardrobeManager)
        manager.operator_entry = OperatorEntry()

        self.assertEqual(manager.focus_operator_entry(), "break")
        self.assertTrue(manager.operator_entry.focused)

    def test_remaining_time_uses_elapsed_time(self):
        inserted = datetime(2026, 1, 1, 12, 0, 0)
        now = inserted + timedelta(minutes=12, seconds=30)
        self.assertEqual(calculate_remaining_time(inserted, 100, now), 5250)

    def test_expired_time_is_zero(self):
        inserted = datetime(2026, 1, 1, 12, 0, 0)
        now = inserted + timedelta(minutes=100, seconds=1)
        self.assertEqual(calculate_remaining_time(inserted, 100, now), 0)

    def test_history_parses_insert_and_remove_events(self):
        line = "[01-01-2026 12:00:00] JIG #7 <- Shelf 1, Row 2, Column 1, Position 2"
        event = parse_history_line(line)
        self.assertEqual(event["action"], "remove")
        self.assertEqual(event["position"], (0, 1, 0, 1))

    def test_history_parses_jig_position_change(self):
        line = (
            "[01-01-2026 12:00:00] JIG #7 ~> Shelf 1, Row 1, Column 2, "
            "Position 1 -> Shelf 1, Row 1, Column 1, Position 1"
        )
        event = parse_history_line(line)
        self.assertEqual(event["action"], "move")
        self.assertEqual(event["from_position"], (0, 0, 1, 0))
        self.assertEqual(event["position"], (0, 0, 0, 0))

    def test_remaining_time_can_be_restored_from_history_timestamp(self):
        inserted = datetime(2026, 1, 1, 12, 0, 0)
        current = datetime(2026, 1, 1, 13, 39, 30)
        self.assertEqual(calculate_remaining_time(inserted, 100, current), 30)

    def test_startup_marks_expired_jig_as_not_removed(self):
        manager = WardrobeManager.__new__(WardrobeManager)
        manager.wardrobe_state = {(0, 0, 0, 0): 7}
        manager.jig_insertion_times = {
            (0, 0, 0, 0): datetime(2026, 1, 1, 12, 0, 0)
        }
        manager.jig_timers = {}
        manager.timer_threads = {}
        manager.expired_jigs = set()
        manager.initial_time = 100
        manager.update_display = lambda: None

        manager.start_all_timers(datetime(2026, 1, 1, 13, 40, 1))

        self.assertEqual(manager.jig_timers[(0, 0, 0, 0)], 0)
        self.assertIn((0, 0, 0, 0), manager.expired_jigs)

    def test_clicking_expired_jig_removes_it_and_records_history(self):
        class StatusLabel:
            def config(self, **kwargs):
                self.options = kwargs

        with NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as history:
            history_file = history.name
        try:
            pos_key = (0, 0, 0, 0)
            manager = WardrobeManager.__new__(WardrobeManager)
            manager.current_jig = None
            manager.wardrobe_state = {pos_key: 7}
            manager.jig_timers = {pos_key: 0}
            manager.jig_insertion_times = {pos_key: datetime(2026, 1, 1, 12, 0, 0)}
            manager.timer_threads = {pos_key: None}
            manager.expired_jigs = {pos_key}
            manager.history_file = history_file
            manager.empty_sound_file = ""
            manager.status_label = StatusLabel()
            manager.save_state = lambda: None
            manager.update_display = lambda: None

            manager.select_position(*pos_key)

            self.assertEqual(manager.wardrobe_state, {})
            self.assertNotIn(pos_key, manager.expired_jigs)
            with open(history_file, encoding="utf-8") as history:
                self.assertIn("JIG #7 <-", history.read())
        finally:
            os.unlink(history_file)

    def test_moving_jig_preserves_insertion_time_and_records_history(self):
        with NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as history:
            history_file = history.name
        try:
            source = (0, 0, 1, 0)
            destination = (0, 0, 0, 0)
            inserted_at = datetime(2026, 1, 1, 12, 0, 0)
            manager = WardrobeManager.__new__(WardrobeManager)
            manager.wardrobe_state = {source: 7}
            manager.jig_timers = {source: 30}
            manager.jig_insertion_times = {source: inserted_at}
            manager.timer_threads = {}
            manager.expired_jigs = set()
            manager.warning_sound_played = set()
            manager.history_file = history_file

            manager.move_jig_to_previous_column(0, 0, 0)

            self.assertEqual(manager.wardrobe_state, {destination: 7})
            self.assertEqual(manager.jig_timers[destination], 30)
            self.assertEqual(manager.jig_insertion_times[destination], inserted_at)
            with open(history_file, encoding="utf-8") as history:
                self.assertIn("JIG #7 ~>", history.read())
        finally:
            os.unlink(history_file)

    def test_history_restores_original_time_after_jig_position_change(self):
        with NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as history:
            history.write(
                "[01-01-2026 12:00:00] JIG #7 -> Półka 1, Rząd 1, Kolumna 2, Pozycja 1\n"
            )
            history.write(
                "[01-01-2026 12:30:00] JIG #7 ~> Półka 1, Rząd 1, Kolumna 2, "
                "Pozycja 1 -> Półka 1, Rząd 1, Kolumna 1, Pozycja 1\n"
            )
            history_file = history.name
        try:
            destination = (0, 0, 0, 0)
            manager = WardrobeManager.__new__(WardrobeManager)
            manager.history_file = history_file
            manager.wardrobe_state = {}
            manager.jig_timers = {}
            manager.jig_insertion_times = {}
            manager.timer_threads = {}
            manager.expired_jigs = set()
            manager.initial_time = 100
            manager.update_display = lambda: None
            manager.start_jig_timer = lambda pos_key: None

            manager.load_history()
            manager.start_all_timers(datetime(2026, 1, 1, 13, 0, 0))

            self.assertEqual(manager.wardrobe_state, {destination: 7})
            self.assertEqual(
                manager.jig_insertion_times[destination],
                datetime(2026, 1, 1, 12, 0, 0)
            )
            self.assertEqual(manager.jig_timers[destination], 2400)
            self.assertNotIn((0, 0, 1, 0), manager.wardrobe_state)
        finally:
            os.unlink(history_file)

    def test_empty_history_does_not_restore_saved_jigs(self):
        with NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as history:
            history_file = history.name
        try:
            manager = WardrobeManager.__new__(WardrobeManager)
            manager.history_file = history_file
            manager.wardrobe_state = {(0, 0, 0, 0): 7}
            manager.jig_timers = {(0, 0, 0, 0): 6000}
            manager.jig_insertion_times = {
                (0, 0, 0, 0): datetime(2026, 1, 1, 12, 0, 0)
            }
            manager.expired_jigs = {(0, 0, 0, 0)}

            manager.load_history()

            self.assertEqual(manager.wardrobe_state, {})
            self.assertEqual(manager.jig_timers, {})
            self.assertEqual(manager.jig_insertion_times, {})
            self.assertEqual(manager.expired_jigs, set())
        finally:
            os.unlink(history_file)

    def test_missing_history_does_not_restore_saved_jigs(self):
        manager = WardrobeManager.__new__(WardrobeManager)
        manager.history_file = "history-file-that-does-not-exist.txt"
        manager.wardrobe_state = {(0, 0, 0, 0): 7}
        manager.jig_timers = {(0, 0, 0, 0): 6000}
        manager.jig_insertion_times = {
            (0, 0, 0, 0): datetime(2026, 1, 1, 12, 0, 0)
        }
        manager.expired_jigs = {(0, 0, 0, 0)}

        manager.load_history()

        self.assertEqual(manager.wardrobe_state, {})


if __name__ == "__main__":
    unittest.main()
