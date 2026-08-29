# Calculate OT

A bilingual (Thai / English) Streamlit application for employee attendance, overtime calculation, monthly payroll summaries, extra income/deductions, a rough tax estimator, and Excel/PDF exports. Data is stored locally in SQLite.

## Run it

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

The first run creates `calculate_ot.db` automatically. The supplied 2026 calendar's traditional and company holidays are preloaded; weekends default to **ORANGE** (weekly holiday). The Calendar page lets an administrator override or add dates.

## Features

- Mobile-friendly responsive layout with a pink theme.
- Payroll adjustments per employee and month: other income, deductions, and calculated net pay.
- Tax Calculator page using a rough progressive estimate with a 50% standard expense deduction capped at 100,000 THB and 60,000 THB personal allowance by default.

The tax page is an estimate for planning only. Confirm current rules and deductions with the Revenue Department or a tax professional.

## Deploy

The app is ready for Streamlit Community Cloud or another container platform. Set the app entry point to `app.py`, install `requirements.txt`, and use a persistent volume for `calculate_ot.db` if data must survive restarts. For local production-style startup:

```powershell
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

## Calculation policy

`Hourly rate = Monthly salary / 30 / 8`

| Day type | Regular hours | Overtime hours |
| --- | --- | --- |
| WHITE – Working Day | First 8 hours × 1 | After 8 hours × 1.5 |
| BLUE – Traditional Holiday | — | All hours × 3 |
| ORANGE – Weekly Holiday | First 8 hours × 1 | After 8 hours × 3 |
| GREEN – Company Holiday | First 8 hours × 1 | After 8 hours × 3 |

The monthly summary aggregates `regular pay + overtime pay` from the attendance records using the salary cycle **วันที่ 16 ของเดือนก่อนหน้า ถึงวันที่ 15 ของเดือนที่เลือก**. For example, payroll month `2026-08` covers `2026-07-16` through `2026-08-15`. The employee's monthly salary is also shown as a reference amount used to derive each hourly rate.

## Verify payroll rules

```powershell
python -m unittest test_calculations.py
```
