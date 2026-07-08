import argparse
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


ap = argparse.ArgumentParser()
ap.add_argument("--db", required=True, help="SQLAlchemy URL for the source Neon database")
ap.add_argument("--out-dir", default="exports", help="folder where CSV exports will be saved")
ap.add_argument("--crosswalk", default="crosswalk.csv", help="crosswalk export file name")
ap.add_argument("--vendors", default="vendors.csv", help="vendors export file name")
ap.add_argument("--skip-vendors", action="store_true", help="export only crosswalk")
args = ap.parse_args()

out_dir = Path(args.out_dir)
out_dir.mkdir(parents=True, exist_ok=True)

engine = create_engine(args.db, pool_pre_ping=True)

with engine.connect() as conn:
    crosswalk = pd.read_sql(
        text(
            """
            SELECT
                COALESCE(NULLIF(TRIM(vendor_id), ''), 'GLOBAL') AS vendor_id,
                TRIM(supplier_id) AS supplier_id,
                TRIM(tow_code) AS tow_code
            FROM crosswalk
            ORDER BY vendor_id, supplier_id
            """
        ),
        conn,
    )

    crosswalk_path = out_dir / args.crosswalk
    crosswalk.to_csv(crosswalk_path, index=False, encoding="utf-8-sig")
    print(f"Exported {len(crosswalk):,} crosswalk rows to {crosswalk_path}")

    if not args.skip_vendors:
        try:
            vendors = pd.read_sql(
                text(
                    """
                    SELECT
                        TRIM(vendor_id) AS vendor_id,
                        TRIM(vendor_name) AS vendor_name
                    FROM vendors
                    ORDER BY vendor_id
                    """
                ),
                conn,
            )
        except Exception as exc:
            print(f"Skipped vendors export: {exc}")
        else:
            vendors_path = out_dir / args.vendors
            vendors.to_csv(vendors_path, index=False, encoding="utf-8-sig")
            print(f"Exported {len(vendors):,} vendor rows to {vendors_path}")
