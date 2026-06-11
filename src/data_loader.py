import os
import urllib.request
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

# URL of the dataset
DATASET_URL = "https://raw.githubusercontent.com/anurag3290/Retail-Giant-Sales-Forecasting-Time-Series-Modelling/master/Global%20Superstore.csv"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DATA_PATH = os.path.join(DATA_DIR, "raw_sales_data.csv")
DB_PATH = os.path.join(DATA_DIR, "sales.db")

def ensure_directories():
    """Ensure data and power_bi/mockups directories exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "power_bi", "mockups"), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "sql"), exist_ok=True)
    print(f"[+] Verified directory structure.")

def download_dataset():
    """Download the Global Superstore CSV if it doesn't already exist."""
    if not os.path.exists(RAW_DATA_PATH):
        print(f"[*] Downloading Global Superstore dataset from {DATASET_URL}...")
        try:
            # Setup headers to prevent blocks
            req = urllib.request.Request(
                DATASET_URL, 
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req) as response, open(RAW_DATA_PATH, 'wb') as out_file:
                # Read in chunks to show progress
                chunk_size = 1024 * 1024  # 1MB
                downloaded = 0
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    print(f"    Downloaded: {downloaded / (1024 * 1024):.2f} MB", end="\r")
            print("\n[+] Download completed successfully.")
        except Exception as e:
            print(f"\n[-] Error downloading dataset: {e}")
            raise e
    else:
        print("[+] Dataset already exists locally. Skipping download.")

def clean_numeric(val):
    """Clean currency/numeric strings (remove symbols, commas, handle parentheses)."""
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip().replace("$", "").replace(",", "")
    if val_str.startswith("(") and val_str.endswith(")"):
        val_str = "-" + val_str[1:-1]
    try:
        return float(val_str)
    except ValueError:
        return 0.0

