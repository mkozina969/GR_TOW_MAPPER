import argparse

import psycopg2


ap = argparse.ArgumentParser()
ap.add_argument("--db", required=True, help="postgresql://... (use ?sslmode=require)")
args = ap.parse_args()

conn = psycopg2.connect(args.db)
conn.autocommit = False
cur = conn.cursor()

try:
    cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vendors (
            vendor_id TEXT PRIMARY KEY,
            vendor_name TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS crosswalk (
            tow_code TEXT NOT NULL,
            supplier_id TEXT NOT NULL,
            vendor_id TEXT NOT NULL DEFAULT 'GLOBAL'
        )
        """
    )

    cur.execute(
        """
        UPDATE crosswalk
        SET vendor_id = 'GLOBAL'
        WHERE vendor_id IS NULL OR trim(vendor_id) = ''
        """
    )

    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_crosswalk_vendor_supplier
        ON crosswalk (vendor_id, supplier_id)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_crosswalk_supplier
        ON crosswalk (supplier_id)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_crosswalk_tow_code
        ON crosswalk (tow_code)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_crosswalk_vendor
        ON crosswalk (vendor_id)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_vendors_vendor_name
        ON vendors (vendor_name)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_crosswalk_supplier_trgm
        ON crosswalk USING gin (supplier_id gin_trgm_ops)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_crosswalk_tow_code_trgm
        ON crosswalk USING gin (tow_code gin_trgm_ops)
        """
    )

    conn.commit()
    print("Neon indexes and constraints are ready.")
except Exception:
    conn.rollback()
    raise
finally:
    cur.close()
    conn.close()
