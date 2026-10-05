from __future__ import annotations

import hashlib
import io
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


MASTER_URL = "https://index-api.tpso.go.th/OpenApi/Imex/Month/MasterData"
MONTH_URL = "https://index-api.tpso.go.th/OpenApi/Imex/Month"
FRED_SERIES = {
    "DEXTHUS": {
        "name": "Thai Baht to U.S. Dollar Spot Exchange Rate",
        "owner": "Board of Governors of the Federal Reserve System (US)",
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXTHUS",
        "citation": (
            "Board of Governors of the Federal Reserve System (US), "
            "Thai Baht to U.S. Dollar Spot Exchange Rate [DEXTHUS], "
            "retrieved from FRED, Federal Reserve Bank of St. Louis."
        ),
    },
    "DCOILBRENTEU": {
        "name": "Crude Oil Prices: Brent - Europe",
        "owner": "U.S. Energy Information Administration",
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU",
        "citation": (
            "U.S. Energy Information Administration, Crude Oil Prices: "
            "Brent - Europe [DCOILBRENTEU], retrieved from FRED, "
            "Federal Reserve Bank of St. Louis."
        ),
    },
}


def find_project_root() -> Path:
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "PROJECT_SCOPE.md").exists():
            return candidate
    raise FileNotFoundError(
        "ไม่พบ PROJECT_SCOPE.md ใน current directory หรือ parent directories"
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_session() -> requests.Session:
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        respect_retry_after_header=True,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {"User-Agent": "imi-early-warning/1.0 (academic project)"}
    )
    return session


def enumerate_months(
    start_year: int, start_month: int, end_year: int, end_month: int
) -> list[tuple[int, int]]:
    months = []
    year, month = start_year, start_month
    while (year, month) <= (end_year, end_month):
        months.append((year, month))
        month += 1
        if month == 13:
            year += 1
            month = 1
    return months


