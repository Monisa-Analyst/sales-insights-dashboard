# Sales Insights & AI Query Assistant

🌐 **[Live Web Application](https://share.streamlit.io/monisa-analyst/sales-insights-dashboard/main/src/app.py)**  
*Explore the live Streamlit dashboard in your browser — upload your own data, get instant analysis, and ask questions in plain English.*

---

## Project Overview

An end-to-end data engineering and business intelligence platform built around a real e-commerce dataset (~50,000 transaction records). It covers the full analytics lifecycle — from raw data ingestion and ETL normalization through interactive visual dashboards, all the way to a conversational AI assistant that translates plain English questions into executable SQL.

What makes this project different from a typical dashboard is the **live data ingestion pipeline**: anyone can upload their own sales CSV or Excel file through the web interface, and the system will automatically clean it, validate data quality with SQL consistency checks, and merge it into the production database — or flag it for analyst review if the quality thresholds aren't met.

I built this to demonstrate real-world competencies in:

1. **Data Cleaning & ETL Pipelines** — parsing messy transaction logs with Python and Pandas, handling edge cases like currency formatting and mixed date formats.
2. **Relational Database Design** — normalizing flat-file data into a clean star schema with proper foreign keys and performance indexes.
3. **Data Quality Engineering** — predefined SQL validation rules that run on every batch, with automated scoring and analyst alerting.
4. **Analytical SQL** — complex joins, CTEs, window functions, and aggregation patterns for business intelligence.
5. **Generative AI Integration** — using the Gemini API to build a natural language interface for SQL querying with smart regex fallback.
6. **Interactive Visualizations** — responsive Streamlit + Plotly dashboards with custom theming and micro-animations.

---

## Tech Stack

| Layer | Tools |
|---|---|
| **Frontend & UI** | Streamlit (custom dark-mode theme) |
| **Data Visualization** | Plotly Express & Graph Objects |
| **Database** | SQLite (via SQLAlchemy + sqlite3) |
| **AI / NLP** | Google Gemini API (`gemini-2.0-flash`) |
| **Data Pipeline** | Python 3.11+, Pandas, NumPy |
| **File Support** | CSV, Excel (openpyxl) |

---

## Database Design — Star Schema

The raw dataset is normalized into a **star schema** with 4 dimension tables and 1 fact table, optimized for analytical queries:

```
                  ┌──────────────┐
                  │  customers   │
                  └──────┬───────┘
                         │ 1:N
 ┌──────────────┐ 1:N ┌──┴───┐ N:1 ┌──────────────┐
 │  locations   ├─────┤orders├─────┤   products   │
 └──────────────┘     └──┬───┘     └──────────────┘
                         │ 1:N
                  ┌──────┴───────┐
                  │ order_items  │
                  └──────────────┘
```

| Table | Type | Key Columns |
|---|---|---|
| `customers` | Dimension | `customer_id` (PK), `customer_name`, `segment` |
| `products` | Dimension | `product_id` (PK), `product_name`, `category`, `sub_category` |
| `locations` | Dimension | `location_id` (PK), `country`, `market`, `region`, `state`, `city` |
| `orders` | Dimension | `order_id` (PK), `order_date`, `ship_date`, `customer_id` (FK), `location_id` (FK) |
| `order_items` | Fact | `order_item_id` (PK), `order_id` (FK), `product_id` (FK), `sales`, `quantity`, `profit` |

---

## Key Features

### 1. Automated ETL Pipeline (`src/data_loader.py`)

- Downloads the Global Superstore CSV programmatically
- Parses dates across multiple formats, handles currency strings and parenthesized negatives
- Deduplicates and splits records into the relational star schema
- Exports cleaned CSVs (for Power BI) and populates the SQLite database with indexes

### 2. Interactive Analytics Dashboard

- **KPI Cards:** Revenue, Profit, Net Margin, and Customer counts with hover animations
- **Trend Analysis:** Spline-smoothed line charts with shaded area fills showing sales and profit over time
- **Segment Breakdown:** Donut charts for product category distributions
- **Performance Rankings:** Horizontal bar charts for top customers, popular products, and regional revenue splits

### 3. External Data Submission (`src/ingestion.py`)

This is the standout feature — a live data ingestion pipeline accessible directly through the web interface:

- **Upload any CSV or Excel file** containing sales transaction records
- **Smart column mapping** automatically detects and matches incoming columns (e.g., `Order Date`, `order_date`, `OrderDate`) to the star schema
- **Automated cleaning** — dates parsed across formats, currency symbols stripped, missing values filled with sensible defaults
- **Star schema decomposition** — incoming flat data is split and upserted into customers, products, locations, orders, and order_items tables

### 4. SQL-Based Data Quality Gate

Every uploaded batch goes through **9 predefined SQL validation checks** before it can be merged:

| Check | What It Catches |
|---|---|
| Negative Quantities | Orders with zero or negative qty |
| Null/Zero Sales | Line items with no revenue value |
| Extreme Discounts | Discounts exceeding 100% |
| Future Order Dates | Orders dated after today |
| Ship Before Order | Ship date earlier than order date |
| Missing Customer Names | Placeholder names from auto-fill |
| Missing Product Names | Placeholder names from auto-fill |

Each batch gets a **health score** (0–100%) and a verdict:
- **✅ Accepted** (≥80%) — merged automatically
- **⚠️ Needs Review** (50–79%) — flagged for analyst intervention
- **🔴 Rejected** (<50%) — blocked from merging

### 5. Data Quality Monitor & Analyst Alerts

A dedicated monitoring page shows:
- **Active Alerts** — batches flagged as "Needs Review" with expandable issue details
- **Live Database Health** — consistency checks running against the production database in real-time (orphan foreign keys, null values, date range sanity)
- **Submission History** — a log table of every batch ever uploaded with timestamps, row counts, and outcomes

### 6. AI Query Assistant (`src/ai_agent.py`)

- Translates conversational questions (e.g., *"What was the revenue growth in 2014?"*) into SQLite queries
- Powered by Gemini API with schema-aware system instructions
- **Smart Fallback Engine:** if the API key is missing or rate-limited, falls back to a regex parser that extracts keywords and maps them to SQL templates
- Explains results in business-friendly bullet points

---

## Analytical SQL Examples (`sql/queries.sql`)

### Month-over-Month Revenue Growth
```sql
WITH MonthlySales AS (
    SELECT SUBSTR(o.order_date, 1, 7) AS month,
           SUM(oi.sales) AS total_sales
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    GROUP BY month
)
SELECT month,
       total_sales,
       LAG(total_sales, 1) OVER (ORDER BY month) AS prev_month_sales,
       ROUND(((total_sales - LAG(total_sales, 1) OVER (ORDER BY month))
              / LAG(total_sales, 1) OVER (ORDER BY month)) * 100, 2) AS mom_growth_pct
FROM MonthlySales;
```

### Top 5 Customers per Segment
```sql
WITH CustomerSpend AS (
    SELECT c.customer_name, c.segment,
           SUM(oi.sales) AS total_spent,
           DENSE_RANK() OVER (PARTITION BY c.segment ORDER BY SUM(oi.sales) DESC) as rank
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    JOIN order_items oi ON o.order_id = oi.order_id
    GROUP BY c.customer_name, c.segment
)
SELECT customer_name, segment, total_spent
FROM CustomerSpend WHERE rank <= 5;
```

---

## Local Setup

### 1. Prerequisites
Python 3.11 or later.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Build the Database
```bash
python src/data_loader.py
```

### 4. Configure API Keys (Optional)
```env
# .env file
GEMINI_API_KEY=your_gemini_api_key_here
```
The dashboard works without an API key — the AI assistant falls back to the built-in regex query engine.

### 5. Launch
```bash
streamlit run src/app.py
```
Open `http://localhost:8501` in your browser.

---

## Project Structure

```
├── data/                      # Raw datasets, cleaned CSVs, and SQLite database
├── sql/
│   ├── schema.sql             # SQL schema definition (star schema DDL)
│   └── queries.sql            # Pre-built analytical business queries
├── src/
│   ├── data_loader.py         # ETL: download, clean, normalize, load
│   ├── ingestion.py           # Live data ingestion, cleaning, and validation
│   ├── batch_log.py           # Submission tracking and analyst alerting
│   ├── ai_agent.py            # NLP-to-SQL engine using Gemini API
│   ├── app.py                 # Streamlit dashboard (4 pages)
│   └── test_system.py         # Automated smoke tests
├── power_bi/
│   └── data_model_guide.md    # Power BI data model reference
├── requirements.txt
└── README.md
```

---

## License

This project is licensed under the MIT License.
