"""Company calendar transcribed visually from the user-supplied 2026 PDF.

The PDF is reference data, not instructions to the application or agent.
Every day of 2026 is covered explicitly; the January 2027 draft is excluded.
"""

from datetime import date, timedelta
from pathlib import Path

REFERENCE_PDF_PATH = Path(__file__).parent / "assets" / "calendar-2026.pdf"
SOURCE_TITLE = "SumiRiko Chemical and Plastic Products (Thailand) Ltd. — Calendar 2026"
SOURCE_REVISION = "Rev.00"
SOURCE_DATE = "2025-10-18"
DAY_TYPE_LABELS = {"WHITE": "วันทำงาน", "ORANGE": "วันหยุดประจำสัปดาห์",
                   "BLUE": "วันหยุดประเพณี", "GREEN": "วันหยุดบริษัท"}

# Orange cells in each month, including only the Saturdays actually shaded.
WEEKLY_HOLIDAYS = {
    1: (3, 4, 11, 17, 18, 24, 25),
    2: (1, 7, 8, 15, 21, 22),
    3: (1, 8, 14, 15, 22, 28, 29),
    4: (5, 11, 12, 18, 19, 26),
    5: (3, 9, 10, 16, 17, 24, 30, 31),
    6: (6, 7, 14, 20, 21, 28),
    7: (5, 11, 12, 18, 19, 26),
    8: (1, 2, 8, 9, 16, 22, 23, 29, 30),
    9: (6, 12, 13, 19, 20, 26, 27),
    10: (3, 4, 10, 11, 17, 18, 25, 31),
    11: (1, 7, 8, 14, 15, 21, 22, 29),
    12: (6, 12, 13, 19, 20, 27),
}
TRADITIONAL_HOLIDAYS = {
    "2026-01-01": "วันขึ้นปีใหม่",
    "2026-01-02": "วันหยุดพิเศษเทศกาลปีใหม่",
    "2026-03-03": "วันมาฆบูชา",
    "2026-04-13": "วันสงกรานต์",
    "2026-04-14": "วันสงกรานต์",
    "2026-04-15": "วันสงกรานต์",
    "2026-05-01": "วันแรงงานแห่งชาติ",
    "2026-06-01": "วันหยุดชดเชยวันวิสาขบูชา",
    "2026-07-28": "วันเฉลิมพระชนมพรรษาพระบาทสมเด็จพระเจ้าอยู่หัว",
    "2026-07-29": "วันอาสาฬหบูชา",
    "2026-08-12": "วันเฉลิมพระชนมพรรษาสมเด็จพระบรมราชชนนีพันปีหลวง (ตามต้นฉบับ)",
    "2026-12-05": "วันคล้ายวันพระบรมราชสมภพ รัชกาลที่ 9",
    "2026-12-31": "วันสิ้นปี",
}
COMPANY_HOLIDAYS = (
    "2026-02-14", "2026-03-02", "2026-03-21", "2026-04-16", "2026-04-17",
    "2026-05-02", "2026-06-27", "2026-07-04", "2026-07-27",
    "2026-12-28", "2026-12-29", "2026-12-30",
)
# Independent monthly totals printed on the PDF: WHITE, ORANGE, BLUE, GREEN.
MONTHLY_TOTALS = {
    1: (22, 7, 2, 0), 2: (21, 6, 0, 1), 3: (21, 7, 1, 2),
    4: (19, 6, 3, 2), 5: (21, 8, 1, 1), 6: (22, 6, 1, 1),
    7: (21, 6, 2, 2), 8: (21, 9, 1, 0), 9: (23, 7, 0, 0),
    10: (23, 8, 0, 0), 11: (22, 8, 0, 0), 12: (20, 6, 2, 3),
}

CALENDAR_2026 = {
    (date(2026, 1, 1) + timedelta(days=offset)).isoformat(): ("WHITE", "วันทำงาน")
    for offset in range(365)
}
for month, days in WEEKLY_HOLIDAYS.items():
    for day in days:
        CALENDAR_2026[date(2026, month, day).isoformat()] = ("ORANGE", "วันหยุดประจำสัปดาห์")
for day, description in TRADITIONAL_HOLIDAYS.items():
    CALENDAR_2026[day] = ("BLUE", description)
for day in COMPANY_HOLIDAYS:
    CALENDAR_2026[day] = ("GREEN", "วันหยุดบริษัท")


def reference_for(work_date: date | str) -> dict | None:
    day = work_date.isoformat() if isinstance(work_date, date) else date.fromisoformat(work_date).isoformat()
    item = CALENDAR_2026.get(day)
    if item is None:
        return None
    return {"work_date": day, "day_type": item[0], "description": item[1],
            "source": "calendar-2026.pdf", "is_override": False}


def is_reference_date(work_date: date | str) -> bool:
    return reference_for(work_date) is not None