def process_and_normalize():
    """Load, clean, normalize, and save the dataset."""
    print("[*] Reading raw dataset (using latin1 encoding)...")
    # Read the dataset
    df = pd.read_csv(RAW_DATA_PATH, encoding='latin-1')
    print(f"[+] Loaded {len(df)} records.")

    # Trim column names
    df.columns = [col.strip() for col in df.columns]

    print("[*] Cleaning and parsing columns...")
    # Parse dates (standardizing to string YYYY-MM-DD for SQL compatibility)
    df['Order Date'] = pd.to_datetime(df['Order Date'], errors='coerce', format='mixed')
    df['Ship Date'] = pd.to_datetime(df['Ship Date'], errors='coerce', format='mixed')
    
    # Check for date conversion issues and fill defaults if any
    df['Order Date'] = df['Order Date'].fillna(pd.Timestamp('2014-01-01'))
    df['Ship Date'] = df['Ship Date'].fillna(df['Order Date'] + pd.Timedelta(days=4))
    
    # Format dates as YYYY-MM-DD
    df['Order Date'] = df['Order Date'].dt.strftime('%Y-%m-%d')
    df['Ship Date'] = df['Ship Date'].dt.strftime('%Y-%m-%d')

    # Clean numeric fields
    for col in ['Sales', 'Profit', 'Shipping Cost', 'Discount']:
        if col in df.columns:
            df[col] = df[col].apply(clean_numeric)

    # 1. Dimension: Customers
    print("[*] Creating customers dimension...")
    customers_df = df[['Customer ID', 'Customer Name', 'Segment']].copy()
    customers_df = customers_df.drop_duplicates(subset=['Customer ID']).reset_index(drop=True)
    customers_df.columns = ['customer_id', 'customer_name', 'segment']

    # 2. Dimension: Products
    print("[*] Creating products dimension...")
    products_df = df[['Product ID', 'Product Name', 'Category', 'Sub-Category']].copy()
    products_df = products_df.drop_duplicates(subset=['Product ID']).reset_index(drop=True)
    products_df.columns = ['product_id', 'product_name', 'category', 'sub_category']

    # 3. Dimension: Locations
    print("[*] Creating locations dimension...")
    locations_cols = ['Country', 'Market', 'Region', 'State', 'City', 'Postal Code']
    # Replace NaN in Postal Code with 'N/A' as many international rows won't have postal codes
    df['Postal Code'] = df['Postal Code'].fillna('N/A').astype(str)
    
    locations_df = df[locations_cols].copy()
    locations_df = locations_df.drop_duplicates().reset_index(drop=True)
    locations_df.insert(0, 'location_id', locations_df.index + 1)
    locations_df.columns = ['location_id', 'country', 'market', 'region', 'state', 'city', 'postal_code']

    # Map Location ID back to the main DataFrame
    print("[*] Mapping locations to main records...")
    df = df.merge(
        locations_df, 
        left_on=['Country', 'Market', 'Region', 'State', 'City', 'Postal Code'],
        right_on=['country', 'market', 'region', 'state', 'city', 'postal_code'],
        how='left'
    )

    # 4. Dimension: Orders
    print("[*] Creating orders dimension...")
    orders_df = df[['Order ID', 'Order Date', 'Ship Date', 'Ship Mode', 'Customer ID', 'location_id', 'Shipping Cost', 'Order Priority']].copy()
    
    # We group by Order ID to sum shipping cost and capture order level attributes
    orders_grouped = orders_df.groupby('Order ID').agg({
        'Order Date': 'first',
        'Ship Date': 'first',
        'Ship Mode': 'first',
        'Customer ID': 'first',
        'location_id': 'first',
        'Shipping Cost': 'sum',
        'Order Priority': 'first'
    }).reset_index()
    orders_grouped.columns = ['order_id', 'order_date', 'ship_date', 'ship_mode', 'customer_id', 'location_id', 'shipping_cost', 'order_priority']

    # 5. Fact: Order Items
    print("[*] Creating order items fact...")
    order_items_df = df[['Order ID', 'Product ID', 'Sales', 'Quantity', 'Discount', 'Profit']].copy()
    order_items_df.insert(0, 'order_item_id', order_items_df.index + 1)
    order_items_df.columns = ['order_item_id', 'order_id', 'product_id', 'sales', 'quantity', 'discount', 'profit']

    # Save to Cleaned CSVs for Power BI import
    print("[*] Saving cleaned dataframes to CSV...")
    customers_df.to_csv(os.path.join(DATA_DIR, "cleaned_customers.csv"), index=False)
    products_df.to_csv(os.path.join(DATA_DIR, "cleaned_products.csv"), index=False)
    locations_df.to_csv(os.path.join(DATA_DIR, "cleaned_locations.csv"), index=False)
    orders_grouped.to_csv(os.path.join(DATA_DIR, "cleaned_orders.csv"), index=False)
    order_items_df.to_csv(os.path.join(DATA_DIR, "cleaned_order_items.csv"), index=False)
    print("[+] CSV files saved successfully.")

    # Save to SQLite Database
    print(f"[*] Loading data into SQLite Database: {DB_PATH}...")
    engine = create_engine(f"sqlite:///{DB_PATH}")
    
    customers_df.to_sql("customers", engine, if_exists="replace", index=False)
    products_df.to_sql("products", engine, if_exists="replace", index=False)
    locations_df.to_sql("locations", engine, if_exists="replace", index=False)
    orders_grouped.to_sql("orders", engine, if_exists="replace", index=False)
    order_items_df.to_sql("order_items", engine, if_exists="replace", index=False)
    
    print("[+] Database loaded successfully with indexes.")
    
    # Add primary key indexes for faster joins (using SQLite raw connection)
    with engine.begin() as conn:
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_pk ON customers (customer_id);"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_products_pk ON products (product_id);"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_locations_pk ON locations (location_id);"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_pk ON orders (order_id);"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_order_items_pk ON order_items (order_item_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders (customer_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_orders_location ON orders (location_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_items_order ON order_items (order_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_items_product ON order_items (product_id);"))
        
    print("[+] SQLite indexes created.")

if __name__ == "__main__":
    ensure_directories()
    download_dataset()
    process_and_normalize()
    print("[+] Data loader process finished successfully!")
