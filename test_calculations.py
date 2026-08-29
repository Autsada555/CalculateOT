"""Regression tests for Calculate OT's payroll rules.

Run with: python -m unittest test_calculations.py
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import database as db


class PayrollRuleTests(unittest.TestCase):
    def test_white_day(self) -> None:
        # 30,000 / 30 / 8 = 125 per hour
        result = db.calculate_pay(30_000, 10, "WHITE")
        self.assertEqual(result["regular_pay"], 1_000)
        self.assertEqual(result["overtime_pay"], 375)  # 2 × 125 × 1.5
        self.assertEqual(result["total_pay"], 1_375)

    def test_traditional_holiday(self) -> None:
        result = db.calculate_pay(30_000, 8, "BLUE")
        self.assertEqual(result["regular_hours"], 0)
        self.assertEqual(result["overtime_pay"], 3_000)  # 8 × 125 × 3

    def test_weekly_and_company_holiday(self) -> None:
        for day_type in ("ORANGE", "GREEN"):
            result = db.calculate_pay(30_000, 10, day_type)
            self.assertEqual(result["regular_pay"], 1_000)
            self.assertEqual(result["overtime_pay"], 750)  # 2 × 125 × 3
            self.assertEqual(result["total_pay"], 1_750)

    def test_monthly_aggregation(self) -> None:
        original_path = db.DB_PATH
        with tempfile.TemporaryDirectory() as temp_dir:
            db.DB_PATH = Path(temp_dir) / "test.db"
            try:
                db.init_db()
                db.save_employee("EMP001", "Test Employee", 30_000)
                employee = db.get_employees()[0]
                db.save_attendance(employee["id"], "2026-01-05", 10, "WHITE")
                db.save_attendance(employee["id"], "2026-01-06", 8, "BLUE")
                self.assertEqual(db.generate_monthly_payroll("2026-01"), 1)
                summary = db.get_payroll_summary("2026-01")[0]
                self.assertEqual(summary["regular_pay"], 1_000)
                self.assertEqual(summary["overtime_pay"], 3_375)
                self.assertEqual(summary["total_pay"], 4_375)
            finally:
                db.DB_PATH = original_path

    def test_tax_estimate_uses_progressive_brackets(self) -> None:
        result = db.calculate_tax(600_000)
        self.assertEqual(result["gross_income"], 600_000)
        self.assertEqual(result["taxable_income"], 440_000)
        self.assertEqual(result["estimated_tax"], 21_500)

    def test_payroll_period_closes_on_day_fifteen(self) -> None:
        self.assertEqual(db.payroll_period("2026-08"), ("2026-07-16", "2026-08-15"))
        self.assertEqual(db.payroll_period("2026-01"), ("2025-12-16", "2026-01-15"))


if __name__ == "__main__":
    unittest.main()
