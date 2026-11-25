"""
dataVault (Cloud-Ready + Auto-Setup + Backup Download + Data Quality + Gold Download)
CSV files -> Bronze (raw) -> Silver (clean) -> Gold (final)
"""
import io
import os
from datetime import datetime

import pandas as pd
import psycopg2
import streamlit as st

st.set_page_config(
    page_title="dataVault | Modern Data Warehouse",
    page_icon="🗄️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------
# 1. SETTINGS: database details & backup folder
# ---------------------------------------------------------------
DB = dict(host="localhost", dbname="datavault", user="postgres", password="admin", port="5432")

HISTORY_DIR = "upload_history"
os.makedirs(HISTORY_DIR, exist_ok=True)

FILES = {
    "cust_info.csv": "crm_cust_info",
    "prd_info.csv": "crm_prd_info",
    "sales_details.csv": "crm_sales_details",
    "cust_az12.csv": "erp_cust_az12",
    "loc_a101.csv": "erp_loc_a101",
    "px_cat_g1v2.csv": "erp_px_cat_g1v2",
}

# ---------------------------------------------------------------
# 2. THEMES
# ---------------------------------------------------------------
THEMES = {
    "Clean Light (Deep Blue)": {
        "bg": "#F4F6FA", "surface": "#FFFFFF", "sidebar": "#FFFFFF",
        "border": "#DDE3EC", "border_strong": "#C3CCD9",
        "text": "#0F172A", "muted": "#5B6B7F",
        "primary": "#1D4ED8", "primary_text": "#1D4ED8", "primary_soft": "#E8EFFD",
        "cta": "#C2410C", "cta_hover": "#9A3412", "cta_text": "#FFFFFF",
        "shadow": "0 1px 3px rgba(15,23,42,.08)",
        "ok": "#15803D", "ok_bg": "#E7F6EC",
    },
    "Clean Light (Green)": {
        "bg": "#F4F7F5", "surface": "#FFFFFF", "sidebar": "#FFFFFF",
        "border": "#DCE5DF", "border_strong": "#C2D0C7",
        "text": "#10231A", "muted": "#566B5E",
        "primary": "#15803D", "primary_text": "#15803D", "primary_soft": "#E6F4EA",
        "cta": "#C2410C", "cta_hover": "#9A3412", "cta_text": "#FFFFFF",
        "shadow": "0 1px 3px rgba(16,35,26,.08)",
        "ok": "#15803D", "ok_bg": "#E6F4EA",
    },
    "Slate Dark (Indigo)": {
        "bg": "#0F172A", "surface": "#172036", "sidebar": "#0B1220",
        "border": "#2A3A55", "border_strong": "#3B4D6B",
        "text": "#E2E8F0", "muted": "#94A3B8",
        "primary": "#4338CA", "primary_text": "#A5B4FC", "primary_soft": "#1E2A4A",
        "cta": "#F59E0B", "cta_hover": "#FBBF24", "cta_text": "#1B1405",
        "shadow": "0 1px 3px rgba(0,0,0,.4)",
        "ok": "#4ADE80", "ok_bg": "rgba(74,222,128,.12)",
    },
}

try:
    _is_dark = st.context.theme.type == "dark"
except Exception:
    _is_dark = False
THEME_NAMES = list(THEMES)
DEFAULT_THEME = "Slate Dark (Indigo)" if _is_dark else "Clean Light (Deep Blue)"

with st.sidebar:
    st.markdown("## dataVault")
    st.caption("Medallion Data Warehouse")
    st.divider()
    theme_name = st.selectbox("Theme", THEME_NAMES, index=THEME_NAMES.index(DEFAULT_THEME))

T = THEMES[theme_name]

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root {{
  --bg:{T['bg']}; --surface:{T['surface']}; --sidebar:{T['sidebar']};
  --border:{T['border']}; --border_strong:{T['border_strong']};
  --text:{T['text']}; --muted:{T['muted']};
  --primary:{T['primary']}; --primary-text:{T['primary_text']}; --primary-soft:{T['primary_soft']};
  --cta:{T['cta']}; --cta-hover:{T['cta_hover']}; --cta-text:{T['cta_text']};
  --shadow:{T['shadow']}; --ok:{T['ok']}; --ok-bg:{T['ok_bg']};
}}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<style>
html, body, .stApp { font-family:'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; }
.stApp { background:var(--bg); color:var(--text); }
.block-container { padding-top:2rem; max-width:1400px; }
#MainMenu, footer { visibility:hidden; }
header[data-testid="stHeader"] { background:transparent; }
hr { border-color:var(--border) !important; }

h1, h2, h3, h4, h5, h6,
.stApp [data-testid="stMarkdown"] p, .stApp [data-testid="stMarkdown"] li,
.stApp [data-testid="stWidgetLabel"] p { color:var(--text); }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color:var(--muted) !important; }

section[data-testid="stSidebar"] { background:var(--sidebar); border-right:1px solid var(--border); }

.hero { background:var(--primary); padding:22px 28px; border-radius:12px; margin-bottom:22px; box-shadow:var(--shadow); }
.hero p.hero-title { font-size:1.8rem; font-weight:700; margin:0; color:#FFFFFF !important; letter-spacing:-0.01em; }
.hero p.hero-sub { font-size:0.98rem; margin:6px 0 0 0; color:rgba(255,255,255,.88) !important; }

div[data-testid="stMetric"] { background:var(--surface); border:1px solid var(--border); border-radius:12px;
  padding:16px 20px; box-shadow:var(--shadow); }
div[data-testid="stMetric"] label, div[data-testid="stMetricLabel"] p { color:var(--muted) !important; font-weight:500 !important; }
div[data-testid="stMetricValue"] { color:var(--primary-text) !important; font-weight:700 !important; font-size:1.8rem !important; }

button[kind="primary"], button[data-testid="stBaseButton-primary"] {
  background:var(--cta) !important; border:1px solid var(--cta) !important; border-radius:10px !important;
  font-weight:600 !important; box-shadow:var(--shadow) !important; }
button[kind="primary"] p, button[data-testid="stBaseButton-primary"] p { color:var(--cta-text) !important; }
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {
  background:var(--cta-hover) !important; border-color:var(--cta-hover) !important; }

button[kind="secondary"], button[data-testid="stBaseButton-secondary"] {
  background:var(--surface) !important; border:1px solid var(--border_strong) !important;
  border-radius:10px !important; font-weight:600 !important; }
button[kind="secondary"] p, button[data-testid="stBaseButton-secondary"] p { color:var(--primary-text) !important; }
button[kind="secondary"]:hover, button[data-testid="stBaseButton-secondary"]:hover { border-color:var(--primary-text) !important; }
button:focus-visible { outline:2px solid var(--primary-text) !important; outline-offset:2px; }

div[data-baseweb="tab-list"] { gap:4px; border-bottom:1px solid var(--border); }
button[data-baseweb="tab"] { background:transparent; }
button[data-baseweb="tab"] p { color:var(--muted); font-weight:600; font-size:1rem; }
button[data-baseweb="tab"][aria-selected="true"] p { color:var(--primary-text); }
div[data-baseweb="tab-highlight"] { background:var(--primary-text) !important; height:3px !important; }
div[data-baseweb="tab-border"] { background:transparent !important; }

div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, .stDateInput input, .stTextInput input {
  background:var(--surface) !important; border-color:var(--border) !important; }
div[data-baseweb="select"] *, .stDateInput input, .stTextInput input { color:var(--text); }
div[data-baseweb="popover"] ul, div[data-baseweb="popover"] > div { background:var(--surface) !important; }
li[role="option"] { color:var(--text) !important; }
li[role="option"]:hover, li[aria-selected="true"] { background:var(--primary-soft) !important; }

div[data-testid="stFileUploaderDropzone"] { background:var(--surface) !important; border:1.5px dashed var(--border_strong);
  border-radius:12px; }
div[data-testid="stFileUploaderDropzone"]:hover { border-color:var(--primary-text); }
div[data-testid="stFileUploaderDropzone"] span, div[data-testid="stFileUploaderDropzone"] small { color:var(--muted) !important; }
div[data-testid="stFileUploaderFile"], div[data-testid="stFileUploaderFile"] * { color:var(--text) !important; }

div[data-testid="stVerticalBlockBorderWrapper"] { background:var(--surface); border-color:var(--border) !important; border-radius:12px; }
div[data-testid="stDataFrame"] { border:1px solid var(--border); border-radius:10px; overflow:hidden; }
div[data-testid="stAlert"], div[data-testid="stAlert"] p { color:var(--text) !important; }

.status-pill { display:inline-block; padding:5px 12px; border-radius:999px; background:var(--ok-bg);
  border:1px solid var(--ok); color:var(--ok); font-size:0.82rem; font-weight:600; }
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------
# 3. DATABASE HELPERS & AUTO-SETUP
# ---------------------------------------------------------------
def connect():
    try:
        if "DATABASE_URL" in st.secrets:
            return psycopg2.connect(st.secrets["DATABASE_URL"])
    except Exception:
        pass
    return psycopg2.connect(**DB)


@st.cache_resource
def init_db():
    """Creates Bronze, Silver, Gold schemas, tables, procedure & views safely if they don't exist."""
    setup_sql = """
    CREATE SCHEMA IF NOT EXISTS bronze;
    CREATE SCHEMA IF NOT EXISTS silver;
    CREATE SCHEMA IF NOT EXISTS gold;

    CREATE TABLE IF NOT EXISTS bronze.crm_cust_info (
        cst_id INT, cst_key VARCHAR(50), cst_firstname VARCHAR(50),
        cst_lastname VARCHAR(50), cst_marital_status VARCHAR(50),
        cst_gndr VARCHAR(50), cst_create_date DATE
    );
    CREATE TABLE IF NOT EXISTS bronze.crm_prd_info (
        prd_id INT, prd_key VARCHAR(50), prd_nm VARCHAR(100),
        prd_cost INT, prd_line VARCHAR(50),
        prd_start_dt TIMESTAMP, prd_end_dt TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS bronze.crm_sales_details (
        sls_ord_num VARCHAR(50), sls_prd_key VARCHAR(50), sls_cust_id INT,
        sls_order_dt INT, sls_ship_dt INT, sls_due_dt INT,
        sls_sales INT, sls_quantity INT, sls_price INT
    );
    CREATE TABLE IF NOT EXISTS bronze.erp_cust_az12 (
        cid VARCHAR(50), bdate DATE, gen VARCHAR(50)
    );
    CREATE TABLE IF NOT EXISTS bronze.erp_loc_a101 (
        cid VARCHAR(50), cntry VARCHAR(50)
    );
    CREATE TABLE IF NOT EXISTS bronze.erp_px_cat_g1v2 (
        id VARCHAR(50), cat VARCHAR(50), subcat VARCHAR(50), maintenance VARCHAR(50)
    );
    CREATE TABLE IF NOT EXISTS bronze.upload_history (
        upload_id SERIAL PRIMARY KEY, file_name VARCHAR(255), target_table VARCHAR(100),
        rows_loaded INT, saved_file_path TEXT, status VARCHAR(100),
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS silver.crm_cust_info (
        cst_id INT, cst_key VARCHAR(50), cst_firstname VARCHAR(50),
        cst_lastname VARCHAR(50), cst_marital_status VARCHAR(50),
        cst_gndr VARCHAR(50), cst_create_date DATE,
        dwh_create_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS silver.crm_prd_info (
        prd_id INT, cat_id VARCHAR(50), prd_key VARCHAR(50), prd_nm VARCHAR(100),
        prd_cost INT, prd_line VARCHAR(50), prd_start_dt DATE, prd_end_dt DATE,
        dwh_create_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS silver.crm_sales_details (
        sls_ord_num VARCHAR(50), sls_prd_key VARCHAR(50), sls_cust_id INT,
        sls_order_dt DATE, sls_ship_dt DATE, sls_due_dt DATE,
        sls_sales INT, sls_quantity INT, sls_price INT,
        dwh_create_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS silver.erp_cust_az12 (
        cid VARCHAR(50), bdate DATE, gen VARCHAR(50),
        dwh_create_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS silver.erp_loc_a101 (
        cid VARCHAR(50), cntry VARCHAR(50),
        dwh_create_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS silver.erp_px_cat_g1v2 (
        id VARCHAR(50), cat VARCHAR(50), subcat VARCHAR(50), maintenance VARCHAR(50),
        dwh_create_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE OR REPLACE PROCEDURE silver.load_silver()
    LANGUAGE plpgsql
    AS $$
    BEGIN
        TRUNCATE TABLE silver.crm_cust_info;
        INSERT INTO silver.crm_cust_info (
            cst_id, cst_key, cst_firstname, cst_lastname,
            cst_marital_status, cst_gndr, cst_create_date
        )
        SELECT
            cst_id, cst_key, TRIM(cst_firstname), TRIM(cst_lastname),
            CASE WHEN UPPER(TRIM(cst_marital_status)) = 'S' THEN 'Single'
                 WHEN UPPER(TRIM(cst_marital_status)) = 'M' THEN 'Married'
                 ELSE 'n/a' END,
            CASE WHEN UPPER(TRIM(cst_gndr)) = 'F' THEN 'Female'
                 WHEN UPPER(TRIM(cst_gndr)) = 'M' THEN 'Male'
                 ELSE 'n/a' END,
            cst_create_date
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY cst_id ORDER BY cst_create_date DESC) AS flag_last
            FROM bronze.crm_cust_info WHERE cst_id IS NOT NULL
        ) t WHERE flag_last = 1;

        TRUNCATE TABLE silver.crm_prd_info;
        INSERT INTO silver.crm_prd_info (
            prd_id, cat_id, prd_key, prd_nm, prd_cost, prd_line, prd_start_dt, prd_end_dt
        )
        SELECT
            prd_id,
            REPLACE(SUBSTRING(prd_key FROM 1 FOR 5), '-', '_'),
            SUBSTRING(prd_key FROM 7),
            prd_nm, COALESCE(prd_cost, 0),
            CASE UPPER(TRIM(prd_line))
                WHEN 'M' THEN 'Mountain' WHEN 'R' THEN 'Road'
                WHEN 'S' THEN 'Other Sales' WHEN 'T' THEN 'Touring'
                ELSE 'n/a' END,
            prd_start_dt::DATE,
            (LEAD(prd_start_dt) OVER (PARTITION BY prd_key ORDER BY prd_start_dt) - INTERVAL '1 day')::DATE
        FROM bronze.crm_prd_info;

        TRUNCATE TABLE silver.crm_sales_details;
        INSERT INTO silver.crm_sales_details (
            sls_ord_num, sls_prd_key, sls_cust_id,
            sls_order_dt, sls_ship_dt, sls_due_dt,
            sls_sales, sls_quantity, sls_price
        )
        SELECT
            sls_ord_num, sls_prd_key, sls_cust_id,
            CASE WHEN sls_order_dt = 0 OR LENGTH(sls_order_dt::TEXT) != 8 THEN NULL ELSE TO_DATE(sls_order_dt::TEXT, 'YYYYMMDD') END,
            CASE WHEN sls_ship_dt = 0 OR LENGTH(sls_ship_dt::TEXT) != 8 THEN NULL ELSE TO_DATE(sls_ship_dt::TEXT, 'YYYYMMDD') END,
            CASE WHEN sls_due_dt = 0 OR LENGTH(sls_due_dt::TEXT) != 8 THEN NULL ELSE TO_DATE(sls_due_dt::TEXT, 'YYYYMMDD') END,
            CASE WHEN sls_sales IS NULL OR sls_sales <= 0 OR sls_sales != sls_quantity * ABS(sls_price) THEN sls_quantity * ABS(sls_price) ELSE sls_sales END,
            sls_quantity,
            CASE WHEN sls_price IS NULL OR sls_price <= 0 THEN sls_sales / NULLIF(sls_quantity, 0) ELSE sls_price END
        FROM bronze.crm_sales_details;

        TRUNCATE TABLE silver.erp_cust_az12;
        INSERT INTO silver.erp_cust_az12 (cid, bdate, gen)
        SELECT
            CASE WHEN cid LIKE 'NAS%' THEN SUBSTRING(cid FROM 4) ELSE cid END,
            CASE WHEN bdate > CURRENT_DATE THEN NULL ELSE bdate END,
            CASE WHEN UPPER(TRIM(gen)) IN ('F', 'FEMALE') THEN 'Female'
                 WHEN UPPER(TRIM(gen)) IN ('M', 'MALE') THEN 'Male'
                 ELSE 'n/a' END
        FROM bronze.erp_cust_az12;

        TRUNCATE TABLE silver.erp_loc_a101;
        INSERT INTO silver.erp_loc_a101 (cid, cntry)
        SELECT
            REPLACE(cid, '-', ''),
            CASE WHEN TRIM(cntry) = 'DE' THEN 'Germany'
                 WHEN TRIM(cntry) IN ('US', 'USA') THEN 'United States'
                 WHEN TRIM(cntry) = '' OR cntry IS NULL THEN 'n/a'
                 ELSE TRIM(cntry) END
        FROM bronze.erp_loc_a101;

        TRUNCATE TABLE silver.erp_px_cat_g1v2;
        INSERT INTO silver.erp_px_cat_g1v2 (id, cat, subcat, maintenance)
        SELECT id, cat, subcat, maintenance FROM bronze.erp_px_cat_g1v2;
    END;
    $$;

    CREATE OR REPLACE VIEW gold.dim_customers AS
    SELECT
        ROW_NUMBER() OVER (ORDER BY ci.cst_id) AS customer_key,
        ci.cst_id AS customer_id, ci.cst_key AS customer_number,
        ci.cst_firstname AS first_name, ci.cst_lastname AS last_name,
        la.cntry AS country, ci.cst_marital_status AS marital_status,
        CASE WHEN ci.cst_gndr != 'n/a' THEN ci.cst_gndr ELSE COALESCE(ca.gen, 'n/a') END AS gender,
        ca.bdate AS birthdate, ci.cst_create_date AS create_date
    FROM silver.crm_cust_info ci
    LEFT JOIN silver.erp_cust_az12 ca ON ci.cst_key = ca.cid
    LEFT JOIN silver.erp_loc_a101  la ON ci.cst_key = la.cid;

    CREATE OR REPLACE VIEW gold.dim_products AS
    SELECT
        ROW_NUMBER() OVER (ORDER BY pn.prd_start_dt, pn.prd_key) AS product_key,
        pn.prd_id AS product_id, pn.prd_key AS product_number, pn.prd_nm AS product_name,
        pn.cat_id AS category_id, pc.cat AS category, pc.subcat AS subcategory,
        pc.maintenance AS maintenance, pn.prd_cost AS cost,
        pn.prd_line AS product_line, pn.prd_start_dt AS start_date
    FROM silver.crm_prd_info pn
    LEFT JOIN silver.erp_px_cat_g1v2 pc ON pn.cat_id = pc.id
    WHERE pn.prd_end_dt IS NULL;

    CREATE OR REPLACE VIEW gold.fact_sales AS
    SELECT
        sd.sls_ord_num AS order_number, pr.product_key AS product_key, cu.customer_key AS customer_key,
        sd.sls_order_dt AS order_date, sd.sls_ship_dt AS shipping_date, sd.sls_due_dt AS due_date,
        sd.sls_sales AS sales_amount, sd.sls_quantity AS quantity, sd.sls_price AS price
    FROM silver.crm_sales_details sd
    LEFT JOIN gold.dim_products  pr ON sd.sls_prd_key = pr.product_number
    LEFT JOIN gold.dim_customers cu ON sd.sls_cust_id = cu.customer_id;
    """
    conn = connect()
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(setup_sql)
    finally:
        conn.close()
    return True


@st.cache_data(ttl=60)
def read(query):
    conn = connect()
    try:
        return pd.read_sql(query, conn)
    finally:
        conn.close()


def load_csv(file, table):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_path = os.path.abspath(os.path.join(HISTORY_DIR, f"{timestamp}_{file.name}"))

    raw_bytes = file.getvalue()
    with open(saved_path, "wb") as f:
        f.write(raw_bytes)

    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE TABLE bronze.{table};")
            text = raw_bytes.decode("utf-8-sig", errors="replace")
            cur.copy_expert(f"COPY bronze.{table} FROM STDIN WITH (FORMAT csv, HEADER true)", io.StringIO(text))
            cur.execute(f"SELECT COUNT(*) FROM bronze.{table};")
            rows = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO bronze.upload_history (file_name, target_table, rows_loaded, saved_file_path, status) "
                "VALUES (%s, %s, %s, %s, %s);",
                (file.name, f"bronze.{table}", rows, saved_path, "Success"),
            )
        conn.commit()
        return rows, saved_path
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run_silver():
    conn = connect()
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("CALL silver.load_silver();")
    finally:
        conn.close()
    st.cache_data.clear()


# ---------------------------------------------------------------
# 4. TABS
# ---------------------------------------------------------------
def upload_tab():
    st.subheader("Upload your CSV files")
    st.caption("Drop one or all six files. Names must be: " + ", ".join(FILES))

    files = st.file_uploader("CSV files", type=["csv"], accept_multiple_files=True, label_visibility="collapsed")

    if files and st.button("Load files and clean data", type="primary", use_container_width=True):
        loaded = 0
        for f in files:
            table = FILES.get(f.name.lower())
            if not table:
                st.warning(f"Skipped {f.name}: name not recognised.")
                continue
            try:
                rows, path = load_csv(f, table)
                st.success(f"{f.name} loaded into bronze.{table} ({rows:,} rows). Backup saved.")
                loaded += 1
            except Exception as e:
                st.error(f"{f.name} failed: {e}")
        if loaded:
            with st.spinner("Cleaning data (Silver and Gold)..."):
                try:
                    run_silver()
                    st.toast("Silver and Gold layers updated", icon="✅")
                    st.success("Done. Silver and Gold are up to date.")
                except Exception as e:
                    st.error(f"Cleaning failed: {e}")

    st.divider()
    st.subheader("Upload history (audit log and backups)")
    try:
        history = read(
            "SELECT upload_id, file_name, target_table, rows_loaded, status, uploaded_at, saved_file_path "
            "FROM bronze.upload_history ORDER BY uploaded_at DESC LIMIT 20;"
        )
        if history.empty:
            st.info("No uploads yet.")
        else:
            st.dataframe(
                history.drop(columns=["upload_id"]),
                use_container_width=True,
                hide_index=True,
            )

            available = history[
                history["saved_file_path"].fillna("").apply(lambda p: bool(p) and os.path.exists(p))
            ]
            if not available.empty:
                st.markdown("#### Download a backup file")
                options = {
                    f"#{row['upload_id']} | {row['file_name']} ({row['uploaded_at']})": row
                    for _, row in available.iterrows()
                }
                c1, c2 = st.columns([3, 1])
                selected_label = c1.selectbox(
                    "Select backup to download",
                    list(options.keys()),
                    label_visibility="collapsed",
                )
                selected_row = options[selected_label]
                with open(selected_row["saved_file_path"], "rb") as f:
                    backup_bytes = f.read()

                c2.download_button(
                    "Download backup CSV",
                    data=backup_bytes,
                    file_name=os.path.basename(selected_row["saved_file_path"]),
                    mime="text/csv",
                    type="primary",
                    use_container_width=True,
                )
            else:
                st.caption("No local backup files found on disk for these entries.")
    except Exception as e:
        st.warning(f"Could not read history: {e}")


def quality_tab():
    st.subheader("Data quality: Bronze (raw) vs Silver (cleaned)")
    st.caption("Proof of deduplication, whitespace trimming, standardization, and sales fixes.")
    try:
        audit = read("""
            SELECT 'CRM Customers' AS dataset,
                   (SELECT COUNT(*) FROM bronze.crm_cust_info) AS bronze_rows,
                   (SELECT COUNT(*) FROM silver.crm_cust_info) AS silver_rows
            UNION ALL
            SELECT 'CRM Products',
                   (SELECT COUNT(*) FROM bronze.crm_prd_info),
                   (SELECT COUNT(*) FROM silver.crm_prd_info)
            UNION ALL
            SELECT 'CRM Sales',
                   (SELECT COUNT(*) FROM bronze.crm_sales_details),
                   (SELECT COUNT(*) FROM silver.crm_sales_details)
            UNION ALL
            SELECT 'ERP Demographics',
                   (SELECT COUNT(*) FROM bronze.erp_cust_az12),
                   (SELECT COUNT(*) FROM silver.erp_cust_az12)
            UNION ALL
            SELECT 'ERP Locations',
                   (SELECT COUNT(*) FROM bronze.erp_loc_a101),
                   (SELECT COUNT(*) FROM silver.erp_loc_a101)
            UNION ALL
            SELECT 'ERP Categories',
                   (SELECT COUNT(*) FROM bronze.erp_px_cat_g1v2),
                   (SELECT COUNT(*) FROM silver.erp_px_cat_g1v2);
        """)
        st.dataframe(audit, use_container_width=True, hide_index=True)

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Bronze sample** (`bronze.crm_cust_info`)")
            st.dataframe(read("SELECT * FROM bronze.crm_cust_info LIMIT 15;"), use_container_width=True, hide_index=True)
        with c2:
            st.markdown("**Silver sample** (`silver.crm_cust_info`)")
            st.dataframe(
                read("SELECT cst_id, cst_key, cst_firstname, cst_lastname, cst_marital_status, cst_gndr FROM silver.crm_cust_info LIMIT 15;"),
                use_container_width=True, hide_index=True
            )
    except Exception as e:
        st.warning(f"Could not load quality audit: {e}")


def download_tab():
    st.subheader("Download final (Gold) data")
    st.caption("Clean, business-ready data. Open the CSV in Excel, Power BI, or ML models.")
    try:
        tables = read("SELECT table_name FROM information_schema.tables WHERE table_schema = 'gold' ORDER BY 1;")
        names = tables["table_name"].tolist()
    except Exception as e:
        st.error(f"Could not read the Gold layer: {e}")
        return
    if not names:
        st.info("No Gold tables yet. Upload your files first.")
        return

    name = st.selectbox("Choose a Gold table", names)
    data = read(f'SELECT * FROM gold."{name}";')
    st.write(f"**{len(data):,}** rows, **{len(data.columns)}** columns")
    st.dataframe(data.head(100), use_container_width=True, hide_index=True)
    st.download_button(
        "Download as CSV",
        data.to_csv(index=False).encode("utf-8-sig"),
        f"gold_{name}.csv",
        "text/csv",
        type="primary",
    )


# ---------------------------------------------------------------
# 5. RUN THE APP
# ---------------------------------------------------------------
try:
    init_db()
    with st.sidebar:
        st.markdown('<span class="status-pill">● PostgreSQL connected</span>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Refresh data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
except Exception as e:
    st.error(f"Cannot connect to PostgreSQL. Check the DB settings or Secrets.\n\n{e}")
    st.stop()

st.markdown(
    """
<div class="hero">
<p class="hero-title">dataVault Analytics Platform</p>
<p class="hero-sub">Medallion data warehouse with Bronze, Silver and Gold layers. Live ingestion, audit history and data quality.</p>
</div>
""",
    unsafe_allow_html=True,
)

tab1, tab2, tab3 = st.tabs(["1. Upload", "2. Data quality", "3. Download"])
with tab1:
    upload_tab()
with tab2:
    quality_tab()
with tab3:
    download_tab() 
    