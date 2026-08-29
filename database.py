"""SQLite storage and payroll calculation rules for Calculate OT."""

from __future__ import annotations

import calendar
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

DB_PATH = Path(__file__).with_name("calculate_ot.db")
DAY_TYPES = ("WHITE", "BLUE", "ORANGE", "GREEN")

# Company and traditional holidays transcribed from the supplied 2026 calendar.
DEFAULT_2026_DATES = {
    "2026-01-01": ("BLUE", "New Year's Day"),
    "2026-01-02": ("BLUE", "New Year holiday"),
    "2026-02-14": ("GREEN", "Company holiday"),
    "2026-03-02": ("GREEN", "Company holiday"),
    "2026-03-03": ("BLUE", "Makha Bucha Day"),
    "2026-03-21": ("GREEN", "Company holiday"),
    "2026-04-13": ("BLUE", "Songkran Day"),
    "2026-04-14": ("BLUE", "Songkran Day"),
    "2026-04-15": ("BLUE", "Songkran Day"),
    "2026-04-16": ("GREEN", "Company holiday"),
    "2026-04-17": ("GREEN", "Company holiday"),
    "2026-05-01": ("BLUE", "Labour Day"),
    "2026-05-02": ("GREEN", "Company holiday"),
    "2026-06-01": ("BLUE", "Traditional holiday"),
    "2026-06-27": ("GREEN", "Company holiday"),
    "2026-07-04": ("GREEN", "Company holiday"),
    "2026-07-27": ("GREEN", "Company holiday"),
    "2026-07-28": ("BLUE", "King's Birthday"),
    "2026-07-29": ("BLUE", "Buddhist Lent Day"),
    "2026-08-12": ("BLUE", "Queen Mother's Birthday"),
    "2026-12-05": ("BLUE", "King Bhumibol's Birthday"),
    "2026-12-29": ("GREEN", "Company holiday"),
    "2026-12-30": ("GREEN", "Company holiday"),
    "2026-12-31": ("BLUE", "New Year's Eve"),
}


@contextmanager
def get_connection():
    """Yield a transaction and always release the SQLite file handle.

    Explicit closure matters on Windows where a lingering connection can keep the
    database locked for subsequent attendance and export operations.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_code TEXT NOT NULL UNIQUE,
                employee_name TEXT NOT NULL,
                monthly_salary REAL NOT NULL CHECK(monthly_salary >= 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                work_date TEXT NOT NULL,
                working_hours REAL NOT NULL CHECK(working_hours >= 0 AND working_hours <= 24),
                day_type TEXT NOT NULL CHECK(day_type IN ('WHITE','BLUE','ORANGE','GREEN')),
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(employee_id, work_date),
                FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS overtime_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attendance_id INTEGER NOT NULL UNIQUE,
                employee_id INTEGER NOT NULL,
                work_date TEXT NOT NULL,
                day_type TEXT NOT NULL,
                hourly_rate REAL NOT NULL,
                regular_hours REAL NOT NULL,
                overtime_hours REAL NOT NULL,
                regular_multiplier REAL NOT NULL,
                overtime_multiplier REAL NOT NULL,
                regular_pay REAL NOT NULL,
                overtime_pay REAL NOT NULL,
                total_pay REAL NOT NULL,
                calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(attendance_id) REFERENCES attendance(id) ON DELETE CASCADE,
                FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS payroll_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                payroll_month TEXT NOT NULL,
                monthly_salary REAL NOT NULL,
                attendance_days INTEGER NOT NULL,
                regular_hours REAL NOT NULL,
                overtime_hours REAL NOT NULL,
                regular_pay REAL NOT NULL,
                overtime_pay REAL NOT NULL,
                total_pay REAL NOT NULL,
                generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(employee_id, payroll_month),
                FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS payroll_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                payroll_month TEXT NOT NULL,
                other_income REAL NOT NULL DEFAULT 0 CHECK(other_income >= 0),
                deductions REAL NOT NULL DEFAULT 0 CHECK(deductions >= 0),
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(employee_id, payroll_month),
                FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS calendar_dates (
                work_date TEXT PRIMARY KEY,
                day_type TEXT NOT NULL CHECK(day_type IN ('WHITE','BLUE','ORANGE','GREEN')),
                description TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(work_date);
            CREATE INDEX IF NOT EXISTS idx_ot_date ON overtime_records(work_date);
            CREATE INDEX IF NOT EXISTS idx_payroll_month ON payroll_summary(payroll_month);
            """
        )
        for work_date, (day_type, description) in DEFAULT_2026_DATES.items():
            conn.execute(
                """INSERT OR IGNORE INTO calendar_dates(work_date, day_type, description)
                   VALUES (?, ?, ?)""",
                (work_date, day_type, description),
            )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(payroll_summary)")}
        if "other_income" not in columns:
            conn.execute("ALTER TABLE payroll_summary ADD COLUMN other_income REAL NOT NULL DEFAULT 0")
        if "deductions" not in columns:
            conn.execute("ALTER TABLE payroll_summary ADD COLUMN deductions REAL NOT NULL DEFAULT 0")
        if "net_pay" not in columns:
            conn.execute("ALTER TABLE payroll_summary ADD COLUMN net_pay REAL NOT NULL DEFAULT 0")


