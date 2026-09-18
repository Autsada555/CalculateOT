"""A salary-first calculator that needs no employee or attendance setup."""

from __future__ import annotations

import csv
from datetime import date, timedelta
from io import StringIO

import streamlit as st

import database as db
from salary_calculator import calculate_monthly_salary


THAI_MONTHS = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
               "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
DAY_LABELS = {"WHITE": "วันทำงาน", "BLUE": "วันหยุดประเพณี",
              "ORANGE": "วันหยุดประจำสัปดาห์", "GREEN": "วันหยุดบริษัท"}
DAY_BADGES = {"WHITE": "gray", "BLUE": "blue", "ORANGE": "orange", "GREEN": "green"}


def money(value: float) -> str:
    return f"฿{value or 0:,.2f}"


def thai_date(value: date | str) -> str:
    day = date.fromisoformat(value) if isinstance(value, str) else value
    return f"{day.day} {THAI_MONTHS[day.month - 1]} {day.year + 543}"


def period_dates(month: str) -> list[date]:
    start, end = map(date.fromisoformat, db.payroll_period(month))
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def amount(label: str, key: str, help: str | None = None) -> float:
    return st.number_input(label, min_value=0.0, value=0.0, step=100.0,
                           format="%.2f", key=key, help=help, persist_state="session")


def open_calendar() -> None:
    st.session_state.navigation = "Calendar"


