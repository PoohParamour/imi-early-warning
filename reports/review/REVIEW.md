# รายงานตรวจทาน IMI Early Warning

วันที่ตรวจ: 5 ตุลาคม 2026 · ตรวจตาม snapshot ปัจจุบัน โดยคงการออกแบบและผลหลักที่เปิด test แล้ว

## 1. สรุป

พบประเด็น 7 ข้อ: แก้แล้ว 5 ข้อ และเสนอเท่านั้น 2 ข้อ ตามขอบเขตที่ทีมอนุญาต
ประเด็นร้ายแรงที่สุดคือใช้ validation labels ที่ยังไม่พร้อม ณ test origins ช่วงต้นในการเลือก alpha/โมเดล แม้การคัด training rows แต่ละรอบถูกต้อง
การแก้ที่ดำเนินการแล้วไม่เปลี่ยนค่าทำนาย MAE, DM p-value หรือข้อสรุปหลักว่าไม่พบความได้เปรียบอย่างมีนัยสำคัญหลัง Holm; เปลี่ยน F1 ที่คำนวณผิดและข้อความระยะเตือน
ผลกระทบของการแก้เวลา model selection ต่อข้อสรุปยัง **[ยังไม่ยืนยัน]** เพราะต้องเปลี่ยนวิธีทดลองที่ทีมสั่งให้เสนอเท่านั้น จึงยังรับรองว่าเป็น real-time backtest ถูกต้องทั้งช่วงไม่ได้
รัน notebook ทั้ง 7 ไฟล์ใน kernel ใหม่ครบตามลำดับแล้ว checkpoint เดิมผ่านทั้งหมด แต่ checkpoint เดิมไม่ครอบคลุมข้อผิดพลาดในชั้น model selection ที่ตรวจพบครั้งนี้

## 2. ตารางปัญหา

เลขบรรทัดด้านล่างอ้างอิงไฟล์หลังแก้และรันซ้ำ ข้อที่แก้แล้วจึงชี้ไปยังโค้ดฉบับแก้ ส่วนหลักฐานก่อนแก้อธิบายในคอลัมน์หลักฐานและตารางเปรียบเทียบผลรัน

