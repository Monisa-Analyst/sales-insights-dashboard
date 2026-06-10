"""
data_loader.py
Downloads the Global Superstore dataset, cleans it up, splits into
normalized tables, and dumps everything into a local SQLite DB + CSVs.

Run this once before starting the dashboard:
    python src/data_loader.py
"""

import os, sys
import urllib.request
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

# paths
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
RAW_CSV = os.path.join(DATA_DIR, "raw_sales_data.csv")
DB_FILE = os.path.join(DATA_DIR, "sales.db")

DATASET_URL = "https://raw.githubusercontent.com/anurag3290/Retail-Giant-Sales-Forecasting-Time-Series-Modelling/master/Global%20Superstore.csv"


def setup_folders():
    """make sure all the project folders exist"""
    for path in [DATA_DIR, os.path.join(ROOT, "power_bi", "mockups"), os.path.join(ROOT, "sql")]:
        os.makedirs(path, exist_ok=True)
    print("folders ready")


def grab_dataset():
    """download csv if we don't have it yet"""
    if os.path.exists(RAW_CSV):
        print("dataset already downloaded, skipping")
        return

    print(f"downloading dataset...")
    try:
        req = urllib.request.Request(DATASET_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as resp, open(RAW_CSV, 'wb') as f:
            total = 0
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                total += len(chunk)
                print(f"  {total / (1024*1024):.1f} MB downloaded", end="\r")
        print("\ndownload done!")
    except Exception as err:
        print(f"download failed: {err}")
        raise


def parse_number(val):
    """handle currency strings, parentheses for negatives, etc"""
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace("$", "").replace(",", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except ValueError:
        return 0.0


def build_tables():
    """main ETL - read raw csv, clean, normalize into star schema, save"""
    print("reading raw csv...")
    df = pd.read_csv(RAW_CSV, encoding='latin-1')
    print(f"loaded {len(df)} rows")

    # clean up column names (sometimes have trailing spaces)
    df.columns = [c.strip() for c in df.columns]

    # dates
    df['Order Date'] = pd.to_datetime(df['Order Date'], errors='coerce', format='mixed')
    df['Ship Date'] = pd.to_datetime(df['Ship Date'], errors='coerce', format='mixed')
    df['Order Date'] = df['Order Date'].fillna(pd.Timestamp('2014-01-01'))
    df['Ship Date'] = df['Ship Date'].fillna(df['Order Date'] + pd.Timedelta(days=4))
    df['Order Date'] = df['Order Date'].dt.strftime('%Y-%m-%d')
    df['Ship Date'] = df['Ship Date'].dt.strftime('%Y-%m-%d')

    # numeric columns
    for col in ['Sales', 'Profit', 'Shipping Cost', 'Discount']:
        if col in df.columns:
            df[col] = df[col].apply(parse_number)

    # --- customers table ---
    print("building customers...")
    customers = df[['Customer ID', 'Customer Name', 'Segment']].drop_duplicates(
        subset=['Customer ID']).reset_index(drop=True)
    customers.columns = ['customer_id', 'customer_name', 'segment']

    # --- products table ---
    print("building products...")
    products = df[['Product ID', 'Product Name', 'Category', 'Sub-Category']].drop_duplicates(
        subset=['Product ID']).reset_index(drop=True)
    products.columns = ['product_id', 'product_name', 'category', 'sub_category']

    # --- locations table ---
    print("building locations...")
    df['Postal Code'] = df['Postal Code'].fillna('N/A').astype(str)
    loc_cols = ['Country', 'Market', 'Region', 'State', 'City', 'Postal Code']
    locations = df[loc_cols].drop_duplicates().reset_index(drop=True)
    locations.insert(0, 'location_id', locations.index + 1)
    locations.columns = ['location_id', 'country', 'market', 'region', 'state', 'city', 'postal_code']

    # map location_id back
    df = df.merge(locations,
                  left_on=['Country', 'Market', 'Region', 'State', 'City', 'Postal Code'],
                  right_on=['country', 'market', 'region', 'state', 'city', 'postal_code'],
                  how='left')

    # --- orders table ---
    print("building orders...")
    orders = df.groupby('Order ID').agg({
        'Order Date': 'first', 'Ship Date': 'first', 'Ship Mode': 'first',
        'Customer ID': 'first', 'location_id': 'first',
        'Shipping Cost': 'sum', 'Order Priority': 'first'
    }).reset_index()
    orders.columns = ['order_id', 'order_date', 'ship_date', 'ship_mode',
                       'customer_id', 'location_id', 'shipping_cost', 'order_priority']

    # --- order_items (fact table) ---
    print("building order items...")
    items = df[['Order ID', 'Product ID', 'Sales', 'Quantity', 'Discount', 'Profit']].copy()
    items.insert(0, 'order_item_id', range(1, len(items) + 1))
    items.columns = ['order_item_id', 'order_id', 'product_id', 'sales', 'quantity', 'discount', 'profit']

    # save csvs (for power bi)
    print("saving csvs...")
    customers.to_csv(os.path.join(DATA_DIR, "cleaned_customers.csv"), index=False)
    products.to_csv(os.path.join(DATA_DIR, "cleaned_products.csv"), index=False)
    locations.to_csv(os.path.join(DATA_DIR, "cleaned_locations.csv"), index=False)
    orders.to_csv(os.path.join(DATA_DIR, "cleaned_orders.csv"), index=False)
    items.to_csv(os.path.join(DATA_DIR, "cleaned_order_items.csv"), index=False)

    # load into sqlite
    print(f"loading into sqlite ({DB_FILE})...")
    engine = create_engine(f"sqlite:///{DB_FILE}")
    customers.to_sql("customers", engine, if_exists="replace", index=False)
    products.to_sql("products", engine, if_exists="replace", index=False)
    locations.to_sql("locations", engine, if_exists="replace", index=False)
    orders.to_sql("orders", engine, if_exists="replace", index=False)
    items.to_sql("order_items", engine, if_exists="replace", index=False)

    # indexes for faster queries
    with engine.begin() as conn:
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_cust_pk ON customers (customer_id);"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_prod_pk ON products (product_id);"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_loc_pk ON locations (location_id);"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_ord_pk ON orders (order_id);"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_oi_pk ON order_items (order_item_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ord_cust ON orders (customer_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ord_loc ON orders (location_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_oi_order ON order_items (order_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_oi_prod ON order_items (product_id);"))

    print("all done! database is ready.")


if __name__ == "__main__":
    setup_folders()
    grab_dataset()
    build_tables()
    print("data loader finished.")
