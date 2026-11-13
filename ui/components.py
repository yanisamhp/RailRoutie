"""RailRoutie UI components. Pure HTML builders (testable) plus thin st.markdown renderers."""
from __future__ import annotations

import html

import streamlit as st

from . import data
from .theme import line_style


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def render(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


# ---------------------------------------------------------------- small pieces
def line_badge(line_id, label=None) -> str:
    style = line_style(line_id)
    text = label or style["name_th"] or str(line_id)
    return f'<span class="rl-badge" style="background:{style["color"]};color:{style["text"]}">{esc(text)}</span>'


def status_chip(view: dict) -> str:
    return f'<span class="rl-status {esc(view["kind"])}">{esc(view["label"])}</span>'


def stat_card(label, value, est: bool = False) -> str:
    cls = ' class="est"' if est else ""
    return f'<div class="rl-stat"><small>{esc(label)}</small><b{cls}>{esc(value)}</b></div>'


# ---------------------------------------------------------------- timeline
def timeline_html(route: dict) -> str:
    """Vertical timeline, one block per leg, transfer blocks between legs. No times are invented."""
    route = route if isinstance(route, dict) else {}
    legs = route.get("legs") or []
    ids = route.get("station_line_ids") or []
    transfers = route.get("transfers") or []
    if not legs:
        if not ids:
            return ""
        legs = [{"line_id": data.station_line(ids[0]), "line_name_th": "", "station_line_ids": ids, "stations": len(ids)}]
    last_leg = len(legs) - 1
    parts = []
    for li, leg in enumerate(legs):
        lid = leg.get("line_id") or ""
        style = line_style(lid)
        members = leg.get("station_line_ids") or []
        name = leg.get("line_name_th") or style["name_th"] or lid
        count = leg.get("stations", len(members))
        parts.append(f'<div class="rl-leg" style="--lc:{style["color"]}">')
        parts.append(f'<div class="rl-leg-head">{line_badge(lid, name)}<span>{esc(count)} สถานี</span></div>')
        parts.append('<div class="rl-stops">')
        for si, sid in enumerate(members):
            key = si == 0 or si == len(members) - 1
            tag = ""
            if li == 0 and si == 0:
                tag = ' <span class="rl-chip">ต้นทาง</span>'
            if li == last_leg and si == len(members) - 1:
                tag = ' <span class="rl-chip">ปลายทาง</span>'
            sub = " · ".join(x for x in (data.station_name_en(sid), data.station_code(sid)) if x)
            parts.append(f'<div class="rl-stop{" key" if key else ""}">{esc(data.station_name(sid))}{tag}<small>{esc(sub)}</small></div>')
        parts.append('</div></div>')
        if li < last_leg:
            a = members[-1] if members else None
            b = (legs[li + 1].get("station_line_ids") or [None])[0]
            tr = next((t for t in transfers if isinstance(t, dict) and t.get("from") == a and t.get("to") == b), None)
            dist = (tr or {}).get("distance_m_from_file")
            extra = ""
            if isinstance(dist, (int, float)) and not isinstance(dist, bool):
                extra = f"<small>ระยะเชื่อมต่อตามไฟล์ข้อมูล ประมาณ {dist:,.0f} ม. (ไม่ใช่เวลาเดิน)</small>"
            parts.append(f'<div class="rl-transfer">เปลี่ยนสาย: {esc(data.station_name(a))} → {esc(data.station_name(b))}{extra}</div>')
    return "".join(parts)


# ---------------------------------------------------------------- fare breakdown
def segment_rows_html(fare: dict) -> str:
    rows = []
    for seg in (fare or {}).get("fare_segments") or []:
        if not isinstance(seg, dict):
            continue
        system = seg.get("fare_system") or ""
        a, b = seg.get("from_station_line_id"), seg.get("to_station_line_id")
        route_txt = f"{data.station_name(a)} → {data.station_name(b)}" if a and b else ""
        amount = data.format_baht(seg.get("fare_thb"))
        flag = "" if seg.get("status") == "OK" else ' <span class="rl-chip">ประมาณการ</span>'
        rows.append(
            '<div style="display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid #F0EAE3">'
            f'<div style="flex:0 0 auto">{line_badge(system)}</div>'
            f'<div style="flex:1;font-size:13px;color:#5E554F">{esc(route_txt)}</div>'
            f'<div style="font-variant-numeric:tabular-nums;font-weight:600">{esc(amount)}{flag}</div></div>'
        )
    return "".join(rows)


# ---------------------------------------------------------------- alternatives
def alt_card_html(index: int, candidate: dict, is_main: bool, is_cheapest: bool) -> str:
    route = (candidate or {}).get("route") or {}
    fare = (candidate or {}).get("fare") or {}
    summary = route.get("summary") or {}
    view = data.fare_view(fare)
    transfers = summary.get("transfer_count", len(route.get("transfers") or []))
    stations = len(route.get("station_line_ids") or [])
    chips = ""
    if is_main:
        chips += '<span class="rl-chip">เส้นทางหลัก</span>'
    if is_cheapest and view["kind"] == "ok":
        chips += '<span class="rl-chip">ถูกที่สุดในกลุ่มที่เปรียบเทียบ</span>'
    badges = "".join(line_badge(l) for l in summary.get("lines_used") or [])
    amount_style = ' style="opacity:.8"' if view["kind"] == "est" else ""
    return (
        f'<div class="rl-alt{" best" if is_main else ""}">'
        f'<h4>ตัวเลือก {esc(index)}</h4><div style="margin-bottom:10px">{chips}</div>'
        f'<div style="margin-bottom:10px">{badges}</div>'
        '<dl>'
        f'<dt>จุดเปลี่ยนสาย</dt><dd>{esc(transfers)}</dd>'
        f'<dt>จำนวนสถานี</dt><dd>{esc(stations)}</dd>'
        f'<dt>ค่าโดยสาร</dt><dd{amount_style}>{esc(view["amount_text"])}</dd>'
        f'<dt>สถานะราคา</dt><dd>{status_chip(view)}</dd>'
        '</dl></div>'
    )


# ---------------------------------------------------------------- notes
def scope_notes(plan: dict, poi: bool = False) -> list:
    plan = plan if isinstance(plan, dict) else {}
    fare = plan.get("fare") or {}
    n = len(plan.get("candidates") or [])
    notes = []
    if plan.get("network_wide_cheapest_proven") is True:
        notes.append("Backend ระบุว่าเส้นทางที่ถูกที่สุดของทั้งเครือข่ายผ่านการพิสูจน์แล้ว")
    else:
        notes.append(f"เปรียบเทียบเฉพาะ {n} เส้นทางที่ระบบเสนอ ไม่ได้พิสูจน์ว่าเป็นเส้นทางที่ถูกที่สุดในเครือข่ายทั้งหมด")
    snap = fare.get("data_snapshot_date")
    notes.append(f"ข้อมูลค่าโดยสารอ้างอิงวันที่ {snap}" + " ไม่ใช่ข้อมูลเรียลไทม์" if snap else "ข้อมูลค่าโดยสารไม่ใช่ข้อมูลเรียลไทม์ และไม่ระบุวันที่อ้างอิง")
    if data.fare_view(fare)["kind"] == "est":
        notes.append("ค่าโดยสารเส้นทางนี้เป็นราคาประมาณการ ยังไม่ผ่านการตรวจสอบเป็นราคาทางการ")
    notes.append("พิกัดสถานีในชุดข้อมูลทั้งหมดเป็นค่าชั่วคราว (PROVISIONAL) บางสถานียังไม่ผ่านการตรวจสอบ")
    if poi:
        notes.append("ระยะระหว่างสถานที่กับสถานีเป็นระยะเส้นตรง (Haversine) ไม่ใช่ระยะทางเดินจริง")
    return notes


def notes_html(notes: list) -> str:
    return "".join(f'<div class="rl-note" style="margin-bottom:8px">{esc(n)}</div>' for n in notes)
