# IMI Early Warning

การพัฒนาแบบจำลอง Machine Learning เพื่อเตือนล่วงหน้าการเปลี่ยนแปลงดัชนีราคานำเข้า: กรณีศึกษาเปรียบเทียบกลุ่มปุ๋ยและกลุ่มผลิตภัณฑ์นมของไทย

*Machine Learning for Early Warning of Import Price Changes: A Comparative Study of Thai Fertilizer and Dairy Import Price Indices*

โครงงานรายวิชา [กรอก: ชื่อวิชา / ภาคการศึกษา] ดำเนินการตามกระบวนการ CRISP-DM ครบ 6 ขั้น

## โครงการนี้ทำอะไร

ดัชนีราคาสินค้านำเข้า (IMI) ของ สนค. กระทรวงพาณิชย์ เผยแพร่หลังสิ้นเดือนอ้างอิง 26–41 วัน ขณะที่อัตราแลกเปลี่ยนและราคาน้ำมันมีข้อมูลรายวัน โครงการนี้ทดสอบว่าข้อมูลที่ออกเร็วกว่าเหล่านี้ช่วยพยากรณ์การเปลี่ยนแปลงของ IMI กลุ่มปุ๋ย (318) และนม (402) ได้แม่นกว่าการใช้ประวัติ IMI อย่างเดียวหรือไม่ โดยใช้กลุ่มเชื้อเพลิง (100) เป็น sanity check

จุดเน้นคือการจำลองการใช้งานจริง: พยากรณ์ ณ วันที่ 15 ของเดือน t+2 ใช้เฉพาะข้อมูลที่เผยแพร่แล้ว ณ วันนั้น และกำหนดการเปรียบเทียบหลักไว้ก่อนเปิดผลช่วงทดสอบ

## ผลสรุป

| หัวข้อ | ผล |
|---|---|
| ค่าเงิน + น้ำมัน ช่วยพยากรณ์ IMI หรือไม่ (h=3) | ไม่ช่วยอย่างมีนัยสำคัญทั้งปุ๋ยและนม (Holm p ต่ำสุด 0.38) |
| ข้อมูลที่ออกเร็วกว่า IMI | ช่วยเฉพาะเดือนที่พยากรณ์ เช่น เชื้อเพลิง h=2 แม่นกว่า No-change 20% (p = 0.021) |
| กลุ่มนม | แม่นกว่า No-change 13–19% ที่ h=2–5 จากประวัติราคาเอง ไม่ได้มาจากข้อมูลภายนอก |
| สัญญาณ High Risk | ไม่ดีกว่าการเตือนทุกเดือน (ปุ๋ย F1 0.45 เทียบ 0.55; นมไม่เตือนเลย) |
| รอบที่ 2 (เชิงสำรวจ) | ราคายูเรียและ DAP โลกลด MAE ของปุ๋ย 6.6% ใน test แต่ขัดกับผล validation จึงเป็นเพียงข้อเสนอให้ยืนยันกับข้อมูลใหม่ |

ผลทั้งหมดอยู่ใน `logs/metrics/*.csv` และบันทึกการตัดสินใจทุกขั้นอยู่ใน `logs/process_log.md`

## Dashboard

เปิดไฟล์ `reports/dashboard/imi_dashboard.html` ในเบราว์เซอร์ได้โดยไม่ต้องต่ออินเทอร์เน็ต หน้าแรกบอกทิศทางราคานำเข้าด้วยภาษาธรรมดาพร้อมช่วงความคลาดเคลื่อนและระดับความน่าเชื่อถือ ส่วนรายละเอียดทางเทคนิคกดเปิดได้

## โครงสร้างโปรเจกต์

```
notebooks/
  01_data_acquisition.ipynb     ดึงข้อมูล IMI, FRED, CPI/PPI และบันทึก checksum
  02_data_understanding.ipynb   สำรวจข้อมูล, correlation, pass-through
  03_data_preparation.ipynb     target, feature, วันพยากรณ์, ตรวจ data leakage
  04_modeling.ipynb             baselines, ARIMA, Ridge, XGBoost ด้วย rolling origin
  05_evaluation.ipynb           MAE, Diebold-Mariano (HLN) + Holm, alert, embargo
  05b_iteration2.ipynb          รอบที่ 2: ราคาวัตถุดิบโลก (เชิงสำรวจ)
  06_deployment.ipynb           สร้าง dashboard
data/
  raw/          ข้อมูลดิบและ sources.json (URL, เวลาดาวน์โหลด, SHA-256) ห้ามแก้
  interim/      ค่าเฉลี่ยรายเดือนของข้อมูลภายนอก (สร้างจาก notebook)
  processed/    ตาราง feature/target (สร้างจาก notebook)
logs/
  process_log.md   บันทึกการทำงานและการตัดสินใจ
  metrics/         ตารางตัวเลขผลลัพธ์ (csv)
reports/
  figures/         กราฟ
  dashboard/       imi_dashboard.html
scripts/
  acquire_data.py  สคริปต์ดึงข้อมูลรุ่นแรก (notebook 01 เป็นฉบับที่ใช้จริง)
```