def _row_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def get_employees() -> list[dict[str, Any]]:
    with get_connection() as conn:
        return _row_dicts(conn.execute("SELECT * FROM employees ORDER BY employee_code"))


def save_employee(employee_code: str, employee_name: str, monthly_salary: float, employee_id: int | None = None) -> None:
    code, name = employee_code.strip(), employee_name.strip()
    if not code or not name:
        raise ValueError("Employee ID and employee name are required.")
    if monthly_salary < 0:
        raise ValueError("Monthly salary cannot be negative.")
    with get_connection() as conn:
        if employee_id:
            conn.execute(
                """UPDATE employees SET employee_code=?, employee_name=?, monthly_salary=?,
                   updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (code, name, monthly_salary, employee_id),
            )
            # This application uses the master salary as the current hourly-rate source.
            # Recalculate its attendance immediately and make saved monthly summaries
            # regenerate explicitly, so no report silently uses an old rate.
            records = conn.execute(
                "SELECT id, work_date, working_hours, day_type FROM attendance WHERE employee_id=?",
                (employee_id,),
            ).fetchall()
            for record in records:
                pay = calculate_pay(monthly_salary, record["working_hours"], record["day_type"])
                conn.execute(
                    """UPDATE overtime_records SET hourly_rate=?, regular_hours=?, overtime_hours=?,
                       regular_multiplier=?, overtime_multiplier=?, regular_pay=?, overtime_pay=?,
                       total_pay=?, calculated_at=CURRENT_TIMESTAMP WHERE attendance_id=?""",
                    (*pay.values(), record["id"]),
                )
            conn.execute("DELETE FROM payroll_summary WHERE employee_id=?", (employee_id,))
        else:
            conn.execute(
                "INSERT INTO employees(employee_code, employee_name, monthly_salary) VALUES (?, ?, ?)",
                (code, name, monthly_salary),
            )


def delete_employee(employee_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM employees WHERE id=?", (employee_id,))


def day_type_for(work_date: date | str) -> str:
    day = work_date.isoformat() if isinstance(work_date, date) else work_date
    with get_connection() as conn:
        row = conn.execute("SELECT day_type FROM calendar_dates WHERE work_date=?", (day,)).fetchone()
    if row:
        return row["day_type"]
    # Saturday/Sunday are weekly holidays unless an explicit calendar item overrides them.
    return "ORANGE" if date.fromisoformat(day).weekday() >= 5 else "WHITE"


def get_calendar_dates(year: int, month: int | None = None) -> list[dict[str, Any]]:
    prefix = f"{year:04d}-{month:02d}" if month else f"{year:04d}"
    with get_connection() as conn:
        return _row_dicts(
            conn.execute(
                "SELECT * FROM calendar_dates WHERE work_date LIKE ? ORDER BY work_date", (f"{prefix}%",))
            )


def save_calendar_date(work_date: date | str, day_type: str, description: str = "") -> None:
    day = work_date.isoformat() if isinstance(work_date, date) else work_date
    if day_type not in DAY_TYPES:
        raise ValueError("Invalid day type.")
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO calendar_dates(work_date, day_type, description, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(work_date) DO UPDATE SET day_type=excluded.day_type,
               description=excluded.description, updated_at=CURRENT_TIMESTAMP""",
            (day, day_type, description.strip()),
        )


