"""A weekday-aligned company calendar and explicit local overrides."""

from __future__ import annotations

import calendar
from datetime import date

import streamlit as st

import database as db
import calendar_reference as reference
from salary_view import DAY_BADGES, DAY_LABELS, THAI_MONTHS, thai_date


def layout_calendar() -> None:
    st.badge("Calendar 2026", icon=":material/calendar_month:", color="red")
    st.title("ปฏิทินวันทำงาน")
    st.caption("ดูวันทำงานและวันหยุดตามปฏิทินบริษัท เพื่อใช้คำนวณ OT ให้ตรงประเภทวัน")
    c1, c2 = st.columns(2)
    year = c1.number_input("ปี ค.ศ.", min_value=2020, max_value=2100, value=2026, step=1, key="calendar_year")
    month = c2.selectbox("เดือน", list(range(1, 13)), index=date.today().month - 1,
                        format_func=lambda m: THAI_MONTHS[m - 1], key="calendar_month")
    days = {day: db.get_calendar_day(day) for day in db.month_days(year, month)}
    with st.container(horizontal=True):
        for kind, label in DAY_LABELS.items():
            st.badge(label, color=DAY_BADGES[kind])

    if year != 2026:
        st.warning("มีปฏิทินอ้างอิงเฉพาะปี 2026 ปีนี้ใช้จันทร์–ศุกร์เป็นวันทำงาน และเสาร์–อาทิตย์เป็นวันหยุด เว้นแต่คุณกำหนดวันไว้เอง")
    counts = st.columns(4)
    for column, (kind, label) in zip(counts, DAY_LABELS.items()):
        column.metric(label, f"{sum(item['day_type'] == kind for item in days.values())} วัน", border=True)

    st.subheader(f"{THAI_MONTHS[month - 1]} {year + 543}", anchor=False)
    st.caption("สีตรงกับประเภทวันในต้นฉบับ • เครื่องหมาย • หลังวันที่หมายถึงกำหนดเอง")
    # A native Markdown table keeps all seven weekdays together, without the
    # minimum column widths that cause a seven-column layout to overflow.
    weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(year, month)
    rows = []
    for week in weeks:
        row = []
        for day in week:
            if day.month != month:
                row.append("")
                continue
            info = days[day]
            marker = " •" if info.get("is_override") else ""
            row.append(f":{DAY_BADGES[info['day_type']]}-badge[**{day.day}**]{marker}")
        rows.append(row)
    st.markdown("| อา. | จ. | อ. | พ. | พฤ. | ศ. | ส. |\n"
                "| :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n" +
                "\n".join("| " + " | ".join(row) + " |" for row in rows))

    holidays = [{"วันที่": thai_date(day), "ประเภทวัน": DAY_LABELS[info["day_type"]],
                 "รายละเอียด": info["description"]}
                for day, info in days.items() if info["day_type"] in ("BLUE", "GREEN")]
    if holidays:
        st.subheader("วันหยุดสำคัญเดือนนี้", anchor=False)
        for holiday in holidays:
            st.write(f"**{holiday['วันที่']}** · {holiday['รายละเอียด']}")

    with st.expander("ปฏิทินต้นฉบับและหมายเหตุ", expanded=True):
        st.write("**อ้างอิง Calendar 2026.pdf ที่แนบมา**")
        st.caption("ปฏิทินบริษัทปี 2026 มีวันทำงาน 256 วัน · วันหยุดประจำสัปดาห์ 84 วัน · วันหยุดประเพณี 13 วัน · วันหยุดบริษัท 12 วัน (ก่อนการกำหนดวันเอง)")
        st.caption("วันเสาร์บางวันเป็นวันทำงาน ให้ยึดประเภทวันในปฏิทินนี้")
        st.info("สำหรับกะกลางคืน: ต้นฉบับมีหมายเหตุสลับวัน 23 ม.ค. ↔ 14 ก.พ. และ 10 เม.ย. ↔ 9 พ.ค. โปรดตรวจหมายเหตุในต้นฉบับและกำหนดประเภทวันให้ตรงกะก่อนคำนวณ")
        path = reference.REFERENCE_PDF_PATH
        if path.exists():
            st.download_button("ดาวน์โหลดปฏิทินต้นฉบับ", path.read_bytes(), "Calendar 2026.pdf",
                               mime="application/pdf", icon=":material/download:")

    with st.expander("กำหนดวันเป็นกรณีพิเศษ"):
        st.caption("ใช้เมื่อมีการเปลี่ยนวันทำงานหรือทำงานต่างกะ การกำหนดนี้มีผลทั้งแอป รวมถึงหน้าคำนวณส่วนตัว บันทึกเวลาเดิมจะไม่เปลี่ยนตาม")
        selected_date = st.date_input("วันที่ต้องการกำหนด", value=date(year, month, 1), key="override_date")
        current = db.get_calendar_day(selected_date)
        # Date-scoped keys stop a previous date's type from leaking into the next one.
        kind = st.selectbox("ประเภทวัน", list(DAY_LABELS), index=list(DAY_LABELS).index(current["day_type"]),
                            format_func=DAY_LABELS.get, key=f"override_type_{selected_date}")
        description = st.text_input("รายละเอียด", value=current["description"], key=f"override_note_{selected_date}")
        if st.button("บันทึกประเภทวัน", type="primary", icon=":material/save:"):
            db.save_calendar_date(selected_date, kind, description)
            st.session_state.notice = "บันทึกประเภทวันแล้ว การคำนวณใหม่จะใช้ประเภทวันนี้"
            st.rerun()
        overrides = db.get_calendar_dates(year, month)
        if overrides:
            chosen = st.selectbox("วันที่ต้องการคืนค่าตามปฏิทิน", [row["work_date"] for row in overrides], format_func=thai_date)
            if st.button("คืนค่าประเภทวันตามปฏิทิน", icon=":material/restore:"):
                db.delete_calendar_date(chosen)
                st.session_state.notice = "คืนค่าประเภทวันตามปฏิทินอ้างอิงแล้ว"
                st.rerun()
