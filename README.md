# Supplier to TOW Mapper

Map supplier invoice product codes to internal TOW codes using a persistent PostgreSQL database on Neon.

## Greece mapper app

Run:

```cmd
streamlit run streamlit_app.py
```

This is the default Streamlit Cloud entry point and opens the GR invoice mapper.

Use a separate Neon project for this app. Do not point it at the original Tow Mapper database.

Secrets:

```toml
GR_DATABASE_URL = "your_gr_neon_project_connection_string"
ADMIN_PIN = "your_admin_pin"
```

Main features:

- Upload supplier invoices and map supplier codes to TOW codes
- Download standard or custom Excel, Pallets PRN (20/30/50), Regular PRN (10/15/15), and Navision Portal CSV
- Set filenames for custom Excel, PRN, and Portal CSV downloads
- Apply vendor-specific packaging conversions and review the conversion audit
- Preview and import mapping and conversion batches from XLSX or CSV in the PIN-protected mapper admin
- Search and edit `crosswalk` mappings
- Add or update single mappings
- Bulk import CSV/Excel mappings
Use the PIN-protected Admin section on the main mapper page to manage mappings and conversion rules.

Exports download directly to the browser. There is no Download Center or Neon Object Storage configuration.

Before release, initialize the conversion table on the **GR Neon database** by running [the additive migration](migrations/001_item_uom_conversion.sql). Alternatively, after deploying, unlock the mapper's Admin section and click **Initialize UoM table** before running any invoice mapping. The migration creates an empty rules table and does not change existing vendors or mappings. See [packaging conversion](UOM_SETUP.md) and [bulk imports](BULK_IMPORT.md).

The GR mapper uses these existing tables:

- `crosswalk`
- `vendors`

## Original mapper app

The original duplicated mapper is preserved as `tow_mapper_app.py`.

Run locally only if needed:

```cmd
streamlit run tow_mapper_app.py
```

Secrets:

```toml
DATABASE_URL = "your_original_tow_mapper_neon_connection_string"
ADMIN_PIN = "your_admin_pin"
```

## Copy data from original Neon to GR Neon

Export from the original Tow Mapper Neon database:

```cmd
py export_neon_to_csv.py --db "postgresql+psycopg2://USER:PASSWORD@HOST/neondb?sslmode=require" --out-dir exports
```

This creates:

- `exports\crosswalk.csv`
- `exports\vendors.csv` if the original database has a `vendors` table

Import `crosswalk.csv` into the GR Neon database:

```cmd
py migrate_csv_to_db.py --csv exports\crosswalk.csv --db "postgresql+psycopg2://USER:PASSWORD@GR_HOST/neondb?sslmode=require" --chunk 500
```

You can also upload `exports\crosswalk.csv` in the GR Streamlit app under `Import / Export`.

Import vendors into the GR Neon database:

```cmd
py bulk_copy_vendors_to_neon.py --csv "..\vendors.csv" --db "postgresql://USER:PASSWORD@GR_HOST/neondb?sslmode=require" --rebuild --sep auto
```

Ensure indexes/constraints exist in GR Neon:

```cmd
py ensure_neon_indexes.py --db "postgresql://USER:PASSWORD@GR_HOST/neondb?sslmode=require"
```

This also creates trigram indexes for fast contains search on `supplier_id` and `tow_code`.