def delete_calendar_date(work_date: date | str) -> None:
    day = work_date.isoformat() if isinstance(work_date, date) else work_date
    with get_connection() as conn:
        conn.execute("DELETE FROM calendar_dates WHERE work_date=?", (day,))


def calculate_pay(monthly_salary: float, working_hours: float, day_type: str) -> dict[str, float]:
    """Apply the agreed payroll policy to a single attendance day."""
    if working_hours < 0 or working_hours > 24:
        raise ValueError("Working hours must be between 0 and 24.")
    hourly_rate = monthly_salary / 30 / 8
    if day_type == "BLUE":
        regular_hours, overtime_hours, regular_multiplier, overtime_multiplier = 0.0, working_hours, 0.0, 3.0
    elif day_type in ("ORANGE", "GREEN"):
        regular_hours, overtime_hours, regular_multiplier, overtime_multiplier = min(working_hours, 8), max(working_hours - 8, 0), 1.0, 3.0
    elif day_type == "WHITE":
        regular_hours, overtime_hours, regular_multiplier, overtime_multiplier = min(working_hours, 8), max(working_hours - 8, 0), 1.0, 1.5
    else:
        raise ValueError("Invalid day type.")
    regular_pay = regular_hours * hourly_rate * regular_multiplier
    overtime_pay = overtime_hours * hourly_rate * overtime_multiplier
    return {
        "hourly_rate": round(hourly_rate, 2),
        "regular_hours": regular_hours,
        "overtime_hours": overtime_hours,
        "regular_multiplier": regular_multiplier,
        "overtime_multiplier": overtime_multiplier,
        "regular_pay": round(regular_pay, 2),
        "overtime_pay": round(overtime_pay, 2),
        "total_pay": round(regular_pay + overtime_pay, 2),
    }


def save_attendance(employee_id: int, work_date: date | str, working_hours: float, day_type: str, notes: str = "") -> None:
    day = work_date.isoformat() if isinstance(work_date, date) else work_date
    with get_connection() as conn:
        employee = conn.execute("SELECT monthly_salary FROM employees WHERE id=?", (employee_id,)).fetchone()
        if not employee:
            raise ValueError("Employee was not found.")
        conn.execute(
            """INSERT INTO attendance(employee_id, work_date, working_hours, day_type, notes, updated_at)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(employee_id, work_date) DO UPDATE SET working_hours=excluded.working_hours,
               day_type=excluded.day_type, notes=excluded.notes, updated_at=CURRENT_TIMESTAMP""",
            (employee_id, day, working_hours, day_type, notes.strip()),
        )
        attendance = conn.execute(
            "SELECT id FROM attendance WHERE employee_id=? AND work_date=?", (employee_id, day)
        ).fetchone()
        pay = calculate_pay(employee["monthly_salary"], working_hours, day_type)
        conn.execute(
            """INSERT INTO overtime_records(attendance_id, employee_id, work_date, day_type, hourly_rate,
               regular_hours, overtime_hours, regular_multiplier, overtime_multiplier, regular_pay,
               overtime_pay, total_pay, calculated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(attendance_id) DO UPDATE SET employee_id=excluded.employee_id,
               work_date=excluded.work_date, day_type=excluded.day_type, hourly_rate=excluded.hourly_rate,
               regular_hours=excluded.regular_hours, overtime_hours=excluded.overtime_hours,
               regular_multiplier=excluded.regular_multiplier, overtime_multiplier=excluded.overtime_multiplier,
               regular_pay=excluded.regular_pay, overtime_pay=excluded.overtime_pay,
               total_pay=excluded.total_pay, calculated_at=CURRENT_TIMESTAMP""",
            (attendance["id"], employee_id, day, day_type, *pay.values()),
        )