## วิธีรันซ้ำ

ต้องใช้ Python 3.13

```sh
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

รัน notebook ตามลำดับ (แต่ละไฟล์อ่านผลของไฟล์ก่อนหน้า):

```sh
for nb in 01_data_acquisition 02_data_understanding 03_data_preparation \
          04_modeling 05_evaluation 05b_iteration2 06_deployment; do
  jupyter nbconvert --to notebook --execute --inplace notebooks/$nb.ipynb \
    --ExecutePreprocessor.timeout=1800
done
```

- **ข้อมูลดิบ:** notebook 01 อ่าน snapshot ใน `data/raw/` ตาม `sources.json` และตรวจ SHA-256 เป็นค่าเริ่มต้น ไม่ยิง API ซ้ำ ถ้าต้องการดึงข้อมูลใหม่ให้ตั้ง `DOWNLOAD_NEW`, `DOWNLOAD_RELEASE_CALENDAR`, `DOWNLOAD_DOMESTIC` และ `DOWNLOAD_COMMODITY` เป็น `True` (ไฟล์ใหม่จะมี timestamp ในชื่อ ไม่เขียนทับของเดิม)
- **ข้อควรระวังเมื่อดึงข้อมูลใหม่:** ตัวเลขใน `logs/metrics/` จะเปลี่ยน และ notebook 03 มี assert จำนวนแถวที่ผูกกับ snapshot วันที่ 5 ต.ค. 2569 ที่ต้องปรับตามข้อมูลใหม่
- **เวลา:** notebook 04 ใช้เวลาราว 4 นาที (มี progress bar) ส่วนที่เหลือใช้เวลาไม่นาน
- **ตัวเลขใน `logs/metrics/`:** สร้างจาก notebook ถ้ารันซ้ำกับ snapshot เดิมจะได้ค่าเท่าเดิม

## แหล่งข้อมูล

| ข้อมูล | แหล่ง | ใบอนุญาต |
|---|---|---|
| ดัชนีราคาสินค้านำเข้า (IMI), CPI, PPI | [สนค. กระทรวงพาณิชย์](https://data.go.th/dataset/tpso_data_70) ผ่าน API index-api.tpso.go.th | Open Data Common |
| อัตราแลกเปลี่ยนบาทต่อดอลลาร์ (DEXTHUS) | [FRED](https://fred.stlouisfed.org/series/DEXTHUS) / Federal Reserve H.10 | Public Domain (ขออ้างอิง) |
| ราคาน้ำมัน Brent (DCOILBRENTEU) | [FRED](https://fred.stlouisfed.org/series/DCOILBRENTEU) / U.S. EIA | Public Domain (ขออ้างอิง) |
| ราคายูเรียและ DAP (รอบที่ 2) | [World Bank Pink Sheet](https://www.worldbank.org/en/research/commodity-markets) | CC BY 4.0 |
| FAO Dairy Price Index (รอบที่ 2) | [FAO](https://www.fao.org/worldfoodsituation/FoodPricesIndex/en/) | ตาม FAO Terms |

ข้อมูลทุกไฟล์ในโฟลเดอร์ `data/raw/` ดาวน์โหลดเมื่อ 5 ต.ค. 2569 พร้อมบันทึก URL, เวลา และ SHA-256 ใน `data/raw/sources.json`

## ข้อจำกัด

- IMI เป็นดัชนีระดับกลุ่มสินค้า คิดเป็นดอลลาร์สหรัฐ ไม่ใช่ต้นทุนจริงของบริษัท
- วันเผยแพร่ IMI ย้อนหลังยืนยันได้เพียง 21 เดือนล่าสุดกับหลักฐานเสริม 2 เดือน และแหล่งข้อมูลทั้งหมดไม่มีประวัติการปรับแก้ย้อนหลัง
- ข้อมูลราว 300 เดือนต่อกลุ่ม และช่วง validation มี 48 เดือน ทำให้การทดสอบนัยสำคัญมีกำลังต่ำ
- ผลช่วง test ถูกเปิดดูแล้ว ผลรอบที่ 2 จึงเป็นผลเชิงสำรวจเท่านั้น
- ผลจากสองกลุ่มสรุปแทนสินค้านำเข้าทุกกลุ่มไม่ได้ และระบบเป็นต้นแบบ ไม่ใช่ระบบใช้งานจริง

## รายชื่อสมาชิกในกลุ่ม

| ลำดับ | ชื่อ-นามสกุล | รหัสนักศึกษา |
|:---:|:---|:---|
| 1 | กวีวัฒน์ สานนท์กุลวัฒน์ | 67070005 |
| 2 | ธนกฤต ประมายะ | 67070058 |
| 3 | ธิติวัฒน์ สมพันธุ์เดชสกุล | 67070080 |
| 4 | ภคพล โพธิวร | 67070124 |
| 5 | ภัทรพล เพ็ชรรัตน์ | 67070127 |
| 6 | ภูวาริช กองจร | 67070140 |
| 7 | ธัชกร กิตติวันฤกษ์ | 67070238 |

