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
- Export matched/unmatched results
- Search and edit `crosswalk` mappings
- Add or update single mappings
- Bulk import CSV/Excel mappings
- Export mappings
- Edit vendor names

The database editor is available as the `Admin Database` page in Streamlit navigation.

The Greece app creates these tables on its configured Neon project if they do not exist:

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