def summary_csv(month: str, result: dict) -> bytes:
    """Export this exact quick calculation, separate from attendance payroll."""
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["สรุปคำนวณเงินเดือน", month])
    writer.writerow(["รอบเริ่ม", db.payroll_period(month)[0], "รอบสิ้นสุด", db.payroll_period(month)[1]])
    writer.writerow(["รายการ", "จำนวนเงิน (บาท)"])
    writer.writerow(["เงินเดือนเต็มเดือน", result["salary"]])
    for name, value in result["incomes"].items():
        writer.writerow([name, value])
    writer.writerow(["ค่าทำงานเพิ่ม / OT", result["additional_work_pay"]])
    writer.writerow(["รายได้รวมก่อนหัก", result["gross_pay"]])
    for name, value in result["deductions"].items():
        writer.writerow([name, -value])
    writer.writerow(["ยอดรับสุทธิ", result["net_pay"]])
    writer.writerow([])
    writer.writerow(["วันที่", "ประเภทวัน", "ชั่วโมงทำงานรวม", "ค่าทำงานเพิ่ม (บาท)"])
    for entry in result["entries"]:
        writer.writerow([entry["work_date"], DAY_LABELS[entry["day_type"]],
                         entry["working_hours"], entry["additional_work_pay"]])
    writer.writerow([])
    writer.writerow(["ฐาน OT", "เงินเดือน / 30 / 8; เงินเพิ่มไม่รวมฐาน OT"])
    writer.writerow(["หมายเหตุ", "คำนวณตามนโยบายเดิมของระบบ; รายการหักเป็นยอดที่ผู้ใช้กรอก"])
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def layout_quick_calculator(selected_month: str) -> None:
    st.badge("เงินเดือน & OT", color="red", icon=":material/favorite:")
    st.title("เงินเดือนเดือนนี้ ได้เท่าไหร่?")
    st.caption("กรอกเงินเดือนและเงินเพิ่ม แล้วดูยอดรับสุทธิได้เลย • เปลี่ยนตัวเลขแล้วกด Enter หรือคลิกออกจากช่องเพื่ออัปเดต")
    start, end = db.payroll_period(selected_month)
    st.write(f":material/date_range: **รอบเงินเดือน {selected_month}** · {thai_date(start)} – {thai_date(end)}")

    inputs, results = st.columns([1.4, 1], gap="medium")
    prefix = f"quick_{selected_month}"
    with inputs:
        with st.container(border=True):
            st.subheader("1. เงินเดือนและเงินเพิ่ม", anchor=False)
            salary = amount("เงินเดือนพื้นฐาน (บาท / เดือน)", f"{prefix}_salary",
                            "ใช้เงินเดือนเต็มเดือนเป็นรายได้หลัก และเป็นฐานคำนวณ OT ÷ 30 ÷ 8")
            st.caption("เงินเพิ่มต่อเดือน · ไม่มีรายการไหน เว้นเป็น 0 ได้เลย")
            c1, c2 = st.columns(2)
            with c1:
                diligence = amount("เบี้ยขยัน (บาท)", f"{prefix}_diligence")
                transport = amount("ค่าเดินทาง (บาท)", f"{prefix}_transport")
            with c2:
                food = amount("ค่าอาหาร (บาท)", f"{prefix}_food")
                shift = amount("ค่ากะ (บาท)", f"{prefix}_shift")
            other = amount("เงินเพิ่มอื่น ๆ / โบนัส (บาท)", f"{prefix}_other_income")
            incomes = {"เบี้ยขยัน": diligence, "ค่าอาหาร": food, "ค่าเดินทาง": transport,
                       "ค่ากะ": shift, "เงินเพิ่มอื่น ๆ / โบนัส": other}

        with st.container(border=True):
            st.subheader("2. รายการหัก", anchor=False)
            st.caption("กรอกยอดหักจริงของเดือนนี้ ระบบจะนำไปลบจากรายได้รวม")
            c1, c2 = st.columns(2)
            with c1:
                social = amount("ประกันสังคม (บาท)", f"{prefix}_social")
            with c2:
                tax = amount("ภาษีหัก ณ ที่จ่าย (บาท)", f"{prefix}_tax")
            deductions_other = amount("รายการหักอื่น ๆ (บาท)", f"{prefix}_deductions")
            deductions = {"ประกันสังคม": social, "ภาษีหัก ณ ที่จ่าย": tax, "รายการหักอื่น ๆ": deductions_other}

        with st.container(border=True):
            st.subheader("3. OT และทำงานวันหยุด", anchor=False)
            st.caption("เลือกเฉพาะวันที่ทำงานเพิ่ม ประเภทวันจะอ้างอิงจากปฏิทินให้อัตโนมัติ")
            dates = period_dates(selected_month)
            metadata = {day: db.get_calendar_day(day) for day in dates}
            chosen = st.multiselect(
                "วันที่ทำ OT / ทำงานวันหยุด", dates,
                format_func=lambda d: f"{thai_date(d)} · {DAY_LABELS[metadata[d]['day_type']]}",
                placeholder="เลือกวันที่ทำงานเพิ่มได้หลายวัน", key=f"{prefix}_dates",
                persist_state="session",
            )
            entries = []
            for day in sorted(chosen):
                info = metadata[day]
                kind = info["day_type"]
                with st.container(border=True):
                    st.write(f"**{thai_date(day)}** :{DAY_BADGES[kind]}-badge[{DAY_LABELS[kind]}]")
                    st.caption(info["description"])
                    ordinary = kind == "WHITE"
                    hours = st.number_input(
                        "ชั่วโมง OT หลังงานปกติ 8 ชม." if ordinary else "ชั่วโมงทำงานทั้งหมดในวันหยุด",
                        min_value=0.0, max_value=16.0 if ordinary else 24.0, value=0.0, step=0.5,
                        key=f"{prefix}_{day.isoformat()}_{kind}_hours", persist_state="session",
                    )
                    working_hours = hours + 8 if ordinary else hours
                    preview = db.calculate_pay(salary, working_hours, kind)
                    added = preview["overtime_pay"] if ordinary else preview["total_pay"]
                    st.caption(f"เพิ่มจากวันนี้ {money(added)} · " +
                               ("OT ×1.5" if ordinary else "ทุกชั่วโมง ×3" if kind == "BLUE" else "8 ชม.แรก ×1 · หลัง 8 ชม. ×3"))
                    entries.append({"work_date": day, "day_type": kind, "working_hours": working_hours})
            if not chosen:
                st.caption("ยังไม่มี OT · คำนวณเงินเดือนและเงินเพิ่มได้ตามปกติ")
            if any(day.year != 2026 for day in chosen):
                st.warning("บางวันที่เลือกอยู่นอกปฏิทินอ้างอิงปี 2026 ระบบใช้วันจันทร์–ศุกร์เป็นวันทำงาน และเสาร์–อาทิตย์เป็นวันหยุด เว้นแต่กำหนดเองในหน้าปฏิทิน")

    try:
        result = calculate_monthly_salary(salary, incomes, deductions, entries)
    except ValueError as exc:
        with results:
            st.error(f"กรุณาตรวจข้อมูลที่กรอก: {exc}")
        return

    with results:
        with st.container(border=True):
            st.badge("คำนวณอัตโนมัติ", icon=":material/check_circle:", color="green")
            st.metric("ยอดรับสุทธิเดือนนี้", money(result["net_pay"]))
            st.caption("เงินเดือน + เงินเพิ่ม + ค่าทำงานเพิ่ม − รายการหัก")
            st.divider()
            for label, value in [("เงินเดือนพื้นฐาน", salary), ("เงินเพิ่มทั้งหมด", result["total_income"]),
                                 ("OT / ทำงานวันหยุด", result["additional_work_pay"]),
                                 ("รายได้รวมก่อนหัก", result["gross_pay"]),
                                 ("รายการหักทั้งหมด", -result["total_deductions"])]:
                label_col, value_col = st.columns([1.4, 1])
                label_col.write(label)
                value_col.markdown(f"**{money(value)}**", text_alignment="right")
            if result["net_pay"] < 0:
                st.warning("รายการหักมากกว่ารายได้รวม กรุณาตรวจสอบยอดที่กรอก")
            if not salary and entries:
                st.warning("ยังไม่ได้กรอกเงินเดือนพื้นฐาน ค่า OT จึงเป็น 0 บาท")
            st.download_button("ดาวน์โหลดสรุปยอด (.csv)", summary_csv(selected_month, result),
                               file_name=f"salary_{selected_month}.csv", mime="text/csv", type="primary",
                               icon=":material/download:", width="stretch")
            st.caption("เก็บค่าที่กรอกระหว่างเปลี่ยนหน้าในแท็บนี้ แยกตามรอบเดือน • ดาวน์โหลดสรุปไว้ก่อนปิดแท็บ")

        with st.container(border=True):
            st.subheader("ฐานคำนวณของคุณ", anchor=False)
            st.metric("ค่าจ้างต่อชั่วโมง", money(salary / 30 / 8))
            st.caption("เงินเดือนพื้นฐาน ÷ 30 วัน ÷ 8 ชั่วโมง")
            with st.expander("ดูวิธีคิดและรายละเอียด"):
                st.write("เงินเดือนนับเต็มเดือนเพียงครั้งเดียว วันทำงานปกติบวกเฉพาะ OT หลัง 8 ชั่วโมง ส่วนวันหยุดบวกค่าทำงานตามอัตราเดิมของระบบ")
                st.write("• วันทำงาน: OT ×1.5\n• วันหยุดประเพณี: ทุกชั่วโมง ×3\n• วันหยุดประจำสัปดาห์ / บริษัท: 8 ชม.แรก ×1 และหลังจากนั้น ×3")
                st.caption("เงินเพิ่มต่าง ๆ ไม่รวมในฐาน OT • ประกันสังคมและภาษีใช้ยอดที่คุณกรอก • หน้านี้เป็นการคำนวณส่วนตัว ไม่ได้เพิ่มรายการเข้ารายงานบันทึกเวลาทำงาน")

        with st.container(border=True):
            st.subheader("ปฏิทินอ้างอิง 2026", anchor=False)
            in_reference = [day for day in dates if day.year == 2026]
            if len(in_reference) == len(dates):
                workdays = sum(metadata[day]["day_type"] == "WHITE" for day in dates)
                a, b = st.columns(2)
                a.metric("วันทำงานในรอบ", f"{workdays} วัน")
                b.metric("วันหยุดในรอบ", f"{len(dates) - workdays} วัน")
            else:
                st.caption("รอบนี้มีวันที่อยู่นอกปี 2026 โปรดตรวจประเภทวันก่อนเพิ่ม OT")
            st.caption("อ้างอิง Calendar 2026.pdf ของบริษัท รวมวันเสาร์ที่เป็นวันทำงาน")
            st.button("เปิดปฏิทินวันทำงาน", icon=":material/calendar_month:",
                      on_click=open_calendar, width="stretch")
            with st.expander("วันหยุดในรอบเงินเดือนนี้"):
                holidays = [day for day in dates if metadata[day]["day_type"] != "WHITE"]
                for day in holidays:
                    st.write(f"**{thai_date(day)}** · {metadata[day]['description']}")
                if not holidays:
                    st.caption("ไม่มีวันหยุดในรอบนี้")
