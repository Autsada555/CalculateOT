"""A standalone monthly estimate that adds extra pay to a full monthly salary.

No employee or database record is required. Day rates come from the application's
existing policy in ``database.calculate_pay``; this module only aggregates them.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP, localcontext
from typing import Any

import database as db


def _number(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label} must be a finite, non-negative number.") from exc
    if isinstance(value, bool) or not math.isfinite(number) or number < 0:
        raise ValueError(f"{label} must be a finite, non-negative number.")
    return number


def _money(value: Decimal | float) -> float:
    # Decimal summation avoids binary floating-point drift between displayed
    # line items and totals. Allow the full finite float range for validation.
    with localcontext() as context:
        context.prec = 340
        result = float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if not math.isfinite(result):
        raise ValueError("The calculated amount is too large.")
    return result


def _sum_money(values: Sequence[float]) -> float:
    with localcontext() as context:
        context.prec = 340
        return _money(sum((Decimal(str(value)) for value in values), Decimal(0)))


def _items(values: Mapping[str, float] | None, label: str) -> dict[str, float]:
    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise ValueError(f"{label} must contain named amounts.")
    result = {}
    for name, value in values.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Every {label} item needs a name.")
        if name.strip() in result:
            raise ValueError(f"Duplicate {label} item: {name.strip()}.")
        result[name.strip()] = _money(_number(value, f"{label}: {name}"))
    return result


def _rate_hours(values: Mapping[Any, float], label: str, max_hours: float = 24) -> dict[float, float]:
    if not isinstance(values, Mapping):
        raise ValueError(f"{label} must contain named hours.")
    result: dict[float, float] = {}
    for rate, hours in values.items():
        try:
            multiplier = float(rate)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{label} contains an invalid rate.") from exc
        if multiplier not in (1.0, 1.5, 2.0, 3.0):
            raise ValueError(f"{label} contains an unsupported rate.")
        result[multiplier] = _number(hours, f"{label}: {multiplier:g}")
    if sum(result.values()) > max_hours:
        raise ValueError(f"{label} must total no more than {max_hours:g} hours.")
    return result


def _work_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError("Each work entry needs a valid work date.") from exc


def calculate_monthly_salary(
    monthly_salary: float,
    incomes: Mapping[str, float] | None = None,
    deductions: Mapping[str, float] | None = None,
    work_entries: Sequence[Mapping[str, Any]] | None = None,
    rate_hours: Mapping[Any, float] | None = None,
) -> dict[str, Any]:
    """Return a monthly salary estimate and its itemized breakdown.

    ``work_entries`` contain ``work_date`` (or ``date``), ``working_hours`` and
    ``day_type``. Hours mean total hours worked that day, including the first
    eight hours. Dates must be unique; callers choose the payroll date range.

    Monthly salary includes regular wages on WHITE days, so only their overtime
    is added. BLUE, ORANGE and GREEN entries add their entire policy day total.
    ``total_income`` is the sum of extra income items, and ``gross_pay`` includes
    salary, those items and additional work pay. ``overtime_pay`` includes all
    policy overtime; ``holiday_pay`` is the remaining holiday contribution.
    These two components sum to ``additional_work_pay``. Deductions are supplied
    by the caller; tax or other statutory deductions are not inferred.

    Input amounts and monthly totals are rounded to cents using ROUND_HALF_UP.
    Daily pay retains the existing policy's rounding. The function is pure and
    never saves or loads employee, calendar, or attendance records.
    """
    salary = _money(_number(monthly_salary, "Monthly salary"))
    income_items = _items(incomes, "Income")
    deduction_items = _items(deductions, "Deduction")
    entries: list[dict[str, Any]] = []
    seen_dates: set[str] = set()
    if work_entries is not None and (
        not isinstance(work_entries, Sequence) or isinstance(work_entries, (str, bytes))
    ):
        raise ValueError("Work entries must be a list of daily records.")

    for record in work_entries or []:
        if not isinstance(record, Mapping):
            raise ValueError("Each work entry must contain a date, hours and day type.")
        day = _work_date(record.get("work_date", record.get("date")))
        if "work_date" in record and "date" in record and _work_date(record["date"]) != day:
            raise ValueError("A work entry contains conflicting dates.")
        if day in seen_dates:
            raise ValueError(f"Duplicate work date: {day}.")
        seen_dates.add(day)
        hours = _number(record.get("working_hours"), "Working hours")
        if hours > 24:
            raise ValueError("Working hours must be between 0 and 24.")
        day_type = record.get("day_type")
        if day_type not in db.DAY_TYPES:
            raise ValueError("Invalid day type.")
        custom_rate_hours = record.get("rate_hours")
        if custom_rate_hours is None:
            pay = db.calculate_pay(salary, hours, day_type)
        else:
            entry_rate_hours = _rate_hours(custom_rate_hours, "Rate hours")
            hourly_rate = salary / 30 / 8
            custom_total = _money(sum(
                custom_hours * hourly_rate * multiplier
                for multiplier, custom_hours in entry_rate_hours.items()
            ))
            pay = {
                "hourly_rate": round(hourly_rate, 2),
                "regular_hours": 0.0,
                "overtime_hours": sum(entry_rate_hours.values()),
                "regular_multiplier": 0.0,
                "overtime_multiplier": 0.0,
                "regular_pay": 0.0,
                "overtime_pay": custom_total,
                "total_pay": custom_total,
            }
        if not all(math.isfinite(value) for value in pay.values()):
            raise ValueError("The calculated amount is too large.")
        additional_pay = pay["overtime_pay"] if day_type == "WHITE" else pay["total_pay"]
        # Daily total and its components can differ by one cent under the
        # existing policy. Reconcile here without changing the policy fields.
        holiday_pay = _sum_money([additional_pay, -pay["overtime_pay"]])
        entries.append({
            "work_date": day,
            "working_hours": hours,
            "day_type": day_type,
            **pay,
            "additional_work_pay": additional_pay,
            "holiday_pay": holiday_pay,
            "rate_hours": entry_rate_hours if custom_rate_hours is not None else None,
        })

    overall_rate_hours = _rate_hours(rate_hours, "Rate hours", max_hours=200) if rate_hours is not None else {}
    hourly_rate = salary / 30 / 8
    overall_rate_pay = _money(sum(
        hours * hourly_rate * multiplier
        for multiplier, hours in overall_rate_hours.items()
    ))
    total_income = _sum_money(list(income_items.values()))
    total_deductions = _sum_money(list(deduction_items.values()))
    additional_work_pay = _sum_money([entry["additional_work_pay"] for entry in entries] + [overall_rate_pay])
    overtime_pay = _sum_money([entry["overtime_pay"] for entry in entries] + [overall_rate_pay])
    holiday_pay = _sum_money([entry["holiday_pay"] for entry in entries])
    gross_pay = _sum_money([salary, total_income, additional_work_pay])
    return {
        "salary": salary,
        "incomes": income_items,
        "deductions": deduction_items,
        "total_income": total_income,
        "total_deductions": total_deductions,
        "additional_work_pay": additional_work_pay,
        "overtime_pay": overtime_pay,
        "holiday_pay": holiday_pay,
        "gross_pay": gross_pay,
        "net_pay": _sum_money([gross_pay, -total_deductions]),
        "hourly_rate": db.calculate_pay(salary, 0, "WHITE")["hourly_rate"],
        "rate_hours": overall_rate_hours,
        "entries": entries,
    }
