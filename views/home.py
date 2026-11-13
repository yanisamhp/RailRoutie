# Editorial home page; frontend only, existing pages and backend stay unchanged.
from __future__ import annotations
import base64
from pathlib import Path
import streamlit as st
from ui.components import line_badge, render
from ui.theme import LINE_ORDER

hero_path = Path(__file__).resolve().parents[1] / "assets" / "hero_train.jpg"
if hero_path.exists():
    img = base64.b64encode(hero_path.read_bytes()).decode("ascii")
    render(f'<div class="ed-hero-photo ed-layered-hero" role="img" aria-label="ภาพรถไฟฟ้าบนทางยกระดับ" style="background-image:linear-gradient(0deg,rgba(0,0,0,.06),rgba(0,0,0,.06)),url(data:image/jpeg;base64,{img})"><span class="ed-photo-tag">EXPLORE YOUR CITY <b>↗</b></span></div>')
else:
    render('<div class="ed-hero-photo ed-hero-placeholder"><span>YOUR CITY, YOUR JOURNEY.</span></div>')

render('''
<section class="ed-welcome ed-welcome-layered">
  <div class="ed-headline"><span class="ed-overline">WELCOME TO YOUR CITY / BANGKOK RAIL</span><h1>WELCOME<span>.</span></h1><div class="ed-under">YOUR CITY. YOUR ROUTE. &nbsp; ↗</div></div>
  <div class="ed-intro"><span class="ed-intro-no">01 / DISCOVER THE CITY</span><h2>ทุกจุดหมาย<br>เริ่มต้นด้วยเส้นทางที่ใช่<span class="ed-period">.</span></h2><div class="ed-intro-rule"></div><p>ค้นหาเส้นทางรถไฟฟ้า เปรียบเทียบค่าโดยสาร<br>และวางแผนการเดินทางได้ง่าย ๆ ในที่เดียว</p></div>
</section>
''')

# SECTION 02 / How it works — immediately after the hero
render('''<section class="ed-section ed-section-second"><div class="ed-section-top"><span>HOW IT WORKS</span><span>THREE SIMPLE STEPS</span></div>
<h2 class="ed-section-title">จากจุดเริ่มต้น ถึงจุดหมาย<span>.</span></h2>
<div class="ed-steps">
 <article><span class="ed-step-no">01 / SEARCH</span><h3>เลือกจุดหมาย</h3><p>เลือกสายและสถานีใน BY STATION หรือพิมพ์ชื่อสถานที่ใน BY PLACE / POI</p></article>
 <article><span class="ed-step-no">02 / ROUTE</span><h3>สำรวจเส้นทาง</h3><p>ดูเส้นทางทางเลือก สถานีที่ผ่าน และจุดเปลี่ยนสายจากข้อมูลระบบ</p></article>
 <article><span class="ed-step-no">03 / FARE</span><h3>เปรียบเทียบราคา</h3><p>ตรวจค่าโดยสารแยกตามระบบ พร้อมสถานะความน่าเชื่อถือของราคา</p></article>
</div></section>''')

# SECTION 03 / CTA — same functional page links as original
render('<div class="ed-cta-heading"><span>START YOUR JOURNEY</span><span>CHOOSE HOW TO SEARCH&nbsp; ↓</span></div>')
left,right=st.columns(2,gap="medium")
with left:
    with st.container(key="cta1"):
        st.page_link("views/stations.py",label="BY STATION   ↗")
    render('<p class="ed-cta-help">เลือกสายรถไฟฟ้า → เลือกสถานีต้นทางและปลายทาง</p>')
with right:
    with st.container(key="cta2"):
        st.page_link("views/places.py",label="BY PLACE / POI   ↗")
    render('<p class="ed-cta-help">พิมพ์ชื่อสถานที่ได้ทันที ไม่ต้องเลือกสาย</p>')

render('<div class="ed-lines-head"><span>NETWORK COVERAGE</span><span>11 RAIL LINES</span></div>')
render('<div class="ed-line-list">'+''.join(line_badge(l) for l in LINE_ORDER)+'</div>')
render('''<div class="ed-disclaimer"><div class="ed-note-title">GOOD TO KNOW / ข้อควรรู้</div><div class="ed-note-grid">
<p>ต้นแบบเชิงวิชาการ ไม่ใช่ข้อมูลตารางเดินรถหรือระบบจำหน่ายตั๋วแบบเรียลไทม์</p>
<p>ราคาอาจเป็นข้อมูลประมาณการ และการเปรียบเทียบจำกัดเฉพาะเส้นทางที่ระบบค้นพบ</p>
<p>พิกัดสถานีบางส่วนอยู่ระหว่างทบทวน ระยะ POI เป็นระยะเส้นตรง ไม่ใช่ระยะเดินจริง</p>
</div></div>''')
