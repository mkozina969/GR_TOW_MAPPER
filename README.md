# Supplier → TOW Mapper (Cloud DB)

Map supplier invoice product codes to internal **TOW** codes using a **persistent PostgreSQL (Neon)** database.  
All inserts/updates survive Streamlit restarts.

---

## 🔧 Setup (local)

```cmd
cd C:\Users\mkozi\OneDrive\Desktop\tow-mapper-cloud
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

## Greece admin app

This duplicate repository also includes `gr_admin_app.py`, a separate Streamlit admin app for Greece colleagues.

It connects to the same Neon database using:

- `DATABASE_URL`
- `ADMIN_PIN`

Run locally:

```cmd
streamlit run gr_admin_app.py
```

Main features:

- Search and edit `crosswalk` mappings
- Add or update single mappings
- Bulk import CSV/Excel mappings
- Export mappings
- Edit vendor names
