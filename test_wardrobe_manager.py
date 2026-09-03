import unittest
from datetime import datetime, timedelta
import os
import sys
import types
from tempfile import NamedTemporaryFile

if "tkinter" not in sys.modules:
    tkinter_stub = types.ModuleType("tkinter")
    tkinter_stub.messagebox = types.SimpleNamespace(
        showerror=lambda *args, **kwargs: None,
        showwarning=lambda *args, **kwargs: None,
        showinfo=lambda *args, **kwargs: None,
    )
    sys.modules["tkinter"] = tkinter_stub

from wardrobe_manager import (
    WardrobeManager,
    calculate_remaining_time,
    format_history_entry,
    parse_history_line,
    validate_operator_id,
)


class TimerCalculationTests(unittest.TestCase):
    def test_remaining_time_uses_elapsed_time(self):
        inserted = datetime(2026, 1, 1, 12, 0, 0)
        now = inserted + timedelta(minutes=12, seconds=30)
        self.assertEqual(calculate_remaining_time(inserted, 100, now), 5250)

    def test_expired_time_is_zero(self):
        inserted = datetime(2026, 1, 1, 12, 0, 0)
        now = inserted + timedelta(minutes=100, seconds=1)
        self.assertEqual(calculate_remaining_time(inserted, 100, now), 0)

    def test_history_parses_insert_and_remove_events(self):
        line = "[01-01-2026 12:00:00] JIG #7 <- Półka 1, Rząd 2, Kolumna 1, Pozycja 2"
        event = parse_history_line(line)
        self.assertEqual(event["action"], "remove")
        self.assertEqual(event["position"], (0, 1, 0, 1))
        self.assertIsNone(event["operator_id"])

    def test_history_parses_operator_id_in_new_format(self):
        line = "[01-01-2026 12:00:00] JIG #7 | OPERATOR ID: A1B2 -> Półka 1, Rząd 2, Kolumna 1, Pozycja 2"
        event = parse_history_line(line)
        self.assertEqual(event["action"], "insert")
        self.assertEqual(event["operator_id"], "A1B2")
        self.assertEqual(event["position"], (0, 1, 0, 1))

    def test_history_entry_formatter_includes_operator_id(self):
        timestamp = datetime(2026, 1, 1, 12, 0, 0)
        line = format_history_entry(7, 0, 1, 0, 1, operator_id="A1B2", timestamp=timestamp)
        self.assertEqual(
            line,
            "[01-01-2026 12:00:00] JIG #7 | OPERATOR ID: A1B2 -> Półka 1, Rząd 2, Kolumna 1, Pozycja 2\n",
        )

    def test_validate_operator_id_accepts_exactly_four_characters(self):
        self.assertEqual(validate_operator_id(" A1B2 "), "A1B2")

    def test_validate_operator_id_rejects_invalid_length(self):
        with self.assertRaises(ValueError):
            validate_operator_id("ABC")
        with self.assertRaises(ValueError):
            validate_operator_id("ABCDE")

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
        manager.jig_operator_ids = {}
        manager.initial_time = 100
        manager.update_display = lambda: None

        manager.start_all_timers(datetime(2026, 1, 1, 13, 40, 1))

        self.assertEqual(manager.jig_timers[(0, 0, 0, 0)], 0)
        self.assertIn((0, 0, 0, 0), manager.expired_jigs)

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
            manager.jig_operator_ids = {(0, 0, 0, 0): "A1B2"}

            manager.load_history()

            self.assertEqual(manager.wardrobe_state, {})
            self.assertEqual(manager.jig_timers, {})
            self.assertEqual(manager.jig_insertion_times, {})
            self.assertEqual(manager.expired_jigs, set())
            self.assertEqual(manager.jig_operator_ids, {})
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
        manager.jig_operator_ids = {(0, 0, 0, 0): "A1B2"}

        manager.load_history()

        self.assertEqual(manager.wardrobe_state, {})

    def test_load_history_restores_operator_id_for_active_jig(self):
        with NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as history:
            history.write(
                "[01-01-2026 12:00:00] JIG #7 | OPERATOR ID: A1B2 -> "
                "Półka 1, Rząd 1, Kolumna 1, Pozycja 1\n"
            )
            history_file = history.name
        try:
            manager = WardrobeManager.__new__(WardrobeManager)
            manager.history_file = history_file
            manager.wardrobe_state = {}
            manager.jig_timers = {}
            manager.jig_insertion_times = {}
            manager.expired_jigs = set()
            manager.jig_operator_ids = {}

            manager.load_history()

            self.assertEqual(manager.wardrobe_state, {(0, 0, 0, 0): 7})
            self.assertEqual(manager.jig_operator_ids, {(0, 0, 0, 0): "A1B2"})
        finally:
            os.unlink(history_file)


if __name__ == "__main__":
    unittest.main()
