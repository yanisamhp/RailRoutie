"""RailRoutie: Thai Transit Planner. Streamlit entrypoint. UI only; the backend is untouched."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent

# Keep routing data portable between local development and Streamlit Cloud.
import os
os.environ.setdefault("DAI_ROUTING_DATA_DIR", str(ROOT / "data_original"))
for _dir in (ROOT, ROOT / "routing", ROOT / "fare"):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

st.set_page_config(page_title="RailRoutie: Thai Transit Planner", page_icon="🚆", layout="wide", initial_sidebar_state="collapsed")

from ui.components import render  # noqa: E402
from ui.theme import inject_css  # noqa: E402

inject_css()

pages = [
    st.Page("views/home.py", title="Home", url_path="home", default=True),
    st.Page("views/stations.py", title="Stations", url_path="stations"),
    st.Page("views/places.py", title="Places", url_path="places"),
]
navigation = st.navigation(pages, position="hidden")

with st.container(key="topnav"):
    brand, n1, n2, n3 = st.columns([6, 1.2, 1.4, 1.3], vertical_alignment="center")
    with brand:
        render('<div class="rl-brand"><span class="rl-logo"></span><b>RailRoutie</b><span class="sub">Thai Transit Planner</span></div>')
    active = navigation.url_path
    with n1.container(key="rr_nav_home_active" if active == "" else "rr_nav_home"):
        st.page_link("views/home.py", label="Home")
    with n2.container(key="rr_nav_stations_active" if active == "stations" else "rr_nav_stations"):
        st.page_link("views/stations.py", label="Stations")
    with n3.container(key="rr_nav_places_active" if active == "places" else "rr_nav_places"):
        st.page_link("views/places.py", label="Places")


st.markdown("""<style>
[class*="st-key-rr_nav_"] a {
    color:#242424!important;
    text-decoration:none!important;
    font-weight:600!important;
    border-bottom:3px solid transparent!important;
    border-radius:0!important;
    padding:12px 4px!important;
}
[class*="st-key-rr_nav_"] a:hover {color:#DC111D!important;}
[class*="st-key-rr_nav_"][class*="_active"] a {
    color:#DC111D!important;
    border-bottom-color:#DC111D!important;
    font-weight:800!important;
}
[class*="st-key-rr_nav_"] a p {color:inherit!important;}
</style>""", unsafe_allow_html=True)

navigation.run()
render('<div class="rl-foot">RailRoutie · Thai Transit Planner &nbsp;|&nbsp; Academic Prototype · ไม่ใช่ข้อมูลการเดินรถหรือราคาตั๋วแบบเรียลไทม์</div>')
