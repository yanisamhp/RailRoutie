"""Cached handle to the existing TransportBackend (unchanged)."""
from __future__ import annotations

import streamlit as st

from . import data


@st.cache_resource(show_spinner=False)
def get_backend():
    from transport_backend import TransportBackend

    return TransportBackend(data.ROOT)
