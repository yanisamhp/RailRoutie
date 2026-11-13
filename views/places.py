"""Places: plan a journey between two places (POI search)."""
from __future__ import annotations

import streamlit as st

from ui import data
from ui.backend import get_backend
from ui.components import render
from ui.journey import render_journey
from ui.search import poi_picker

STATE = "journey_place"
BLOCKED = {"POI_CONFIRMATION_REQUIRED", "POI_UNAVAILABLE", "INVALID_STATION_SELECTION"}
render(
    '<p class="rl-kicker">Places</p><h1 class="rl-page-title">วางแผนเดินทางจากสถานที่</h1>'
    '<p class="rl-muted" style="margin-bottom:26px">ค้นหาชื่อสถานที่ภาษาไทยหรืออังกฤษ ระบบจะจับคู่กับสถานีที่ใกล้ที่สุดด้วยระยะเส้นตรง (ใช้ OpenStreetMap Nominatim ต้องเชื่อมต่ออินเทอร์เน็ต)</p>'
)
with st.container(key="panel"):
    c1, c2 = st.columns(2, gap="large")
    with c1:
        render('<p class="rl-label">From</p>')
        origin = poi_picker("สถานที่ต้นทาง", "origin")
    with c2:
        render('<p class="rl-label">To</p>')
        destination = poi_picker("สถานที่ปลายทาง", "destination")
    st.write("")
    # The backend searches up to 3 candidate routes; alternatives are collapsed in results.
    alternatives = 3
    go = st.button("ค้นหาเส้นทาง", type="primary", use_container_width=True, key="places_go", disabled=origin is None or destination is None)

if go:
    try:
        with st.spinner("กำลังคำนวณเส้นทางและค่าโดยสาร..."):
            result = get_backend().plan_places(
                origin["query"],
                destination["query"],
                origin_choice=origin["choice"],
                destination_choice=destination["choice"],
                alternatives=alternatives,
            )
        status = (result or {}).get("status")
        if status in BLOCKED:
            st.session_state.pop(STATE, None)
            st.warning(data.PLAN_STATUS_TH.get(status, "ยังวางแผนไม่ได้"))
        else:
            st.session_state[STATE] = {"mode": "poi", "result": result}
            st.session_state.pop("places_option", None)
    except Exception as exc:
        st.error(f"ไม่สามารถคำนวณเส้นทางได้: {exc}")

journey = st.session_state.get(STATE)
if journey:
    st.write("")
    st.write("")
    render_journey(journey, "places")
