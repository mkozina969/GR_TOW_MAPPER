# Supplier to TOW Mapper

Map supplier invoice product codes to internal TOW codes using a persistent PostgreSQL database on Neon.

## Original mapper app

Run:

```cmd
streamlit run streamlit_app.py
```

Secrets:

```toml
DATABASE_URL = "your_original_tow_mapper_neon_connection_string"
ADMIN_PIN = "your_admin_pin"
```

## Greece admin app

This repository also includes `gr_admin_app.py`, a separate Streamlit admin app for Greece colleagues.

Run:

```cmd
streamlit run gr_admin_app.py
```

Use a separate Neon branch for this app. Do not point it at the original Tow Mapper branch.

Secrets:

```toml
GR_DATABASE_URL = "your_gr_neon_branch_connection_string"
ADMIN_PIN = "your_admin_pin"
```

Main features:

- Search and edit `crosswalk` mappings
- Add or update single mappings
- Bulk import CSV/Excel mappings
- Export mappings
- Edit vendor names

The Greece app creates these tables on its configured Neon branch if they do not exist:

- `crosswalk`
- `vendors`
