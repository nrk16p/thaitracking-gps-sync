import os
import logging
from datetime import datetime, timedelta

import requests
from requests.auth import HTTPBasicAuth

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────
THAITRACKING_URL = 'https://wlittt.com:8033/Realtime/menatran/menatran'
BACKEND_URL       = 'https://backend-tdm.onrender.com/gpsdata'

PLATE_TYPE = 'H'
GPS_VENDOR = 'thaitracking'
TIME_OFFSET_HOURS = 0  # thaitracking ส่งเวลาไทยอยู่แล้ว (ยืนยันแล้วตอนทดสอบ)
TIMEOUT = 30


def load_env_file(path: str = '.env') -> None:
    """โหลด .env แบบง่าย ๆ สำหรับรัน local (Jenkins ใช้ env จริง)"""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())


def _to_bkk(dt_str) -> str:
    for fmt in ('%d/%m/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
        try:
            dt = datetime.strptime(str(dt_str), fmt)
            return (dt + timedelta(hours=TIME_OFFSET_HOURS)).strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            continue
    return str(dt_str)


def fetch_gps(username: str, password: str) -> list:
    resp = requests.get(
        THAITRACKING_URL,
        auth=HTTPBasicAuth(username, password),
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = (data.get('data') or data.get('result') or data.get('items')
                   or next((v for v in data.values() if isinstance(v, list)), []))
    else:
        records = []

    log.info(f'thaitracking fetch OK — {len(records)} records')
    return records


def _speed_kmh(v):
    """speed → int km/h; ค่าว่าง/อ่านไม่ได้ → None (ไม่ทำให้ทั้งรอบพัง)"""
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def build_payload(records: list) -> list:
    payload = []
    for r in records:
        plate = r.get('plate', '')
        lat = r.get('latitude')
        lng = r.get('longitude')
        speed = r.get('speed')

        try:
            is_stopped = float(speed) == 0
        except (TypeError, ValueError):
            is_stopped = str(speed) in ('', '0', '0.0')

        payload.append({
            'gps_id'        : str(plate),
            'plate_master'  : plate,
            'plate_type'    : PLATE_TYPE,
            'gps_vendor'    : GPS_VENDOR,
            'current_latlng': f'{lat},{lng}' if lat not in (None, '') and lng not in (None, '') else '',
            'gps_updated_at': _to_bkk(r.get('gps_datetime')),
            'status'        : 'หยุด' if is_stopped else 'วิ่ง',
            'speed'         : _speed_kmh(speed),                    # km/h
        })
    return payload


def post_to_backend(payload: list) -> None:
    resp = requests.post(
        BACKEND_URL,
        json=payload,
        headers={'Content-Type': 'application/json'},
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json() if resp.text else []
    updated = len([r for r in result if r.get('gps_updated_at')])
    log.info(f'POST {resp.status_code} — sent={len(payload)}, updated={updated}')


def main():
    log.info(f'=== thaitracking GPS sync started — {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} ===')

    load_env_file()
    username = os.environ.get('THAITRACKING_USERNAME', '')
    password = os.environ.get('THAITRACKING_PASSWORD', '')
    if not username or not password:
        raise SystemExit('Missing THAITRACKING_USERNAME / THAITRACKING_PASSWORD env vars')

    records = fetch_gps(username, password)
    payload = build_payload(records)

    if not payload:
        raise SystemExit('No GPS data fetched — aborting POST')

    post_to_backend(payload)
    log.info('=== Done ===')


if __name__ == '__main__':
    main()
