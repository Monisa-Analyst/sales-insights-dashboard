"""
ingestion.py
Handles the full pipeline when someone uploads a sales CSV or Excel file:
  1. Parse and normalize column names
  2. Clean values (dates, currency strings, missing fields)
  3. Decompose into star schema tables and merge with existing data
  4. Run SQL consistency checks and compute a health score
  5. Return a verdict (Accepted / Needs Review / Rejected)
"""

import os
import re
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime


def _get_db_path():
    """figure out where the database lives"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.path.exists("/mount/src/sales-insights-dashboard"):
        return "/tmp/sales.db"
    return os.path.join(root, "data", "sales.db")


# --- Column Mapping ---
# maps common variations of column names to our star schema fields
_COLUMN_ALIASES = {
    "order_id":       ["order id", "order_id", "orderid", "order no", "order number"],
    "order_date":     ["order date", "order_date", "orderdate", "date"],
    "ship_date":      ["ship date", "ship_date", "shipdate", "shipping date"],
    "ship_mode":      ["ship mode", "ship_mode", "shipmode", "shipping mode"],
    "customer_id":    ["customer id", "customer_id", "customerid", "cust id"],
    "customer_name":  ["customer name", "customer_name", "customername", "client", "buyer"],
    "segment":        ["segment", "customer segment"],
    "product_id":     ["product id", "product_id", "productid", "item id"],
    "product_name":   ["product name", "product_name", "productname", "item", "item name"],
    "category":       ["category", "product category"],
    "sub_category":   ["sub-category", "sub_category", "subcategory", "sub category"],
    "city":           ["city"],
    "state":          ["state", "province"],
    "country":        ["country", "nation"],
    "postal_code":    ["postal code", "postal_code", "postalcode", "zip", "zip code", "zipcode"],
    "market":         ["market", "region market"],
    "region":         ["region"],
    "sales":          ["sales", "revenue", "amount", "total sales"],
    "quantity":       ["quantity", "qty", "units", "count"],
    "discount":       ["discount", "disc", "discount rate"],
    "profit":         ["profit", "net profit", "margin"],
    "shipping_cost":  ["shipping cost", "shipping_cost", "freight"],
    "order_priority": ["order priority", "order_priority", "priority"],
}


def _map_columns(df):
    """
    Try to match the incoming dataframe columns to our expected schema.
    Returns a dict of {our_name: their_column_name} for matched columns,
    and a list of unmapped columns.
    """
    mapped = {}
    incoming = {c.strip().lower(): c for c in df.columns}
    unmapped_incoming = set(incoming.keys())

    for our_name, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in incoming:
                mapped[our_name] = incoming[alias]
                unmapped_incoming.discard(alias)
                break

    leftover = [incoming[k] for k in unmapped_incoming]
    return mapped, leftover


def _parse_number(val):
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


def _parse_dates(series):
    """try multiple date formats until something sticks"""
    result = pd.to_datetime(series, errors="coerce", format="mixed")
    # fill any still-null dates with a sensible default
    result = result.fillna(pd.Timestamp("2024-01-01"))
    return result.dt.strftime("%Y-%m-%d")


def clean_dataframe(df):
    """
    Takes the raw uploaded dataframe, maps columns, cleans values.
    Returns (cleaned_df, column_mapping, warnings_list).
    """
    mapping, unmapped = _map_columns(df)
    warnings = []

    if not mapping:
        return None, {}, ["Could not match any columns. Check your file format."]

    # rename matched columns to our schema names
    rename_map = {v: k for k, v in mapping.items()}
    cleaned = df.rename(columns=rename_map).copy()

    # only keep the columns we recognize
    keep = [c for c in cleaned.columns if c in _COLUMN_ALIASES]
    cleaned = cleaned[keep]

    # handle dates
    if "order_date" in cleaned.columns:
        cleaned["order_date"] = _parse_dates(cleaned["order_date"])
    else:
        cleaned["order_date"] = datetime.now().strftime("%Y-%m-%d")
        warnings.append("No order_date column found — defaulting to today.")

    if "ship_date" in cleaned.columns:
        cleaned["ship_date"] = _parse_dates(cleaned["ship_date"])
    else:
        cleaned["ship_date"] = cleaned["order_date"]
        warnings.append("No ship_date column found — using order_date as fallback.")

    # handle numeric fields
    for col in ["sales", "profit", "discount", "shipping_cost", "quantity"]:
        if col in cleaned.columns:
            cleaned[col] = cleaned[col].apply(_parse_number)
        else:
            default = 0 if col != "quantity" else 1
            cleaned[col] = default
            if col in ("sales", "profit"):
                warnings.append(f"No '{col}' column found — defaulting to 0.")

    # fill missing text fields
    text_defaults = {
        "customer_id": lambda: "CUST-" + pd.Series(range(1, len(cleaned)+1)).astype(str),
        "customer_name": "Unknown Customer",
        "segment": "Consumer",
        "product_id": lambda: "PROD-" + pd.Series(range(1, len(cleaned)+1)).astype(str),
        "product_name": "Unknown Product",
        "category": "General",
        "sub_category": "Other",
        "city": "Unknown",
        "state": "Unknown",
        "country": "Unknown",
        "market": "Unknown",
        "region": "Unknown",
        "postal_code": "N/A",
        "ship_mode": "Standard Class",
        "order_priority": "Medium",
    }

    for col, default in text_defaults.items():
        if col not in cleaned.columns:
            if callable(default):
                cleaned[col] = default()
            else:
                cleaned[col] = default
        else:
            if callable(default):
                mask = cleaned[col].isna() | (cleaned[col].astype(str).str.strip() == "")
                if mask.any():
                    cleaned.loc[mask, col] = default().loc[mask]
            else:
                cleaned[col] = cleaned[col].fillna(default).replace("", default)

    # make sure order_id exists
    if "order_id" not in cleaned.columns:
        ts = datetime.now().strftime("%Y%m%d%H%M")
        cleaned["order_id"] = [f"ORD-{ts}-{i}" for i in range(1, len(cleaned)+1)]
        warnings.append("No order_id column found — auto-generated IDs.")

    if unmapped:
        warnings.append(f"Ignored unrecognized columns: {', '.join(unmapped[:5])}")

    return cleaned, mapping, warnings


# --- SQL Consistency Checks ---

_CHECKS = [
    {
        "name": "Negative Quantities",
        "severity": "warning",
        "sql": "SELECT COUNT(*) as cnt FROM _staging WHERE quantity <= 0",
        "desc": "Rows with zero or negative quantity",
    },
    {
        "name": "Null or Zero Sales",
        "severity": "warning",
        "sql": "SELECT COUNT(*) as cnt FROM _staging WHERE sales IS NULL OR sales = 0",
        "desc": "Rows with no sales value",
    },
    {
        "name": "Extreme Discounts",
        "severity": "warning",
        "sql": "SELECT COUNT(*) as cnt FROM _staging WHERE discount > 1.0",
        "desc": "Discount exceeding 100%",
    },
    {
        "name": "Future Order Dates",
        "severity": "warning",
        "sql": f"SELECT COUNT(*) as cnt FROM _staging WHERE order_date > '{datetime.now().strftime('%Y-%m-%d')}'",
        "desc": "Orders dated in the future",
    },
    {
        "name": "Ship Before Order",
        "severity": "warning",
        "sql": "SELECT COUNT(*) as cnt FROM _staging WHERE ship_date < order_date",
        "desc": "Ship date is earlier than order date",
    },
    {
        "name": "Missing Customer Names",
        "severity": "info",
        "sql": "SELECT COUNT(*) as cnt FROM _staging WHERE customer_name = 'Unknown Customer'",
        "desc": "Rows with placeholder customer names",
    },
    {
        "name": "Missing Product Names",
        "severity": "info",
        "sql": "SELECT COUNT(*) as cnt FROM _staging WHERE product_name = 'Unknown Product'",
        "desc": "Rows with placeholder product names",
    },
]


def run_quality_checks(df):
    """
    Load the cleaned dataframe into a temporary sqlite table and run
    all our validation queries against it. Returns a list of check
    results and an overall health score.
    """
    conn = sqlite3.connect(":memory:")
    df.to_sql("_staging", conn, index=False, if_exists="replace")

    total_rows = len(df)
    issues = []
    flagged_rows = 0

    for check in _CHECKS:
        try:
            result = conn.execute(check["sql"]).fetchone()
            bad_count = result[0] if result else 0
        except Exception as e:
            bad_count = 0
            issues.append({
                "name": check["name"],
                "severity": "error",
                "count": 0,
                "desc": f"Check failed to run: {e}",
                "passed": False,
            })
            continue

        passed = bad_count == 0
        if not passed and check["severity"] in ("warning", "critical"):
            flagged_rows += bad_count

        issues.append({
            "name": check["name"],
            "severity": check["severity"],
            "count": bad_count,
            "desc": check["desc"],
            "passed": passed,
        })

    conn.close()

    # health score: percentage of rows with no issues
    if total_rows > 0:
        health = max(0, (1 - flagged_rows / total_rows)) * 100
    else:
        health = 0

    return issues, round(health, 1)


def determine_verdict(health_score):
    """decide what to do with this batch based on the health score"""
    if health_score >= 80:
        return "Accepted"
    elif health_score >= 50:
        return "Needs Review"
    else:
        return "Rejected"


def merge_into_database(df):
    """
    Take the cleaned, validated dataframe and upsert it into the
    production star schema tables. Handles deduplication against
    existing dimension records.
    """
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # -- upsert customers --
    cust_cols = ["customer_id", "customer_name", "segment"]
    customers = df[cust_cols].drop_duplicates(subset=["customer_id"])
    for _, row in customers.iterrows():
        cur.execute(
            "INSERT OR IGNORE INTO customers (customer_id, customer_name, segment) VALUES (?, ?, ?)",
            (row["customer_id"], row["customer_name"], row["segment"])
        )

    # -- upsert products --
    prod_cols = ["product_id", "product_name", "category", "sub_category"]
    products = df[prod_cols].drop_duplicates(subset=["product_id"])
    for _, row in products.iterrows():
        cur.execute(
            "INSERT OR IGNORE INTO products (product_id, product_name, category, sub_category) VALUES (?, ?, ?, ?)",
            (row["product_id"], row["product_name"], row["category"], row["sub_category"])
        )

    # -- upsert locations --
    # first grab the current max location_id so we can assign new ones
    max_loc = cur.execute("SELECT COALESCE(MAX(location_id), 0) FROM locations").fetchone()[0]
    loc_cols = ["country", "market", "region", "state", "city", "postal_code"]
    locations = df[loc_cols].drop_duplicates()

    loc_id_map = {}
    for _, row in locations.iterrows():
        key = (row["country"], row["market"], row["region"], row["state"], row["city"], str(row["postal_code"]))
        existing = cur.execute(
            "SELECT location_id FROM locations WHERE country=? AND market=? AND region=? AND state=? AND city=? AND postal_code=?",
            key
        ).fetchone()

        if existing:
            loc_id_map[key] = existing[0]
        else:
            max_loc += 1
            cur.execute(
                "INSERT INTO locations (location_id, country, market, region, state, city, postal_code) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (max_loc, *key)
            )
            loc_id_map[key] = max_loc

    # -- upsert orders --
    order_groups = df.groupby("order_id").agg({
        "order_date": "first",
        "ship_date": "first",
        "ship_mode": "first",
        "customer_id": "first",
        "country": "first",
        "market": "first",
        "region": "first",
        "state": "first",
        "city": "first",
        "postal_code": "first",
        "shipping_cost": "sum",
        "order_priority": "first",
    }).reset_index()

    for _, row in order_groups.iterrows():
        loc_key = (row["country"], row["market"], row["region"], row["state"], row["city"], str(row["postal_code"]))
        location_id = loc_id_map.get(loc_key, 1)
        cur.execute(
            "INSERT OR IGNORE INTO orders (order_id, order_date, ship_date, ship_mode, customer_id, location_id, shipping_cost, order_priority) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (row["order_id"], row["order_date"], row["ship_date"], row["ship_mode"],
             row["customer_id"], location_id, row["shipping_cost"], row["order_priority"])
        )

    # -- insert order items (always append, they get new auto-incremented ids) --
    max_oi = cur.execute("SELECT COALESCE(MAX(order_item_id), 0) FROM order_items").fetchone()[0]
    for _, row in df.iterrows():
        max_oi += 1
        cur.execute(
            "INSERT INTO order_items (order_item_id, order_id, product_id, sales, quantity, discount, profit) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (max_oi, row["order_id"], row["product_id"], row["sales"],
             int(row["quantity"]), row["discount"], row["profit"])
        )

    conn.commit()
    conn.close()
    return len(df)


def run_production_checks():
    """
    Run live consistency checks against the production database.
    Used by the Data Quality dashboard to show current db health.
    """
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)

    checks = []

    # orphan orders (customer_id not in customers)
    try:
        cnt = conn.execute("""
            SELECT COUNT(*) FROM orders o
            WHERE o.customer_id NOT IN (SELECT customer_id FROM customers)
        """).fetchone()[0]
        checks.append({"name": "Orphan Orders", "desc": "Orders referencing missing customers", "count": cnt, "severity": "critical"})
    except Exception:
        checks.append({"name": "Orphan Orders", "desc": "Check failed", "count": -1, "severity": "error"})

    # orphan order items (order_id not in orders)
    try:
        cnt = conn.execute("""
            SELECT COUNT(*) FROM order_items oi
            WHERE oi.order_id NOT IN (SELECT order_id FROM orders)
        """).fetchone()[0]
        checks.append({"name": "Orphan Line Items", "desc": "Items referencing missing orders", "count": cnt, "severity": "critical"})
    except Exception:
        checks.append({"name": "Orphan Line Items", "desc": "Check failed", "count": -1, "severity": "error"})

    # orphan product references
    try:
        cnt = conn.execute("""
            SELECT COUNT(*) FROM order_items oi
            WHERE oi.product_id NOT IN (SELECT product_id FROM products)
        """).fetchone()[0]
        checks.append({"name": "Orphan Product Refs", "desc": "Items referencing missing products", "count": cnt, "severity": "critical"})
    except Exception:
        checks.append({"name": "Orphan Product Refs", "desc": "Check failed", "count": -1, "severity": "error"})

    # date range
    try:
        row = conn.execute("SELECT MIN(order_date), MAX(order_date), COUNT(*) FROM orders").fetchone()
        checks.append({"name": "Date Range", "desc": f"Orders from {row[0]} to {row[1]} ({row[2]:,} total)", "count": 0, "severity": "info"})
    except Exception:
        checks.append({"name": "Date Range", "desc": "Check failed", "count": -1, "severity": "error"})

    # null sales
    try:
        cnt = conn.execute("SELECT COUNT(*) FROM order_items WHERE sales IS NULL OR sales = 0").fetchone()[0]
        checks.append({"name": "Zero/Null Sales", "desc": "Line items with no revenue value", "count": cnt, "severity": "warning"})
    except Exception:
        checks.append({"name": "Zero/Null Sales", "desc": "Check failed", "count": -1, "severity": "error"})

    # negative quantities
    try:
        cnt = conn.execute("SELECT COUNT(*) FROM order_items WHERE quantity <= 0").fetchone()[0]
        checks.append({"name": "Bad Quantities", "desc": "Line items with zero or negative qty", "count": cnt, "severity": "warning"})
    except Exception:
        checks.append({"name": "Bad Quantities", "desc": "Check failed", "count": -1, "severity": "error"})

    # table row counts
    try:
        tables = {}
        for tbl in ["customers", "products", "locations", "orders", "order_items"]:
            tables[tbl] = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        summary = " · ".join(f"{t}: {c:,}" for t, c in tables.items())
        checks.append({"name": "Table Sizes", "desc": summary, "count": 0, "severity": "info"})
    except Exception:
        checks.append({"name": "Table Sizes", "desc": "Check failed", "count": -1, "severity": "error"})

    conn.close()
    return checks
