"""Shared journey result renderer for the Stations and Places pages."""
from __future__ import annotations

import streamlit as st

from . import data
from .theme import line_style
from .components import (
    esc,
    line_badge,
    notes_html,
    render,
    scope_notes,
    segment_rows_html,
    stat_card,
    status_chip,
    timeline_html,
)


def _amount(fare):
    v = fare.get("total_fare_thb") if isinstance(fare, dict) else None
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _transfers(route):
    s = route.get("summary") or {}
    return s.get("transfer_count", len(route.get("transfers") or []))


def _candidate_labels(cands) -> dict[int, list[str]]:
    """Relative badges within the returned candidates; never imply global optimality.

    Lowest fare only uses verified (OK) price cases; estimated/unpriced excluded.
    """
    labels = {i: [] for i in range(len(cands))}
    if not cands:
        return labels
    verified = []
    for i, candidate in enumerate(cands):
        fv = data.fare_view(candidate.get("fare") or {})
        amt = _amount(candidate.get("fare") or {})
        if fv["kind"] == "ok" and amt is not None:
            verified.append((i, amt))
    if verified:
        lowest = min(amt for _, amt in verified)
        for i, amt in verified:
            if amt == lowest:
                labels[i].append("ค่าโดยสารต่ำสุดในตัวเลือกที่ตรวจสอบราคาได้")
    counts = [_transfers(c.get("route") or {}) for c in cands]
    numeric = [n for n in counts if isinstance(n, (int, float)) and not isinstance(n, bool)]
    if numeric:
        minimum = min(numeric)
        for i, count in enumerate(counts):
            if count == minimum:
                labels[i].append("เปลี่ยนสายน้อยสุดในตัวเลือก")
    return labels


def _labels_html(labels: list[str]) -> str:
    parts = []
    for value in labels:
        cls = "rl-choice-tag--fare" if value.startswith("ค่าโดยสาร") else "rl-choice-tag--transfer"
        parts.append(f'<span class="rl-choice-tag {cls}">{esc(value)}</span>')
    return " ".join(parts)


def option_label(i, cand, labels=None):
    route, fare = cand.get("route") or {}, cand.get("fare") or {}
    fv = data.fare_view(fare)
    amt = fv["amount_text"] if fv["kind"] == "ok" else (f"≈{fv['amount_text']}" if fv["kind"] == "est" else "no fare")
    t = _transfers(route)
    badges = (labels or {}).get(i, [])
    short = []
    if any(v.startswith("ค่าโดยสาร") for v in badges):
        short.append("ราคาต่ำสุด*")
    if any(v.startswith("เปลี่ยนสาย") for v in badges):
        short.append("เปลี่ยนสายน้อยสุด*")
    suffix = " · " + ", ".join(short) if short else ""
    return f"ทางเลือก {i + 1} · {amt} · เปลี่ยนสาย {t} จุด{suffix}"


def options_table_html(cands, selected, cheapest_ids, labels=None):
    rows = []
    for i, c in enumerate(cands):
        route, fare = c.get("route") or {}, c.get("fare") or {}
        fv = data.fare_view(fare)
        tags = _labels_html((labels or {}).get(i, []))
        lines = "".join(line_badge(l) for l in (route.get("summary") or {}).get("lines_used") or [])
        rows.append(
            f'<tr class="{"on" if i == selected else ""}"><td>Option {i + 1}{tags}</td>'
            f'<td>{esc(fv["amount_text"])}</td><td>{esc(len(route.get("station_line_ids") or []))}</td>'
            f'<td>{esc(_transfers(route))}</td><td>{lines}</td><td>{status_chip(fv)}</td></tr>'
        )
    head = "<tr><th>Option</th><th>Fare</th><th>Stops</th><th>Transfers</th><th>Lines</th><th>Fare status</th></tr>"
    return f'<div style="overflow-x:auto"><table class="rl-table">{head}{"".join(rows)}</table></div>'


