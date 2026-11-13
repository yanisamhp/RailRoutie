"""Stations: plan a journey between two stations."""
from __future__ import annotations

import streamlit as st

from ui.backend import get_backend
from ui.components import render
from ui.journey import render_journey
from ui.search import station_by_line

STATE = "journey_station"
render(
    '<p class="rl-kicker">Stations</p><h1 class="rl-page-title">วางแผนเดินทางจากสถานี</h1>'
    '<p class="rl-muted" style="margin-bottom:26px">กดเลือกสายรถไฟฟ้า แล้วเลือกสถานีในสายนั้น เลือก “ทุกสาย” หากต้องการค้นหาข้ามสาย</p>'
)
with st.container(key="panel"):
    c1, c2 = st.columns(2, gap="large")
    with c1:
        render('<p class="rl-label">From</p>')
        origin = station_by_line("สถานีต้นทาง", "so")
    with c2:
        render('<p class="rl-label">To</p>')
        destination = station_by_line("สถานีปลายทาง", "sd")
    # The backend searches up to 3 candidate routes; alternatives are collapsed in results.
    alternatives = 3
    go = st.button("ค้นหาเส้นทาง", type="primary", use_container_width=True, key="stations_go", disabled=origin is None or destination is None)

if go:
    try:
        with st.spinner("กำลังคำนวณเส้นทางและค่าโดยสาร..."):
            result = get_backend().plan(origin, destination, alternatives=alternatives)
        st.session_state[STATE] = {"mode": "station", "result": result}
        st.session_state.pop("stations_option", None)
    except Exception as exc:
        st.error(f"ไม่สามารถคำนวณเส้นทางได้: {exc}")

journey = st.session_state.get(STATE)
if journey:
    st.write("")
    st.write("")
    render_journey(journey, "stations")
