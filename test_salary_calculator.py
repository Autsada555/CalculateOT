"""Monthly quick-calculator tests, independent of SQLite and employee setup."""

from datetime import date, datetime
import unittest
from unittest.mock import patch

import database as db
from salary_calculator import calculate_monthly_salary


def work(day: str, hours: float, kind: str) -> dict:
    return {"work_date": day, "working_hours": hours, "day_type": kind}


class MonthlySalaryTests(unittest.TestCase):
    def test_salary_allowances_and_deductions_need_no_employee(self):
        with patch.object(db, "get_connection", side_effect=AssertionError("Database accessed")):
            result = calculate_monthly_salary(
                30_000,
                {"ค่าตำแหน่ง": 1_500, "ค่าเดินทาง": 800, "เบี้ยขยัน": 500},
                {"ประกันสังคม": 875, "รายการหักอื่น": 125},
            )
        self.assertEqual(result["salary"], 30_000)
        self.assertEqual(result["hourly_rate"], 125)
        self.assertEqual(result["total_income"], 2_800)
        self.assertEqual(result["additional_work_pay"], 0)
        self.assertEqual(result["gross_pay"], 32_800)
        self.assertEqual(result["total_deductions"], 1_000)
        self.assertEqual(result["net_pay"], 31_800)
        self.assertEqual(result["entries"], [])

    def test_normal_days_do_not_double_count_monthly_regular_wages(self):
        result = calculate_monthly_salary(30_000, work_entries=[
            work("2026-01-05", 8, "WHITE"), work("2026-01-06", 10, "WHITE"),
        ])
        self.assertEqual(result["additional_work_pay"], 375)
        self.assertEqual(result["net_pay"], 30_375)
        self.assertEqual(result["holiday_pay"], 0)
        self.assertEqual(result["entries"][0]["regular_pay"], 1_000)
        self.assertEqual(result["entries"][0]["additional_work_pay"], 0)

    def test_traditional_holiday_uses_existing_three_times_policy(self):
        result = calculate_monthly_salary(30_000, work_entries=[work("2026-01-01", 8, "BLUE")])
        self.assertEqual(result["additional_work_pay"], 3_000)
        self.assertEqual(result["overtime_pay"], 3_000)
        self.assertEqual(result["holiday_pay"], 0)
        self.assertEqual(result["net_pay"], 33_000)

    def test_weekly_and_company_holidays_add_regular_and_overtime_pay(self):
        for kind in ("ORANGE", "GREEN"):
            with self.subTest(kind=kind):
                result = calculate_monthly_salary(30_000, work_entries=[work("2026-01-03", 10, kind)])
                self.assertEqual(result["holiday_pay"], 1_000)
                self.assertEqual(result["overtime_pay"], 750)
                self.assertEqual(result["additional_work_pay"], 1_750)
                self.assertEqual(result["net_pay"], 31_750)

    def test_combined_estimate_and_zero_hours(self):
        result = calculate_monthly_salary(30_000, {"Extra": 500}, {"Deduction": 750}, [
            work("2026-01-01", 8, "BLUE"), work("2026-01-03", 10, "ORANGE"),
            work("2026-01-05", 10, "WHITE"), work("2026-01-06", 0, "GREEN"),
        ])
        self.assertEqual(result["overtime_pay"], 4_125)
        self.assertEqual(result["holiday_pay"], 1_000)
        self.assertEqual(result["additional_work_pay"], 5_125)
        self.assertEqual(result["gross_pay"], 35_625)
        self.assertEqual(result["net_pay"], 34_875)
        self.assertEqual(result["entries"][-1]["additional_work_pay"], 0)

    def test_custom_overtime_rates_are_aggregated_per_day(self):
        result = calculate_monthly_salary(30_000, work_entries=[{
            "work_date": "2026-01-05",
            "working_hours": 4,
            "day_type": "WHITE",
            "rate_hours": {1: 1, 1.5: 2, 2: 0.5, 3: 0.5},
        }])
        self.assertEqual(result["additional_work_pay"], 812.50)
        self.assertEqual(result["entries"][0]["rate_hours"][1.5], 2)

    def test_custom_overtime_rates_cannot_exceed_24_hours(self):
        with self.assertRaisesRegex(ValueError, "no more than 24 hours"):
            calculate_monthly_salary(30_000, work_entries=[{
                "work_date": "2026-01-05",
                "working_hours": 24,
                "day_type": "WHITE",
                "rate_hours": {1: 24, 1.5: 1},
            }])

    def test_monthly_overtime_rates_allow_up_to_200_hours(self):
        result = calculate_monthly_salary(30_000, rate_hours={1.5: 200})
        self.assertEqual(result["rate_hours"], {1.5: 200})
        with self.assertRaisesRegex(ValueError, "no more than 200 hours"):
            calculate_monthly_salary(30_000, rate_hours={1.5: 200, 1: 0.5})

    def test_decimal_items_round_consistently_to_cents(self):
        result = calculate_monthly_salary(1_000.005, {"A": 0.105, "B": 0.105}, {"C": 0.105})
        self.assertEqual(result["salary"], 1_000.01)
        self.assertEqual(result["incomes"], {"A": 0.11, "B": 0.11})
        self.assertEqual(result["total_income"], 0.22)
        self.assertEqual(result["gross_pay"], 1_000.23)
        self.assertEqual(result["net_pay"], 1_000.12)

    def test_daily_rounding_preserves_existing_policy_and_reconciles_components(self):
        entries = [work(f"2026-01-{day:02}", 10.27, "ORANGE") for day in range(1, 20)]
        result = calculate_monthly_salary(12_345.67, work_entries=entries)
        expected = db.calculate_pay(12_345.67, 10.27, "ORANGE")
        for field, value in expected.items():
            self.assertEqual(result["entries"][0][field], value)
        self.assertEqual(result["additional_work_pay"], round(expected["total_pay"] * 19, 2))
        self.assertEqual(round(result["holiday_pay"] + result["overtime_pay"], 2), result["additional_work_pay"])

    def test_deductions_can_exceed_income_without_silently_clipping(self):
        self.assertEqual(calculate_monthly_salary(0, deductions={"Advance": 100})["net_pay"], -100)

    def test_date_alias_and_date_objects(self):
        result = calculate_monthly_salary(30_000, work_entries=[
            {"date": date(2026, 1, 5), "working_hours": 10, "day_type": "WHITE"},
            {"date": datetime(2026, 1, 6, 12), "working_hours": 8, "day_type": "WHITE"},
        ])
        self.assertEqual([entry["work_date"] for entry in result["entries"]], ["2026-01-05", "2026-01-06"])

    def test_invalid_amounts_are_rejected(self):
        for value in (-1, float("nan"), float("inf"), float("-inf"), None, True, "bad"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    calculate_monthly_salary(value)
                with self.assertRaises(ValueError):
                    calculate_monthly_salary(30_000, {"A": value})
                with self.assertRaises(ValueError):
                    calculate_monthly_salary(30_000, deductions={"A": value})

    def test_invalid_hours_and_types_are_rejected(self):
        for hours in (-1, 24.01, float("nan"), float("inf"), None, True):
            with self.subTest(hours=hours), self.assertRaises(ValueError):
                calculate_monthly_salary(30_000, work_entries=[work("2026-01-05", hours, "WHITE")])
        for kind in ("PINK", "white", None, []):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                calculate_monthly_salary(30_000, work_entries=[work("2026-01-05", 8, kind)])

    def test_invalid_or_duplicate_dates_are_rejected(self):
        for day in ("", "2026-02-30", None):
            with self.subTest(day=day), self.assertRaises(ValueError):
                calculate_monthly_salary(30_000, work_entries=[work(day, 8, "WHITE")])
        with self.assertRaisesRegex(ValueError, "Duplicate work date"):
            calculate_monthly_salary(30_000, work_entries=[
                work("2026-01-05", 10, "WHITE"), work(date(2026, 1, 5), 8, "WHITE"),
            ])
        with self.assertRaisesRegex(ValueError, "conflicting dates"):
            calculate_monthly_salary(30_000, work_entries=[{
                **work("2026-01-05", 10, "WHITE"), "date": "2026-01-06",
            }])


if __name__ == "__main__":
    unittest.main()