def diff_html(base, cand):
    """How the selected option differs from Option 1. Fare delta only when both fares are verified (OK)."""
    rb, rc = base.get("route") or {}, cand.get("route") or {}
    fb, fc = base.get("fare") or {}, cand.get("fare") or {}
    parts = []
    if data.fare_view(fb)["kind"] == "ok" and data.fare_view(fc)["kind"] == "ok":
        d = _amount(fc) - _amount(fb)
        parts.append("ค่าโดยสารเท่ากับตัวเลือก 1" if d == 0 else f"ค่าโดยสาร{'แพงกว่า' if d > 0 else 'ถูกกว่า'}ตัวเลือก 1 อยู่ {data.format_baht(abs(d))}")
    else:
        parts.append("เทียบส่วนต่างราคาไม่ได้ เพราะราคาของตัวเลือกใดตัวเลือกหนึ่งยังไม่ผ่านการตรวจสอบ")
    ds = len(rc.get("station_line_ids") or []) - len(rb.get("station_line_ids") or [])
    parts.append("จำนวนสถานีเท่ากับตัวเลือก 1" if ds == 0 else f"{'มากกว่า' if ds > 0 else 'น้อยกว่า'}ตัวเลือก 1 อยู่ {abs(ds)} สถานี")
    dt = _transfers(rc) - _transfers(rb)
    parts.append("จุดเปลี่ยนสายเท่ากัน" if dt == 0 else f"จุดเปลี่ยนสาย{'มากกว่า' if dt > 0 else 'น้อยกว่า'}ตัวเลือก 1 อยู่ {abs(dt)} จุด")
    return '<div class="rl-diff"><b>เทียบกับตัวเลือก 1:</b> ' + " · ".join(esc(p) for p in parts) + "</div>"


def matched_station(matching, sid):
    for item in (matching or {}).get("nearest_stations") or []:
        ids = item.get("station_line_ids") or [item.get("station_line_id")]
        if sid in ids or item.get("station_line_id") == sid:
            return item
    return None


def poi_section(result, route):
    render('<p class="rl-kicker">Place to station</p><p class="rl-title">สถานที่และสถานีที่ใช้</p>')
    cols = st.columns(2, gap="large")
    pairs = [
        ("ต้นทาง", result.get("origin_matching"), route.get("origin")),
        ("ปลายทาง", result.get("destination_matching"), route.get("destination")),
    ]
    for col, (label, matching, sid) in zip(cols, pairs):
        with col:
            poi_name = ((matching or {}).get("poi") or {}).get("name", "")
            item = matched_station(matching, sid)
            extra = ""
            if item:
                dist = item.get("distance_m")
                dist_txt = f"ห่างประมาณ {dist:,.0f} ม. (ระยะเส้นตรง)" if isinstance(dist, (int, float)) else ""
                warn = ' <span class="rl-chip">พิกัดสถานียังไม่ยืนยัน</span>' if item.get("coordinate_warning") else ""
                extra = f'<br><span style="color:#817A74;font-size:12px">{esc(dist_txt)}</span>{warn}'
            render(f'<div class="rl-note"><b>{esc(label)}: {esc(poi_name)}</b><br>สถานีที่ใช้: {esc(data.station_name(sid))} {esc(data.station_code(sid))}{extra}</div>')
    shown = set()
    for matching in (result.get("origin_matching"), result.get("destination_matching")):
        for warning in (matching or {}).get("warnings") or []:
            if warning not in shown:
                shown.add(warning)
                st.caption(f"หมายเหตุ: {warning}")


