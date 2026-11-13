"""railly search widgets: station picker and POI picker. UI only; POI search is the existing backend."""
from __future__ import annotations

import sys

import streamlit as st

from . import data
from .components import esc, render
from .theme import line_style

for _dir in (data.ROOT / "routing", data.ROOT / "fare"):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))
from poi_search import search_poi  # noqa: E402  (existing backend module)


def _station_option(sid) -> str:
    row = data.station_row(sid)
    line = line_style(row.get("line_id", ""))["name_th"] or row.get("line_id", "")
    return f"{row.get('name_th', '')} · {row.get('name_en', '')} ({row.get('station_code', '')}) — {line}"


def station_picker(title: str, key: str):
    """Returns a station_line_id or None. With several matches the user must choose explicitly."""
    query = st.text_input(title, placeholder="พิมพ์ชื่อสถานี ไทยหรืออังกฤษ เช่น สยาม, Siam, A1", key=f"{key}_station_query")
    q = query.strip()
    if not q:
        st.caption("พิมพ์ชื่อหรือรหัสสถานีเพื่อค้นหา")
        return None
    rows = data.search_stations(q)
    if not rows:
        st.warning("ไม่พบสถานีที่ตรงกับคำค้นหา ลองพิมพ์ชื่ออื่นหรือสะกดใหม่")
        return None
    ids = [r["station_line_id"] for r in rows]
    if len(ids) == 1:
        st.caption(f"พบ 1 สถานี: {_station_option(ids[0])}")
        return ids[0]
    if len(ids) >= 30:
        st.caption("แสดง 30 รายการแรก ลองพิมพ์ให้เฉพาะเจาะจงขึ้น")
    return st.selectbox(
        "เลือกสถานีจากผลค้นหา",
        ids,
        index=None,
        placeholder=f"พบ {len(ids)} สถานี เลือกหนึ่งรายการ",
        format_func=_station_option,
        key=f"{key}_station_pick_{q.casefold()}",
        label_visibility="collapsed",
    )


def _candidate_option(candidate: dict) -> str:
    name = candidate.get("name") or "ไม่ทราบชื่อ"
    addr = candidate.get("display_name") or ""
    if addr.startswith(name):
        addr = addr[len(name):].lstrip(", ")
    addr = addr[:80] + ("…" if len(addr) > 80 else "")
    return f"{name} — {addr}" if addr else name


def _place_card(place: dict) -> None:
    link = place.get("source_url") or ""
    src = f' · <a href="{esc(link)}" target="_blank" rel="noopener">ดูบน OpenStreetMap</a>' if link.startswith("https://") else ""
    render(
        '<div class="rl-note" style="margin-top:6px">'
        f'<b>{esc(place.get("name"))}</b><br>'
        f'<span style="color:#817A74;font-size:12px">{esc(place.get("display_name"))}{src}</span></div>'
    )


