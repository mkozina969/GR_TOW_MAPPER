import argparse
from pathlib import Path
import csv
import psycopg2
import psycopg2.extras

ap = argparse.ArgumentParser()
ap.add_argument("--csv", required=True, help="path to crosswalk.csv")
ap.add_argument("--db", required=True, help="postgresql://... (use ?sslmode=require)")
ap.add_argument("--rebuild", action="store_true", help="drop & recreate base table before load")
ap.add_argument("--sep", default="auto", choices=["auto", ",", ";"], help="CSV delimiter")
args = ap.parse_args()

csv_path = Path(args.csv)
if not csv_path.exists():
    raise SystemExit(f"CSV not found: {csv_path}")

def sniff_sep(p: Path) -> str:
    if args.sep in (",",";"):
        return args.sep
    # auto: sniff the first non-empty line
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
        cur.execute("DROP TABLE IF EXISTS crosswalk")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS crosswalk (
            tow_code    TEXT NOT NULL,
            supplier_id TEXT NOT NULL,
            vendor_id   TEXT
        )
    """)
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_crosswalk_vendor_supplier
        ON crosswalk (vendor_id, supplier_id)
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_crosswalk_supplier ON crosswalk (supplier_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_crosswalk_tow_code ON crosswalk (tow_code)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_crosswalk_vendor ON crosswalk (vendor_id)")

    # staging
    cur.execute("DROP TABLE IF EXISTS crosswalk_stage")
    cur.execute("""
        CREATE TABLE crosswalk_stage (
            tow_code    TEXT,
            supplier_id TEXT,
            vendor_id   TEXT
        )
    """)

    # COPY into staging
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        # If header names might differ (e.g., 'tow' instead of 'tow_code'),
        # map them with DictReader to a uniform order, then copy from a temp file-like.
        reader = csv.DictReader(f, delimiter=sep)
        required = {"tow_code","supplier_id","vendor_id"}
        # accept alternates
        header_map = {
            "tow_code": None,
            "supplier_id": None,
            "vendor_id": None
        }
        for name in reader.fieldnames or []:
            low = (name or "").strip().lower()
            if low in ("tow_code","tow"):
                header_map["tow_code"] = name
            elif low in ("supplier_id","supplier_code"):
                header_map["supplier_id"] = name
            elif low in ("vendor_id",):
                header_map["vendor_id"] = name

        if not header_map["tow_code"] or not header_map["supplier_id"]:
            raise SystemExit(f"CSV needs tow/tow_code and supplier_id/supplier_code. Found: {reader.fieldnames}")

        # Stream rows to COPY via an in-memory CSV stream in canonical column order
        from io import StringIO
        buf = StringIO()
        w = csv.writer(buf, lineterminator="\n", delimiter=sep)
        for row in reader:
            tow = (row.get(header_map["tow_code"], "") or "").strip()
            sup = (row.get(header_map["supplier_id"], "") or "").strip()
            ven = (row.get(header_map["vendor_id"], "") or "").strip() if header_map["vendor_id"] else ""
            w.writerow([tow, sup, ven])

        buf.seek(0)
        cur.copy_expert(
            f"COPY crosswalk_stage (tow_code, supplier_id, vendor_id) FROM STDIN WITH (FORMAT csv, DELIMITER '{sep}')",
            buf
        )

    # Normalize + deduplicate + upsert.
    # If the CSV contains the same vendor_id + supplier_id more than once,
    # PostgreSQL cannot update that target row twice in one INSERT statement.
    # DISTINCT ON keeps the last copied row for each mapping key.
    cur.execute("""
        INSERT INTO crosswalk (tow_code, supplier_id, vendor_id)
SELECT tow_code, supplier_id, vendor_id
FROM (
  SELECT DISTINCT ON (vendor_id_norm, supplier_id_norm)
    trim(tow_code) AS tow_code,
    supplier_id_norm AS supplier_id,
    vendor_id_norm AS vendor_id,
    stage_id
  FROM (
    SELECT
      ctid AS stage_id,
      tow_code,
      upper(trim(supplier_id)) AS supplier_id_norm,
      COALESCE(NULLIF(upper(trim(vendor_id)), ''), 'GLOBAL') AS vendor_id_norm
    FROM crosswalk_stage
    WHERE trim(COALESCE(supplier_id, '')) <> ''
      AND trim(COALESCE(tow_code, '')) <> ''
  ) normalized
  ORDER BY vendor_id_norm, supplier_id_norm, stage_id DESC
) deduped
ON CONFLICT (vendor_id, supplier_id)
DO UPDATE SET tow_code = EXCLUDED.tow_code;

    """)

    # cleanup
    cur.execute("DROP TABLE crosswalk_stage")

    conn.commit()
    print("Bulk load completed successfully.")
except Exception as e:
    conn.rollback()
    raise
finally:
    cur.close()
    conn.close()
