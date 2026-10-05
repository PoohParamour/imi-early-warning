# Process Log

## [2026-10-05] ขั้นตอน: การเตรียมโครงสร้างโครงการ
**สิ่งที่ทำ:** จัดเตรียมโครงสร้างโฟลเดอร์ตามขอบเขตโครงการ และสร้าง Python virtual environment ด้วย Python 3.13

**ผลที่ได้:** มี notebook เปล่าครบ 6 ขั้น โฟลเดอร์ข้อมูล 3 ระดับ โฟลเดอร์บันทึก metrics และโฟลเดอร์สำหรับกราฟ โดยยังไม่ได้ดาวน์โหลดหรือวิเคราะห์ข้อมูล

**สิ่งที่พบ / ปัญหา:** ไม่พบปัญหาในขั้นตอนการเตรียมโครงสร้าง

**การตัดสินใจและเหตุผล:** ใช้ชื่อ virtual environment ว่า `.venv` และไม่ติดตั้ง dependency จนกว่าจะกำหนดชุด package ที่ใช้จริงในขั้น Data Acquisition

**ขั้นต่อไป:** จัดทำและรัน `01_data_acquisition.ipynb` ตาม checkpoint ที่กำหนดใน `PROJECT_SCOPE.md`


## [2026-10-05] ขั้นตอน: 01 Data Acquisition
**สิ่งที่ทำ:** ดาวน์โหลด IMI ทุกรหัสตาม MasterData จำนวน 320 เดือน ดาวน์โหลด DEXTHUS และ DCOILBRENTEU จาก FRED ตรวจ schema และบันทึก metadata พร้อม SHA-256

**ผลที่ได้:** IMI จำนวน 25,752 แถว ครอบคลุม 2000-01 ถึง 2026-08 จาก 81 รหัสและ 320 requests โดยไม่มี request ล้มเหลว; DEXTHUS จำนวน 11,931 แถว (11,395 ค่าที่ไม่ว่าง) ช่วง 1981-01-02 ถึง 2026-09-25; DCOILBRENTEU จำนวน 10,270 แถว (9,097 ค่าที่ไม่ว่าง) ช่วง 1987-05-20 ถึง 2026-09-29

**สิ่งที่พบ / ปัญหา:** การดาวน์โหลด FRED ด้วย Python requests เกิด read timeout ซ้ำ ขณะที่ URL เดียวกันดาวน์โหลดด้วย curl สำเร็จ จึงเปลี่ยน transport ของ FRED เป็น curl พร้อมกำหนด timeout และ retry ข้อมูล FRED มีค่าว่างในวันหยุดหรือวันที่ไม่มี observation โดยเก็บไว้ตามต้นฉบับและไม่แทนด้วยศูนย์

**การตัดสินใจและเหตุผล:** เก็บผลตอบกลับ IMI เป็นตาราง CSV และเก็บ request body ทั้งหมดใน manifest แยกต่างหากเพื่อให้ตรวจสอบย้อนกลับได้ ข้อมูล raw ทุกไฟล์ใช้ timestamp UTC ในชื่อไฟล์เพื่อป้องกันการเขียนทับ

**ขั้นต่อไป:** ดำเนินการ 02 Data Understanding เพื่อตรวจค่าว่าง ความต่อเนื่อง ความผันผวน และ lag correlation


## [2026-10-05] ขั้นตอน: 02 Data Understanding
**สิ่งที่ทำ:** ตรวจ schema, checksum, duplicate, missing value และความต่อเนื่องของ IMI วิเคราะห์จำนวน observation รายวัน แนวโน้ม ความผันผวน สัดส่วนเดือนที่ดัชนีไม่ขยับ และ lag correlation ระหว่าง IMI กับ DEXTHUS และ DCOILBRENTEU

**ผลที่ได้:** IMI มี 25,752 แถว 81 รหัส 320 เดือน กลุ่ม 100/318/402 มีข้อมูลครบ ความผันผวน log 2 เดือนเท่ากับ 9.12%, 4.97% และ 2.88% ตามลำดับ Brent มีข้อมูลถึงวันที่ 24 ต่ำสุด 7 วันในเดือน 2002-11, 2006-03

**สิ่งที่พบ / ปัญหา:** รหัส 315, 401 และ 417 หยุดเผยแพร่ก่อนเดือนล่าสุด แต่ไม่กระทบสามกลุ่มที่ใช้ ทุกแถว IMI มี createdAt เดียวกันจึงตรวจประวัติ revision ไม่ได้ ข้อมูลรายวันมีค่าว่างในวันหยุด และ Brent บางเดือนมี observation น้อย

**การตัดสินใจและเหตุผล:** ยืนยันใช้กลุ่ม 318 และ 402 เป็นกลุ่มหลักและ 100 เป็น sanity check ตาม Scope คง sensitivity check วันที่ 17 เทียบวันที่ 24 และไม่เพิ่ม feature จาก correlation เชิงสำรวจ

**ขั้นต่อไป:** ดำเนินการ 03 Data Preparation โดยสร้าง target และ feature ตาม forecast origin พร้อมตรวจ data leakage


## [2026-10-05] ขั้นตอน: 03 Data Preparation
**สิ่งที่ทำ:** แปลงเดือน IMI จาก พ.ศ. เป็น ค.ศ. สร้าง target h=1 และ h=2 สร้าง IMI history, DEXTHUS, Brent, partial-month วันที่ 24 และ sensitivity วันที่ 17 พร้อมกำหนด feature sets และตรวจ data leakage รายแถว

**ผลที่ได้:** ตาราง processed มี 1,839 แถว h=1 จำนวน 307 แถวต่อกลุ่ม และ h=2 จำนวน 306 แถวต่อกลุ่ม ช่วง test ของ h=2 มี 90 origins ต่อกลุ่ม Leakage audit ไม่พบ violation จาก 8 เงื่อนไขตรวจสอบ

**สิ่งที่พบ / ปัญหา:** วันเผยแพร่ IMI จริงย้อนหลังยังไม่ยืนยัน จึงใช้สมมติฐาน forecast origin วันที่ 25 ตาม Scope ข้อมูล FRED ใช้ observation date เป็นตัวแทน availability และต้องประเมิน sensitivity วันที่ 17 เทียบวันที่ 24 ในขั้น Evaluation

**การตัดสินใจและเหตุผล:** เก็บตารางแบบ long แยก horizon เพื่อให้ rolling-origin training ตรวจ target availability ได้โดยตรง บันทึก target_available_date และวัน observation ล่าสุดของ partial features เพื่อ audit ย้อนกลับ

**ขั้นต่อไป:** ดำเนินการ 04 Modeling โดยตัด training rows ที่ target_available_date อยู่หลัง forecast origin ของแต่ละรอบ และ fit preprocessing เฉพาะ training data