def fare_panel(fare):
    fv = data.fare_view(fare)
    dim = "opacity:.8;" if fv["kind"] == "est" else ""
    with st.container(border=True):
        render(
            '<p class="rl-kicker">Fare</p>'
            '<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px">'
            f'<span style="font-size:32px;font-weight:600;font-variant-numeric:tabular-nums;{dim}">{esc(fv["amount_text"])}</span>'
            f'{status_chip(fv)}</div>'
        )
        if fv["kind"] == "est":
            st.warning("ราคานี้เป็นประมาณการ ยังไม่ผ่านการตรวจสอบเป็นราคาทางการ")
        elif fv["kind"] == "na":
            st.warning(f"{fv['label']}: ระบบจึงไม่แสดงตัวเลขค่าโดยสาร")
            reasons = fare.get("reasons") or []
            if reasons:
                st.caption("รหัสเหตุผลจาก Backend: " + ", ".join(str(r) for r in reasons))
        if fv["show_amount"]:
            render(segment_rows_html(fare))
        meta = []
        if fare.get("data_snapshot_date"):
            meta.append(f"ข้อมูลราคาอ้างอิงวันที่ {fare['data_snapshot_date']}")
        if fare.get("passenger_type") == "adult":
            meta.append("ผู้โดยสารผู้ใหญ่")
        if fare.get("ticket_type") == "single_journey":
            meta.append("ตั๋วเที่ยวเดียว")
        if meta:
            st.caption(" · ".join(meta))
        sources = fare.get("sources") or []
        if sources:
            with st.expander("แหล่งข้อมูลราคา"):
                for src in sources:
                    url = src.get("url") or ""
                    link = f' · <a href="{esc(url)}" target="_blank" rel="noopener">เปิดแหล่งข้อมูล</a>' if url.startswith("https://") else ""
                    render(f'<div class="rl-muted" style="margin-bottom:6px">{esc(src.get("publisher"))} · {esc(src.get("source_type"))} · สถานะ: {esc(src.get("verification_status"))}{link}</div>')


def _recommend_index(cands: list) -> int:
    """Choose within only the Backend-supplied candidates.

    Priority: fewest transfers, then an available verified fare, then smaller
    verified fare, then fewer listed station nodes. Never claim global optimum.
    """
    if not cands:
        return 0

    def score(i):
        c = cands[i]
        route, fare = c.get("route") or {}, c.get("fare") or {}
        transfers = _transfers(route)
        transfers = transfers if isinstance(transfers, (int, float)) and not isinstance(transfers, bool) else 10**6
        verified = data.fare_view(fare)["kind"] == "ok" and _amount(fare) is not None
        amount = _amount(fare) if verified else float("inf")
        stops = len(route.get("station_line_ids") or [])
        return (transfers, 0 if verified else 1, amount, stops, i)

    return min(range(len(cands)), key=score)


def _option_description(cand: dict, tags: list[str], *, recommended=False) -> str:
    route, fare = cand.get("route") or {}, cand.get("fare") or {}
    n = len(route.get("station_line_ids") or [])
    t = _transfers(route)
    fv = data.fare_view(fare)
    line_ids = (route.get("summary") or {}).get("lines_used") or []
    names = [line_style(lid)["name_th"] for lid in line_ids]
    text = f"{fv['amount_text']} · {n} สถานี · เปลี่ยนสาย {t} ครั้ง"
    if names:
        text += " · " + " → ".join(names)
    notes = []
    if recommended:
        notes.append("เส้นทางแนะนำ")
    if any("ค่าโดยสารต่ำสุด" in tag for tag in tags):
        notes.append("ค่าโดยสารต่ำสุดในตัวเลือกที่ตรวจสอบราคาได้")
    if any("เปลี่ยนสายน้อยสุด" in tag for tag in tags):
        notes.append("เปลี่ยนสายน้อยสุดในตัวเลือก")
    if notes:
        text += "\n" + " · ".join(notes)
    if fv["kind"] != "ok":
        text += "\nสถานะราคา: " + fv["label"]
    return text


