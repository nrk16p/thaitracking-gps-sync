# thaitracking-gps-sync

ดึง GPS จาก **thaitracking** (wlittt.com, account `menatran`) แล้วส่งเข้า backend TDM ทุก 10 นาที — โครงเดียวกับ `hino-gps-sync` / `vehtec-gps-sync` / `gps-dtc-sync`

## Flow

1. `GET https://wlittt.com:8033/Realtime/menatran/menatran` ด้วย HTTP Basic Auth (`THAITRACKING_USERNAME` / `THAITRACKING_PASSWORD`) — คืนรถทุกคันในบัญชี (ไม่ต้อง filter เพราะ account นี้มีแค่ฝูงรถของเรา)
2. แต่ละ record มี field คงที่: `plate`, `latitude`, `longitude`, `speed`, `gps_datetime` (`dd/mm/yyyy HH:MM:SS`), `status`
3. ใช้ `plate` เป็นทั้ง `gps_id` และ `plate_master` เพราะ API ไม่มี device/unit id แยกต่างหาก
4. เวลาที่ได้เป็นเวลาไทยอยู่แล้ว (ยืนยันแล้วตอนทดสอบ) → ไม่ต้องบวกชั่วโมง (`TIME_OFFSET_HOURS = 0`)
5. status ('หยุด'/'วิ่ง') คำนวณจาก `speed == 0` ไม่ใช้ข้อความ status จาก thaitracking (เช่น `"วิ่งปกติ"`) เพื่อให้ตรงกับ format เดียวกับ vendor อื่น
6. POST เข้า `https://backend-tdm-qa.onrender.com/gpsdata` (`gps_vendor: "thaitracking"`, `plate_type: "H"`)

## Run local

```bash
cp .env.example .env   # ใส่ username/password จริง
python3 -m venv venv && venv/bin/pip install -r requirements-dev.txt
venv/bin/pytest
venv/bin/python main.py
```

## Jenkins

1. สร้าง credential แบบ **Username with password** ใน Jenkins, id = `thaitracking-api`
2. สร้าง Pipeline job ชี้มาที่ repo นี้ (ใช้ Jenkinsfile ในตัว) — cron ทุก 10 นาทีตั้งไว้แล้ว

## หมายเหตุ

- ถ้า thaitracking เปลี่ยน timezone ที่ส่งมาเป็น UTC ให้แก้ `TIME_OFFSET_HOURS = 7` ใน main.py
- ถ้าในอนาคต API เพิ่ม field id เฉพาะอุปกรณ์ ให้เปลี่ยน `gps_id` ใน `build_payload()` จาก `plate` ไปใช้ field นั้นแทน