| ระดับ | ไฟล์:บรรทัด | ปัญหา | หลักฐาน | ผลกระทบต่อตัวเลขในรายงาน | สถานะ |
|---|---|---|---|---|---|
| วิกฤต (ผลผิดด้านการจำลองเวลา) | [NB04:837](/Users/pattarapol/itkmitl/imi-early-warning/notebooks/04_modeling.ipynb:837), [NB05:186](/Users/pattarapol/itkmitl/imi-early-warning/notebooks/05_evaluation.ipynb:186), [NB05b:439](/Users/pattarapol/itkmitl/imi-early-warning/notebooks/05b_iteration2.ipynb:439) | เลือก alpha และ series จาก validation ครบถึง t=2018-12 แล้วนำไปใช้กับ test origins ที่ validation target บางส่วนยังไม่เผยแพร่ เป็น leakage ในชั้นการเลือกโมเดล | h=3: target ของ validation แถวสุดท้ายพร้อม 2019-05-15 แต่ test สอง origins แรกออก 2019-03-15 และ 2019-04-15; h=2–6 มี 1–5 origins แรกต่อ horizon รวม 45 จาก 1,320 origins ของสามกลุ่ม ดู [selection_availability.csv](/Users/pattarapol/itkmitl/imi-early-warning/reports/review/selection_availability.csv:2) | กระทบความถูกต้องของการอ้างผลเสมือนใช้งานจริงช่วงต้น; ค่า MAE/p หลังแก้วิธีเลือกยังไม่ยืนยัน ไม่ได้เปลี่ยนผลหลัก | เสนอเท่านั้น |
| สำคัญ | [NB05:1129](/Users/pattarapol/itkmitl/imi-early-warning/notebooks/05_evaluation.ipynb:1129), [NB05b:969](/Users/pattarapol/itkmitl/imi-early-warning/notebooks/05b_iteration2.ipynb:969) | F1 เดิมเป็น NaN เมื่อไม่มีการเตือน แม้มีเหตุการณ์จริงและ FN > 0 | นม h=3 มี 29 เหตุการณ์ ไม่เตือนเลย: TP=0, FP=0, FN=29 ดังนั้น F1=2TP/(2TP+FP+FN)=0; เดิม NaN 7 แถวใน 05 และ 2 แถวใน 05b | F1 ทั้ง 9 แถวเป็น 0; precision ยังคงไม่กำหนดเมื่อไม่มีการเตือน; MAE/DM ไม่เปลี่ยน | แก้แล้ว |
| สำคัญ | [NB06:824](/Users/pattarapol/itkmitl/imi-early-warning/notebooks/06_deployment.ipynb:824), [Scope:21](/Users/pattarapol/itkmitl/imi-early-warning/PROJECT_SCOPE.md:21), [Scope:59](/Users/pattarapol/itkmitl/imi-early-warning/PROJECT_SCOPE.md:59) | ข้อความเดิม “ล่วงหน้า 2–5 เดือน” และ “ระยะเตือนเท่ากับ h” ใช้ h จากเดือนฐาน t แทนระยะจากวันออก forecast | origin 2026-09-15; h=2 เป้าหมายเดือน ก.ย. ซึ่งเริ่มไปแล้ว 14 วัน; h=3 เริ่ม ต.ค. อีก 16 วัน; h=5 เริ่ม ธ.ค. อีก 77 วัน ตาม [ค่าพยากรณ์ล่าสุด](/Users/pattarapol/itkmitl/imi-early-warning/logs/metrics/06_latest_forecasts.csv:2) | แก้ความหมายเป็น nowcast ถึงเดือนเป้าหมายอีก 3 เดือนจากเดือนที่ออก forecast สำหรับ h=2–5; ค่าพยากรณ์ทั้ง 10 ค่าเดิม | แก้แล้ว |
| สำคัญ | [Scope:42](/Users/pattarapol/itkmitl/imi-early-warning/PROJECT_SCOPE.md:42), [NB02:1342](/Users/pattarapol/itkmitl/imi-early-warning/notebooks/02_data_understanding.ipynb:1342), [NB06:822](/Users/pattarapol/itkmitl/imi-early-warning/notebooks/06_deployment.ipynb:822) | การนำ median lag ของ CPI มาบวกเป็นระยะเตือนที่ผู้ใช้ได้รับจริงยังเกินสิ่งที่การวิเคราะห์นี้ทดสอบ การถดถอยความสัมพันธ์ย้อนหลังไม่ได้ประเมินระบบพยากรณ์ราคาที่ SME จ่ายแบบ end-to-end | CPI cumulative=0.088446, 95% CI=[−0.000195, 0.177086], p=0.050501; median lag=4 เป็น point estimate โดยยังไม่มีช่วงความไม่แน่นอนของ lag; joint test มีนัยสำคัญ p=6.12×10⁻⁶ จึงไม่ใช่ข้อสรุปว่าไม่มีความสัมพันธ์ ดู [ผล pass-through](/Users/pattarapol/itkmitl/imi-early-warning/logs/metrics/02_passthrough_summary.csv:2) | ไม่เปลี่ยน regression หรือเลข 4 เดือน แต่ยังรับรองไม่ได้ว่าเพิ่มระยะเตือนราคาจริงได้ 4 เดือน | เสนอเท่านั้น |
| เล็กน้อย | [NB05:186](/Users/pattarapol/itkmitl/imi-early-warning/notebooks/05_evaluation.ipynb:186), [Scope:362](/Users/pattarapol/itkmitl/imi-early-warning/PROJECT_SCOPE.md:362) | คำว่า “ดีที่สุดจาก validation” ใน Scope ไม่ระบุว่าโค้ดตัด No-change ออกจากผู้สมัคร | สำหรับนม No-change มี validation MAE ต่ำกว่าผู้สมัครที่เลือกทุก h=2–6; ที่ h=3 เท่ากับ 0.989088 เทียบ 1.142309 | แก้คำอธิบายให้ตรงการเลือกจริง ไม่ได้รวม No-change กลับเข้า candidate set และไม่เปลี่ยนโมเดล | แก้แล้ว |
| เล็กน้อย | [NB05b:931](/Users/pattarapol/itkmitl/imi-early-warning/notebooks/05b_iteration2.ipynb:931), [NB05b:954](/Users/pattarapol/itkmitl/imi-early-warning/notebooks/05b_iteration2.ipynb:954) | NB05b มี Bartlett fallback แต่ไม่ได้บันทึกว่าแต่ละการทดสอบใช้วิธีใดตามกติกา audit ใน Scope | เพิ่ม `variance_method_vs_ridge3` และ `variance_method_vs_no_change`; ผลจริงทั้ง 20 การเปรียบเทียบใช้ acf; ทดสอบข้อมูลจำลองที่ ACF variance ติดลบแล้วใช้ Bartlett | เพิ่ม 2 คอลัมน์ใน 05b_results; ตัวเลขเดิมทุกคอลัมน์คงเดิม | แก้แล้ว |
| เล็กน้อย | [Scope:382](/Users/pattarapol/itkmitl/imi-early-warning/PROJECT_SCOPE.md:382), [Scope:441](/Users/pattarapol/itkmitl/imi-early-warning/PROJECT_SCOPE.md:441), [Scope:442](/Users/pattarapol/itkmitl/imi-early-warning/PROJECT_SCOPE.md:442) | เอกสารบางจุดยังระบุ 2 horizons ทั้งที่ใช้ 5, เงื่อนไข No-change เขียน threshold ≤ 0 ทั้งที่โค้ดใช้ ŷ > threshold, และ checkpoint ไม่แยก target ของ training กับแถวที่ทำนาย | ตรวจผลจริงมี h=2,3,4,5,6; เมื่อ threshold=0 และ ŷ=0 ตามกฎ strict > ต้องไม่เตือน | แก้เป็น 5 horizons และ threshold < 0 พร้อมแยกคำอธิบาย availability; ไม่มีการเปลี่ยนกติกาหรือตัวเลข | แก้แล้ว |

