"""Calculate OT – bilingual payroll and overtime management application."""

from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import database as db

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
except ImportError:  # surfaced as an actionable message when PDF is requested
    colors = None


st.set_page_config(page_title="Calculate OT", page_icon="⏱️", layout="wide", initial_sidebar_state="expanded")

TRANSLATIONS = {
    "ไทย": {
        "Dashboard": "แดชบอร์ด", "Employees": "ข้อมูลพนักงาน", "Attendance": "บันทึกเวลาทำงาน",
        "Payroll": "เงินเดือนประจำเดือน", "Calendar": "ปฏิทินวันทำงาน", "Reports": "รายงาน / ส่งออก",
        "Tax Calculator": "คำนวณภาษีคร่าวๆ",
        "Monthly Salary": "เงินเดือนต่อเดือน", "Total OT": "ค่า OT", "Total Salary": "เงินเดือนอ้างอิง",
        "Total Pay": "ค่าจ้างตามเวลาทำงาน", "Save": "บันทึก", "Delete": "ลบ", "Working Date": "วันที่ทำงาน",
        "Working Hours": "ชั่วโมงทำงาน", "Day Type": "ประเภทวัน", "Employee ID": "รหัสพนักงาน",
        "Employee Name": "ชื่อพนักงาน", "Notes": "หมายเหตุ", "Select Employee": "เลือกพนักงาน",
    },
    "English": {},
}

DAY_META = {
    "WHITE": {"label": "Working Day / วันทำงาน", "color": "#f8fafc", "text": "#172033"},
    "BLUE": {"label": "Traditional Holiday / วันหยุดประเพณี", "color": "#0284c7", "text": "white"},
    "ORANGE": {"label": "Weekly Holiday / วันหยุดประจำสัปดาห์", "color": "#f59e0b", "text": "#172033"},
    "GREEN": {"label": "Company Holiday / วันหยุดบริษัท", "color": "#65a30d", "text": "white"},
}


def tr(text: str) -> str:
    return TRANSLATIONS.get(st.session_state.language, {}).get(text, text)


def money(value: float | int | None) -> str:
    return f"฿{float(value or 0):,.2f}"


def clear_messages() -> None:
    st.session_state.pop("notice", None)


def set_notice(message: str) -> None:
    st.session_state.notice = message


def show_notice() -> None:
    if message := st.session_state.pop("notice", None):
        st.success(message)


def as_dataframe(rows: list[dict], columns: dict[str, str] | None = None) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if columns and not frame.empty:
        frame = frame.rename(columns=columns)
    return frame


def employee_label(employee: dict) -> str:
    return f"{employee['employee_code']} — {employee['employee_name']}"


def make_excel(month: str, attendance_rows: list[dict], payroll_rows: list[dict]) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        attendance = pd.DataFrame(attendance_rows)
        payroll = pd.DataFrame(payroll_rows)
        attendance.to_excel(writer, sheet_name="Attendance & OT", index=False)
        payroll.to_excel(writer, sheet_name="Payroll Summary", index=False)
        for worksheet in writer.book.worksheets:
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            for col in worksheet.columns:
                letter = col[0].column_letter
                worksheet.column_dimensions[letter].width = min(max(len(str(cell.value or "")) for cell in col) + 2, 28)
    return output.getvalue()


