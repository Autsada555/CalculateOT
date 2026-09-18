"""Check PDF totals and preserve local edits during calendar migration."""

from collections import Counter
from pathlib import Path
import tempfile
import unittest

import database as db
from calendar_reference import CALENDAR_2026, MONTHLY_TOTALS, reference_for


class CalendarReferenceTests(unittest.TestCase):
    def test_full_year_matches_pdf_monthly_and_annual_totals(self):
        self.assertEqual(len(CALENDAR_2026), 365)
        self.assertEqual(Counter(kind for kind, _ in CALENDAR_2026.values()),
                         {"WHITE": 256, "ORANGE": 84, "BLUE": 13, "GREEN": 12})
        for month, expected in MONTHLY_TOTALS.items():
            counts = Counter(kind for day, (kind, _) in CALENDAR_2026.items()
                             if day.startswith(f"2026-{month:02d}-"))
            self.assertEqual(tuple(counts[kind] for kind in ("WHITE", "ORANGE", "BLUE", "GREEN")), expected)

    def test_source_exceptions_and_scope(self):
        for day in ["2026-01-10", "2026-01-31", "2026-02-28", "2026-08-15", "2026-09-05", "2026-11-28"]:
            self.assertEqual(reference_for(day)["day_type"], "WHITE")
        self.assertEqual(reference_for("2026-12-28")["day_type"], "GREEN")
        self.assertEqual(reference_for("2026-07-29")["description"], "วันอาสาฬหบูชา")
        self.assertIsNone(reference_for("2027-01-01"))
        self.assertIsNone(reference_for("2025-12-16"))


class CalendarStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.temp.name) / "calendar-test.db"
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.original
        self.temp.cleanup()

    def test_overrides_win_and_delete_restores_source(self):
        day = "2026-09-05"
        self.assertEqual(db.day_type_for(day), "WHITE")
        db.save_calendar_date(day, "BLUE", "วันหยุดเพิ่มเติม")
        self.assertEqual(db.day_type_for(day), "BLUE")
        self.assertTrue(db.get_calendar_day(day)["is_override"])
        db.init_db()
        self.assertEqual(db.day_type_for(day), "BLUE")
        db.delete_calendar_date(day)
        self.assertEqual(db.day_type_for(day), "WHITE")
        self.assertFalse(db.get_calendar_day(day)["is_override"])
        self.assertEqual(db.get_calendar_dates(2026, 9), [])

    def test_migration_only_removes_unchanged_seeds_and_is_idempotent(self):
        with db.get_connection() as conn:
            conn.execute("DELETE FROM app_migrations")
            for day, (kind, description) in db.DEFAULT_2026_DATES.items():
                conn.execute("INSERT INTO calendar_dates(work_date, day_type, description) VALUES (?, ?, ?)",
                             (day, kind, description))
        db.save_calendar_date("2026-01-02", "WHITE", "วันทำงานที่กำหนดเอง")
        db.save_employee("TEST", "Test", 30000)
        employee = db.get_employees()[0]
        db.save_attendance(employee["id"], "2026-01-10", 8, "ORANGE")
        db.init_db()
        self.assertEqual(db.day_type_for("2026-01-02"), "WHITE")
        self.assertEqual(db.get_calendar_day("2026-07-29")["description"], "วันอาสาฬหบูชา")
        self.assertEqual(db.day_type_for("2026-12-28"), "GREEN")
        self.assertEqual(db.get_attendance()[0]["day_type"], "ORANGE")
        # An explicit edit matching an old seed after migration must survive.
        db.save_calendar_date("2026-07-29", *db.DEFAULT_2026_DATES["2026-07-29"])
        db.init_db()
        self.assertTrue(db.get_calendar_day("2026-07-29")["is_override"])

    def test_dates_outside_source_are_identified_as_fallback(self):
        self.assertEqual(db.get_calendar_day("2027-01-02")["source"], "weekend_fallback")
        self.assertEqual(db.day_type_for("2027-01-02"), "ORANGE")


if __name__ == "__main__":
    unittest.main()
