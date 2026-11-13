"""RailRoutie theme: colors, line colors and global CSS. UI only, no backend logic."""
from __future__ import annotations

import streamlit as st

RED = "#A83F3A"

# Display colors per line_id. NOT verified against official sources:
# check before the presentation. Change them here only.
LINE_STYLES = {
    "BTS-SUK": {
        "name_th": "รถไฟฟ้าบีทีเอส สายสุขุมวิท",
        "short": "BTS สุขุมวิท",
        "color": "#6DB33F",
        "text": "#1F2A14"
    },
    "BTS-SIL": {
        "name_th": "รถไฟฟ้าบีทีเอส สายสีลม",
        "short": "BTS สีลม",
        "color": "#0B6B3A",
        "text": "#FFFFFF"
    },
    "BTS-GLD": {
        "name_th": "รถไฟฟ้าสายสีทอง",
        "short": "BTS สายสีทอง",
        "color": "#C9A24B",
        "text": "#2B2417"
    },
    "MRT-BLU": {
        "name_th": "รถไฟฟ้ามหานคร สายเฉลิมรัชมงคล",
        "short": "MRT สีน้ำเงิน",
        "color": "#1B4F9C",
        "text": "#FFFFFF"
    },
    "MRT-PPL": {
        "name_th": "รถไฟฟ้ามหานคร สายฉลองรัชธรรม",
        "short": "MRT สีม่วง",
        "color": "#7A3E9D",
        "text": "#FFFFFF"
    },
    "MRT-YLW": {
        "name_th": "รถไฟฟ้าสายสีเหลือง",
        "short": "MRT สีเหลือง",
        "color": "#F2C200",
        "text": "#2B2417"
    },
    "MRT-PNK": {
        "name_th": "รถไฟฟ้าสายสีชมพู",
        "short": "MRT สีชมพู",
        "color": "#E86AA6",
        "text": "#3A1626"
    },
    "MRT-PNK-MT": {
        "name_th": "รถไฟฟ้าสายสีชมพู ส่วนต่อขยายเข้าเมืองทองธานี",
        "short": "MRT สีชมพู (เมืองทอง)",
        "color": "#E86AA6",
        "text": "#3A1626"
    },
    "ARL": {
        "name_th": "รถไฟฟ้าแอร์พอร์ตเรลลิงก์",
        "short": "Airport Rail Link",
        "color": "#B7202E",
        "text": "#FFFFFF"
    },
    "SRT-DRD": {
        "name_th": "รถไฟชานเมืองสายสีแดงเข้ม",
        "short": "สายสีแดงเข้ม",
        "color": "#8F1D2C",
        "text": "#FFFFFF"
    },
    "SRT-LRD": {
        "name_th": "รถไฟชานเมืองสายสีแดงอ่อน",
        "short": "สายสีแดงอ่อน",
        "color": "#E0584A",
        "text": "#FFFFFF"
    },
}
LINE_ORDER = list(LINE_STYLES.keys())
DEFAULT_LINE = {"name_th": "", "short": "", "color": "#817A74", "text": "#FFFFFF"}


def line_style(line_id: str) -> dict:
    return LINE_STYLES.get(str(line_id), DEFAULT_LINE)


def line_button_css(prefixes=("so", "sd")) -> str:
    """Per-line colors for the line chips (st.button keys: <prefix>_line_<LINE_ID>[_on])."""
    r = [
        '[class*="_line_"] button{width:100%;min-height:38px;padding:0 6px;font-size:13px;font-weight:500;'
        'background:#fff!important;color:#5E554F!important;border:1px solid #E6DDD4!important;'
        'border-radius:10px!important;box-shadow:none!important}',
        '[class*="_line_"] button p{font-size:13px;white-space:nowrap}',
        '[class*="_line_"] button:hover{border-color:#A83F3A!important;color:#A83F3A!important}',
    ]
    for p in prefixes:
        for lid, s in LINE_STYLES.items():
            c, t = s["color"], s["text"]
            r.append(f".st-key-{p}_line_{lid} button{{border-left:4px solid {c}!important}}")
            r.append(f".st-key-{p}_line_{lid}_on button{{background:{c}!important;border-color:{c}!important;color:{t}!important}}")
            r.append(f".st-key-{p}_line_{lid}_on button p{{color:{t}!important}}")
        r.append(f".st-key-{p}_line_ALL_on button{{background:#302C2A!important;border-color:#302C2A!important;color:#fff!important}}")
        r.append(f".st-key-{p}_line_ALL_on button p{{color:#fff!important}}")
    return "".join(r)


