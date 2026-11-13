# Dai Backend v1 — POI Search, Station Matching & Routing

Thai Public Transport Planner (DSI463), **Phase 2 — Python backend only** (ยังไม่มี Streamlit / `app.py`)

| ไฟล์ | หน้าที่ |
|---|---|
| `data_loader.py` | โหลด CSV ทั้ง 4 ไฟล์จาก `dai_routing_v2/` (อ่านอย่างเดียว) และตรวจ referential integrity |
| `poi_search.py` | Task A — ค้นหาชื่อสถานที่ (Nominatim) → พิกัด + แหล่งข้อมูล |
| `station_matching.py` | Task B — สถานีใกล้ที่สุด Top-k ด้วย **ระยะเส้นตรง (Haversine)** |
| `routing_engine.py` | Task C — Routing (Dijkstra/heapq + Yen's k-shortest) โหมด `shortest_edges` / `fewest_transfers` |
| `tests/` | pytest (POI search mock HTTP ทั้งหมด ไม่ยิง network) |
| `run_tests_to_csv.py` | รันชุดทดสอบรับมอบงาน → `routing_test_results.csv`, `poi_matching_test_results.csv` |
| `fixtures/poi_fixtures.json` | ผล Nominatim ที่บันทึกไว้ (จากการรัน `--live` วันที่ 2026-11-10) ใช้รันแบบ offline |

ข้อมูล: `dai_routing_v2` — 195 station-line records, 11 lines, 184 RIDE edges, 21 connections (20 TRANSFER + 1 BRANCH_JUNCTION)

---

## ติดตั้งและรัน

```bash
cd deliverables/dai_backend_v1
python -m pip install -r requirements.txt   # requests, pytest (ไม่ใช้ networkx)

# Tests
python -m pytest -q

# CSV ผลทดสอบ (POI ใช้ fixture ที่บันทึกไว้)
python run_tests_to_csv.py
# CSV ผลทดสอบ โดยยิง Nominatim จริง (≤ 1 req/s, มี cache) และอัปเดต fixture
python run_tests_to_csv.py --live

# CLI
python poi_search.py "สยามพารากอน" --stations 3
python station_matching.py 13.7468 100.5350 --top-k 5
python routing_engine.py ARL:A1 MRT-BLU:BL04 --mode fewest_transfers --json
python routing_engine.py ARL:A1 MRT-BLU:BL04 --alternatives 3
```

ตำแหน่ง dataset: ค่า default คือ `../../dai_routing_v2/` (relative จากไฟล์ใน `dai_backend_v1`, ใช้ `pathlib`)
เปลี่ยนได้ด้วย argument `data_dir=` ของทุกฟังก์ชัน, `--data-dir` ใน CLI หรือ env `DAI_ROUTING_DATA_DIR`

Environment:
- `NOMINATIM_USER_AGENT` — User-Agent ที่ระบุตัวตนแอป (default `DSI463-ThaiTransportPlanner/0.1 (student project)`) **ควรใส่ช่องทางติดต่อทีมก่อนใช้งานจริง**
- บน Windows console ที่ไม่ใช่ UTF-8 CLI จะ reconfigure stdout เป็น UTF-8 ให้เอง

---

## Task A — `poi_search.py`

```python
from poi_search import search_poi, confirm_poi
res = search_poi("สนามบินสุวรรณภูมิ", limit=5)
if res["needs_confirmation"]:
    res = confirm_poi(res, 0)          # index ที่ "ผู้ใช้" เลือก
poi = res["selected"]
```

ผลลัพธ์:
```json
{
  "query": "สยามพารากอน",
  "status": "OK",
  "candidates": [
    {"name": "สยามพารากอน", "display_name": "สยามพารากอน, 991, ถนนพระรามที่ 1, ...",
     "latitude": 13.7467785, "longitude": 100.534954, "provider": "nominatim",
     "source_id": "osm:way/781138575", "source_url": "https://www.openstreetmap.org/way/781138575",
     "category": "shop", "type": "mall", "importance": 0.415}
  ],
  "needs_confirmation": false,
  "selected": { "...": "candidate ที่เลือก (null ถ้า AMBIGUOUS)" },
  "provider": "nominatim",
  "from_cache": false,
  "fallback_query": null,
  "message": "One result found."
}
```

**Fallback query:** ถ้าค้นทั้งชื่อแล้วได้ `NOT_FOUND` และ query ขึ้นต้นด้วย `ตลาดนัด` หรือ `ตลาด` จะตัดคำนำหน้าแล้วค้นใหม่ 1 ครั้ง
(ผ่าน provider เดิม จึงยังเคารพ 1 req/s และ cache) ถ้าเจอผล → `status="AMBIGUOUS"`, `needs_confirmation=true`,
`selected=null` **เสมอ แม้ได้ผลเดียว** (เพราะเป็นผลของคำค้นอื่น) และ `fallback_query` = คำที่ใช้ค้นจริง
ถ้าไม่เจอ → `NOT_FOUND`; ถ้า fallback ล้ม → `NETWORK_ERROR`/`RATE_LIMITED` พร้อม `fallback_query`
ตัวอย่าง: `"ตลาดนัดเซฟวัน"` → NOT_FOUND → fallback `"เซฟวัน"` → AMBIGUOUS (ตลาดเซฟวัน Go สายไหม)

| status | ความหมาย |
|---|---|
| `OK` | ได้ **1 ผลพอดี** (หลังรวมผลซ้ำ) → `selected` = ผลนั้น |
| `AMBIGUOUS` | ได้ **มากกว่า 1 ผล** (หรือได้ผลจาก fallback) → `needs_confirmation=true`, `selected=null` คืน candidates ทั้งหมด (ชื่อ, พิกัด, provider, source) ให้ผู้ใช้เลือกเองผ่าน `confirm_poi` — **ไม่เลือกให้อัตโนมัติ** |
| `CONFIRMED` | ผลจาก `confirm_poi(result, index)` |
| `INVALID_SELECTION` | index ใน `confirm_poi` ไม่ถูกต้อง |
| `NOT_FOUND` | ไม่พบสถานที่ |
| `NETWORK_ERROR` | timeout / connection error / HTTP อื่น / JSON เสีย |
| `RATE_LIMITED` | HTTP 429 |
| `INVALID_QUERY` | query ว่าง, ไม่ใช่ string หรือยาวเกิน 200 ตัวอักษร |

Nominatim Usage Policy: User-Agent ระบุตัวตน, ≤ 1 request/วินาที (throttle ทั้ง process), timeout 10 s,
cache JSON ใน `.cache/nominatim/` (cache เฉพาะ response สำเร็จ; key รวม viewbox/bounded), `countrycodes=th`, `accept-language=th,en`

**ขอบเขตการค้นหา (กรุงเทพฯ และปริมณฑล):** `viewbox` คำนวณจาก bounding box ของสถานีทั้ง 195 จุดใน dataset
(ผ่าน `data_loader`, ฟังก์ชัน `compute_viewbox()`) ขยายขอบด้านละ `VIEWBOX_MARGIN_DEG = 0.05°` (≈ 5.5 km) และส่ง **`bounded=1`**
เพื่อให้ Nominatim คืนเฉพาะผลในกรอบ ค่าปัจจุบัน: `100.358250,14.040650,100.802249,13.517664` (lon_min,lat_max,lon_max,lat_min)
→ ผลต่างจังหวัด เช่น ตลาดเซฟวันโคราช จะไม่ถูกคืนมา
ไม่มีการกรองเพิ่มตามระยะถึงสถานีหรือตามจังหวัด (คู่มือไม่ได้กำหนด) — POI ที่อยู่ในกรอบแต่ไกลสถานียังได้ `FAR_FROM_NETWORK` จาก Task B
ผลที่ชื่อเดียวกันห่างกัน ≤ 150 m (เช่น node + way ของที่เดียวกัน) ถูกรวมเป็นผลเดียว
เปลี่ยน geocoder ได้โดย subclass `GeocodingProvider` แล้วส่ง `search_poi(q, provider=MyProvider())`
`search_poi` ไม่ raise exception ออกไปหาผู้เรียกในทุกกรณี (ถ้าโหลด dataset เพื่อคำนวณ viewbox ไม่ได้ → `NETWORK_ERROR` พร้อมข้อความ)

## Task B — `station_matching.py`

> **ระยะทางทั้งหมดเป็นระยะเส้นตรง (Haversine, รัศมีโลก 6,371,008.8 m) ระหว่างพิกัด POI กับพิกัดจุดสถานี —
> ไม่ใช่ระยะเดิน ไม่ใช่เวลาเดิน และไม่ใช่ระยะถึงทางออกสถานี**

```python
from station_matching import find_nearest_stations, match_poi_to_stations, haversine_m
find_nearest_stations(13.7468, 100.5350, top_k=5, group_same_station=True)
match_poi_to_stations(res, top_k=3)    # รับ candidate หรือผล search_poi/confirm_poi ได้ตรงๆ
```

```json
{
  "query": "สยามพารากอน",
  "poi": {"name": "สยามพารากอน", "latitude": 13.7467785, "longitude": 100.534954, "provider": "nominatim",
          "source_id": "osm:way/781138575", "source_url": "https://www.openstreetmap.org/way/781138575"},
  "nearest_stations": [
    {"station_line_id": "BTS-SIL:CEN", "station_line_ids": ["BTS-SIL:CEN", "BTS-SUK:CEN"],
     "name_en": "Siam", "name_th": "สยาม", "line_id": "BTS-SIL", "line_ids": ["BTS-SIL", "BTS-SUK"],
     "line_name_th": "สายสีลม", "latitude": 13.7456, "longitude": 100.5341, "distance_m": 156.3,
     "coordinate_origin": "MASTER_EXISTING", "coordinate_qa_status": "WITHIN_100M", "coordinate_warning": false}
  ],
  "distance_method": "haversine_straight_line",
  "status": "OK",
  "warnings": [],
  "message": "Distances are straight-line (Haversine) between coordinate points, not walking distance."
}
```

- `group_same_station=True` รวม station-line ที่เป็นสถานีเดียวกัน: (`name_th` ตรงกัน หรือ `name_en` ตรงกันเมื่อตัดวงเล็บท้าย) **และ** ห่าง ≤ 300 m, หรือเชื่อมด้วย TRANSFER ที่ `distance_m_from_file = 0`.
  `station_line_id` = record ที่ใกล้ที่สุดในกลุ่ม, `station_line_ids` = ทั้งหมด (เรียงใกล้→ไกล)
  ตัวอย่างที่ถูกรวม: Siam, Phaya Thai, Krung Thon Buri, Krung Thep Aphiwat, Bang Wa, Tao Poon, Lat Phrao, Hua Mak, Samrong, Wat Phra Sri Mahathat
- `coordinate_warning = true` เมื่อ record ใดในกลุ่มเป็น `OSM_PROVISIONAL` หรือ QA ไม่ใช่ `WITHIN_100M`/`WITHIN_200M`
- `top_k` ถูกจำกัดในช่วง 1–10 (แนะนำ 3–5); ผู้ใช้ควรเลือกสถานีเองได้ ไม่บังคับอันดับ 1

| status | ความหมาย |
|---|---|
| `OK` | ปกติ |
| `FAR_FROM_NETWORK` | สถานีใกล้สุดไกลเกิน 3 km (เส้นตรง) — ยังคืนรายการสถานีพร้อม `warnings` |
| `INVALID_COORDINATES` | lat/lon ไม่ใช่ตัวเลข, NaN/inf หรือนอกช่วง |
| `POI_NOT_CONFIRMED` | ส่งผล AMBIGUOUS ที่ยังไม่ยืนยันให้ `match_poi_to_stations` |

## Task C — `routing_engine.py`

Graph: node = `station_line_id`; edge = RIDE + TRANSFER + BRANCH_JUNCTION, **สองทิศทางทั้งหมด** (ตาม README ของ dataset — ต้องตรวจทิศทางจริงก่อน production)

| โหมด | cost (lexicographic) |
|---|---|
| `shortest_edges` | (จำนวน edge ทั้งหมด RIDE+TRANSFER+BRANCH_JUNCTION, จำนวน TRANSFER) |
| `fewest_transfers` | (จำนวน TRANSFER, จำนวน RIDE, จำนวน BRANCH_JUNCTION) |

`BRANCH_JUNCTION` (`MRT-PNK:PK10` ↔ `MRT-PNK-MT:MT01`) **ไม่นับเป็น transfer**

```python
from routing_engine import find_route, find_alternative_routes, route_between_candidates, route_to_text
r = find_route("ARL:A1", "MRT-BLU:BL04", optimization="fewest_transfers")
alts = find_alternative_routes("ARL:A1", "MRT-BLU:BL04", k=3)        # สำหรับเทียบราคา
best = route_between_candidates(["BTS-SUK:CEN", "BTS-SIL:CEN"], ["BTS-SIL:S2", "MRT-BLU:BL26"])
print(route_to_text(r))
```

```json
{
  "route_id": "route_3f2a9c1b7e",
  "status": "OK",
  "optimization": "fewest_transfers",
  "origin": "ARL:A1", "destination": "MRT-BLU:BL04",
  "station_line_ids": ["ARL:A1", "ARL:A2", "...", "ARL:A6", "MRT-BLU:BL21", "...", "MRT-BLU:BL04"],
  "edges": [
    {"from": "ARL:A1", "to": "ARL:A2", "type": "RIDE", "line_id": "ARL", "edge_id": "RIDE-001"},
    {"from": "ARL:A6", "to": "MRT-BLU:BL21", "type": "TRANSFER", "line_id": null,
     "edge_id": "CONN-015", "connection_id": "CONN-015"}
  ],
  "summary": {"ride_count": 22, "transfer_count": 1, "branch_junction_count": 0, "edge_count": 23,
              "lines_used": ["ARL", "MRT-BLU"]},
  "legs": [
    {"line_id": "ARL", "line_name_th": "แอร์พอร์ตเรลลิงก์", "from": "ARL:A1", "to": "ARL:A6",
     "station_line_ids": ["ARL:A1", "...", "ARL:A6"], "stations": 6, "rides": 5, "entered_via": "START"},
    {"line_id": "MRT-BLU", "line_name_th": "สายสีน้ำเงิน", "from": "MRT-BLU:BL21", "to": "MRT-BLU:BL04",
     "station_line_ids": ["MRT-BLU:BL21", "...", "MRT-BLU:BL04"], "stations": 18, "rides": 17, "entered_via": "TRANSFER"}
  ],
  "transfers": [{"from": "ARL:A6", "to": "MRT-BLU:BL21", "connection_id": "CONN-015", "distance_m_from_file": 251.0}],
  "branch_junctions": [],
  "message": ""
}
```

| status | ความหมาย |
|---|---|
| `OK` | พบเส้นทาง |
| `SAME_STATION` | ต้นทาง = ปลายทาง (edges ว่าง) หรือสถานีเดียวกันต่างสายที่เชื่อมด้วย TRANSFER ระยะ 0 (edges = TRANSFER 1 เส้น, ride 0) |
| `NO_ROUTE` | ไม่มีเส้นทาง (ปัจจุบัน graph เชื่อมถึงกันทั้ง 195 nodes) |
| `UNKNOWN_STATION` | ID ไม่อยู่ใน dataset (`unknown_ids` ระบุตัวที่ผิด) |
| `INVALID_OPTIMIZATION` | โหมดไม่ใช่ `shortest_edges`/`fewest_transfers` |

- `find_alternative_routes(o, d, k)` — Yen's k-shortest paths ภายใต้ทั้ง 2 โหมด → รวม → dedupe ตามลำดับสถานี → เรียงตาม (transfer, ride); `route_id` = `route_001…`, มี `found_by`, `rank`. **ไม่อ้างว่าเส้นทางใดถูกที่สุด** — ใช้ส่งให้ Fare Engine เทียบราคา
- `route_between_candidates(origin_ids, dest_ids, optimization)` — ลองทุกคู่ (เช่น Top-3 สถานีของ POI ต้นทาง × ปลายทาง) คืนเส้นทางดีที่สุดตามโหมด พร้อม `selected_origin`, `selected_destination`, `pairs_tried`, `pairs_failed`
- `route_to_text(route)` — ข้อความภาษาไทยสำหรับแสดงผลเท่านั้น (แยกจากข้อมูล structured)
- `find_route` ไม่ raise exception สำหรับ input ผิด

## Task D — Tests

```
python -m pytest -q        → 84 passed
python run_tests_to_csv.py → routing 20/20 PASS, poi_matching 22/22 PASS (ทั้งโหมด fixture และ --live, 2026-11-10)
```

ผลทดสอบเส้นทางหลัก (ทั้ง 2 โหมดให้ผลเท่ากัน):

| origin | destination | RIDE | TRANSFER | ผล |
|---|---|---|---|---|
| ARL:A1 | ARL:A8 | 7 | 0 | PASS |
| MRT-BLU:BL01 | MRT-PPL:PP10 | 15 | 1 (CONN-011 Tao Poon) | PASS |
| ARL:A1 | MRT-BLU:BL04 | 22 | 1 (CONN-015 ARL:A6→MRT-BLU:BL21) | PASS |

ครอบคลุมเพิ่ม: same station / same station ต่างสาย / unknown ID / BRANCH_JUNCTION ไม่นับ transfer /
ความถูกต้องเชิงโครงสร้างของ path / graph connected 195 nodes / alternative routes ไม่ซ้ำ /
haversine / top-k / grouping สถานีซ้ำ / พิกัดผิด / ไกลจากเครือข่าย / POI search (mock) ทุก status + cache + throttle +
fallback query (เจอ/ไม่เจอ/network error/ไม่มีคำนำหน้า/ไม่เลือกอัตโนมัติ/throttle+cache) +
viewbox ครอบคลุมทุกสถานี + `bounded=1` + >1 ผลเป็น AMBIGUOUS เสมอ

`run_tests_to_csv.py` ตรวจเพิ่มทุก POI ว่า candidates ทุกตัวอยู่ใน viewbox และใส่รายชื่อ candidates ไว้ใน `note`
`fixtures/poi_fixtures.json` บันทึกใหม่ทั้งไฟล์ทุกครั้งที่รัน `--live` (มี `_meta` ระบุ viewbox/bounded)

| test | query | ผล (2026-11-10, bounded=1) |
|---|---|---|
| PM-002 | `ตลาดนัดเซฟวัน` | ชื่อเต็ม NOT_FOUND → fallback `เซฟวัน` → `AMBIGUOUS` (ผู้ใช้ต้องยืนยัน) candidate: ตลาดเซฟวัน Go สายไหม → `BTS-SUK:N23` 304.4 m; ไม่มีผลโคราช |
| PM-007 | `ตลาดเซฟวัน` | `OK` 1 ผล: ตลาดเซฟวัน Go สายไหม → `BTS-SUK:N23` 304.4 m; ไม่มีผลโคราช (เดิม bounded=0 ได้ตลาดเซฟวันโคราช ~189 km) |

ชื่อ "ตลาดนัดเซฟวัน" กำกวม: ตลาดเซฟวันหลักอยู่นครราชสีมา (นอกขอบเขตโปรเจกต์) ส่วนในกรุงเทพฯ คือตลาดเซฟวัน Go สายไหม

---

## ข้อจำกัด (ห้ามกล่าวอ้างเกินนี้)

1. **พิกัด 55 จุดเป็น OSM provisional** (`PROVISIONAL_NOT_VERIFIED`) และอีก 8 จุดมี QA `REVIEW_200_500M`/`NO_USABLE_OSM_POINT` (เช่น `ARL:A1`) → `coordinate_warning=true`
2. **ระยะเส้นตรง ≠ ระยะเดิน/เวลาเดิน** และพิกัดสถานีเป็นจุดเดียว ไม่ใช่ทางออก
3. **ทิศทางการเดินรถสมมติเป็นสองทางทุก connection** — ต้องตรวจทิศทางและเงื่อนไขการเปลี่ยนสายจริงก่อน production
4. **BRANCH_JUNCTION** (PK10↔MT01, ระยะในไฟล์ 607 m) ต้องตรวจรูปแบบบริการจริง (ต้องเปลี่ยนขบวนหรือไม่ / ค่าโดยสาร)
5. **ยังไม่มี Fastest / Cheapest** — ไม่มีข้อมูลเวลาเดินทางหรือค่าโดยสารใน dataset; Cheapest ต้องให้ Fare Engine เทียบจาก `find_alternative_routes`
6. Nominatim ครอบคลุมชื่อไทยไม่ครบ และการสะกดเปลี่ยนผลมาก: (ทดสอบ 2026-11-10)
   `"ตลาดนัดเซฟวัน"` → NOT_FOUND (จึงมี fallback ตัด `ตลาดนัด`); `"เซฟวัน"` / `"ตลาดเซฟวัน"` → ตลาดเซฟวัน Go (สายไหม กทม.)
   → UI ต้องแสดง `display_name` ให้ผู้ใช้ยืนยันเสมอ และอาจต้องมีช่องค้นหาซ้ำ/ใส่พิกัดเอง
   → fallback ครอบคลุมแค่คำนำหน้า `ตลาดนัด`/`ตลาด` เท่านั้น
7. `bounded=1` ตัดสถานที่นอกกรอบ bounding box ของสถานี (+0.05°) ออกทั้งหมด — ถ้าผู้ใช้ต้องการต้นทาง/ปลายทางนอกกรอบจะได้ `NOT_FOUND`
   กรอบเป็นสี่เหลี่ยมตามพิกัด ไม่ใช่ขอบเขตจังหวัดจริงของปริมณฑล
8. ผลค้นหาบางรายการเป็นจุดย่อย (เช่น สนามบินสุวรรณภูมิ → ประตู/ป้ายรถ 5 จุด) ผู้ใช้ต้องเลือกจุดที่ต้องการเอง
9. Metadata สาย (ชื่อ/สี) ยังเป็น provisional (AI_DRAFT)

---

## Integration Contract สำหรับ Bambi (Routing → Fare Engine)

คีย์ที่ Fare Engine ใช้ได้จาก route dict (ทั้ง `find_route` และแต่ละรายการของ `find_alternative_routes`):

| คีย์ | ชนิด | ใช้ทำอะไร |
|---|---|---|
| `route_id` | str | อ้างอิงเส้นทางใน fare result (`route_001…` สำหรับ alternatives) |
| `status` | str | คิดราคาเฉพาะ `OK`; `SAME_STATION` ไม่มี ride (ride_count 0) |
| `optimization` | str | `shortest_edges` / `fewest_transfers` / `alternatives` |
| `station_line_ids` | list[str] | ลำดับสถานี (key ตรงกับ dataset กลาง) |
| `edges[]` | list | `from`, `to`, `type` (`RIDE`/`TRANSFER`/`BRANCH_JUNCTION`), `line_id` (null สำหรับ connection), `edge_id`, `connection_id` |
| `legs[]` | list | **ช่วงตามสาย → ใช้แยก fare segment**: `line_id`, `from`, `to`, `station_line_ids`, `stations`, `rides`, `entered_via` (`START`/`TRANSFER`/`BRANCH_JUNCTION`) |
| `transfers[]` | list | จุดเปลี่ยนสาย + `connection_id` (ใช้ตรวจกฎส่วนลด/ข้ามผู้ให้บริการ) |
| `branch_junctions[]` | list | ช่วงที่ผ่านจุดแยกสาขา (ไม่ใช่ transfer แต่ line_id เปลี่ยน) |
| `summary` | dict | `ride_count`, `transfer_count`, `branch_junction_count`, `edge_count`, `lines_used` |

### ข้อตกลงกับ Bambi (ตกลงแล้ว 10 พ.ย. 2026)

- ฟังก์ชันฝั่ง Fare Engine: `calculate_fare(route) -> dict` และ `calculate_fares(routes) -> list[dict]` (คืนตามลำดับ input)
- ผลจาก Fare Engine: `route_id`, `status`, `total_fare_thb`, `fare_segments`, `sources`, `reasons`
- หน่วยราคาเป็นบาท (`*_thb`, float); ไม่มีข้อมูล = `null` (ไม่ใช้ 0); list ว่าง = `[]`
- คิดได้บางช่วง → `total_fare_thb = null` แต่ยังแสดงช่วงที่คิดได้ใน `fare_segments` พร้อม `reasons`
- Status ฝั่ง Fare Engine: `OK`, `FARE_DATA_UNAVAILABLE`, `INVALID_ROUTE`, `NO_TRAVEL`, `INVALID_CONTEXT`, `UNSUPPORTED_FARE_CONTEXT`

| กรณีจาก Routing | Fare Engine คืน |
|---|---|
| `SAME_STATION` และ `edges` ว่าง (เช่น `ARL:A1` → `ARL:A1`) | `NO_TRAVEL`, ราคา 0 (หมายถึงไม่ได้เดินทาง) |
| `SAME_STATION` มีแต่ `TRANSFER` ไม่มี `RIDE` (เช่น `BTS-SUK:CEN` → `BTS-SIL:CEN`) | `FARE_DATA_UNAVAILABLE`, `null` |
| `UNKNOWN_STATION` / `NO_ROUTE` (`route_id` อาจเป็น `null`) | `INVALID_ROUTE` + `reasons` |
| ผ่าน `BRANCH_JUNCTION` PK10 → MT01 | ส่งตาม Dataset; ตอนนี้กฎราคายังไม่ยืนยัน → `null` |
| เปลี่ยนสายข้าม operator | ไม่ใช้ส่วนลดอัตโนมัติ; คู่ที่กฎไม่ชัด → `null` |

หมายเหตุ: Fare data ตอนนี้ครอบคลุม 5/11 สาย สายที่ยังไม่มีข้อมูลคืน `null`
ตัวอย่าง Route JSON จากโค้ดจริง 8 เคส: `../route_samples_for_bambi.json`

---

## Open questions for team

| # | เรื่อง | สถานะปัจจุบันในโค้ด | ต้องการคำตอบจาก |
|---|---|---|---|
| 1 | **BRANCH_JUNCTION `MRT-PNK:PK10` ↔ `MRT-PNK-MT:MT01`** (CONN-021) — ในไฟล์ห่างกัน **607 m** และชื่อต่างกัน (เมืองทองธานี / อิมแพ็ค เมืองทองธานี) เป็นสถานีเดียวกันหรือต้องลงเปลี่ยนขบวน? ขบวนวิ่งตรงจากสายหลักเข้าสาขาได้ไหม? | ไม่นับเป็น transfer (ตาม README dataset), leg ถัดไปมี `entered_via="BRANCH_JUNCTION"`, ไม่ถูกรวมเป็นสถานีเดียวกันใน station matching | มิวมิว (รูปแบบบริการจริง); Bambi ตอนนี้คืน `null` จนกว่ากฎราคาจะยืนยัน |
| 2 | ~~**ค่าโดยสารกรณี `SAME_STATION` ที่ `ride_count = 0`**~~ — **ตกลงแล้วกับ Bambi**: edges ว่าง → `NO_TRAVEL` (0); มีแต่ TRANSFER → `FARE_DATA_UNAVAILABLE` (null) | Routing คืน `SAME_STATION` เหมือนเดิม; Fare Engine แยกจาก `edges` | — |
| 3 | **การรวมสถานีใน station matching**: บางหว้า (`BTS-SIL:S12` + `MRT-BLU:BL34`, ห่าง ~70 m, `name_th` เดียวกัน) และวัดพระศรีมหาธาตุ (`BTS-SUK:N17` + `MRT-PNK:PK16`, TRANSFER ระยะ 0 ในไฟล์ / พิกัดห่าง ~120 m, PK16 เป็น OSM provisional) ถูกแสดงเป็นตัวเลือกเดียว | กฎ: `name_th` ตรงกัน หรือ `name_en` ตรงกันเมื่อตัดวงเล็บท้าย + ห่าง ≤ 300 m, หรือ TRANSFER ระยะ 0; ยังเก็บ `station_line_ids` ครบ; ปิดได้ด้วย `group_same_station=False` | มิวมิว: ยืนยันว่าควรรวมเป็นสถานีเดียวกันสำหรับ UI หรือไม่ |
| 4 | ~~**เกณฑ์ importance 0.15**~~ — **ยกเลิกแล้ว**: ตอนนี้ผลมากกว่า 1 รายการเป็น `AMBIGUOUS` เสมอ ให้ผู้ใช้เลือกเอง (ตามคู่มือ Task A) | ไม่มีการเลือกอัตโนมัติจากหลายผล | — |
| 5 | **ขอบเขตค้นหา POI** = bounding box สถานี + 0.05° พร้อม `bounded=1` (ผลนอกกรอบไม่ถูกคืน) | `VIEWBOX_MARGIN_DEG` ใน `poi_search.py` | ทีม: margin นี้พอสำหรับ "ปริมณฑล" หรือไม่ |