def thai_font() -> str:
    candidates = [
        Path("C:/Windows/Fonts/LeelawUI.ttf"), Path("C:/Windows/Fonts/THSarabunNew.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                pdfmetrics.registerFont(TTFont("AppFont", str(candidate)))
                return "AppFont"
            except Exception:
                continue
    return "Helvetica"


def make_pdf(month: str, summary_rows: list[dict]) -> bytes:
    if colors is None:
        raise RuntimeError("Install reportlab to generate PDF files.")
    buffer = BytesIO()
    font = thai_font()
    document = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=24)
    styles = getSampleStyleSheet()
    title = Paragraph(f"Calculate OT — Payroll Summary ({month})", styles["Title"])
    headers = ["Employee ID", "Employee name", "Days", "Regular hrs", "OT hrs", "Regular pay", "OT pay", "Total pay"]
    table_data = [headers]
    for row in summary_rows:
        table_data.append([
            row["employee_code"], row["employee_name"], row["attendance_days"],
            f"{row['regular_hours']:,.2f}", f"{row['overtime_hours']:,.2f}",
            f"{row['regular_pay']:,.2f}", f"{row['overtime_pay']:,.2f}", f"{row['total_pay']:,.2f}",
        ])
    if len(table_data) == 1:
        table_data.append(["—", "No payroll data", "", "", "", "", "", ""])
    table = Table(table_data, repeatRows=1, colWidths=[65, 150, 40, 60, 50, 70, 65, 70])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    document.build([title, Spacer(1, 14), table])
    return buffer.getvalue()


def layout_dashboard(selected_month: str) -> None:
    st.title("⏱️ " + tr("Dashboard"))
    st.caption("Overview of calculated attendance pay and overtime")
    totals = db.dashboard_totals(selected_month)
    card_1, card_2, card_3, card_4 = st.columns(4)
    card_1.metric(tr("Total Salary"), money(totals["salary"]), help="Total monthly salary in the employee master")
    card_2.metric("Regular Pay / ค่าจ้างปกติ", money(totals["regular_pay"]))
    card_3.metric(tr("Total OT"), money(totals["overtime_pay"]))
    card_4.metric(tr("Total Pay"), money(totals["total_pay"]))

    records = db.get_attendance(selected_month)
    if not records:
        st.info("No attendance records for this month yet. Add employees and attendance to see the dashboard.")
        return
    frame = pd.DataFrame(records)
    left, right = st.columns(2)
    with left:
        by_employee = frame.groupby(["employee_code", "employee_name"], as_index=False)["overtime_pay"].sum()
        by_employee["employee"] = by_employee["employee_code"] + " — " + by_employee["employee_name"]
        fig = px.bar(by_employee, x="employee", y="overtime_pay", color="overtime_pay", color_continuous_scale="Teal", title="OT by Employee / OT รายพนักงาน")
        fig.update_layout(coloraxis_showscale=False, margin=dict(l=10, r=10, t=50, b=10), yaxis_title="THB")
        st.plotly_chart(fig, use_container_width=True)
    with right:
        all_records = db.get_attendance()
        monthly = pd.DataFrame(all_records)
        if monthly.empty:
            return
        monthly["month"] = monthly["work_date"].str[:7]
        trend = monthly.groupby("month", as_index=False)["overtime_pay"].sum()
        fig = px.line(trend, x="month", y="overtime_pay", markers=True, title="OT by Month / OT รายเดือน")
        fig.update_traces(line_color="#0f766e")
        fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), yaxis_title="THB", xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Recent attendance / รายการล่าสุด")
    display = frame[["work_date", "employee_code", "employee_name", "day_type", "working_hours", "regular_pay", "overtime_pay", "total_pay"]].copy()
    st.dataframe(display, use_container_width=True, hide_index=True, column_config={
        "regular_pay": st.column_config.NumberColumn("Regular Pay", format="฿%.2f"),
        "overtime_pay": st.column_config.NumberColumn("OT Pay", format="฿%.2f"),
        "total_pay": st.column_config.NumberColumn("Total Pay", format="฿%.2f"),
    })


