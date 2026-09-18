# Calculate OT

แอป Streamlit ธีมชมพูพาสเทลสำหรับคำนวณเงินเดือนและ OT พร้อมปฏิทินบริษัทปี 2026 เปิดแอปแล้วกรอกตัวเลขได้ทันที โดยไม่ต้องเพิ่มพนักงานหรือบันทึกเวลาก่อน เมนูจัดการพนักงาน บันทึกเวลา เงินเดือน และรายงานเดิมยังใช้งานได้ ข้อมูลส่วนจัดการเก็บใน SQLite

## คำนวณเงินเดือนแบบง่าย

1. เลือกรอบเงินเดือนในแถบด้านข้าง (วันที่ 16 เดือนก่อน ถึงวันที่ 15 ของเดือนที่เลือก)
2. กรอกเงินเดือนพื้นฐาน เบี้ยขยัน ค่าอาหาร ค่าเดินทาง ค่ากะ และเงินเพิ่มอื่น ๆ เป็นยอดรวมต่อเดือน
3. กรอกยอดประกันสังคม ภาษีหัก ณ ที่จ่าย และรายการหักอื่น ๆ ตามยอดจริง ไม่ได้คำนวณอัตราหักให้อัตโนมัติ
4. ถ้ามี OT ให้เลือกวันที่ทำงานเพิ่ม ระบบอ่านประเภทวันจากปฏิทิน: วันทำงานกรอกเฉพาะ OT หลัง 8 ชั่วโมง; วันหยุดกรอกชั่วโมงทำงานทั้งหมด
5. ยอดรับสุทธิอัปเดตเมื่อกด Enter หรือออกจากช่อง และดาวน์โหลดสรุปเป็น CSV ที่เปิดใน Excel ได้

สูตร: **เงินเดือนเต็มเดือน + เงินเพิ่ม + OT / ค่าทำงานวันหยุด − รายการหัก**

เงินเดือนพื้นฐานเป็นฐาน OT (`เงินเดือน ÷ 30 ÷ 8`) เงินเพิ่มไม่รวมในฐานนี้ วันทำงานปกติบวกเฉพาะ OT เพื่อไม่ให้นับค่าจ้างปกติซ้ำ เงินเดือนเต็มเดือนยังไม่หักการขาดงานหรือลางานอัตโนมัติ ให้กรอกยอดในรายการหักหากมี

ตัวเลขหน้าคำนวณเก็บระหว่างเปลี่ยนหน้าในแท็บเดิม แยกตามรอบเดือน แต่ไม่บันทึกลงประวัติพนักงานหรือรายงานเงินเดือนเดิม ให้ดาวน์โหลดสรุปก่อนปิดแท็บหรือเริ่มเซสชันใหม่

## ปฏิทินอ้างอิง

อ่านประเภทวันครบทั้ง 365 วันจาก `assets/calendar-2026.pdf` ซึ่งเป็นสำเนาไฟล์ที่ผู้ใช้แนบ (18/10/2025, Rev.00) รวมวันเสาร์ที่เป็นวันทำงาน มีวันทำงาน 256 วัน วันหยุดประจำสัปดาห์ 84 วัน วันหยุดประเพณี 13 วัน และวันหยุดบริษัท 12 วัน

หน้าปฏิทินเรียงวันที่ตรงวันในสัปดาห์ แสดงวันหยุดสำคัญ และมีปุ่มดาวน์โหลดต้นฉบับ การกำหนดวันเองมีผลเหนือปฏิทินอ้างอิงและใช้ทั้งแอป ลบการกำหนดเพื่อคืนค่าตามต้นฉบับ บันทึกเวลาที่มีอยู่แล้วจะไม่เปลี่ยนประเภทวันตามการแก้ปฏิทิน

หมายเหตุกะกลางคืนในต้นฉบับ: สลับ 23 ม.ค. กับ 14 ก.พ. และ 10 เม.ย. กับ 9 พ.ค. ต้องตรวจและกำหนดวันให้ตรงกะเอง ปฏิทินเดือนมกราคม 2027 ในต้นฉบับระบุว่าเป็นฉบับร่าง จึงไม่ใช้เป็นค่าเริ่มต้น นอกปี 2026 จะมีข้อความแจ้งว่าใช้กฎจันทร์–ศุกร์ทำงาน / เสาร์–อาทิตย์หยุด เว้นแต่กำหนดเอง

## Run it

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

The first run creates `calculate_ot.db` automatically. Verified 2026 reference dates are separate from user overrides. A one-time migration removes only unchanged legacy holiday seed rows so the reference can apply; custom overrides and attendance records are retained.

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
python -m unittest discover -v
```