_JOURNEY_CSS = r"""
/* V9: Journey result only; independent of older theme overrides */
.rl-journey-hero{background:#f6f6f6;border:1px solid #e7e7e7;padding:30px 34px;margin:24px 0 18px}
.rl-journey-hero-top{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}
.rl-journey-eyebrow{font-size:11px;letter-spacing:.17em;color:#d9111e;font-weight:800}
.rl-journey-price-row{display:flex;justify-content:space-between;gap:30px;align-items:flex-end;margin:20px 0 20px;flex-wrap:wrap}
.rl-journey-price{font-size:clamp(42px,5vw,64px);line-height:1.05;font-weight:800;color:#1f1f1f;letter-spacing:-.04em}
.rl-journey-price-caption{font-size:12px;color:#727272;margin-top:10px}
.rl-journey-facts{display:flex;gap:48px;align-items:flex-end}
.rl-journey-facts>div{display:flex;flex-direction:column;gap:6px}
.rl-journey-facts strong{font-size:30px;line-height:1;color:#222}
.rl-journey-facts span{font-size:12px;color:#696969}
.rl-journey-lines{display:flex;flex-wrap:wrap;gap:7px;padding:15px 0;border-top:1px solid #e4e4e4}
.rl-journey-badges{display:flex;gap:8px;flex-wrap:wrap}
.rl-journey-disclaimer{color:#777;font-size:11px;line-height:1.8;margin:17px 0 0}
.rl-alt-card{border-top:1px solid #e4e4e4;padding:18px 0 8px;margin-top:8px}
.rl-alt-title{font-size:16px;font-weight:700;color:#222}
.rl-alt-desc{white-space:pre-line;font-size:13px;color:#666;line-height:1.85;margin:8px 0}
@media(max-width:760px){.rl-journey-hero{padding:22px 20px}.rl-journey-facts{gap:24px}.rl-journey-facts strong{font-size:24px}}
"""

