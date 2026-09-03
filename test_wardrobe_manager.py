import unittest
from datetime import datetime, timedelta

from wardrobe_manager import calculate_remaining_time, parse_history_line


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


if __name__ == "__main__":
    unittest.main()
