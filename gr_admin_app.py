from __future__ import annotations

import os
from io import BytesIO
from typing import Dict, Iterable

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


st.set_page_config(page_title="GR TOW Mapper Admin", layout="wide")


@st.cache_resource(show_spinner=False)
def get_engine() -> Engine:
    db_url = os.getenv("DATABASE_URL") or st.secrets.get("DATABASE_URL", "")
    if not db_url:
        st.error("DATABASE_URL is not configured in Streamlit secrets or environment.")
        st.stop()
    return create_engine(db_url, pool_pre_ping=True)


engine = get_engine()


def read_sql(query: str, params: dict | None = None) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params or {})


def execute_sql(query: str, params: dict | list[dict] | None = None) -> None:
    with engine.begin() as conn:
        if params is None:
            conn.execute(text(query))
        else:
            conn.execute(text(query), params)


def normalize_vendor(value: object) -> str:
    vendor = str(value or "").strip().upper()
    return vendor or "GLOBAL"


def normalize_text(value: object) -> str:
    return str(value or "").strip()


def ensure_schema() -> None:
    execute_sql(
        """
        CREATE TABLE IF NOT EXISTS crosswalk (
            tow_code TEXT NOT NULL,
            supplier_id TEXT NOT NULL,
            vendor_id TEXT NOT NULL DEFAULT 'GLOBAL'
        )
        """
    )
    execute_sql(
        """
        UPDATE crosswalk
        SET vendor_id = 'GLOBAL'
        WHERE vendor_id IS NULL OR trim(vendor_id) = ''
        """
    )
    execute_sql(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_crosswalk_vendor_supplier
        ON crosswalk (vendor_id, supplier_id)
        """
    )
    execute_sql(
        """
        CREATE TABLE IF NOT EXISTS vendors (
            vendor_id TEXT PRIMARY KEY,
            vendor_name TEXT
        )
        """
    )


def to_excel_bytes(sheets: Dict[str, pd.DataFrame]) -> bytes:
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, index=False, sheet_name=name[:31] or "Sheet")
    return bio.getvalue()


def upsert_crosswalk(rows: Iterable[dict]) -> int:
    cleaned: list[dict] = []
    for row in rows:
        vendor_id = normalize_vendor(row.get("vendor_id"))
        supplier_id = normalize_text(row.get("supplier_id")).upper()
        tow_code = normalize_text(row.get("tow_code"))
        if supplier_id and tow_code:
            cleaned.append(
                {
                    "vendor_id": vendor_id,
                    "supplier_id": supplier_id,
                    "tow_code": tow_code,
                }
            )

    if not cleaned:
        return 0

    execute_sql(
        """
        INSERT INTO crosswalk (vendor_id, supplier_id, tow_code)
        VALUES (:vendor_id, :supplier_id, :tow_code)
        ON CONFLICT (vendor_id, supplier_id)
        DO UPDATE SET tow_code = EXCLUDED.tow_code
        """,
        cleaned,
    )
    st.cache_data.clear()
    return len(cleaned)


def delete_crosswalk(rows: Iterable[dict]) -> int:
    cleaned: list[dict] = []
    for row in rows:
        vendor_id = normalize_vendor(row.get("vendor_id"))
        supplier_id = normalize_text(row.get("supplier_id")).upper()
        if supplier_id:
            cleaned.append({"vendor_id": vendor_id, "supplier_id": supplier_id})

    if not cleaned:
        return 0

    execute_sql(
        """
        DELETE FROM crosswalk
        WHERE vendor_id = :vendor_id AND supplier_id = :supplier_id
        """,
        cleaned,
    )
    st.cache_data.clear()
    return len(cleaned)


@st.cache_data(show_spinner=False)
def table_counts() -> dict:
    counts = read_sql(
        """
        SELECT
            (SELECT COUNT(*) FROM crosswalk) AS crosswalk_rows,
            (SELECT COUNT(*) FROM vendors) AS vendor_rows
        """
    )
    return counts.iloc[0].to_dict()


@st.cache_data(show_spinner=False)
def load_crosswalk(vendor: str, supplier: str, tow: str, limit: int) -> pd.DataFrame:
    clauses: list[str] = []
    params: dict = {"limit": limit}

    if vendor:
        clauses.append("vendor_id ILIKE :vendor")
        params["vendor"] = f"%{vendor.strip()}%"
    if supplier:
        clauses.append("supplier_id ILIKE :supplier")
        params["supplier"] = f"%{supplier.strip()}%"
    if tow:
        clauses.append("tow_code ILIKE :tow")
        params["tow"] = f"%{tow.strip()}%"

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return read_sql(
        f"""
        SELECT vendor_id, supplier_id, tow_code
        FROM crosswalk
        {where}
        ORDER BY vendor_id, supplier_id
        LIMIT :limit
        """,
        params,
    )


@st.cache_data(show_spinner=False)
def load_vendors() -> pd.DataFrame:
    return read_sql(
        """
        SELECT vendor_id, vendor_name
        FROM vendors
        ORDER BY vendor_id
        """
    )


def require_admin_pin() -> None:
    expected_pin = str(os.getenv("ADMIN_PIN") or st.secrets.get("ADMIN_PIN", "")).strip()
    if not expected_pin:
        st.warning("ADMIN_PIN is not configured. The app is locked.")
        st.stop()

    if "gr_admin_unlocked" not in st.session_state:
        st.session_state["gr_admin_unlocked"] = False

    if st.session_state["gr_admin_unlocked"]:
        return

    st.title("GR TOW Mapper Admin")
    pin = st.text_input("Admin PIN", type="password")
    if st.button("Unlock", type="primary"):
        st.session_state["gr_admin_unlocked"] = str(pin).strip() == expected_pin
        if not st.session_state["gr_admin_unlocked"]:
            st.error("Wrong PIN.")
        else:
            st.rerun()
    st.stop()


ensure_schema()
require_admin_pin()

st.title("GR TOW Mapper Admin")
st.caption("Edit Neon database mappings for Greece without touching the invoice mapping workflow.")

counts = table_counts()
metric_cols = st.columns(3)
metric_cols[0].metric("Mappings", f"{int(counts['crosswalk_rows']):,}")
metric_cols[1].metric("Vendors", f"{int(counts['vendor_rows']):,}")
metric_cols[2].metric("Database", "Connected")

tab_map, tab_import, tab_vendors = st.tabs(["Mappings", "Import / Export", "Vendors"])

with tab_map:
    st.subheader("Search and edit mappings")
    f1, f2, f3, f4 = st.columns([1.2, 1.4, 1.2, 0.8])
    with f1:
        vendor_filter = st.text_input("Vendor filter", value="")
    with f2:
        supplier_filter = st.text_input("Supplier code filter", value="")
    with f3:
        tow_filter = st.text_input("TOW code filter", value="")
    with f4:
        row_limit = st.number_input("Limit", min_value=50, max_value=5000, value=500, step=50)

    df = load_crosswalk(vendor_filter, supplier_filter, tow_filter, int(row_limit))
    edit_df = df.copy()
    edit_df.insert(0, "delete", False)

    edited = st.data_editor(
        edit_df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "delete": st.column_config.CheckboxColumn("Delete"),
            "vendor_id": st.column_config.TextColumn("vendor_id", help="Blank is saved as GLOBAL."),
            "supplier_id": st.column_config.TextColumn("supplier_id"),
            "tow_code": st.column_config.TextColumn("tow_code"),
        },
        key="crosswalk_editor",
    )

    c_save, c_delete, c_download = st.columns([1, 1, 2])
    with c_save:
        if st.button("Save edited rows", type="primary"):
            saved = upsert_crosswalk(edited.drop(columns=["delete"]).to_dict("records"))
            st.success(f"Saved {saved:,} rows.")
            st.rerun()
    with c_delete:
        if st.button("Delete checked rows"):
            checked = edited[edited["delete"] == True]  # noqa: E712
            deleted = delete_crosswalk(checked.to_dict("records"))
            st.warning(f"Deleted {deleted:,} rows.")
            st.rerun()
    with c_download:
        st.download_button(
            "Download search results Excel",
            data=to_excel_bytes({"crosswalk": df}),
            file_name="gr_tow_mapper_crosswalk.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    st.subheader("Add one mapping")
    with st.form("single_mapping"):
        a1, a2, a3 = st.columns(3)
        vendor_id = a1.text_input("vendor_id", value="GLOBAL")
        supplier_id = a2.text_input("supplier_id")
        tow_code = a3.text_input("tow_code")
        if st.form_submit_button("Add / update", type="primary"):
            saved = upsert_crosswalk(
                [{"vendor_id": vendor_id, "supplier_id": supplier_id, "tow_code": tow_code}]
            )
            if saved:
                st.success("Mapping saved.")
                st.rerun()
            else:
                st.error("supplier_id and tow_code are required.")

with tab_import:
    st.subheader("Bulk import")
    st.caption("CSV or Excel must contain supplier_id and tow_code. vendor_id is optional and defaults to GLOBAL.")
    upload = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx", "xls"])

    if upload is not None:
        suffix = os.path.splitext(upload.name)[1].lower()
        if suffix == ".csv":
            import_df = pd.read_csv(upload, dtype=str).fillna("")
        else:
            import_df = pd.read_excel(upload, dtype=str).fillna("")

        import_df.columns = [str(c).strip() for c in import_df.columns]
        st.dataframe(import_df.head(200), use_container_width=True)

        columns_lower = {c.lower(): c for c in import_df.columns}
        supplier_col = columns_lower.get("supplier_id") or columns_lower.get("supplier_code")
        tow_col = columns_lower.get("tow_code") or columns_lower.get("tow")
        vendor_col = columns_lower.get("vendor_id")

        if not supplier_col or not tow_col:
            st.error("The file needs supplier_id/supplier_code and tow_code/tow columns.")
        elif st.button("Apply import to Neon", type="primary"):
            rows = pd.DataFrame(
                {
                    "vendor_id": import_df[vendor_col] if vendor_col else "GLOBAL",
                    "supplier_id": import_df[supplier_col],
                    "tow_code": import_df[tow_col],
                }
            )
            saved = upsert_crosswalk(rows.to_dict("records"))
            st.success(f"Imported {saved:,} mappings.")
            st.rerun()

    st.subheader("Full export")
    full_df = read_sql("SELECT vendor_id, supplier_id, tow_code FROM crosswalk ORDER BY vendor_id, supplier_id")
    st.download_button(
        "Download all mappings CSV",
        data=full_df.to_csv(index=False).encode("utf-8"),
        file_name="crosswalk_export.csv",
        mime="text/csv",
    )

with tab_vendors:
    st.subheader("Vendor names")
    vendors_df = load_vendors()
    edited_vendors = st.data_editor(
        vendors_df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="vendors_editor",
    )
    if st.button("Save vendors", type="primary"):
        rows = []
        for row in edited_vendors.to_dict("records"):
            vendor_id = normalize_vendor(row.get("vendor_id"))
            vendor_name = normalize_text(row.get("vendor_name"))
            if vendor_id:
                rows.append({"vendor_id": vendor_id, "vendor_name": vendor_name})
        if rows:
            execute_sql(
                """
                INSERT INTO vendors (vendor_id, vendor_name)
                VALUES (:vendor_id, :vendor_name)
                ON CONFLICT (vendor_id)
                DO UPDATE SET vendor_name = EXCLUDED.vendor_name
                """,
                rows,
            )
            st.cache_data.clear()
            st.success(f"Saved {len(rows):,} vendors.")
            st.rerun()
        else:
            st.info("Nothing to save.")
