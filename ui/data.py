"""railly data helpers: station dataset, search and display rules. No routing/fare logic here."""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIONS_CSV = ROOT / "data_original" / "stations_coordinates_provisional.csv"


@lru_cache(maxsize=1)
def load_stations() -> dict:
    """station_line_id -> row (dict), in file order."""
    with STATIONS_CSV.open(encoding="utf-8-sig", newline="") as handle:
        return {row["station_line_id"]: row for row in csv.DictReader(handle)}


def station_row(sid) -> dict:
    return load_stations().get(str(sid), {})


def station_name(sid) -> str:
    row = station_row(sid)
    if not row:
        return str(sid or "-")
    return row.get("name_th") or row.get("name_en") or str(sid)


def station_name_en(sid) -> str:
    return station_row(sid).get("name_en", "")


def station_line(sid) -> str:
    return station_row(sid).get("line_id", "")


def station_code(sid) -> str:
    return station_row(sid).get("station_code", "")


def station_label(sid) -> str:
    row = station_row(sid)
    if not row:
        return str(sid)
    return f"{row.get('name_th', '')} · {row.get('name_en', '')} ({row.get('station_code', '')})"


def search_stations(query: str, limit: int = 30) -> list:
    """Rows matching Thai/English name, code or station_line_id. Empty query -> no results."""
    q = (query or "").strip().casefold()
    if not q:
        return []
    fields = ("name_th", "name_en", "station_code", "station_line_id")
    scored = []
    for i, row in enumerate(load_stations().values()):
        values = [str(row.get(f, "")).casefold() for f in fields]
        if any(v == q or v.startswith(q) for v in values):
            scored.append((0, i, row))
        elif any(q in v for v in values):
            scored.append((1, i, row))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [row for _, _, row in scored[:limit]]


def filter_stations(query: str = "", line_ids=None) -> list:
    """For the Explore page: all stations, optionally filtered by text and line."""
    rows = list(load_stations().values())
    if line_ids:
        rows = [r for r in rows if r.get("line_id") in set(line_ids)]
    q = (query or "").strip().casefold()
    if q:
        fields = ("name_th", "name_en", "station_code", "station_line_id")
        rows = [r for r in rows if any(q in str(r.get(f, "")).casefold() for f in fields)]
    return rows


def line_ids_in_dataset() -> list:
    seen = []
    for row in load_stations().values():
        if row.get("line_id") not in seen:
            seen.append(row.get("line_id"))
    return seen


# ---------------------------------------------------------------- fare display
def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def format_baht(amount) -> str:
    if not _is_number(amount):
        return "—"
    return f"฿{amount:,.0f}" if float(amount) == int(amount) else f"฿{amount:,.2f}"


def fare_view(fare) -> dict:
    """How to present a fare quote.
    kind: ok (verified) | est (estimate, needs review) | na (do not show an amount).
    Mirrors TransportBackend.plan(): PENDING_REVIEW counts as an estimate only if is_estimate is True.
    """
    fare = fare if isinstance(fare, dict) else {}
    status = fare.get("status")
    amount = fare.get("total_fare_thb")
    if status == "OK" and _is_number(amount):
        return {"kind": "ok", "label": "ราคาตรวจสอบแล้ว", "amount_text": format_baht(amount), "show_amount": True}
    if status == "PENDING_REVIEW" and fare.get("is_estimate") is True and _is_number(amount):
        return {"kind": "est", "label": "ประมาณการ (รอตรวจสอบ)", "amount_text": format_baht(amount), "show_amount": True}
    labels = {
        "PENDING_REVIEW": "รอตรวจสอบราคา",
        "FARE_DATA_UNAVAILABLE": "ยังไม่มีข้อมูลราคา",
        "UNKNOWN_STATION": "ไม่รู้จักสถานี",
        "ROUTE_NOT_FAREABLE": "เส้นทางนี้คำนวณราคาไม่ได้",
    }
    return {"kind": "na", "label": labels.get(status, "ไม่มีข้อมูลราคา"), "amount_text": "—", "show_amount": False}


# ---------------------------------------------------------------- messages
POI_STATUS_TH = {
    "NOT_FOUND": "ไม่พบสถานที่นี้ ลองใช้ชื่ออื่นหรือพิมพ์ให้ละเอียดขึ้น",
    "INVALID_QUERY": "คำค้นหาไม่ถูกต้อง กรุณาพิมพ์ชื่อสถานที่",
    "RATE_LIMITED": "ส่งคำค้นหาถี่เกินไป โปรดรอสักครู่แล้วลองอีกครั้ง",
    "NETWORK_ERROR": "เชื่อมต่อบริการค้นหาสถานที่ไม่ได้ ตรวจสอบอินเทอร์เน็ตแล้วลองอีกครั้ง",
}

PLAN_STATUS_TH = {
    "POI_CONFIRMATION_REQUIRED": "ยังวางแผนไม่ได้ กรุณายืนยันสถานที่ให้ครบทั้งต้นทางและปลายทาง",
    "POI_UNAVAILABLE": "ค้นหาสถานที่ไม่สำเร็จ กรุณาตรวจสอบชื่อสถานที่หรือการเชื่อมต่ออินเทอร์เน็ต",
    "INVALID_STATION_SELECTION": "ไม่พบสถานีใกล้เคียงตามที่เลือก กรุณาลองสถานที่อื่น",
    "ROUTING_ERROR": "ไม่พบเส้นทางระหว่างสองสถานีนี้",
}

# coordinate_qa_status -> (level, text). Every coordinate in the dataset is PROVISIONAL.
QA_STATUS_TH = {
    "WITHIN_100M": ("ok", "พิกัดใกล้จุดอ้างอิง OSM (ไม่เกิน 100 ม.)"),
    "WITHIN_200M": ("ok", "พิกัดใกล้จุดอ้างอิง OSM (ไม่เกิน 200 ม.)"),
    "REVIEW_200_500M": ("warn", "พิกัดห่างจุดอ้างอิง OSM 200–500 ม. ควรตรวจสอบ"),
    "PROVISIONAL_NOT_VERIFIED": ("warn", "พิกัดชั่วคราว ยังไม่ผ่านการตรวจสอบ"),
    "NO_USABLE_OSM_POINT": ("warn", "ไม่มีจุดอ้างอิง OSM ที่ใช้ได้ พิกัดยังไม่ยืนยัน"),
}


def qa_info(row: dict):
    return QA_STATUS_TH.get((row or {}).get("coordinate_qa_status"), ("warn", "ยังไม่มีข้อมูลตรวจสอบพิกัด"))