def delete_attendance(attendance_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM attendance WHERE id=?", (attendance_id,))


def payroll_period(payroll_month: str) -> tuple[str, str]:
    """Return the inclusive start/end dates for a payroll month closing on day 15."""
    year, month = (int(part) for part in payroll_month.split("-"))
    previous_month = 12 if month == 1 else month - 1
    previous_year = year - 1 if month == 1 else year
    return f"{previous_year:04d}-{previous_month:02d}-16", f"{year:04d}-{month:02d}-15"


def get_attendance(month: str | None = None, employee_id: int | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT a.id, a.employee_id, e.employee_code, e.employee_name, e.monthly_salary,
               a.work_date, a.working_hours, a.day_type, a.notes, o.hourly_rate,
               o.regular_hours, o.overtime_hours, o.regular_multiplier, o.overtime_multiplier,
               o.regular_pay, o.overtime_pay, o.total_pay
        FROM attendance a JOIN employees e ON e.id=a.employee_id
        LEFT JOIN overtime_records o ON o.attendance_id=a.id
        WHERE 1=1
    """
    params: list[Any] = []
    if month:
        period_start, period_end = payroll_period(month)
        query += " AND a.work_date BETWEEN ? AND ?"
        params.extend((period_start, period_end))
    if employee_id:
        query += " AND a.employee_id=?"
        params.append(employee_id)
    query += " ORDER BY a.work_date DESC, e.employee_code"
    with get_connection() as conn:
        return _row_dicts(conn.execute(query, params))


def generate_monthly_payroll(payroll_month: str) -> int:
    rows = get_attendance(month=payroll_month)
    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["employee_id"], []).append(row)
    with get_connection() as conn:
        conn.execute("DELETE FROM payroll_summary WHERE payroll_month=?", (payroll_month,))
        for employee_id, records in grouped.items():
            first = records[0]
            adjustment = conn.execute(
                "SELECT other_income, deductions FROM payroll_adjustments WHERE employee_id=? AND payroll_month=?",
                (employee_id, payroll_month),
            ).fetchone()
            other_income = float(adjustment["other_income"] if adjustment else 0)
            deductions = float(adjustment["deductions"] if adjustment else 0)
            total_pay = round(sum(r["total_pay"] or 0 for r in records), 2)
            conn.execute(
                """INSERT INTO payroll_summary(employee_id, payroll_month, monthly_salary, attendance_days,
                   regular_hours, overtime_hours, regular_pay, overtime_pay, total_pay, other_income,
                   deductions, net_pay, generated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (
                    employee_id,
                    payroll_month,
                    first["monthly_salary"],
                    len(records),
                    round(sum(r["regular_hours"] or 0 for r in records), 2),
                    round(sum(r["overtime_hours"] or 0 for r in records), 2),
                    round(sum(r["regular_pay"] or 0 for r in records), 2),
                    round(sum(r["overtime_pay"] or 0 for r in records), 2),
                    total_pay,
                    other_income,
                    deductions,
                    round(total_pay + other_income - deductions, 2),
                ),
            )
    return len(grouped)


def save_payroll_adjustment(employee_id: int, payroll_month: str, other_income: float, deductions: float) -> None:
    if other_income < 0 or deductions < 0:
        raise ValueError("Other income and deductions cannot be negative.")
    with get_connection() as conn:
        if not conn.execute("SELECT 1 FROM employees WHERE id=?", (employee_id,)).fetchone():
            raise ValueError("Employee was not found.")
        conn.execute(
            """INSERT INTO payroll_adjustments(employee_id, payroll_month, other_income, deductions, updated_at)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(employee_id, payroll_month) DO UPDATE SET other_income=excluded.other_income,
               deductions=excluded.deductions, updated_at=CURRENT_TIMESTAMP""",
            (employee_id, payroll_month, other_income, deductions),
        )


def get_payroll_adjustments(payroll_month: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        return _row_dicts(conn.execute(
            """SELECT e.id AS employee_id, e.employee_code, e.employee_name,
                      COALESCE(a.other_income, 0) AS other_income,
                      COALESCE(a.deductions, 0) AS deductions
               FROM employees e LEFT JOIN payroll_adjustments a
               ON a.employee_id=e.id AND a.payroll_month=? ORDER BY e.employee_code""",
            (payroll_month,),
        ))


def calculate_tax(annual_income: float, other_annual_income: float = 0, personal_allowance: float = 60_000) -> dict[str, float]:
    """Estimate Thai progressive personal income tax; this is not tax advice."""
    if min(annual_income, other_annual_income, personal_allowance) < 0:
        raise ValueError("Income and allowance cannot be negative.")
    gross_income = annual_income + other_annual_income
    expense_deduction = min(gross_income * 0.5, 100_000)
    taxable_income = max(gross_income - expense_deduction - personal_allowance, 0)
    brackets = ((150_000, 0.0), (150_000, 0.05), (200_000, 0.10), (250_000, 0.15),
                (1_000_000, 0.20), (2_000_000, 0.25), (float("inf"), 0.35))
    remaining, tax = taxable_income, 0.0
    for amount, rate in brackets:
        taxable_in_bracket = min(remaining, amount)
        tax += taxable_in_bracket * rate
        remaining -= taxable_in_bracket
        if remaining <= 0:
            break
    return {
        "gross_income": round(gross_income, 2),
        "expense_deduction": round(expense_deduction, 2),
        "taxable_income": round(taxable_income, 2),
        "estimated_tax": round(tax, 2),
        "monthly_withholding": round(tax / 12, 2),
        "effective_rate": round(tax / gross_income * 100, 2) if gross_income else 0.0,
    }


def get_payroll_summary(payroll_month: str | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT p.*, e.employee_code, e.employee_name
        FROM payroll_summary p JOIN employees e ON e.id=p.employee_id
    """
    params: list[Any] = []
    if payroll_month:
        query += " WHERE p.payroll_month=?"
        params.append(payroll_month)
    query += " ORDER BY p.payroll_month DESC, e.employee_code"
    with get_connection() as conn:
        return _row_dicts(conn.execute(query, params))


def dashboard_totals(payroll_month: str) -> dict[str, float]:
    rows = get_attendance(payroll_month)
    employees = get_employees()
    return {
        "employees": len(employees),
        "salary": round(sum(employee["monthly_salary"] for employee in employees), 2),
        "regular_pay": round(sum(r["regular_pay"] or 0 for r in rows), 2),
        "overtime_pay": round(sum(r["overtime_pay"] or 0 for r in rows), 2),
        "total_pay": round(sum(r["total_pay"] or 0 for r in rows), 2),
    }


def available_months() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute("SELECT DISTINCT work_date FROM attendance").fetchall()
    months = set()
    for row in rows:
        work_date = date.fromisoformat(row["work_date"])
        year, month = work_date.year, work_date.month
        if work_date.day > 15:
            month += 1
            if month == 13:
                year, month = year + 1, 1
        months.add(f"{year:04d}-{month:02d}")
    return sorted(months, reverse=True)


def month_days(year: int, month: int) -> list[date]:
    return [date(year, month, d) for d in range(1, calendar.monthrange(year, month)[1] + 1)]