## 3. สิ่งที่แก้แล้วและผลก่อน–หลัง

| รายการ | ก่อน | หลัง |
|---|---:|---:|
| F1 นม h=3 ของ `ridge/3-cutoff24` | NaN | 0 |
| F1 ที่ไม่มีการเตือนแต่มีเหตุการณ์จริงทั้งหมด | NaN จำนวน 9 แถว | 0 จำนวน 9 แถว |
| F1 ปุ๋ย h=3 ของ `ridge/3` | 0.448276 | 0.448276 |
| MAE ปุ๋ย h=3 ของโมเดลที่เลือก | 6.367293 | 6.367293 |
| MAE นม h=3 ของโมเดลที่เลือก | 2.199321 | 2.199321 |
| Holm p ของ C2 นม h=3 | 0.379489 | 0.379489 |
| ค่าพยากรณ์ล่าสุด h=3 ปุ๋ย / นม | −5.507746 / −0.635251 | −5.507746 / −0.635251 |
| คอลัมน์บันทึก variance method ใน 05b_results | ไม่มี | เพิ่ม 2 คอลัมน์ |

สูตร F1 ใช้ค่าจาก confusion matrix โดยตรงตาม [นิยาม F1 ของ scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.f1_score.html) การมี FN หรือ FP ทำให้ตัวส่วนมีค่าบวก แม้ precision อาจไม่กำหนดเมื่อไม่มี predicted positives กรณีไม่มีทั้งเหตุการณ์และการเตือนยังคงรายงาน NaN

แก้ source โดยตรงใน notebook 02, 05, 05b, 06 และแก้ PROJECT_SCOPE.md จากนั้นรันใหม่ทั้งลำดับ **01 → 02 → 03 → 04 → 05 → 05b → 06** โดยใช้ `.venv/bin/jupyter nbconvert --to notebook --execute --inplace` พร้อม timeout 1,200 วินาทีต่อ cell แต่ละ notebook ใช้ kernel ใหม่ ไม่มี cell error และ checkpoint เดิมผ่านทั้งหมด

ผลเทียบตาราง metrics เดิม 31 ไฟล์: **28 ไฟล์ตรงกันทุก byte** อีก 3 ไฟล์เปลี่ยนเฉพาะ F1 และคอลัมน์ variance method ตามรายการข้างต้น ดู [rerun_comparison.csv](/Users/pattarapol/itkmitl/imi-early-warning/reports/review/rerun_comparison.csv:1)

