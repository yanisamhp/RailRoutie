# หมายเหตุ v6 วันที่ 13 พฤศจิกายน 2026

กรณีเด็กสายแดงที่มีเศษแสดงค่าประมาณพร้อม PENDING_REVIEW แล้ว อ่าน ../RED_CHILD_ESTIMATE_NOTE_TH.md (หรือไฟล์นี้จาก root) ข้อความ v5 ด้านล่างเป็นประวัติ ไม่ใช่การเปลี่ยนค่าประมาณเป็นราคายืนยัน

# อัปเดต v5 วันที่ 11 พฤศจิกายน 2026

ใช้ ../README.md และ ../ITEM5_REVIEW_TH.md เป็นสถานะปัจจุบัน
เพิ่มกฎเด็กตามข้อบังคับใหม่และBTS19แพ็กเกจ; 271testsผ่าน; ข้อ5ยังปิดได้บางส่วน
รายละเอียดด้านล่างเป็นฐานข้อมูลรุ่น v4 และต้องอ่านร่วมกับผลทบทวน v5 โดยเฉพาะเด็กและPass

# Fare QA v4

ผลsuiteจริงอยู่fare_test_results.csv และ../results/test_summary.json
เพิ่มการทดสอบGoldoperator6คู่ currentMangmoom retiredMRTcards EMVsenior tokenexemption existingpass และBluePurplemixeddailycap
ยังไม่อ้างราคาครบทุกสิทธิหรือโปรโมชั่น ดู../SOURCE_REVIEW_REMAINING.md
ข้อมูลBluepriceมาจากtariffกับtopologyจริงและเทียบ37คู่คอลัมน์เตาปูน ส่วนruntimegraphแก้ผ่านnetwork_overlayโดยไม่แก้Master
อัปเดตtestsจากv3ที่คาดว่าARLEMVไม่รองรับและlegacyMRTcardใช้งานได้ ให้ตรงหลักฐานปัจจุบัน เก็บtestsที่ปฏิเสธlegacycardไว้โดยเฉพาะ
ทดสอบDaiJSON8กรณียังคงอยู่ และทดสอบโมดูลDaiจริงในชุดintegrationของroot
