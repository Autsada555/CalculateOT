"""Exercise the salary-first flow against a disposable database."""

from datetime import date
from pathlib import Path
import tempfile
import unittest

from streamlit.testing.v1 import AppTest

import database as db


class SalaryAppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_db = db.DB_PATH
        db.DB_PATH = Path(self.temp.name) / "app-test.db"
        self.app = AppTest.from_file(str(Path(__file__).with_name("app.py")), default_timeout=20)
        self.app.run()
        self.app.selectbox(key="payroll_month").select("2026-09").run()

    def tearDown(self):
        db.DB_PATH = self.original_db
        self.temp.cleanup()

    def assert_clean(self):
        self.assertEqual(len(self.app.exception), 0, str(self.app.exception))

    def test_salary_and_deductions_update_without_save_or_employee(self):
        self.app.number_input(key="quick_2026-09_salary").set_value(30000).run()
        self.app.number_input(key="quick_2026-09_food").set_value(1000).run()
        self.app.number_input(key="quick_2026-09_transport").set_value(500).run()
        self.app.number_input(key="quick_2026-09_social").set_value(875).run()
        self.assert_clean()
        self.assertEqual(self.app.metric[0].value, "฿30,625.00")
        self.assertEqual(db.get_employees(), [])
        self.assertEqual(db.get_attendance(), [])

    def test_ot_dates_use_calendar_and_do_not_double_count_salary(self):
        self.app.number_input(key="quick_2026-09_salary").set_value(30000).run()
        self.app.multiselect(key="quick_2026-09_dates").set_value([date(2026, 9, 7), date(2026, 9, 6)]).run()
        self.app.number_input(key="quick_2026-09_rate_1.5_hours").set_value(2).run()
        self.app.number_input(key="quick_2026-09_rate_1_hours").set_value(8).run()
        self.assert_clean()
        self.assertEqual(self.app.metric[0].value, "฿31,375.00")
        self.app.multiselect(key="quick_2026-09_dates").set_value([]).run()
        self.assertEqual(self.app.metric[0].value, "฿31,375.00")

    def test_draft_survives_calendar_navigation_and_month_switch(self):
        self.app.number_input(key="quick_2026-09_salary").set_value(31000).run()
        self.app.radio(key="navigation").set_value("Calendar").run()
        self.assert_clean()
        self.app.radio(key="navigation").set_value("Quick calculator").run()
        self.assertEqual(self.app.number_input(key="quick_2026-09_salary").value, 31000)
        self.app.selectbox(key="payroll_month").select("2026-08").run()
        self.assertEqual(self.app.number_input(key="quick_2026-08_salary").value, 0)
        self.app.selectbox(key="payroll_month").select("2026-09").run()
        self.assertEqual(self.app.number_input(key="quick_2026-09_salary").value, 31000)
        self.assert_clean()

    def test_existing_pages_open_with_empty_database(self):
        for page in ["Calendar", "Dashboard", "Employees", "Attendance", "Payroll", "Tax Calculator", "Reports"]:
            with self.subTest(page=page):
                self.app.radio(key="navigation").set_value(page).run()
                self.assert_clean()


if __name__ == "__main__":
    unittest.main()