def layout_employees() -> None:
    st.title("👥 " + tr("Employees"))
    st.caption("Employee master / ข้อมูลพนักงาน")
    add_tab, manage_tab = st.tabs(["Add employee / เพิ่มพนักงาน", "Manage employees / จัดการข้อมูล"])
    with add_tab:
        with st.form("employee_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            code = col1.text_input(tr("Employee ID"), placeholder="EMP001")
            name = col2.text_input(tr("Employee Name"), placeholder="Somchai Jaidee")
            salary = col3.number_input(tr("Monthly Salary"), min_value=0.0, step=500.0, format="%.2f")
            submitted = st.form_submit_button("➕ " + tr("Save"), use_container_width=True)
        if submitted:
            try:
                db.save_employee(code, name, salary)
                set_notice("Employee saved successfully.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    with manage_tab:
        employees = db.get_employees()
        if not employees:
            st.info("No employees yet.")
            return
        table = pd.DataFrame(employees)[["id", "employee_code", "employee_name", "monthly_salary"]]
        st.dataframe(table, use_container_width=True, hide_index=True, column_config={"monthly_salary": st.column_config.NumberColumn(tr("Monthly Salary"), format="฿%.2f")})
        selected = st.selectbox("Employee to edit / พนักงานที่ต้องการแก้ไข", employees, format_func=employee_label)
        with st.form("employee_edit"):
            e1, e2, e3 = st.columns(3)
            edit_code = e1.text_input(tr("Employee ID"), value=selected["employee_code"])
            edit_name = e2.text_input(tr("Employee Name"), value=selected["employee_name"])
            edit_salary = e3.number_input(tr("Monthly Salary"), min_value=0.0, value=float(selected["monthly_salary"]), step=500.0)
            save_col, delete_col = st.columns(2)
            update = save_col.form_submit_button("💾 Update / แก้ไข", use_container_width=True)
            delete = delete_col.form_submit_button("🗑️ Delete / ลบ", use_container_width=True, type="secondary")
        try:
            if update:
                db.save_employee(edit_code, edit_name, edit_salary, selected["id"])
                set_notice("Employee updated successfully.")
                st.rerun()
            if delete:
                db.delete_employee(selected["id"])
                set_notice("Employee and related records deleted.")
                st.rerun()
        except Exception as exc:
            st.error(str(exc))


def layout_attendance() -> None:
    st.title("🗓️ " + tr("Attendance"))
    employees = db.get_employees()
    if not employees:
        st.warning("Please add an employee first / กรุณาเพิ่มข้อมูลพนักงานก่อน")
        return
    st.caption("Saving an entry immediately creates or updates its overtime calculation.")
    col1, col2, col3 = st.columns(3)
    employee = col1.selectbox(tr("Select Employee"), employees, format_func=employee_label)
    work_date = col2.date_input(tr("Working Date"), value=date.today())
    working_hours = col3.number_input(tr("Working Hours"), min_value=0.0, max_value=24.0, value=8.0, step=0.5)
    suggested = db.day_type_for(work_date)
    day_type = st.selectbox(tr("Day Type"), list(DAY_META), index=list(DAY_META).index(suggested), format_func=lambda d: DAY_META[d]["label"])
    notes = st.text_input(tr("Notes"), placeholder="Optional / ไม่บังคับ")
    preview = db.calculate_pay(employee["monthly_salary"], working_hours, day_type)
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Hourly rate", money(preview["hourly_rate"]))
    p2.metric("Regular Pay", money(preview["regular_pay"]))
    p3.metric("OT Pay", money(preview["overtime_pay"]))
    p4.metric("Total", money(preview["total_pay"]))
    if st.button("💾 Save attendance & calculate OT / บันทึกและคำนวณ OT", use_container_width=True, type="primary"):
        try:
            db.save_attendance(employee["id"], work_date, working_hours, day_type, notes)
            set_notice("Attendance and overtime calculation saved.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    st.subheader("Attendance & calculated OT / รายการบันทึกเวลา")
    rows = db.get_attendance()
    if rows:
        frame = pd.DataFrame(rows)
        chosen_month = st.selectbox("Filter payroll cycle / เลือกรอบเงินเดือน", ["All"] + db.available_months(), key="attendance_month")
        if chosen_month != "All":
            period_start, period_end = db.payroll_period(chosen_month)
            frame = frame[(frame["work_date"] >= period_start) & (frame["work_date"] <= period_end)]
            st.caption(f"รอบเงินเดือน {chosen_month}: {period_start} ถึง {period_end}")
        shown = frame[["id", "work_date", "employee_code", "employee_name", "day_type", "working_hours", "hourly_rate", "regular_hours", "overtime_hours", "regular_pay", "overtime_pay", "total_pay", "notes"]]
        st.dataframe(shown, use_container_width=True, hide_index=True, column_config={
            "regular_pay": st.column_config.NumberColumn("Regular Pay", format="฿%.2f"),
            "overtime_pay": st.column_config.NumberColumn("OT Pay", format="฿%.2f"),
            "total_pay": st.column_config.NumberColumn("Total Pay", format="฿%.2f"),
        })
        delete_id = st.selectbox("Delete attendance record / ลบรายการ", frame["id"].tolist(), format_func=lambda rec_id: f"Record #{rec_id}", key="attendance_delete")
        if st.button("🗑️ Delete selected attendance / ลบรายการที่เลือก", type="secondary"):
            db.delete_attendance(int(delete_id))
            set_notice("Attendance deleted.")
            st.rerun()
    else:
        st.info("No attendance records yet.")


def layout_payroll(selected_month: str) -> None:
    st.title("💵 " + tr("Payroll"))
    period_start, period_end = db.payroll_period(selected_month)
    st.caption(f"รอบเงินเดือน {selected_month}: {period_start} ถึง {period_end} | Monthly salary is retained as a reference rate.")
    rows = db.get_attendance(selected_month)
    if not rows:
        st.info("No attendance records for this month.")
        return
    st.subheader("Other income & deductions / เงินเพิ่มและรายการหัก")
    adjustment_rows = db.get_payroll_adjustments(selected_month)
    adjustment_employee = st.selectbox(
        "Employee / พนักงาน", adjustment_rows, format_func=employee_label, key="adjustment_employee"
    )
    current_adjustment = next(row for row in adjustment_rows if row["employee_id"] == adjustment_employee["employee_id"])
    with st.form("payroll_adjustment_form"):
        adjustment_col1, adjustment_col2 = st.columns(2)
        other_income = adjustment_col1.number_input(
            "Other income / เงินเพิ่ม", min_value=0.0, value=float(current_adjustment["other_income"]), step=500.0
        )
        deductions = adjustment_col2.number_input(
            "Deductions / รายการหัก", min_value=0.0, value=float(current_adjustment["deductions"]), step=500.0
        )
        save_adjustment = st.form_submit_button("💾 Save adjustment / บันทึก", type="primary")
    if save_adjustment:
        db.save_payroll_adjustment(adjustment_employee["employee_id"], selected_month, other_income, deductions)
        db.generate_monthly_payroll(selected_month)
        set_notice("Payroll adjustment saved and net pay refreshed.")
        st.rerun()
    left, right = st.columns([1, 2])
    with left:
        st.write(f"**Payroll month:** {selected_month}")
        st.write(f"**Attendance records:** {len(rows)}")
        if st.button("🔄 Generate / refresh payroll", type="primary", use_container_width=True):
            count = db.generate_monthly_payroll(selected_month)
            set_notice(f"Payroll generated for {count} employee(s).")
            st.rerun()
    summary = db.get_payroll_summary(selected_month)
    with right:
        totals = db.dashboard_totals(selected_month)
        a, b, c = st.columns(3)
        a.metric("Regular Pay", money(totals["regular_pay"]))
        b.metric("OT Pay", money(totals["overtime_pay"]))
        c.metric("Total Pay", money(totals["total_pay"]))
    if not summary:
        st.warning("Click Generate / refresh payroll to save this month's summary.")
        return
    frame = pd.DataFrame(summary)
    st.subheader("Payroll summary / สรุปเงินเดือน")
    st.dataframe(frame[["employee_code", "employee_name", "monthly_salary", "attendance_days", "regular_hours", "overtime_hours", "regular_pay", "overtime_pay", "total_pay", "other_income", "deductions", "net_pay", "generated_at"]], use_container_width=True, hide_index=True, column_config={
        "monthly_salary": st.column_config.NumberColumn("Monthly Salary", format="฿%.2f"),
        "regular_pay": st.column_config.NumberColumn("Regular Pay", format="฿%.2f"),
        "overtime_pay": st.column_config.NumberColumn("OT Pay", format="฿%.2f"),
        "total_pay": st.column_config.NumberColumn("Total Pay", format="฿%.2f"),
        "other_income": st.column_config.NumberColumn("Other income", format="฿%.2f"),
        "deductions": st.column_config.NumberColumn("Deductions", format="฿%.2f"),
        "net_pay": st.column_config.NumberColumn("Net pay", format="฿%.2f"),
    })


def layout_tax(selected_month: str) -> None:
    st.title("🧾 " + tr("Tax Calculator"))
    st.caption("ระบบดึงเงินที่ได้รับจากบันทึก OT และเงินเพิ่มใน payroll เดือนที่เลือก แล้วประมาณการเป็นรายปี")
    employees = db.get_employees()
    if not employees:
        st.info("ยังไม่มีข้อมูลพนักงานหรือรายได้ให้คำนวณ")
        return
    tax_employee = st.selectbox("Employee / พนักงาน", employees, format_func=employee_label, key="tax_employee")
    tax_month = st.selectbox("Income month / เดือนที่มีรายได้", db.available_months() or [selected_month], index=0, key="tax_month")
    attendance = db.get_attendance(tax_month, tax_employee["id"])
    adjustment = next(
        row for row in db.get_payroll_adjustments(tax_month)
        if row["employee_id"] == tax_employee["id"]
    )
    attendance_income = sum(row["total_pay"] or 0 for row in attendance)
    other_income = float(adjustment["other_income"])
    deductions = float(adjustment["deductions"])
    received = round(attendance_income + other_income - deductions, 2)
    annual_income = round((attendance_income + other_income) * 12, 2)
    st.info(f"รายได้จากระบบเดือน {tax_month}: {money(attendance_income + other_income)} | ได้รับจริงหลังหัก: {money(received)}")
    allowance = st.number_input("Personal allowance / ค่าลดหย่อนส่วนตัว", min_value=0.0, value=60_000.0, step=1_000.0)
    result = db.calculate_tax(annual_income, 0, allowance)
    tax_1, tax_2, tax_3, tax_4 = st.columns(4)
    tax_1.metric("Income this month", money(attendance_income + other_income))
    tax_2.metric("Annualized income", money(result["gross_income"]))
    tax_3.metric("Estimated annual tax", money(result["estimated_tax"]))
    tax_4.metric("Estimated monthly tax", money(result["monthly_withholding"]))
    st.info(f"Effective tax rate: {result['effective_rate']:.2f}% | หักค่าใช้จ่ายเหมาจ่าย 50% สูงสุด 100,000 บาท")


def layout_calendar() -> None:
    st.title("🎨 " + tr("Calendar"))
    st.caption("Saturday and Sunday default to Weekly Holiday (orange). Calendar entries override that rule. The supplied 2026 calendar has been preloaded.")
    legend = "  ".join(f"<span class='legend-pill' style='background:{meta['color']}; color:{meta['text']}'>{kind}: {meta['label']}</span>" for kind, meta in DAY_META.items())
    st.markdown(legend, unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    selected_year = col1.number_input("Year / ปี", min_value=2020, max_value=2100, value=2026, step=1)
    selected_month = col2.selectbox("Month / เดือน", list(range(1, 13)), format_func=lambda m: date(2026, m, 1).strftime("%B"))
    overrides = {row["work_date"]: row for row in db.get_calendar_dates(int(selected_year), int(selected_month))}
    cells = []
    for day in db.month_days(int(selected_year), int(selected_month)):
        row = overrides.get(day.isoformat())
        kind = row["day_type"] if row else db.day_type_for(day)
        description = row["description"] if row else ("Weekly Holiday" if day.weekday() >= 5 else "Working Day")
        meta = DAY_META[kind]
        cells.append(f"<div class='calendar-cell' style='background:{meta['color']};color:{meta['text']}'><b>{day.day}</b><small>{description or meta['label']}</small></div>")
    st.markdown("<div class='calendar-grid'>" + "".join(cells) + "</div>", unsafe_allow_html=True)
    st.divider()
    st.subheader("Set a calendar date / กำหนดประเภทวัน")
    with st.form("calendar_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        selected_date = c1.date_input("Date / วันที่", value=date(int(selected_year), int(selected_month), 1))
        kind = c2.selectbox(tr("Day Type"), list(DAY_META), format_func=lambda d: DAY_META[d]["label"])
        description = c3.text_input("Description / รายละเอียด")
        saved = st.form_submit_button("💾 Save calendar date / บันทึก")
    if saved:
        db.save_calendar_date(selected_date, kind, description)
        set_notice("Calendar date saved. Future attendance selections will use this day type.")
        st.rerun()
    dates = db.get_calendar_dates(int(selected_year), int(selected_month))
    if dates:
        override_frame = pd.DataFrame(dates)
        st.dataframe(override_frame[["work_date", "day_type", "description"]], use_container_width=True, hide_index=True)
        remove_date = st.selectbox("Remove override / ลบการกำหนด", [row["work_date"] for row in dates])
        if st.button("Remove selected override / ลบรายการที่เลือก", type="secondary"):
            db.delete_calendar_date(remove_date)
            set_notice("Calendar override removed. Weekend dates return to orange; weekdays return to white.")
            st.rerun()


def layout_reports(selected_month: str) -> None:
    st.title("📤 " + tr("Reports"))
    st.caption("Generate the monthly payroll first, then download an Excel workbook or PDF summary.")
    attendance = db.get_attendance(selected_month)
    summary = db.get_payroll_summary(selected_month)
    if not summary:
        st.warning("No saved payroll summary exists for this month. Open Payroll and generate it first.")
        return
    excel = make_excel(selected_month, attendance, summary)
    left, right = st.columns(2)
    left.download_button("⬇️ Export Excel / ส่งออก Excel", data=excel, file_name=f"calculate_ot_{selected_month}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    try:
        pdf = make_pdf(selected_month, summary)
        right.download_button("⬇️ Export PDF / ส่งออก PDF", data=pdf, file_name=f"calculate_ot_{selected_month}.pdf", mime="application/pdf", use_container_width=True)
    except Exception as exc:
        right.error(f"PDF export unavailable: {exc}")


def main() -> None:
    db.init_db()
    if "language" not in st.session_state:
        st.session_state.language = "ไทย"
    st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg,#fff7fb 0%,#fff 55%,#fff0f6 100%); color: #4a2538; }
    [data-testid='stSidebar'] { background: linear-gradient(180deg,#d9487d 0%,#9f315d 100%); }
      [data-testid='stSidebar'] * { color: #f8fafc; }
      .brand { font-size: 1.55rem; font-weight: 750; margin-bottom: .2rem; }
      .brand-sub { opacity: .82; font-size: .87rem; margin-bottom: 1.4rem; }
    [data-testid='stMetric'] { background: rgba(255,255,255,.88); border: 1px solid #f2bfd2; padding: 14px; border-radius: 12px; box-shadow: 0 3px 10px rgba(159,49,93,.08); }
      .legend-pill { padding: 5px 10px; margin: 0 4px 8px 0; display:inline-block; border-radius: 999px; font-size:.75rem; font-weight:600; border:1px solid rgba(15,23,42,.12); }
      .calendar-grid { display:grid; grid-template-columns:repeat(7,minmax(58px,1fr)); gap:7px; margin-top:14px; }
      .calendar-cell { min-height:70px; border-radius:10px; padding:8px; box-shadow: inset 0 0 0 1px rgba(15,23,42,.12); }
      .calendar-cell small { display:block; font-size:.68rem; opacity:.86; margin-top:5px; line-height:1.08; }
    [data-testid='stDataFrame'] { max-width: 100%; overflow-x: auto; }
    @media (max-width: 700px) { .calendar-grid { grid-template-columns:repeat(4,1fr); } .calendar-cell { min-height:60px; } h1 { font-size: 1.7rem; } [data-testid='stMetric'] { padding: 10px; } }
    </style>
    """, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown("<div class='brand'>⏱️ Calculate OT</div><div class='brand-sub'>Payroll & overtime management</div>", unsafe_allow_html=True)
        st.session_state.language = st.selectbox("Language / ภาษา", ["ไทย", "English"], index=["ไทย", "English"].index(st.session_state.language))
        page = st.radio("Navigation", ["Dashboard", "Employees", "Attendance", "Payroll", "Tax Calculator", "Calendar", "Reports"], format_func=tr)
        months = db.available_months()
        default_month = date.today().strftime("%Y-%m")
        selected_month = st.selectbox("Payroll month / เดือนเงินเดือน", months if months else [default_month])
        st.divider()
        st.caption("Hourly rate = Monthly salary ÷ 30 ÷ 8")
        st.caption("Blue: all hours ×3 · Orange/Green: >8 hours ×3 · White: >8 hours ×1.5")
    show_notice()
    if page == "Dashboard":
        layout_dashboard(selected_month)
    elif page == "Employees":
        layout_employees()
    elif page == "Attendance":
        layout_attendance()
    elif page == "Payroll":
        layout_payroll(selected_month)
    elif page == "Tax Calculator":
        layout_tax(selected_month)
    elif page == "Calendar":
        layout_calendar()
    else:
        layout_reports(selected_month)


if __name__ == "__main__":
    main()