- ตาราง processed 4,560 แถวและ latest_features ตรงเดิม
- 04_predictions จำนวน 28,560 แถว, alpha selection, ARIMA order, 05b_predictions และ 06_latest_forecasts จำนวน 10 แถวตรงเดิม
- SHA-256 ของ modeling_table: `c97d79ab0c1afade35d0f1bcf999d51b4c0b58c774048c58fc4ba6257640af05`
- SHA-256 ของ 04_predictions: `7fd851a34cf5c05fbc013e0d5d89df1bc2d8c840aead90a02d9296d062b9a881`
- 03_processed_manifest และ 04_run_manifest อ้าง hash เชื่อมกันถูกต้อง
- raw ทั้ง 14 ไฟล์รวม sources.json ไม่เปลี่ยนแม้แต่ byte เดียว; DOWNLOAD flags ทั้ง 4 ตัวเป็น False
- log เก่าคงอยู่ครบแบบ byte-for-byte prefix และเพิ่มรายการตรวจทานท้ายไฟล์

ผลนี้ยืนยันว่าแก้ข้อผิดพลาดที่อนุญาตโดยไม่ปรับผลหลัก แต่การผ่าน checkpoint เดิมไม่ลบล้างปัญหา selection-time availability ในข้อ 1

## 4. ข้อเสนอปรับปรุงที่ไม่ได้แก้

1. **เวลาเลือก alpha/โมเดล — กระทบวิธีประเมินผลหลัก แต่การทดลองแก้ไขหลังเห็น test ต้องแยกเป็นเชิงสำรวจ:** ก่อน test origin แรก ควรใช้เฉพาะ validation labels ที่เผยแพร่แล้ว หรือเลื่อนจุดเริ่มประเมินจน validation labels ครบ ต้องให้ทีมเลือก protocol และบันทึกก่อนรัน ไม่ควรเลือกทางแก้จากผลที่ให้ MAE ดีที่สุด คงผลหลักเดิมไว้เพื่อเปรียบเทียบอย่างโปร่งใส
2. **pass-through — เชิงสำรวจ:** แนะนำให้เรียก 4 เดือนว่า “ค่าประมาณ lag ของความสัมพันธ์ในข้อมูลก่อน 2019” และแยกจากระยะเตือนที่ยืนยันแล้ว หากต้องการอ้างการใช้งานจริง ควรประเมินค่าพยากรณ์ราคาในประเทศหรือราคา supplier บนข้อมูลช่วงใหม่ พร้อมความไม่แน่นอนของ lag ไม่เพิ่มโมเดลหรือเปลี่ยน regression ในการตรวจครั้งนี้
3. **ความสะดวกในการรันกับ snapshot ใหม่ — ไม่ใช่การปรับผลหลัก:** NB03 ยังมี assert จำนวน release=21, IMI=960 และ test h=3=89/h=2=90 รวมถึงวันที่ log แบบ literal 2026-10-05 ปัจจุบันตรง snapshot และรันผ่าน แนะนำแยก snapshot-specific expectations ออกจากกฎตรวจความต่อเนื่อง และเก็บวันที่รันจริงเมื่อทำรอบใหม่ หลักฐาน: [NB03:638](/Users/pattarapol/itkmitl/imi-early-warning/notebooks/03_data_preparation.ipynb:638), [NB03:648](/Users/pattarapol/itkmitl/imi-early-warning/notebooks/03_data_preparation.ipynb:648), [NB04:1255](/Users/pattarapol/itkmitl/imi-early-warning/notebooks/04_modeling.ipynb:1255)
4. **สภาพแวดล้อมและ replay — ไม่เปลี่ยนผลหลัก:** requirements ทั้ง 13 รายการตรงกับเวอร์ชันที่ติดตั้งและ pip check ผ่าน แต่ NumPy และ nbconvert ถูกติดตั้งผ่าน dependency โดยยังไม่ตรึงโดยตรง แนะนำจัดทำ lock ของ environment หากต้องการทำซ้ำบนเครื่องใหม่ และให้ replay mode หยุดพร้อมข้อความเมื่อ snapshot ขาด แทน branch `DOWNLOAD_DOMESTIC or not existing` / `DOWNLOAD_COMMODITY or not existing` ที่อาจดาวน์โหลดแม้ flag=False ไม่ได้ทดสอบการติดตั้งใหม่ทั้ง environment **[ยังไม่ยืนยัน]**; ครั้งนี้ทดสอบ kernel ใหม่ใน `.venv` ปัจจุบัน หลักฐาน: [requirements.txt](/Users/pattarapol/itkmitl/imi-early-warning/requirements.txt:1), [NB01:1568](/Users/pattarapol/itkmitl/imi-early-warning/notebooks/01_data_acquisition.ipynb:1568), [NB01:1784](/Users/pattarapol/itkmitl/imi-early-warning/notebooks/01_data_acquisition.ipynb:1784)

