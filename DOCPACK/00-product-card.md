---
title: devtools-cloud-benchmark — Product Card
doc_id: CARD-devtools-cloud-benchmark
doc_type: product-card
verdict: showcase
version: 0.1
date: 2026-10-18
status: ร่างเพื่อพิจารณา
owner: Product owner (Book Dev)
---

# devtools-cloud-benchmark — Product Card

## 1. สรุปคุณค่าในหนึ่งประโยค

หลักฐานที่ตรวจสอบได้ว่าเจ้าของใช้ PaaS หลายเจ้าเป็นจริง: บริการเดียว deploy ไป Railway, Render, Fly.io และ Cloud Run วัดด้วยวิธีเดียวกัน แล้วลบทิ้ง พร้อม ADR ที่ตอบว่า "ทำไมเลือกเจ้านี้"

## 2. ปัญหาและผู้ใช้เป้าหมาย

- ปัญหา: โลโก้ cloud บน portfolio ไม่ได้พิสูจน์อะไร และ PaaS ส่วนใหญ่ทำได้คล้ายกันจนแยกจุดเด่นไม่ออกถ้าไม่วัดจริง
- ผู้ใช้เป้าหมาย: ผู้จ้าง ลูกค้าที่ปรึกษา และตัวเจ้าของเองตอนเลือก provider ให้ product ใหม่ — ผู้อ่านจริง **[ต้องยืนยัน]**

## 3. สิ่งที่ทำได้จริงตอนนี้

- บริการ `app/main.py` (FastAPI, ไม่มี DB) และ contract `contract/check.py` ที่ตรวจค่าตรงตัว
- `runner/run.py` วัด ready time, latency แบบทีละ request, load ด้วย oha และ CPU share; `runner/orchestrate.py` ทำ deploy → วัด → destroy ทีละ target บนเครื่องเดียว
- สคริปต์ deploy/destroy 4 target และ workflow `bench.yml` (manual) — **ยังไม่เคยรันกับบัญชีจริง**
- เทสต์ 14 ตัว (contract ผ่านกับบริการจริง ล้มกับบริการที่ผิด; orchestrator ลบทิ้งแม้ contract ล้ม, destroy ล้มแล้วรันต้องล้ม, safety sweep ทำต่อทุก target, timeout kill ทั้ง process group, หน้าเว็บแสดงเฉพาะรอบที่ผ่าน)

## 4. หลักฐานสถานะ

| รายการ | ค่า |
|---|---|
| Stack | Python 3.12, FastAPI, uvicorn, oha 1.16.0 |
| Tests | 14 (pytest) |
| CI | `ci.yml` (reusable ci-python + security v1.0.1, image build + contract), `bench.yml` (manual) |
| Live URL | ยังไม่มี |

## 5. คุณค่าและจุดต่าง

- จุดต่าง: ทุกตัวเลขมี run record และผ่าน contract ก่อน; ทุก provider มี ADR; lab ไม่เปิดค้างจึงแทบไม่มีค่าใช้จ่ายระหว่างรอบ
- มุมรายได้: ไม่มีโดยตรง — หลักฐานความสามารถ cloud/platform engineering **[สมมติฐาน]**

## 6. ช่องว่างสำคัญ

- ยังไม่มีผลวัดจริง; ต้องตั้งค่าบัญชีแต่ละ provider ตาม runbook ก่อน
- ตำแหน่ง client (GitHub-hosted runner) ควบคุมไม่ได้
- ราคาต่อรอบยังเป็นค่าประมาณ ต้องตรวจกับหน้าราคาแต่ละเจ้า

## 7. คำตัดสิน

**`showcase`** — ผลงานเชิงวิศวกรรมสำหรับ portfolio; ไม่ใช่ธุรกิจ

## 8. ขั้นต่อไป

1. สร้าง repo บน GitHub และตั้งค่า provider ตาม runbook
2. รัน bench ครั้งแรกทีละ target บันทึกผลใน ADR แล้วเชื่อม Vercel กับ `site/`

## การอนุมัติ

| บทบาท | สถานะ | วันที่ | ลงนาม |
|---|---|---|---|
| Product owner (Book Dev) | รอพิจารณา | — | ________ |

## แหล่งข้อมูล

- `README.md`, `runner/`, `targets/`, `contract/`, `.github/workflows/`