CSS = r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700&display=swap');
:root {--red:#A83F3A;--red-dark:#8F322E;--ink:#302C2A;--muted:#817A74;--cream:#FAF7F1;--rose:#F7ECE7;--line:#ECE6DF}
html, body, .stApp, [class*="css"] {font-family:'Prompt',-apple-system,'Noto Sans Thai',sans-serif}
.stApp {background:#fff;color:var(--ink)}
header[data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer {display:none!important}
.block-container {max-width:1080px;padding-top:1.1rem;padding-bottom:3rem}
h1,h2,h3,h4 {font-family:'Prompt',sans-serif;color:var(--ink);letter-spacing:-.02em}

/* top navigation */
.st-key-topnav {border-bottom:1px solid var(--line);padding-bottom:12px;margin-bottom:48px}
.st-key-topnav [data-testid="stHorizontalBlock"] {flex-wrap:nowrap!important;gap:.2rem!important;align-items:center}
.st-key-topnav [data-testid="stColumn"] {min-width:0!important}
.st-key-topnav a[data-testid="stPageLink-NavLink"] {justify-content:center;padding:7px 14px;border-radius:999px;background:transparent;color:var(--muted)!important;font-size:14px;font-weight:500}
.st-key-topnav a[data-testid="stPageLink-NavLink"] p {color:inherit!important;font-size:14px}
.st-key-topnav a[data-testid="stPageLink-NavLink"]:hover, .st-key-topnav a[data-testid="stPageLink-NavLink"][aria-current="page"] {background:var(--rose);color:var(--red)!important}
.rl-brand {display:flex;align-items:center;gap:9px}
.rl-logo {width:14px;height:14px;border-radius:5px;background:var(--red);display:inline-block}
.rl-brand b {font-size:22px;font-weight:700;color:var(--ink);letter-spacing:-.8px}
.rl-brand span.sub {font-size:11px;color:var(--muted);letter-spacing:1.4px;text-transform:uppercase}

/* inputs and buttons */
.stTextInput input {background:#fff!important;border:1px solid #E6DDD4!important;border-radius:12px!important;min-height:46px;color:var(--ink)!important}
.stTextInput input:focus {border-color:var(--red)!important;box-shadow:0 0 0 2px #A83F3A1F!important}
div[data-baseweb="select"]>div {border-radius:12px!important;border-color:#E6DDD4!important;background:#fff!important;min-height:46px}
div.stButton>button[kind="primary"] {background:var(--red)!important;color:#fff!important;border:1px solid var(--red)!important;border-radius:12px!important;min-height:48px;font-weight:600;box-shadow:none!important}
div.stButton>button[kind="primary"]:hover {background:var(--red-dark)!important;border-color:var(--red-dark)!important}
div.stButton>button[kind="primary"]:disabled {background:#E3D5D1!important;border-color:#E3D5D1!important;color:#fff!important}
div.stButton>button[kind="secondary"] {background:#fff;color:var(--red);border:1px solid #E8D5CF;border-radius:12px;min-height:44px}
[data-testid="stVerticalBlockBorderWrapper"] {border:1px solid var(--line)!important;border-radius:18px!important;background:#fff!important;box-shadow:none!important}
[data-testid="stAlert"] {border-radius:12px!important}
.st-key-panel {background:var(--cream);border:1px solid var(--line);border-radius:22px;padding:30px 30px 26px}
.st-key-panel [data-baseweb="select"]>div {background:#fff!important}

/* hero + page headings */
.rl-eyebrow {color:var(--red);font-size:12px;letter-spacing:2px;font-weight:600;text-transform:uppercase;margin:0 0 12px}
.rl-hero-title {font-weight:700;font-size:clamp(34px,5vw,62px);line-height:1.16;letter-spacing:-2px;margin:0}
.rl-hero-title em {font-style:normal;color:var(--red)}
.rl-hero-sub {color:var(--muted);font-size:16px;line-height:1.9;margin:18px 0 28px;max-width:600px}
.rl-page-title {font-size:clamp(26px,3.2vw,36px);font-weight:600;letter-spacing:-1px;margin:0 0 6px;line-height:1.25}
.rl-kicker {font-size:11px;letter-spacing:1.8px;color:var(--red);font-weight:600;text-transform:uppercase;margin:0 0 6px}
.rl-title {font-size:21px;font-weight:600;margin:0 0 6px;letter-spacing:-.4px}
.rl-label {font-size:12px;font-weight:600;color:var(--muted);letter-spacing:.8px;text-transform:uppercase;margin:0 0 8px}
.rl-muted {color:var(--muted);font-size:14px;line-height:1.8}
.rl-section {margin-top:72px}
.st-key-cta1 a[data-testid="stPageLink-NavLink"] {background:var(--red);color:#fff!important;border-radius:12px;padding:12px 18px;justify-content:center}
.st-key-cta1 a[data-testid="stPageLink-NavLink"] p {color:#fff!important;font-weight:600}
.st-key-cta1 a[data-testid="stPageLink-NavLink"]:hover {background:var(--red-dark)}
.st-key-cta2 a[data-testid="stPageLink-NavLink"] {background:#fff;border:1px solid #E1D3CD;border-radius:12px;padding:11px 18px;justify-content:center}
.st-key-cta2 a[data-testid="stPageLink-NavLink"] p {color:var(--red)!important;font-weight:600}
.st-key-cta2 a[data-testid="stPageLink-NavLink"]:hover {background:var(--rose)}
.rl-grid3 {display:grid;grid-template-columns:repeat(3,1fr);gap:36px;margin-top:22px}
.rl-step {border-top:1px solid var(--line);padding-top:18px}
.rl-step i {font-style:normal;font-size:12px;font-weight:600;color:var(--red);letter-spacing:1.5px}
.rl-step h3 {font-size:18px;font-weight:600;margin:8px 0 6px}
.rl-step p {color:var(--muted);font-size:14px;line-height:1.8;margin:0}
.rl-know {display:grid;grid-template-columns:repeat(2,1fr);gap:14px 36px;margin-top:20px}
.rl-know div {font-size:14px;color:#5E554F;line-height:1.8;padding-left:14px;border-left:2px solid #E4C9C3}

/* line badge, chips, status */
.rl-badge {display:inline-block;border-radius:999px;padding:3px 11px;font-size:12px;font-weight:600;white-space:nowrap;margin:0 4px 4px 0}
.rl-chip {display:inline-block;background:var(--rose);color:var(--red);border-radius:999px;padding:3px 10px;font-size:12px;font-weight:500;margin:2px 6px 2px 0}
.rl-status {display:inline-block;border-radius:999px;padding:4px 12px;font-size:12px;font-weight:600}
.rl-status.ok {background:#E8F2E8;color:#2F6B3A}
.rl-status.est {background:#FFF3D6;color:#8A6A12}
.rl-status.na {background:#EEEAE6;color:#6B645E}

/* result summary */
.rl-stat {border-top:1px solid var(--line);padding:14px 0 0}
.rl-stat small {display:block;color:var(--muted);font-size:12px;margin-bottom:4px}
.rl-stat b {font-size:28px;font-weight:600;letter-spacing:-.6px;font-variant-numeric:tabular-nums}
.rl-stat b.est {color:#8A6A12;opacity:.85}

/* options table */
.rl-table {width:100%;border-collapse:collapse;font-size:13px;margin:10px 0 4px}
.rl-table th {text-align:left;color:var(--muted);font-weight:500;font-size:12px;padding:8px 10px;border-bottom:1px solid var(--line)}
.rl-table td {padding:10px;border-bottom:1px solid #F3EEE8;font-variant-numeric:tabular-nums}
.rl-table tr.on td {background:#FFF8F6}
.rl-table tr.on td:first-child {box-shadow:inset 3px 0 0 var(--red);font-weight:600}
.rl-diff {margin:10px 0 0;font-size:13px;color:#5E554F;line-height:1.8}

/* timeline */
.rl-leg {margin:6px 0 4px}
.rl-leg-head {display:flex;align-items:center;gap:10px;margin:14px 0 8px;font-size:13px;color:var(--muted)}
.rl-stops {border-left:4px solid var(--lc,#C9B8B0);margin-left:7px;padding-left:20px}
.rl-stop {position:relative;padding:3px 0 12px;font-size:14px;color:#5E554F}
.rl-stop:before {content:'';position:absolute;left:-30px;top:8px;width:10px;height:10px;background:#fff;border:3px solid var(--lc,#C9B8B0);border-radius:50%}
.rl-stop.key {font-weight:600;color:var(--ink)}
.rl-stop small {display:block;color:#938A83;font-size:11px;font-weight:400}
.rl-transfer {margin:10px 0 6px 7px;padding:10px 14px;border:1px dashed #D8B9B1;border-radius:12px;background:var(--rose);font-size:13px;color:#6E3A35}
.rl-transfer small {display:block;color:var(--muted);font-size:11px;margin-top:2px}

.rl-alt {background:#fff;border:1px solid var(--line);border-radius:16px;padding:16px 18px;height:100%}
.rl-alt.best {border-color:#D9A9A2;background:#FFFCFB}
.rl-alt h4 {margin:0 0 8px;font-size:15px}
.rl-alt dl {display:grid;grid-template-columns:1fr auto;gap:4px 12px;margin:0;font-size:13px}
.rl-alt dt {color:var(--muted)}
.rl-alt dd {margin:0;text-align:right;font-variant-numeric:tabular-nums}
.rl-note {border-left:3px solid #E4C9C3;padding:4px 0 4px 14px;font-size:13px;color:#5E554F;line-height:1.7;margin-bottom:10px}
.rl-foot {font-size:12px;color:#948B83;text-align:center;margin-top:64px;padding-top:18px;border-top:1px solid var(--line)}

@media (max-width:760px){
  .block-container {padding-left:1rem;padding-right:1rem}
  .rl-grid3, .rl-know {grid-template-columns:1fr;gap:18px}
  .rl-hero-title {letter-spacing:-.8px}
  .rl-brand span.sub {display:none}
  .st-key-panel {padding:20px 16px}
  .rl-stat b {font-size:22px}
}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS + "<style>" + line_button_css() + "</style>", unsafe_allow_html=True)

# --- RAILLY EDITORIAL MINIMAL V2 ---
EDITORIAL_CSS = r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=IBM+Plex+Sans+Thai:wght@400;500;600;700&display=swap');
:root{--red:#DC111D;--red-dark:#B80D17;--ink:#202020;--muted:#6D6D6D;--cream:#FAF9F7;--rose:#F3F3F3;--line:#E8E8E8}
html,body,.stApp,[class*="css"]{font-family:'DM Sans','IBM Plex Sans Thai',sans-serif!important}
.stApp{background:#fff!important;color:var(--ink)!important}
.block-container{max-width:1280px!important;padding:0 52px 70px!important}
[data-testid="stAppViewBlockContainer"]{padding-top:0!important}
.st-key-topnav{height:86px;margin-bottom:0!important;padding:13px 0!important;border-bottom:1px solid #eee!important}
.st-key-topnav [data-testid="stHorizontalBlock"]{align-items:center!important}
.rl-logo{width:11px;height:11px;background:#dc111d;border-radius:0;transform:rotate(45deg)}
.rl-brand b{font-family:'DM Sans',sans-serif!important;font-size:32px!important;font-weight:800!important;letter-spacing:-2px;color:#202020!important}
.rl-brand .sub{letter-spacing:2px!important;color:#777!important;font-size:10px!important;font-weight:700!important}
.st-key-topnav a[data-testid="stPageLink-NavLink"]{background:none!important;color:#555!important;border-radius:0!important;font-weight:700!important;padding:10px 9px!important}
.st-key-topnav a[data-testid="stPageLink-NavLink"] p{font-size:13px!important}
.st-key-topnav a[data-testid="stPageLink-NavLink"]:hover,.st-key-topnav a[data-testid="stPageLink-NavLink"][aria-current="page"]{color:#dc111d!important;background:none!important}
/* The approved image-led editorial home page */
.ed-hero-photo{height:350px;background-position:center 49%;background-size:cover;position:relative;overflow:hidden;background-color:#e7e7e7;margin-top:24px}
.ed-photo-tag{position:absolute;bottom:0;right:0;min-width:235px;background:#dc111d;color:#fff;display:flex;align-items:center;justify-content:space-between;padding:17px 22px;font-size:11px;font-weight:700;letter-spacing:1.5px}
.ed-photo-tag b{font-size:18px}.ed-hero-placeholder{display:flex;align-items:center;justify-content:center;color:#777;font-weight:800;letter-spacing:2px}
.ed-welcome{display:grid;grid-template-columns:1.25fr 1fr;gap:64px;align-items:end;padding:56px 0 60px;border-bottom:1px solid #ddd}
.ed-headline .ed-overline{font-size:11px;letter-spacing:2.1px;font-weight:800;color:#777}
.ed-headline h1{font-family:'DM Sans',sans-serif!important;color:#dc111d!important;font-weight:800!important;letter-spacing:-9px!important;line-height:.98!important;font-size:clamp(65px,8vw,130px)!important;margin:12px 0 18px!important;white-space:nowrap}
.ed-headline h1 span{color:#dc111d}.ed-under{font-size:13px;letter-spacing:.6px;font-weight:700}
.ed-intro{background:#F1F1F1;padding:28px 32px 30px;min-height:205px}.ed-intro-no{font-size:10px;font-weight:800;letter-spacing:1.8px;color:#888}
.ed-intro h2{font-family:'IBM Plex Sans Thai',sans-serif!important;font-size:clamp(21px,2.4vw,32px)!important;line-height:1.35!important;font-weight:700!important;color:#222!important;margin:18px 0 12px!important}
.ed-intro p{font-size:13px;line-height:1.9;color:#616161;margin:0}
.ed-cta-heading,.ed-section-top,.ed-lines-head{display:flex;justify-content:space-between;gap:16px;margin:48px 0 17px;font-size:11px;font-weight:800;letter-spacing:1.7px;color:#747474}
.st-key-cta1 a[data-testid="stPageLink-NavLink"],.st-key-cta2 a[data-testid="stPageLink-NavLink"]{background:#202020!important;color:#fff!important;border:1px solid #202020!important;min-height:68px;border-radius:0!important;justify-content:space-between!important;padding:18px 24px!important;transition:background .2s ease!important}
.st-key-cta1 a[data-testid="stPageLink-NavLink"]:hover,.st-key-cta2 a[data-testid="stPageLink-NavLink"]:hover{background:#dc111d!important;border-color:#dc111d!important}
.st-key-cta2 a[data-testid="stPageLink-NavLink"]{background:white!important;color:#202020!important;border-color:#202020!important}
.st-key-cta2 a[data-testid="stPageLink-NavLink"]:hover{color:#fff!important}
.st-key-cta1 a[data-testid="stPageLink-NavLink"] p,.st-key-cta2 a[data-testid="stPageLink-NavLink"] p{font-family:'DM Sans',sans-serif!important;font-size:17px!important;font-weight:800!important;letter-spacing:1px}
.st-key-cta2 a[data-testid="stPageLink-NavLink"] p{color:#202020!important}.st-key-cta2 a[data-testid="stPageLink-NavLink"]:hover p{color:#fff!important}
.ed-cta-help{font-size:12px;color:#747474;padding-top:8px;margin:0 0 20px!important}
.ed-section{margin-top:70px;border-top:1px solid #e5e5e5}.ed-section-top{margin-top:20px}
.ed-section-title{font-size:clamp(27px,3.6vw,46px)!important;font-weight:800!important;letter-spacing:-1.6px!important;margin:28px 0!important}.ed-section-title span{color:#dc111d}
.ed-steps{display:grid;grid-template-columns:repeat(3,1fr);gap:22px}.ed-steps article{padding:24px 20px 24px 0;border-top:2px solid #202020}
.ed-step-no{font-size:11px;letter-spacing:1.4px;font-weight:800;color:#dc111d}.ed-steps h3{font-size:18px!important;margin:24px 0 9px!important;font-weight:700!important;letter-spacing:-.4px}.ed-steps p{color:#6e6e6e;font-size:13px;line-height:1.9;margin:0}
.ed-lines-head{border-top:1px solid #e5e5e5;padding-top:22px;margin-top:60px}.ed-line-list{display:flex;flex-wrap:wrap;gap:6px}.ed-line-list .rl-badge{border-radius:2px;padding:6px 11px}
.ed-disclaimer{background:#f5f5f5;padding:26px 30px;margin-top:64px}.ed-note-title{font-size:11px;font-weight:800;letter-spacing:1.7px}.ed-note-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}.ed-note-grid p{font-size:12px;line-height:1.85;color:#686868}
/* Standardized editorial headings for the existing station/place pages */
.rl-kicker{font-size:11px!important;font-weight:800!important;letter-spacing:2px!important;color:#dc111d!important;margin-top:34px!important}
.rl-page-title{font-size:clamp(31px,4vw,54px)!important;letter-spacing:-1.4px!important;font-weight:800!important;line-height:1.2!important}
.rl-muted{color:#737373!important}
.st-key-panel{background:#f6f6f6!important;border:0!important;border-radius:0!important;padding:30px 34px!important;margin-top:16px}
.rl-label{font-size:11px!important;font-weight:800!important;letter-spacing:1.5px!important;color:#555!important}
.stTextInput input{border-radius:0!important;border:1px solid #d9d9d9!important;height:49px!important;background:#fff!important}
.stTextInput input:focus{border-color:#dc111d!important;box-shadow:none!important}
div[data-baseweb="select"]>div{border-radius:0!important;min-height:49px!important;border:1px solid #d9d9d9!important}
div.stButton>button[kind="primary"]{background:#dc111d!important;border-color:#dc111d!important;color:#fff!important;border-radius:0!important;min-height:52px!important;font-weight:800!important;letter-spacing:.6px!important}
div.stButton>button[kind="primary"]:hover{background:#b90d16!important;border-color:#b90d16!important}
div.stButton>button[kind="secondary"]{border-radius:0!important;border-color:#d9d9d9!important;color:#303030!important}
div.stButton>button[kind="secondary"]:hover{border-color:#dc111d!important;color:#dc111d!important;background:#fff!important}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:0!important;border-color:#e7e7e7!important;box-shadow:none!important}
[class*="_line_"] button{border-radius:0!important;border:1px solid #e0e0e0!important;background:#fff!important;min-height:39px!important}
[class*="_line_"] button:hover{border-color:#dc111d!important;color:#dc111d!important}
.rl-badge{border-radius:2px!important}.rl-chip,.rl-status{border-radius:2px!important}.rl-stat{border-top:2px solid #222!important}
.rl-alt{border-radius:0!important}.rl-alt.best{background:#fafafa!important;border-color:#dc111d!important}
.rl-transfer{border-radius:0!important;background:#f5f5f5!important;border-color:#ddd!important;color:#222!important}
.rl-table tr.on td{background:#f4f4f4!important}.rl-table tr.on td:first-child{box-shadow:inset 3px 0 0 #dc111d!important}
.rl-foot{margin-top:90px!important;text-align:left!important;color:#878787!important;font-size:11px!important;border-top:1px solid #e3e3e3!important}
/* Light navigation sublinks displayed in search pages */
.ed-search-tabs{display:flex;gap:20px;align-items:center;border-bottom:1px solid #e0e0e0;padding:8px 0 13px;margin:20px 0 30px}
.ed-search-tabs a{font-family:'DM Sans',sans-serif;color:#777;text-decoration:none;font-size:12px;font-weight:800;letter-spacing:1.1px}
.ed-search-tabs a.on{color:#dc111d;border-bottom:2px solid #dc111d;padding-bottom:10px}
@media(max-width:900px){.block-container{padding:0 25px 50px!important}.ed-welcome{gap:28px}.ed-headline h1{font-size:clamp(50px,8vw,90px)!important;letter-spacing:-5px!important}.ed-hero-photo{height:280px}}
@media(max-width:640px){.block-container{padding:0 16px 50px!important}.st-key-topnav{height:auto;min-height:75px}.st-key-topnav [data-testid="stHorizontalBlock"]{gap:0!important}.rl-brand .sub{display:none!important}.rl-brand b{font-size:25px!important}.ed-hero-photo{height:220px;margin-top:12px}.ed-welcome{grid-template-columns:1fr;gap:22px;padding:35px 0}.ed-headline h1{font-size:clamp(48px,14vw,86px)!important;letter-spacing:-5px!important}.ed-intro{padding:23px 24px}.ed-steps,.ed-note-grid{grid-template-columns:1fr}.ed-cta-heading,.ed-section-top,.ed-lines-head{font-size:9px}.st-key-panel{padding:20px 15px!important}.rl-page-title{font-size:31px!important}.ed-hero-photo .ed-photo-tag{min-width:180px;padding:12px 15px;font-size:9px}}
</style>
"""

_original_inject_css = inject_css

def inject_css() -> None:
    _original_inject_css()
    st.markdown(EDITORIAL_CSS, unsafe_allow_html=True)

# --- RAILLY LAYERED HERO V3 / editorial spacing override ---
LAYERED_HERO_CSS = r"""
<style>
/* Bigger photo and overlapping editorial paper layers. Does not change any app logic. */
.ed-layered-hero{
  height: clamp(390px, 37vw, 510px) !important;
  margin-top: 30px !important;
  background-position: center 46% !important;
  background-size: cover !important;
}
.ed-layered-hero:before{
  content:""; position:absolute; inset:0;
  background:linear-gradient(180deg,rgba(0,0,0,.025),transparent 45%,rgba(0,0,0,.10));
  pointer-events:none;
}
.ed-layered-hero .ed-photo-tag{
  padding: 22px 30px !important; min-width: 265px !important;
  min-height:68px; z-index:2;
}
.ed-welcome-layered{
  position:relative !important;
  z-index:3 !important;
  margin-top:-76px !important;
  display:grid !important;
  grid-template-columns: 1.12fr 1fr !important;
  gap: 0 !important;
  padding:0 0 40px !important;
  align-items:stretch !important;
  border-bottom:1px solid #e4e4e4;
}
.ed-welcome-layered .ed-headline{
  background:#fff;
  min-width:0;
  padding:45px 34px 27px 0;
  display:flex;
  flex-direction:column;
  justify-content:space-between;
}
.ed-welcome-layered .ed-overline{
  display:block; color:#676767!important;
  font-size:11px!important; font-weight:800!important;
  letter-spacing:2.4px!important;
}
.ed-welcome-layered .ed-headline h1{
  color:#DF111B!important;
  font-size:clamp(65px,7.45vw,113px)!important;
  line-height:1!important;
  font-weight:800!important;
  letter-spacing:-7px!important;
  margin:28px 0 22px!important;
}
.ed-welcome-layered .ed-under{
  text-transform:uppercase;
  letter-spacing:2.0px;
  font-weight:800;
  color:#222;
  font-size:11px;
}
.ed-welcome-layered .ed-intro{
  background:#EDEDED!important;
  padding:44px 44px 40px!important;
  min-height:290px!important;
  display:flex;
  flex-direction:column;
  justify-content:center;
}
.ed-welcome-layered .ed-intro-no{
  font-size:10px!important;
  color:#757575!important;
  letter-spacing:2.0px!important;
}
.ed-welcome-layered .ed-intro h2{
  color:#191919!important;
  font-size:clamp(26px,2.75vw,38px)!important;
  line-height:1.35!important;
  font-weight:700!important;
  letter-spacing:-.6px!important;
  margin:24px 0 18px!important;
}
.ed-welcome-layered .ed-period{color:#DC111D}
.ed-welcome-layered .ed-intro-rule{height:2px;width:68px;background:#D8171C;margin-bottom:19px}
.ed-welcome-layered .ed-intro p{
  font-size:14px!important;
  color:#515151!important;
  line-height:1.9!important;
  margin:0!important;
}
/* Give CTA navigation a strong, clear transition from the hero. */
.ed-cta-heading{margin-top:28px!important;margin-bottom:17px!important}
.st-key-cta1 a[data-testid="stPageLink-NavLink"],
.st-key-cta2 a[data-testid="stPageLink-NavLink"]{
  min-height:77px!important; padding:21px 26px!important;
}
@media(max-width:1000px){
 .ed-welcome-layered{grid-template-columns:1.06fr 1fr!important}
 .ed-welcome-layered .ed-headline{padding:38px 19px 22px 0!important}
 .ed-welcome-layered .ed-headline h1{font-size:clamp(55px,7.1vw,85px)!important;letter-spacing:-5px!important}
 .ed-welcome-layered .ed-intro{padding:34px 30px!important}
 .ed-welcome-layered .ed-intro h2{font-size:clamp(25px,2.9vw,32px)!important}
}
@media(max-width:700px){
 .ed-layered-hero{height:260px!important;margin-top:15px!important;background-position:44% center!important}
 .ed-layered-hero .ed-photo-tag{padding:12px 15px!important;min-height:45px!important;min-width:180px!important}
 .ed-welcome-layered{display:flex!important;flex-direction:column!important;margin-top:-26px!important;padding-bottom:20px!important}
 .ed-welcome-layered .ed-headline{padding:32px 17px 24px!important}
 .ed-welcome-layered .ed-headline h1{font-size:clamp(51px,12.7vw,85px)!important;letter-spacing:-5px!important;margin:19px 0!important}
 .ed-welcome-layered .ed-intro{min-height:0!important;padding:26px 25px 30px!important}
 .ed-welcome-layered .ed-intro h2{font-size:29px!important;margin:18px 0!important}
 .ed-welcome-layered .ed-intro p{font-size:13px!important}
 .ed-cta-heading{margin-top:26px!important}
}
</style>
"""

_prev_inject_css_layered = inject_css

def inject_css() -> None:
    _prev_inject_css_layered()
    st.markdown(LAYERED_HERO_CSS, unsafe_allow_html=True)

# --- RAILLY V4 / nav hierarchy + reversed homepage sections ---
HOME_HIERARCHY_CSS = r"""
<style>
/* Brand and navigation: legible, deliberate typography */
.st-key-topnav {min-height:104px!important;height:auto!important;padding:19px 0!important;border-bottom:1px solid #E6E6E6!important}
.st-key-topnav [data-testid="stHorizontalBlock"] {align-items:center!important}
.rl-brand {display:flex!important;align-items:center!important;gap:11px!important;flex-wrap:wrap}
.rl-logo {width:15px!important;height:15px!important;flex-shrink:0}
.rl-brand b {font-size:clamp(35px,3.2vw,43px)!important;letter-spacing:-2.2px!important;line-height:1.08!important}
.rl-brand .sub {font-size:12px!important;letter-spacing:1.3px!important;font-weight:700!important;color:#555!important;white-space:nowrap}
.st-key-topnav a[data-testid="stPageLink-NavLink"] {padding:12px 10px!important;min-height:48px!important;display:flex!important;align-items:center!important;justify-content:center!important}
.st-key-topnav a[data-testid="stPageLink-NavLink"] p {font-size:16px!important;font-weight:700!important;line-height:1.25!important}
/* Step-by-step explanation now appears as the second section */
.ed-section-second{margin-top:52px!important;border-top:0!important;padding-top:0!important}
.ed-section-second .ed-section-top{margin-top:0!important;margin-bottom:21px!important;font-size:13px!important;letter-spacing:1.6px!important;color:#555!important}
.ed-section-second .ed-section-title{font-size:clamp(36px,4.3vw,57px)!important;letter-spacing:-1.5px!important;line-height:1.3!important;margin:22px 0 34px!important}
.ed-section-second .ed-steps{gap:26px!important}
.ed-section-second .ed-steps article {padding:30px 12px 25px 0!important}
.ed-section-second .ed-step-no{font-size:12px!important}
.ed-section-second .ed-steps h3{font-size:21px!important;margin:20px 0 12px!important}
.ed-section-second .ed-steps p{font-size:15px!important;line-height:1.85!important;max-width:32ch}
/* Third section: Search CTA distinct from step-by-step explanation */
.ed-cta-heading{border-top:1px solid #DCDCDC!important;padding-top:38px!important;margin-top:74px!important;margin-bottom:24px!important;font-size:13px!important;letter-spacing:1.5px!important;color:#555!important}
.st-key-cta1 a[data-testid="stPageLink-NavLink"],.st-key-cta2 a[data-testid="stPageLink-NavLink"] {min-height:82px!important}
.st-key-cta1 a[data-testid="stPageLink-NavLink"] p,.st-key-cta2 a[data-testid="stPageLink-NavLink"] p{font-size:20px!important;line-height:1.2!important}
.ed-cta-help{font-size:15px!important;line-height:1.8!important;margin:10px 0 27px!important;color:#555!important}
@media(max-width:850px){
 .st-key-topnav {min-height:85px!important}
 .rl-brand b{font-size:31px!important}
 .rl-brand .sub{font-size:10px!important;letter-spacing:.7px!important}
 .st-key-topnav a[data-testid="stPageLink-NavLink"] p{font-size:14px!important}
 .ed-section-second .ed-section-title{font-size:clamp(31px,5vw,43px)!important}
}
@media(max-width:640px){
 .st-key-topnav{padding:14px 0!important}
 .rl-brand{gap:5px!important}
 .rl-brand b{font-size:26px!important}
 .rl-brand .sub{display:none!important}
 .st-key-topnav a[data-testid="stPageLink-NavLink"] {padding:7px 4px!important;min-height:36px!important}
 .st-key-topnav a[data-testid="stPageLink-NavLink"] p{font-size:12px!important}
 .ed-section-second{margin-top:36px!important}
 .ed-section-second .ed-section-top,.ed-cta-heading{font-size:10px!important;letter-spacing:.7px!important;gap:8px!important}
 .ed-section-second .ed-steps{grid-template-columns:1fr!important;gap:8px!important}
 .ed-section-second .ed-steps article{padding:17px 0!important}
 .ed-section-second .ed-steps p{font-size:14px!important}
 .ed-cta-heading{margin-top:48px!important;padding-top:25px!important}
}
</style>
"""
_prev_inject_css_v4 = inject_css

def inject_css() -> None:
    _prev_inject_css_v4()
    st.markdown(HOME_HIERARCHY_CSS, unsafe_allow_html=True)

# RAILLY CHIP STATE FIX — late-injected, DOM-tolerant selectors.
# st-key-* may be on the stButton container or an ancestor, depending on Streamlit version.
# Do NOT rely on the nested `div.stButton > button` chain: it can miss the button.
def _chip_state_css() -> str:
    out = [
        '.stApp [class*="st-key-so_line_"] button[kind="secondary"],'
        '.stApp [class*="st-key-sd_line_"] button[kind="secondary"]'
        '{background:#fff!important;background-color:#fff!important;background-image:none!important;'
        'border:1px solid #d6d6d6!important;color:#222!important;opacity:1!important}',
        '.stApp [class*="st-key-so_line_"] button[kind="secondary"] *, '
        '.stApp [class*="st-key-sd_line_"] button[kind="secondary"] *'
        '{color:#222!important;opacity:1!important}',
    ]
    for prefix in ('so','sd'):
        for line_id, style in [('ALL', {'color':'#222222','text':'#ffffff'})] + list(LINE_STYLES.items()):
            root = f'[class*="st-key-{prefix}_line_{line_id}_on"]'
            bg, fg = style['color'], style['text']
            # Multiple specificity-qualified selectors support both widget DOM variants.
            btn = f'.stApp {root} button[kind="primary"]'
            out.append(
                f'{btn},{btn}:hover,{btn}:focus,{btn}:active'
                '{background:'+bg+'!important;background-color:'+bg+'!important;'
                'background-image:none!important;border:2px solid '+bg+'!important;'
                'color:'+fg+'!important;opacity:1!important;box-shadow:none!important;}'
            )
            out.append(f'{btn} *,{btn}:hover *'+'{color:'+fg+'!important;opacity:1!important;}')
    return '<style>\n' + '\n'.join(out) + '\n</style>'

_inject_css_before_chip_fix = inject_css

def inject_css() -> None:
    _inject_css_before_chip_fix()
    st.markdown(_chip_state_css(), unsafe_allow_html=True)
