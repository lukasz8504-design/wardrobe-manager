import unittest
from datetime import datetime, timedelta
import os
import sys
import types
from tempfile import NamedTemporaryFile

if "tkinter" not in sys.modules:
    tkinter_stub = types.ModuleType("tkinter")
    tkinter_stub.NORMAL = "normal"
    tkinter_stub.DISABLED = "disabled"
    tkinter_stub.END = "end"
    tkinter_stub.messagebox = types.SimpleNamespace(
        showerror=lambda *args, **kwargs: None,
        showwarning=lambda *args, **kwargs: None,
        showinfo=lambda *args, **kwargs: None,
    )
    sys.modules["tkinter"] = tkinter_stub

from wardrobe_manager import (
    UNKNOWN_OPERATOR_ID,
    WardrobeManager,
    calculate_remaining_time,
    format_history_entry,
    parse_history_line,
    validate_operator_id,
)


class FakeEntry:
    def __init__(self, value=""):
        self.value = value
        self.state = "normal"

    def get(self):
        return self.value

    def delete(self, start, end):
        self.value = ""

    def config(self, **kwargs):
        if "state" in kwargs:
            self.state = kwargs["state"]

    def focus_set(self):
        pass


class FakeLabel:
    def __init__(self):
        self.props = {}

    def config(self, **kwargs):
        self.props.update(kwargs)


class FakeRoot:
    def focus_set(self):
        pass