def download_imi(
    session: requests.Session, raw_dir: Path, stamp: str
) -> dict:
    master_response = session.get(MASTER_URL, timeout=60)
    master_response.raise_for_status()
    master_data = master_response.json()
    if not isinstance(master_data, list):
        raise TypeError("MasterData ต้องมี root เป็น list")

    master_path = raw_dir / f"imi_master_{stamp}.json"
    master_path.write_text(
        json.dumps(master_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    imi_master = next(item for item in master_data if item["type"] == "IMI")
    periods = imi_master["dataAvailablePeriods"]
    if len(periods) != 1 or periods[0]["periodType"] != "month":
        raise ValueError(f"ช่วงข้อมูล IMI ไม่ตรงตามที่คาด: {periods}")

    period = periods[0]
    year_base = int(period["yearBase"])
    start_year_be = int(period["startYear"])
    start_month = int(period["startPeriod"])
    end_year_be = int(period["endYear"])
    end_month = int(period["endPeriod"])
    commodity_codes = [
        str(item["code"]).zfill(3) for item in imi_master["commodities"]
    ]
    if len(commodity_codes) != len(set(commodity_codes)):
        raise ValueError("พบ commodity code ซ้ำใน MasterData")

    months = enumerate_months(
        start_year_be, start_month, end_year_be, end_month
    )
    print(f"IMI: {len(commodity_codes):,} รหัส, {len(months):,} เดือน")
    print(
        f"ช่วงข้อมูล: {start_year_be}-{start_month:02d} ถึง "
        f"{end_year_be}-{end_month:02d} (พ.ศ.)"
    )

    rows = []
    request_manifest = []
    for sequence, (year_be, month) in enumerate(months, start=1):
        body = {
            "yearBase": year_base,
            "year": year_be,
            "month": month,
            "type": "IMI",
            "commodities": commodity_codes,
        }
        response = session.post(MONTH_URL, json=body, timeout=60)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or not payload:
            raise ValueError(
                f"ผลตอบกลับผิดรูปแบบหรือไม่มีข้อมูล: พ.ศ. {year_be}-{month:02d}"
            )
        if any(
            int(row["year"]) != year_be or int(row["month"]) != month
            for row in payload
        ):
            raise ValueError(
                f"ปีหรือเดือนในผลตอบกลับไม่ตรงกับ request: "
                f"พ.ศ. {year_be}-{month:02d}"
            )

        rows.extend(payload)
        request_manifest.append(
            {"sequence": sequence, "body": body, "row_count": len(payload)}
        )
        if sequence % 40 == 0 or sequence == len(months):
            print(
                f"ดาวน์โหลดแล้ว {sequence:,}/{len(months):,} เดือน; "
                f"สะสม {len(rows):,} แถว"
            )
        if sequence < len(months):
            time.sleep(0.30)

    manifest_path = raw_dir / f"imi_request_manifest_{stamp}.json"
    manifest_path.write_text(
        json.dumps(request_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    frame = pd.DataFrame(rows)
    required_columns = {
        "commodityCode",
        "commodityNameTH",
        "month",
        "year",
        "yearBase",
        "index",
        "change",
        "changeYear",
        "changeAVG",
        "level",
        "createdAt",
    }
    missing_columns = required_columns - set(frame.columns)
    if missing_columns:
        raise ValueError(f"IMI ขาดคอลัมน์: {sorted(missing_columns)}")
    if frame.duplicated(["commodityCode", "year", "month"]).any():
        raise ValueError("พบ IMI ซ้ำตามรหัส-ปี-เดือน")

    requested_months = set(months)
    returned_months = set(
        zip(frame["year"].astype(int), frame["month"].astype(int))
    )
    if returned_months != requested_months:
        raise ValueError("เดือนที่ได้จาก API ไม่ครบตาม MasterData")

    for code in ("000", "100", "318", "402"):
        count = len(
            frame.loc[frame["commodityCode"] == code, ["year", "month"]]
            .drop_duplicates()
        )
        if count != len(months):
            raise ValueError(f"รหัส {code} มีข้อมูล {count}/{len(months)} เดือน")

    data_path = raw_dir / f"imi_monthly_{stamp}.csv"
    frame.to_csv(data_path, index=False, encoding="utf-8")
    print(f"บันทึก IMI {len(frame):,} แถว: {data_path.name}")

    return {
        "master_data": master_data,
        "master_path": master_path,
        "manifest_path": manifest_path,
        "request_manifest": request_manifest,
        "frame": frame,
        "data_path": data_path,
        "year_base": year_base,
        "start_year_be": start_year_be,
        "start_month": start_month,
        "end_year_be": end_year_be,
        "end_month": end_month,
        "commodity_codes": commodity_codes,
        "months": months,
        "downloaded_at_iso": datetime.strptime(
            stamp, "%Y%m%dT%H%M%SZ"
        ).replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def load_unrecorded_imi_snapshot(raw_dir: Path) -> dict | None:
    sources_path = raw_dir / "sources.json"
    document = json.loads(sources_path.read_text(encoding="utf-8"))
    recorded_files = {item["file"] for item in document.get("sources", [])}
    candidates = sorted(raw_dir.glob("imi_monthly_*.csv"), reverse=True)
    for data_path in candidates:
        if data_path.name in recorded_files:
            continue
        stamp = data_path.stem.removeprefix("imi_monthly_")
        master_path = raw_dir / f"imi_master_{stamp}.json"
        manifest_path = raw_dir / f"imi_request_manifest_{stamp}.json"
        if not master_path.exists() or not manifest_path.exists():
            continue

        master_data = json.loads(master_path.read_text(encoding="utf-8"))
        request_manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
        frame = pd.read_csv(data_path, dtype={"commodityCode": "string"})
        frame["commodityCode"] = frame["commodityCode"].str.zfill(3)
        imi_master = next(item for item in master_data if item["type"] == "IMI")
        period = imi_master["dataAvailablePeriods"][0]
        commodity_codes = [
            str(item["code"]).zfill(3) for item in imi_master["commodities"]
        ]
        months = enumerate_months(
            int(period["startYear"]),
            int(period["startPeriod"]),
            int(period["endYear"]),
            int(period["endPeriod"]),
        )
        returned_months = set(
            zip(frame["year"].astype(int), frame["month"].astype(int))
        )
        if returned_months != set(months):
            raise ValueError("snapshot IMI ที่จะ resume มีเดือนไม่ครบ")
        if len(request_manifest) != len(months):
            raise ValueError("request manifest ของ snapshot IMI มีจำนวนเดือนไม่ครบ")
        for code in ("000", "100", "318", "402"):
            count = len(
                frame.loc[
                    frame["commodityCode"] == code, ["year", "month"]
                ].drop_duplicates()
            )
            if count != len(months):
                raise ValueError(f"snapshot IMI รหัส {code} มีข้อมูลไม่ครบ")

        print(f"Resume snapshot IMI ที่ผ่าน validation: {data_path.name}")
        return {
            "master_data": master_data,
            "master_path": master_path,
            "manifest_path": manifest_path,
            "request_manifest": request_manifest,
            "frame": frame,
            "data_path": data_path,
            "year_base": int(period["yearBase"]),
            "start_year_be": int(period["startYear"]),
            "start_month": int(period["startPeriod"]),
            "end_year_be": int(period["endYear"]),
            "end_month": int(period["endPeriod"]),
            "commodity_codes": commodity_codes,
            "months": months,
            "downloaded_at_iso": datetime.strptime(
                stamp, "%Y%m%dT%H%M%SZ"
            ).replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    return None


def download_fred(
    raw_dir: Path,
    stamp: str,
    target_end_ce: pd.Timestamp,
) -> dict[str, dict]:
    results = {}
    for series_id, metadata in FRED_SERIES.items():
        completed = subprocess.run(
            [
                "curl",
                "--fail",
                "--silent",
                "--show-error",
                "--location",
                "--connect-timeout",
                "15",
                "--max-time",
                "60",
                "--retry",
                "3",
                "--retry-all-errors",
                metadata["url"],
            ],
            check=True,
            capture_output=True,
            timeout=75,
        )
        content = completed.stdout
        if not content:
            raise ValueError(f"{series_id}: FRED ส่งไฟล์ว่างกลับมา")
        path = raw_dir / f"{series_id.lower()}_daily_{stamp}.csv"
        path.write_bytes(content)

        frame = pd.read_csv(io.BytesIO(content), na_values=["."])
        expected_columns = ["observation_date", series_id]
        if list(frame.columns) != expected_columns:
            raise ValueError(
                f"{series_id}: schema {list(frame.columns)} ไม่ตรงกับ "
                f"{expected_columns}"
            )
        frame["observation_date"] = pd.to_datetime(
            frame["observation_date"], errors="raise"
        )
        if not frame["observation_date"].is_monotonic_increasing:
            raise ValueError(f"{series_id}: วันที่ไม่ได้เรียงจากเก่าไปใหม่")
        if frame["observation_date"].min() > pd.Timestamp("2000-01-01"):
            raise ValueError(f"{series_id}: ข้อมูลไม่ครอบคลุมต้นปี 2000")
        if frame["observation_date"].max() < target_end_ce:
            raise ValueError(
                f"{series_id}: ข้อมูลไม่ครอบคลุมเดือนสุดท้ายของ IMI"
            )

        results[series_id] = {
            "path": path,
            "frame": frame,
            "non_null_rows": int(frame[series_id].notna().sum()),
        }
        print(
            f"{series_id}: {len(frame):,} แถว, "
            f"{frame['observation_date'].min().date()} ถึง "
            f"{frame['observation_date'].max().date()}, "
            f"ค่าว่าง {frame[series_id].isna().sum():,} แถว"
        )
    return results


def update_sources(
    raw_dir: Path,
    stamp: str,
    downloaded_at_iso: str,
    imi: dict,
    fred: dict[str, dict],
) -> None:
    sources_path = raw_dir / "sources.json"
    document = json.loads(sources_path.read_text(encoding="utf-8"))
    sources = document.setdefault("sources", [])

    new_sources = [
        {
            "source_id": f"imi-master-{stamp}",
            "name": "IMI MasterData",
            "owner": "สำนักงานนโยบายและยุทธศาสตร์การค้า กระทรวงพาณิชย์",
            "publisher": "สำนักงานนโยบายและยุทธศาสตร์การค้า กระทรวงพาณิชย์",
            "url": MASTER_URL,
            "method": "GET",
            "downloaded_at_utc": imi["downloaded_at_iso"],
            "row_count": len(imi["master_data"]),
            "data_range": None,
            "file": imi["master_path"].name,
            "sha256": sha256(imi["master_path"]),
            "license": "Open Data Common",
            "citation": (
                "สำนักงานนโยบายและยุทธศาสตร์การค้า กระทรวงพาณิชย์. "
                "ข้อมูลดัชนีราคาสินค้านำเข้าของประเทศ. "
                "ศูนย์กลางข้อมูลเปิดภาครัฐ."
            ),
        },
        {
            "source_id": f"imi-monthly-{stamp}",
            "name": "ดัชนีราคาสินค้านำเข้ารายเดือน (IMI)",
            "owner": "สำนักงานนโยบายและยุทธศาสตร์การค้า กระทรวงพาณิชย์",
            "publisher": "สำนักงานนโยบายและยุทธศาสตร์การค้า กระทรวงพาณิชย์",
            "url": MONTH_URL,
            "method": "POST",
            "request_body_template": {
                "yearBase": imi["year_base"],
                "year": "<พ.ศ.>",
                "month": "<1-12>",
                "type": "IMI",
                "commodities": imi["commodity_codes"],
            },
            "request_bodies_file": imi["manifest_path"].name,
            "request_bodies_sha256": sha256(imi["manifest_path"]),
            "request_count": len(imi["request_manifest"]),
            "failed_request_count": 0,
            "downloaded_at_utc": imi["downloaded_at_iso"],
            "row_count": len(imi["frame"]),
            "data_range": {
                "start": (
                    f"{imi['start_year_be'] - 543:04d}-"
                    f"{imi['start_month']:02d}"
                ),
                "end": (
                    f"{imi['end_year_be'] - 543:04d}-"
                    f"{imi['end_month']:02d}"
                ),
                "calendar_in_file": "Buddhist Era",
            },
            "file": imi["data_path"].name,
            "sha256": sha256(imi["data_path"]),
            "license": "Open Data Common",
            "citation": (
                "สำนักงานนโยบายและยุทธศาสตร์การค้า กระทรวงพาณิชย์. "
                "ข้อมูลดัชนีราคาสินค้านำเข้าของประเทศ. "
                "ศูนย์กลางข้อมูลเปิดภาครัฐ."
            ),
        },
    ]

    for series_id, metadata in FRED_SERIES.items():
        result = fred[series_id]
        frame = result["frame"]
        new_sources.append(
            {
                "source_id": f"{series_id.lower()}-{stamp}",
                "name": metadata["name"],
                "owner": metadata["owner"],
                "publisher": "FRED, Federal Reserve Bank of St. Louis",
                "url": metadata["url"],
                "method": "GET",
                "downloaded_at_utc": downloaded_at_iso,
                "row_count": len(frame),
                "non_null_row_count": result["non_null_rows"],
                "data_range": {
                    "start": str(frame["observation_date"].min().date()),
                    "end": str(frame["observation_date"].max().date()),
                },
                "file": result["path"].name,
                "sha256": sha256(result["path"]),
                "license": "Public Domain: Citation Requested",
                "citation": metadata["citation"],
            }
        )

    existing_ids = {item["source_id"] for item in sources}
    new_ids = {item["source_id"] for item in new_sources}
    if existing_ids & new_ids:
        raise ValueError("source_id ซ้ำใน sources.json")
    sources.extend(new_sources)
    document["last_updated_at_utc"] = downloaded_at_iso
    sources_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    expected_files = {item["file"] for item in new_sources}
    recorded_files = {item["file"] for item in document["sources"]}
    if not expected_files <= recorded_files:
        raise ValueError("sources.json บันทึกชื่อไฟล์ไม่ครบ")
    if not all((raw_dir / name).exists() for name in expected_files):
        raise FileNotFoundError("ไม่พบไฟล์ raw บางไฟล์")


def append_process_log(
    root: Path,
    downloaded_at: datetime,
    imi: dict,
    fred: dict[str, dict],
) -> None:
    fx = fred["DEXTHUS"]["frame"]
    brent = fred["DCOILBRENTEU"]["frame"]
    entry = f"""
## [{downloaded_at.date().isoformat()}] ขั้นตอน: 01 Data Acquisition
**สิ่งที่ทำ:** ดาวน์โหลด IMI ทุกรหัสตาม MasterData จำนวน {len(imi['months']):,} เดือน ดาวน์โหลด DEXTHUS และ DCOILBRENTEU จาก FRED ตรวจ schema และบันทึก metadata พร้อม SHA-256

**ผลที่ได้:** IMI จำนวน {len(imi['frame']):,} แถว ครอบคลุม {imi['start_year_be'] - 543:04d}-{imi['start_month']:02d} ถึง {imi['end_year_be'] - 543:04d}-{imi['end_month']:02d} จาก {len(imi['commodity_codes']):,} รหัสและ {len(imi['request_manifest']):,} requests โดยไม่มี request ล้มเหลว; DEXTHUS จำนวน {len(fx):,} แถว ({fred['DEXTHUS']['non_null_rows']:,} ค่าที่ไม่ว่าง) ช่วง {fx['observation_date'].min().date()} ถึง {fx['observation_date'].max().date()}; DCOILBRENTEU จำนวน {len(brent):,} แถว ({fred['DCOILBRENTEU']['non_null_rows']:,} ค่าที่ไม่ว่าง) ช่วง {brent['observation_date'].min().date()} ถึง {brent['observation_date'].max().date()}

**สิ่งที่พบ / ปัญหา:** การดาวน์โหลด FRED ด้วย Python requests เกิด read timeout ซ้ำ ขณะที่ URL เดียวกันดาวน์โหลดด้วย curl สำเร็จ จึงเปลี่ยน transport ของ FRED เป็น curl พร้อมกำหนด timeout และ retry ข้อมูล FRED มีค่าว่างในวันหยุดหรือวันที่ไม่มี observation โดยเก็บไว้ตามต้นฉบับและไม่แทนด้วยศูนย์

**การตัดสินใจและเหตุผล:** เก็บผลตอบกลับ IMI เป็นตาราง CSV และเก็บ request body ทั้งหมดใน manifest แยกต่างหากเพื่อให้ตรวจสอบย้อนกลับได้ ข้อมูล raw ทุกไฟล์ใช้ timestamp UTC ในชื่อไฟล์เพื่อป้องกันการเขียนทับ

**ขั้นต่อไป:** ดำเนินการ 02 Data Understanding เพื่อตรวจค่าว่าง ความต่อเนื่อง ความผันผวน และ lag correlation
"""
    with (root / "logs" / "process_log.md").open("a", encoding="utf-8") as handle:
        handle.write(entry)


def main() -> None:
    root = find_project_root()
    raw_dir = root / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    downloaded_at = datetime.now(timezone.utc)
    stamp = downloaded_at.strftime("%Y%m%dT%H%M%SZ")
    downloaded_at_iso = downloaded_at.isoformat().replace("+00:00", "Z")
    print(f"Project root: {root}")
    print(f"Download timestamp (UTC): {downloaded_at_iso}")

    session = build_session()
    imi = load_unrecorded_imi_snapshot(raw_dir)
    if imi is None:
        imi = download_imi(session, raw_dir, stamp)
    else:
        stamp = imi["data_path"].stem.removeprefix("imi_monthly_")
    target_end_ce = pd.Timestamp(
        year=imi["end_year_be"] - 543,
        month=imi["end_month"],
        day=1,
    )
    fred = download_fred(raw_dir, stamp, target_end_ce)
    update_sources(raw_dir, stamp, downloaded_at_iso, imi, fred)
    append_process_log(root, downloaded_at, imi, fred)

    summary = {
        "imi_codes": len(imi["commodity_codes"]),
        "imi_requested_months": len(imi["months"]),
        "imi_failed_requests": 0,
        "imi_rows": len(imi["frame"]),
        "imi_range_ce": (
            f"{imi['start_year_be'] - 543:04d}-{imi['start_month']:02d} ถึง "
            f"{imi['end_year_be'] - 543:04d}-{imi['end_month']:02d}"
        ),
        "dexthus_rows": len(fred["DEXTHUS"]["frame"]),
        "dexthus_non_null_rows": fred["DEXTHUS"]["non_null_rows"],
        "brent_rows": len(fred["DCOILBRENTEU"]["frame"]),
        "brent_non_null_rows": fred["DCOILBRENTEU"]["non_null_rows"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(
        "CHECKPOINT PASSED: ข้อมูลทั้งสามแหล่งครอบคลุมช่วงที่กำหนด "
        "และ sources.json ครบถ้วน"
    )


if __name__ == "__main__":
    main()
