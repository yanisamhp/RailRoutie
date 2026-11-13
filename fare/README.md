# หมายเหตุ v6 วันที่ 13 พฤศจิกายน 2026

กรณีเด็กสายแดงที่มีเศษแสดงค่าประมาณพร้อม PENDING_REVIEW แล้ว อ่าน ../RED_CHILD_ESTIMATE_NOTE_TH.md (หรือไฟล์นี้จาก root) ข้อความ v5 ด้านล่างเป็นประวัติ ไม่ใช่การเปลี่ยนค่าประมาณเป็นราคายืนยัน

# อัปเดต v5 วันที่ 11 พฤศจิกายน 2026

ใช้ ../README.md และ ../ITEM5_REVIEW_TH.md เป็นสถานะปัจจุบัน
เพิ่มกฎเด็กตามข้อบังคับใหม่และBTS19แพ็กเกจ; 271testsผ่าน; ข้อ5ยังปิดได้บางส่วน
รายละเอียดด้านล่างเป็นฐานข้อมูลรุ่น v4 และต้องอ่านร่วมกับผลทบทวน v5 โดยเฉพาะเด็กและPass

# Bambi Fare component of Integrated v4

เริ่มใช้จาก../README.mdและ../CONTRACT_V1.md; standaloneFareใช้standardlibrary
py run_tests.py
py fare_engine.py examples/arl_latkrabang_phayathai.json

ราคาsnapshot2026-11-10 ผู้ใหญ่7044แถวครบ11สาย และproduct/concession22816แถว
FareEngineอ่านnetwork_overlay.jsonหลังโหลดต้นฉบับเพื่อให้กราฟตรงadapterRouting ไม่เขียนCSVMaster
MRTconcessioncardเก่าหยุดใช้ ให้ใช้ticket_type=emvและcard_schemeที่รองรับพร้อมยืนยันสิทธิ/activation
ดูfare_product_coverage.csvและ../SOURCE_REVIEW_REMAINING.mdสำหรับบริบทที่ยังไม่เปิดใช้
ผลเดิมของJSONด้าย8กรณีเป็นregressionเพิ่มเติม แต่รุ่นนี้มีผลเชื่อมRoutingจริงใน../resultsแล้ว
ไม่ใช้QA_REPORTหรือREADMEรุ่นv3มาสรุปผลรุ่นนี้