def poi_picker(title: str, key: str):
    """Returns {"query", "choice", "place"} or None.
    choice is the POI candidate index the user confirmed (never a station index);
    it is None when the backend already resolved the place (status OK)."""
    query = st.text_input(title, placeholder="เช่น สยามพารากอน, สนามบินสุวรรณภูมิ", key=f"{key}_poi_query")
    q = query.strip()
    if st.button("ค้นหาสถานที่", key=f"{key}_poi_btn", use_container_width=True):
        if not q:
            st.warning("กรุณาพิมพ์ชื่อสถานที่ก่อนค้นหา")
        else:
            with st.spinner("กำลังค้นหาสถานที่..."):
                try:
                    result = search_poi(q)
                except Exception as exc:  # network/provider failure must not crash the page
                    result = {"status": "NETWORK_ERROR", "message": str(exc)}
            st.session_state[f"{key}_poi_state"] = {"query": q, "result": result}
    state = st.session_state.get(f"{key}_poi_state")
    if not q or not state:
        if q:
            st.caption("กด “ค้นหาสถานที่” เพื่อดูรายการ")
        return None
    if state["query"] != q:
        st.caption("คำค้นหาเปลี่ยนไป กด “ค้นหาสถานที่” อีกครั้ง")
        return None

    result = state["result"] if isinstance(state["result"], dict) else {}
    status = result.get("status")
    candidates = result.get("candidates") or []
    if status not in ("OK", "AMBIGUOUS", "CONFIRMED"):
        st.warning(data.POI_STATUS_TH.get(status, "ค้นหาสถานที่ไม่สำเร็จ กรุณาลองอีกครั้ง"))
        if result.get("message"):
            st.caption(str(result["message"]))
        return None
    if not candidates:
        st.warning("ไม่พบรายการสถานที่ ลองใช้ชื่ออื่น")
        return None
    if result.get("fallback_query"):
        st.info(f"ไม่พบ “{q}” โดยตรง ระบบจึงค้นหาด้วย “{result['fallback_query']}” แทน ผลอาจเป็นคนละสถานที่ กรุณาตรวจสอบ")

    needs_choice = status == "AMBIGUOUS" or result.get("needs_confirmation") is True
    if needs_choice:
        st.caption(f"พบ {len(candidates)} รายการ กรุณาเลือกสถานที่ที่ถูกต้อง (ระบบจะไม่เลือกให้อัตโนมัติ)")
        picked = st.selectbox(
            "เลือกและยืนยันสถานที่",
            list(range(len(candidates))),
            index=None,
            placeholder="เลือกสถานที่",
            format_func=lambda i: _candidate_option(candidates[i]),
            key=f"{key}_poi_pick_{q.casefold()}",
            label_visibility="collapsed",
        )
        if picked is None:
            return None
        place, choice = candidates[int(picked)], int(picked)
    else:
        place = result.get("selected") or candidates[0]
        choice = None if result.get("selected") else 0
    _place_card(place)
    return {"query": q, "choice": choice, "place": place}


# ---------------------------------------------------------------- station picker by line
def _set_line(state_key: str, line_id: str) -> None:
    st.session_state[state_key] = line_id


def _station_choice_label(sid, show_line: bool) -> str:
    row = data.station_row(sid)
    base = f"{row.get('station_code', '')} · {row.get('name_th', '')} · {row.get('name_en', '')}"
    if show_line:
        base += f" — {line_style(row.get('line_id', ''))['short'] or row.get('line_id', '')}"
    return base


def station_by_line(title: str, key: str):
    """Tap a line chip first, then choose a station of that line (typing filters the list).
    Returns station_line_id or None. Chip keys: <key>_line_<LINE_ID>[_on]."""
    from .theme import LINE_ORDER

    state_key = f"{key}_line"
    current = st.session_state.get(state_key)
    in_data = data.line_ids_in_dataset()
    options = ["ALL"] + [l for l in LINE_ORDER if l in in_data] + [l for l in in_data if l not in LINE_ORDER]
    for start in range(0, len(options), 4):
        cols = st.columns(4, gap="small")
        for col, lid in zip(cols, options[start:start + 4]):
            with col:
                label = "ทุกสาย" if lid == "ALL" else (line_style(lid)["short"] or lid)
                st.button(
                    label,
                    key=f"{key}_line_{lid}{'_on' if current == lid else ''}",
                    type="primary" if current == lid else "secondary",
                    on_click=_set_line,
                    args=(state_key, lid),
                    use_container_width=True,
                )
    st.write("")
    if current is None:
        st.selectbox(title, [], index=None, placeholder="เลือกสายก่อน แล้วเลือกสถานี", disabled=True, key=f"{key}_station_none")
        return None
    rows = data.filter_stations(line_ids=None if current == "ALL" else [current])
    ids = [r["station_line_id"] for r in rows]
    return st.selectbox(
        title,
        ids,
        index=None,
        placeholder="พิมพ์หรือเลือกสถานี",
        format_func=lambda sid: _station_choice_label(sid, current == "ALL"),
        key=f"{key}_station_{current}",
    )