ข้อ 3–4 เป็นข้อเสนอรองรับการใช้งานรอบใหม่ ไม่ได้นับเป็นความผิดพลาดของตัวเลขใน snapshot ปัจจุบัน และไม่ได้ดาวน์โหลดหรือเปลี่ยน dependency ระหว่างตรวจ

## 5. สิ่งที่ตรวจแล้วไม่พบปัญหา

### การจัดเวลาและข้อมูล

- ตรวจ `training_rows` ของ NB04/05b และ `train_rows` ของ NB06 กับทั้ง 2,040 origins: ได้ชุดแถวตาม target month ≤ t และ target availability ≤ origin ถูกต้อง ความต่าง threshold สูงสุด 1.78×10⁻¹⁵; DA majority มาจาก training ของแต่ละ originจริง ประเด็น selection-time labels เป็นคนละชั้นและแยกไว้ในตารางปัญหา
- คำนวณ target และ seasonal naive ซ้ำจาก raw IMI ทุกแถว ความต่างสูงสุดต่ำกว่า 9.7×10⁻¹⁴; seasonal naive ใช้เดือนไม่เกิน t
- ARIMA ใช้ order จากข้อมูลถึง 2014-12 แล้ว fit coefficients ด้วย `log_imi[:t]`; ไม่มี external feature เข้า ARIMA
- ทวน lead t+1 แบบเต็มเดือนและ cutoff24 ทุกแถวจาก FRED โดยตรง ความต่างต่ำกว่า 9.1×10⁻¹⁴ และ observation ของ lead อยู่ใน t+1; cutoff24 ไม่มีวันที่เกิน 24
- แปลง พ.ศ. −543 ถูกต้อง FRED ข้ามค่าว่างโดยไม่แทนศูนย์; Pink Sheet strip ช่องว่างท้าย `Urea `; FAO อ่านหัวตาราง `Date,` และเลือกเดือนถูกต้อง ทั้ง NB01 และ NB05b รันผ่าน
- CPI เริ่ม 2001-12 จึงใช้การเปลี่ยนแปลงครั้งแรก 2002-01 และได้ n=204 ก่อน 2019; PPI ได้ n=47 และ 25 parameters ตามที่ทีมทราบแล้ว ไม่เปลี่ยนการตีความว่า PPI เป็นหลักฐานอ่อน
- Pass-through ใช้ HAC maxlags=12 และข้อมูลไม่เกิน 2018-12 สูตร cumulative sum และ median lag ตรงนิยามใน Scope การอ้างประโยชน์เชิงพยากรณ์เป็นข้อเสนอแยกต่างหาก
- Alpha grid ใช้ validation ในการหาค่าต่ำสุดจริง ไม่พบกรณี `np.isclose` เลือกค่า MAE สูงกว่าค่าต่ำสุดในผลชุดนี้; ไม่พบการเลือก alpha จาก test MAE

### สถิติ

