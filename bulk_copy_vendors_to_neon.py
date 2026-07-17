import argparse
from pathlib import Path
import csv
from io import StringIO

import psycopg2


ap = argparse.ArgumentParser()
ap.add_argument("--csv", required=True, help="path to vendors.csv")
ap.add_argument("--db", required=True, help="postgresql://... (use ?sslmode=require)")
ap.add_argument("--rebuild", action="store_true", help="drop & recreate vendors table before load")
ap.add_argument("--sep", default="auto", choices=["auto", ",", ";"], help="CSV delimiter")
args = ap.parse_args()

csv_path = Path(args.csv)
if not csv_path.exists():
    raise SystemExit(f"CSV not found: {csv_path}")


def sniff_sep(p: Path) -> str:
    if args.sep in (",", ";"):
        return args.sep
    with open(p, "r", encoding="utf-8-sig", errors="ignore") as f:
        for line in f:
            if line.strip():
                return ";" if line.count(";") >= line.count(",") else ","
    return ","


sep = sniff_sep(csv_path)
print(f"Using delimiter: '{sep}'")

conn = psycopg2.connect(args.db)
conn.autocommit = False
cur = conn.cursor()

try:
    if args.rebuild:
        cur.execute("DROP TABLE IF EXISTS vendors")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vendors (
            vendor_id TEXT PRIMARY KEY,
            vendor_name TEXT
        )
        """
    )

    cur.execute("DROP TABLE IF EXISTS vendors_stage")
    cur.execute(
        """
        CREATE TABLE vendors_stage (
            vendor_id TEXT,
            vendor_name TEXT
        )
        """
    )

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=sep)
        header_map = {"vendor_id": None, "vendor_name": None}

        for name in reader.fieldnames or []:
            low = (name or "").strip().lower()
            if low in ("vendor_id", "vendor", "vendor_code"):
                header_map["vendor_id"] = name
            elif low in ("vendor_name", "name"):
                header_map["vendor_name"] = name

        if not header_map["vendor_id"]:
            raise SystemExit(f"CSV needs vendor_id/vendor/vendor_code. Found: {reader.fieldnames}")

        buf = StringIO()
        writer = csv.writer(buf, lineterminator="\n", delimiter=sep)
        for row in reader:
            vendor_id = (row.get(header_map["vendor_id"], "") or "").strip()
            vendor_name = (row.get(header_map["vendor_name"], "") or "").strip() if header_map["vendor_name"] else ""
            writer.writerow([vendor_id, vendor_name])

        buf.seek(0)
        cur.copy_expert(
            f"COPY vendors_stage (vendor_id, vendor_name) FROM STDIN WITH (FORMAT csv, DELIMITER '{sep}')",
            buf,
        )

    cur.execute(
        """
        INSERT INTO vendors (vendor_id, vendor_name)
        SELECT vendor_id, vendor_name
        FROM (
            SELECT DISTINCT ON (vendor_id_norm)
                vendor_id_norm AS vendor_id,
                trim(vendor_name) AS vendor_name,
                stage_id
            FROM (
                SELECT
                    ctid AS stage_id,
                    upper(trim(vendor_id)) AS vendor_id_norm,
                    vendor_name
                FROM vendors_stage
                WHERE trim(COALESCE(vendor_id, '')) <> ''
            ) normalized
            ORDER BY vendor_id_norm, stage_id DESC
        ) deduped
        ON CONFLICT (vendor_id)
        DO UPDATE SET vendor_name = EXCLUDED.vendor_name
        """
    )

    cur.execute("DROP TABLE vendors_stage")
    conn.commit()
    print("Vendor bulk load completed successfully.")
except Exception:
    conn.rollback()
    raise
finally:
    cur.close()
    conn.close()