class TimerCalculationTests(unittest.TestCase):
    def build_flow_manager(self, jig_value="", operator_value=""):
        manager = WardrobeManager.__new__(WardrobeManager)
        manager.root = FakeRoot()
        manager.jig_entry = FakeEntry(jig_value)
        manager.operator_entry = FakeEntry(operator_value)
        manager.status_label = FakeLabel()
        manager.current_jig = None
        manager.current_operator_id = None
        manager.input_stage = "jig"
        manager.history_file = "/tmp/history.txt"
        manager.state_file = "/tmp/state.json"
        manager.initial_time = 100
        manager.wardrobe_state = {}
        manager.jig_timers = {}
        manager.jig_insertion_times = {}
        manager.timer_threads = {}
        manager.expired_jigs = set()
        manager.jig_operator_ids = {}
        manager.update_display = lambda: None
        manager.save_state = lambda: None
        manager.start_jig_timer = lambda pos_key: None
        manager.save_to_history = lambda *args, **kwargs: None
        return manager

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

    def test_history_entry_formatter_rejects_invalid_operator_id(self):
        with self.assertRaises(ValueError):
            format_history_entry(7, 0, 1, 0, 1, operator_id="BAD!")

    def test_validate_operator_id_accepts_exactly_four_characters(self):
        self.assertEqual(validate_operator_id(" A1B2 "), "A1B2")

    def test_validate_operator_id_rejects_invalid_length(self):
        with self.assertRaises(ValueError):
            validate_operator_id("ABC")
        with self.assertRaises(ValueError):
            validate_operator_id("ABCDE")
        with self.assertRaises(ValueError):
            validate_operator_id("A-12")

    def test_input_jig_moves_to_operator_stage(self):
        manager = self.build_flow_manager(jig_value="12")

        manager.input_jig()

        self.assertEqual(manager.current_jig, 12)
        self.assertEqual(manager.input_stage, "operator")
        self.assertEqual(manager.jig_entry.state, "disabled")
        self.assertEqual(manager.operator_entry.state, "normal")

    def test_input_operator_rejects_invalid_id_and_keeps_operator_stage(self):
        messages = []
        from wardrobe_manager import messagebox

        original_showerror = messagebox.showerror
        messagebox.showerror = lambda title, msg: messages.append(msg)
        try:
            manager = self.build_flow_manager(operator_value="A-12")
            manager.current_jig = 12
            manager.set_input_stage("operator")

            manager.input_operator()

            self.assertEqual(messages, ["OPERATOR ID musi mieć dokładnie 4 znaki alfanumeryczne"])
            self.assertEqual(manager.input_stage, "operator")
            self.assertIsNone(manager.current_operator_id)
        finally:
            messagebox.showerror = original_showerror

    def test_input_operator_moves_to_position_stage_for_valid_id(self):
        manager = self.build_flow_manager(operator_value="AB12")
        manager.current_jig = 12
        manager.set_input_stage("operator")

        manager.input_operator()

        self.assertEqual(manager.current_operator_id, "AB12")
        self.assertEqual(manager.input_stage, "position")
        self.assertEqual(manager.operator_entry.state, "disabled")

    def test_select_position_requires_operator_id(self):
        warnings = []
        from wardrobe_manager import messagebox

        original_showwarning = messagebox.showwarning
        messagebox.showwarning = lambda title, msg: warnings.append(msg)
        try:
            manager = self.build_flow_manager()
            manager.current_jig = 12
            manager.current_operator_id = None

            manager.select_position(0, 0, 0, 0)

            self.assertEqual(warnings, ["Najpierw wprowadź OPERATOR ID"])
            self.assertEqual(manager.wardrobe_state, {})
        finally:
            messagebox.showwarning = original_showwarning

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

    def test_load_history_keeps_missing_operator_id_for_legacy_entries(self):
        with NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as history:
            history.write(
                "[01-01-2026 12:00:00] JIG #7 -> "
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
            self.assertEqual(manager.jig_operator_ids, {})
        finally:
            os.unlink(history_file)

    def test_clear_all_uses_fallback_operator_id_for_legacy_history(self):
        with NamedTemporaryFile(mode="w+", encoding="utf-8", delete=False) as history:
            history.write(
                "[01-01-2026 12:00:00] JIG #7 -> "
                "Półka 1, Rząd 1, Kolumna 1, Pozycja 1\n"
            )
            history_file = history.name
        try:
            manager = WardrobeManager.__new__(WardrobeManager)
            manager.history_file = history_file
            manager.wardrobe_state = {}
            manager.jig_timers = {}
            manager.jig_insertion_times = {}
            manager.timer_threads = {}
            manager.expired_jigs = set()
            manager.jig_operator_ids = {}
            manager.jig_entry = FakeEntry()
            manager.operator_entry = FakeEntry()
            manager.status_label = FakeLabel()
            manager.update_display = lambda: None
            manager.save_state = lambda: None
            manager.current_jig = None
            manager.current_operator_id = None

            manager.load_history()
            manager.clear_all()

            with open(history_file, encoding="utf-8") as saved_history:
                lines = saved_history.read().splitlines()

            self.assertEqual(len(lines), 2)
            self.assertEqual(
                lines[0],
                "[01-01-2026 12:00:00] JIG #7 -> Półka 1, Rząd 1, Kolumna 1, Pozycja 1",
            )
            self.assertIn(f"JIG #7 | OPERATOR ID: {UNKNOWN_OPERATOR_ID} <-", lines[-1])
        finally:
            os.unlink(history_file)

    def test_select_position_remove_uses_current_operator_id(self):
        with NamedTemporaryFile(mode="w+", encoding="utf-8", delete=False) as history:
            history_path = history.name
        try:
            manager = WardrobeManager.__new__(WardrobeManager)
            manager.history_file = history_path
            manager.state_file = "/tmp/wardrobe-state.json"
            manager.initial_time = 100
            manager.wardrobe_state = {(0, 0, 0, 0): 7}
            manager.jig_timers = {(0, 0, 0, 0): 6000}
            manager.jig_insertion_times = {(0, 0, 0, 0): datetime(2026, 1, 1, 12, 0, 0)}
            manager.timer_threads = {}
            manager.expired_jigs = set()
            manager.jig_operator_ids = {(0, 0, 0, 0): "OLD1"}
            manager.current_jig = 99
            manager.current_operator_id = "NEW2"
            manager.jig_entry = FakeEntry()
            manager.operator_entry = FakeEntry()
            manager.status_label = FakeLabel()
            manager.update_display = lambda: None
            manager.save_state = lambda: None
            manager.input_stage = "position"

            manager.select_position(0, 0, 0, 0)

            with open(history_path, encoding="utf-8") as saved_history:
                line = saved_history.read().strip()

            self.assertIn("JIG #7 | OPERATOR ID: NEW2 <-", line)
        finally:
            os.unlink(history_path)


if __name__ == "__main__":
    unittest.main()