- รันฟังก์ชัน `dm.test` จาก [ซอร์สทางการของแพ็กเกจ forecast](https://github.com/robjhyndman/forecast/blob/master/R/DM2.R) ด้วย **R 4.5.1** โดยไม่ต้องติดตั้งแพ็กเกจ forecast ทั้งชุด เปรียบเทียบ absolute-error loss, autocovariance หารด้วย n ที่ lag 0…h−1, HLN k และ Student-t(n−1) แบบสองด้าน
- ผล NB05 จำนวน 27 คู่ตรงกับ R: ความต่างสถิติสูงสุด 2.61×10⁻¹⁵ และ p-value สูงสุด 2.00×10⁻¹⁵; NB05b อีก 20 คู่ต่างไม่เกิน 5.56×10⁻¹⁶
- กรณี ACF variance ไม่บวก Scope กำหนดให้เปลี่ยนเป็น Bartlett โดยคง h จึงเทียบกับ R โดยเลือก `varestimator='bartlett'` อย่างชัดเจน ไม่ใช่ fallback default ของ R ที่อาจเปลี่ยนเป็น h=1 ทดสอบข้อมูลสลับ 2,0 เทียบ 1 ที่ h=2 ได้ Bartlett, statistic=0, p=1 ตรงกัน
- Holm ใช้ 6 การทดสอบของกลุ่ม 318/402 จริง ไม่รวมกลุ่ม sanity check; เทียบ `p.adjust(..., 'holm')` ใน R ต่างไม่เกิน 2.23×10⁻¹⁶
- DA baseline คำนวณจาก majority ของ training โดยใช้ y>0 เป็นขึ้นตรงกัน; กลุ่มปุ๋ย h=3 ได้ DA 0.651685 เทียบ baseline 0.404494 ตามรายงาน
- ทดสอบ alert edge cases รวม 8 กรณีใน NB05/05b: ไม่เตือนแต่มีเหตุการณ์, เตือนผิดทั้งหมด, ทายถูกทั้งหมด และไม่มีทั้งเหตุการณ์กับการเตือน

### Dashboard และการรันซ้ำ

- origin 2026-09-15 ≤ as-of 2026-10-05 ใช้ t=2026-07; IMI 2026-08 ยังไม่ถูกนำเข้า forecast ตาม cutoff ที่กำหนด
- ฟังก์ชัน dashboard คำนวณ origin สุดท้ายของ test ซ้ำได้เท่ากับ 04 ทั้ง 10 คู่กลุ่ม×h; ค่าพยากรณ์ล่าสุดทุกแถวตรงก่อนตรวจ
- เปิด **headless Google Chrome แบบ offline** ด้วย file URL ทั้ง `#g318` และ `#g402` ที่ความกว้าง 390 และ 1440px ทั้ง 4 กรณีแสดงกลุ่มถูกต้อง ไม่มี JavaScript exception และไม่มี overflow ระดับหน้า (`scrollWidth=viewport width`) ตารางบนมือถือเลื่อนแนวนอนได้จริง
- ตรวจค่าที่ render ในตารางเทียบ 06_latest_forecasts/05b_results ครบ 120 assertions และตรวจข้อมูลกราฟ IMI จริง จุดพยากรณ์ แถบ ±MAE ค่า driver และ coefficients เทียบข้อมูลต้นทาง/การ fit ซ้ำ ผ่านทั้งหมด
- Plotly ฝังในไฟล์; Google Fonts โหลดไม่ได้ใน offline แต่ fallback เป็นฟอนต์ระบบและกราฟยังแสดงได้ ไม่พบ functional dependency ที่ต้องใช้อินเทอร์เน็ตในการดู dashboard
- ข้อความ ±MAE ระบุชัดว่าไม่ใช่ช่วงความเชื่อมั่น ผลรอบที่ 2 และเกณฑ์ผ่านตาม horizon มีป้ายเชิงสำรวจ

หลักฐานประกอบ: [review_evidence.json](/Users/pattarapol/itkmitl/imi-early-warning/reports/review/review_evidence.json), [DM เทียบ R](/Users/pattarapol/itkmitl/imi-early-warning/reports/review/dm_reference.csv), [ผล Chrome](/Users/pattarapol/itkmitl/imi-early-warning/reports/review/browser_results.json), [ภาพปุ๋ย 390px](/Users/pattarapol/itkmitl/imi-early-warning/reports/review/dashboard-318-390.png), [ภาพนม 390px](/Users/pattarapol/itkmitl/imi-early-warning/reports/review/dashboard-402-390.png)

คำสั่งตรวจซ้ำโดยไม่เปลี่ยนผลหลัก:

```sh
.venv/bin/python scripts/review_checks.py
Rscript scripts/review_dm.R
.venv/bin/python scripts/review_dashboard.py
```

สคริปต์ R อ่านซอร์สอ้างอิงจาก GitHub; สคริปต์ Chrome ใช้ Google Chrome ที่ติดตั้งใน macOS และ websocket-client ซึ่งมีอยู่ใน environment นี้ การเปรียบเทียบก่อน–หลังครั้งนี้ใช้สำเนาก่อนตรวจที่ `/tmp/imi-review.XVlM77` ผ่าน `--before` และบันทึกผลถาวรไว้ใน rerun_comparison.csv แล้ว การรัน `review_checks.py` โดยไม่ส่ง `--before` จะตรวจข้อมูลปัจจุบันแต่ไม่เขียนทับตารางเปรียบเทียบก่อน–หลัง
