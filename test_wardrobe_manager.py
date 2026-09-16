import unittest
from datetime import datetime, timedelta
import os
import sys
from tempfile import NamedTemporaryFile
from tempfile import TemporaryDirectory
from types import ModuleType
from unittest.mock import patch

fake_messagebox = ModuleType("messagebox")
fake_messagebox.showerror = lambda *args, **kwargs: None
fake_messagebox.showwarning = lambda *args, **kwargs: None
fake_messagebox.askyesno = lambda *args, **kwargs: False

fake_tkinter = ModuleType("tkinter")
fake_tkinter.messagebox = fake_messagebox
fake_tkinter.END = "end"
fake_tkinter.BOTH = "both"
fake_tkinter.X = "x"
fake_tkinter.LEFT = "left"
fake_tkinter.SUNKEN = "sunken"
fake_tkinter.RAISED = "raised"

sys.modules.setdefault("tkinter", fake_tkinter)
sys.modules.setdefault("winsound", ModuleType("winsound"))

from wardrobe_manager import (
    WardrobeManager,
    calculate_remaining_time,
    is_valid_operator_number,
    load_config,
    parse_history_line,
)


class TimerCalculationTests(unittest.TestCase):
    def test_load_config_reads_toml_values(self):
        with TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.toml")
            with open(config_path, "w", encoding="utf-8") as config_file:
                config_file.write(
                    '[WARDROBE]\nnum_shelves = 4\nnum_rows = 2\nnum_columns = 5\n'
                    'squares_per_section = 3\n\n'
                    '[TIMER]\ninitial_time = 120\norange_threshold = 8\nred_threshold = 2\n\n'
                    '[COLORS]\nnormal_bg = "#111111"\norange_bg = "#222222"\nred_bg = "#333333"\n'
                    'normal_text = "#444444"\norange_text = "#555555"\nred_text = "#666666"\n'
                    'empty_bg = "#777777"\nempty_text = "#888888"\nblink_red_bg = "#999999"\n'
                    'blink_orange_bg = "#AAAAAA"\nblink_text = "#BBBBBB"\n\n'
                    '[APPEARANCE]\nsquare_width = 9\nsquare_height = 4\nsquare_font_size = 12\n\n'
                    '[WARDROBE_TITLE]\ntext = "LINE-01"\ncolor = "#123456"\nfont_size = 14\n\n'
                    '[ALERTS]\nnear_expiry_seconds = 45\nblink_interval_ms = 700\n\n'
                    '[SOUNDS]\nempty_sound_file = ""\noccupied_sound_file = "occupied.wav"\n'
                    'expired_sound_file = "expired.wav"\n\n'
                    '[FILES]\nhistory_file = "custom-history.txt"\nstate_file = "custom-state.json"\n'
                )

            config = load_config(config_path)

            self.assertEqual(config["WARDROBE"]["num_shelves"], 4)
            self.assertEqual(config["COLORS"]["normal_bg"], "#111111")
            self.assertEqual(config["WARDROBE_TITLE"]["text"], "LINE-01")
            self.assertEqual(config["FILES"]["state_file"], "custom-state.json")

    def test_manager_initialization_uses_toml_config(self):
        class RootStub:
            def title(self, value):
                self.title_value = value

            def state(self, value):
                self.state_value = value

            def resizable(self, width, height):
                self.resizable_value = (width, height)

        with TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.toml")
            with open(config_path, "w", encoding="utf-8") as config_file:
                config_file.write(
                    '[WARDROBE]\nnum_shelves = 2\nnum_rows = 1\nnum_columns = 3\n'
                    'squares_per_section = 2\n\n'
                    '[TIMER]\ninitial_time = 90\norange_threshold = 6\nred_threshold = 1\n\n'
                    '[COLORS]\nnormal_bg = "#101010"\norange_bg = "#202020"\nred_bg = "#303030"\n'
                    'normal_text = "#404040"\norange_text = "#505050"\nred_text = "#606060"\n'
                    'empty_bg = "#707070"\nempty_text = "#808080"\nblink_red_bg = "#909090"\n'
                    'blink_orange_bg = "#A0A0A0"\nblink_text = "#B0B0B0"\n\n'
                    '[APPEARANCE]\nsquare_width = 11\nsquare_height = 5\nsquare_font_size = 15\n\n'
                    '[WARDROBE_TITLE]\ntext = "QA-LINE"\ncolor = "#abcdef"\nfont_size = 18\n\n'
                    '[ALERTS]\nnear_expiry_seconds = 30\nblink_interval_ms = 250\n\n'
                    '[SOUNDS]\nempty_sound_file = "empty.wav"\noccupied_sound_file = ""\n'
                    'expired_sound_file = "expired.wav"\n\n'
                    '[FILES]\nhistory_file = "history-custom.txt"\nstate_file = "state-custom.json"\n'
                )

            current_dir = os.getcwd()
            os.chdir(temp_dir)
            try:
                with patch.object(WardrobeManager, "load_state", return_value={}), patch.object(
                    WardrobeManager, "load_history"
                ), patch.object(WardrobeManager, "setup_ui"), patch.object(
                    WardrobeManager, "start_all_timers"
                ), patch.object(
                    WardrobeManager, "schedule_expired_blink"
                ):
                    manager = WardrobeManager(RootStub())
            finally:
                os.chdir(current_dir)

        self.assertEqual(manager.num_shelves, 2)
        self.assertEqual(manager.initial_time, 90)
        self.assertEqual(manager.normal_bg, "#101010")
        self.assertEqual(manager.wardrobe_name, "QA-LINE")
        self.assertEqual(manager.near_expiry_seconds, 30)
        self.assertEqual(manager.empty_sound_file, "empty.wav")
        self.assertEqual(manager.history_file, "history-custom.txt")

    def test_apply_config_maps_toml_sections_to_attributes(self):
        manager = WardrobeManager.__new__(WardrobeManager)

        manager.apply_config(
            {
                "WARDROBE": {
                    "num_shelves": 6,
                    "num_rows": 2,
                    "num_columns": 4,
                    "squares_per_section": 3,
                },
                "TIMER": {
                    "initial_time": 80,
                    "orange_threshold": 7,
                    "red_threshold": 2,
                },
                "COLORS": {
                    "normal_bg": "#010101",
                    "orange_bg": "#020202",
                    "red_bg": "#030303",
                    "normal_text": "#040404",
                    "orange_text": "#050505",
                    "red_text": "#060606",
                    "empty_bg": "#070707",
                    "empty_text": "#080808",
                    "blink_red_bg": "#090909",
                    "blink_orange_bg": "#101010",
                    "blink_text": "#111111",
                },
                "APPEARANCE": {
                    "square_width": 12,
                    "square_height": 6,
                    "square_font_size": 16,
                },
                "WARDROBE_TITLE": {
                    "text": "ASSEMBLY",
                    "color": "#121212",
                    "font_size": 20,
                },
                "ALERTS": {
                    "near_expiry_seconds": 15,
                    "blink_interval_ms": 900,
                },
                "SOUNDS": {
                    "empty_sound_file": "empty.wav",
                    "occupied_sound_file": "occupied.wav",
                    "expired_sound_file": "expired.wav",
                },
                "FILES": {
                    "history_file": "history.log",
                    "state_file": "state.json",
                },
            }
        )

        self.assertEqual(manager.num_shelves, 6)
        self.assertEqual(manager.num_rows, 2)
        self.assertEqual(manager.num_columns, 4)
        self.assertEqual(manager.squares_per_section, 3)
        self.assertEqual(manager.initial_time, 80)
        self.assertEqual(manager.red_threshold, 2)
        self.assertEqual(manager.blink_text, "#111111")
        self.assertEqual(manager.jig_width, 12)
        self.assertEqual(manager.wardrobe_name, "ASSEMBLY")
        self.assertEqual(manager.blink_interval_ms, 900)
        self.assertEqual(manager.occupied_sound_file, "occupied.wav")
        self.assertEqual(manager.state_file, "state.json")

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