def render_journey(journey: dict, key: str) -> None:
    st.markdown("<style>" + _JOURNEY_CSS + "</style>", unsafe_allow_html=True)
    mode = journey.get("mode")
    result = journey.get("result") or {}
    plan = result.get("plan") if mode == "poi" else result
    if not isinstance(plan, dict):
        st.warning("ยังไม่มีข้อมูลเส้นทาง")
        return
    route = plan.get("route") or {}
    if route.get("status") == "SAME_STATION":
        st.info("สถานีต้นทางและปลายทางเป็นสถานีเดียวกัน ไม่ต้องเดินทางด้วยรถไฟฟ้า")
        return
    if route.get("status") != "OK":
        st.warning(route.get("message") or data.PLAN_STATUS_TH.get(plan.get("status"), "ไม่พบเส้นทางระหว่างสองสถานีนี้"))
        return

    cands = plan.get("candidates") or [{"route": route, "fare": plan.get("fare")}]
    labels = _candidate_labels(cands)
    suggested = _recommend_index(cands)

    # Reset the chosen route on a different origin/destination or candidate set.
    # Keep a person's explicit choice while interacting with the same results.
    signature = (
        route.get("origin"), route.get("destination"),
        tuple((c.get("route") or {}).get("route_id", str(i)) for i, c in enumerate(cands)),
    )
    sig_key, idx_key = f"{key}_journey_signature_v8", f"{key}_selected_option_v8"
    if st.session_state.get(sig_key) != signature:
        st.session_state[sig_key] = signature
        st.session_state[idx_key] = suggested
    sel = st.session_state.get(idx_key, suggested)
    if not isinstance(sel, int) or not 0 <= sel < len(cands):
        sel = suggested
        st.session_state[idx_key] = sel

    render(
        '<p class="rl-kicker">Your journey</p>'
        f'<p class="rl-page-title">{esc(data.station_name(route.get("origin")))} <span style="color:#DC111D">→</span> {esc(data.station_name(route.get("destination")))}</p>'
    )
    # One prominent hero summary for the currently displayed route; avoid repeating
    # fare/stops/transfers in a second metric grid below.
    display_route = cands[sel].get("route") or route
    display_fare = cands[sel].get("fare") or plan.get("fare") or {}
    display_view = data.fare_view(display_fare)
    display_stops = len(display_route.get("station_line_ids") or [])
    display_transfers = _transfers(display_route)
    display_badges = _labels_html(labels.get(sel, []))
    recommendation = sel == suggested
    display_lines = (display_route.get("summary") or {}).get("lines_used") or []
    display_lines_html = "".join(line_badge(l) for l in display_lines)
    amount = esc(display_view["amount_text"])
    render(
        '<div class="rl-journey-hero">'
        '<div class="rl-journey-hero-top">'
        f'<span class="rl-journey-eyebrow">{"RECOMMENDED ROUTE / เส้นทางแนะนำ" if recommendation else f"ALTERNATIVE ROUTE / ทางเลือก {sel+1}"}</span>'
        f'{status_chip(display_view)}'
        '</div>'
        '<div class="rl-journey-price-row">'
        f'<div><div class="rl-journey-price">{amount}</div>'
        '<div class="rl-journey-price-caption">ค่าโดยสารรวมตามข้อมูลที่ระบบมี</div></div>'
        '<div class="rl-journey-facts">'
        f'<div><strong>{esc(display_stops)}</strong><span>สถานีในเส้นทาง</span></div>'
        f'<div><strong>{esc(display_transfers)}</strong><span>จุดเปลี่ยนสาย</span></div>'
        '</div></div>'
        f'<div class="rl-journey-lines">{display_lines_html}</div>'
        f'<div class="rl-journey-badges">{display_badges}</div>'
        '<p class="rl-journey-disclaimer">เส้นทางแนะนำเลือกจากเส้นทางที่ระบบพบโดยให้ความสำคัญกับการเปลี่ยนสายน้อยก่อน '
        'จากนั้นจึงพิจารณาค่าโดยสารที่ตรวจสอบได้และจำนวนสถานี ไม่ใช่การรับประกันว่าเหมาะสมที่สุดทั้งเครือข่าย</p>'
        '</div>'
    )
    if sel != suggested:
        render(f'<p class="rl-muted">กำลังดูรายละเอียดทางเลือก {sel+1} · <b>เส้นทางแนะนำคือทางเลือก {suggested+1}</b></p>')
        if st.button("กลับไปเส้นทางแนะนำ", key=f"{key}_back_to_rec_v8"):
            st.session_state[idx_key] = suggested
            st.rerun()

    if len(cands) > 1:
        with st.expander(f"ดูเส้นทางทางเลือกเพิ่มเติม ({len(cands)-1} เส้นทาง)", expanded=False):
            st.caption("เลือกดูรายละเอียดเส้นทางอื่นได้ — เปรียบเทียบเฉพาะเส้นทางที่ระบบค้นพบในครั้งนี้")
            for i, cand in enumerate(cands):
                if i == suggested:
                    continue
                st.markdown(
                    f'<div class="rl-alt-card">'
                    f'<div class="rl-alt-title">ทางเลือก {i+1}</div>'
                    f'<p class="rl-alt-desc">{esc(_option_description(cand, labels.get(i, [])))}</p>'
                    '</div>',
                    unsafe_allow_html=True,
                )
                if st.button(
                    f"ดูรายละเอียดทางเลือก {i+1}" + (" ✓" if sel == i else ""),
                    key=f"{key}_view_alt_v8_{i}",
                    use_container_width=True,
                ):
                    st.session_state[idx_key] = i
                    st.rerun()
        if sel != suggested:
            render(diff_html(cands[suggested], cands[sel]).replace("ตัวเลือก 1", "เส้นทางแนะนำ"))
    else:
        render('<p class="rl-muted">ระบบพบเส้นทางที่แสดงได้ 1 เส้นทาง</p>')

    chosen = cands[sel]
    croute, cfare = chosen.get("route") or route, chosen.get("fare") or {}
    summary = croute.get("summary") or {}
    fv = data.fare_view(cfare)
    st.write("")
    if mode == "poi":
        poi_section(result, croute)
        st.write("")

    left, right = st.columns([1.35, 1], gap="large")
    with left:
        render(
            '<p class="rl-kicker">Route</p><p class="rl-title" style="font-size:18px">รายละเอียดเส้นทาง</p>'
            f'<div>{"".join(line_badge(l) for l in summary.get("lines_used") or [])}</div>'
        )
        render(timeline_html(croute))
        if summary.get("branch_junction_count"):
            st.caption(f"เส้นทางผ่านจุดแยกสาย {summary['branch_junction_count']} แห่ง")
    with right:
        fare_panel(cfare)
        st.write("")
        render(notes_html(scope_notes(dict(plan, fare=cfare), poi=mode == "poi")))
