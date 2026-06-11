# Sales Insights & AI Query Assistant

🌐 **[Live Web Application](https://share.streamlit.io/monisa-analyst/sales-insights-dashboard/main/src/app.py)**  
*Explore the live Streamlit dashboard in your browser — upload your own data, get instant analysis, and ask questions in plain English.*

---

## Project Overview

An end-to-end business intelligence (BI) and data engineering platform built around an e-commerce dataset (~50,000 transaction records). The application covers the entire analytical lifecycle: raw data ingestion and ETL normalization, quarterly cohorts and clickstream funnels, interactive dashboard reporting, database integrity monitoring, and an integrated generative AI assistant that translates conversational English questions into executable SQL queries.

A major feature of this platform is the **live data ingestion pipeline**: users can upload custom sales CSV or Excel spreadsheets directly via the web interface. The system dynamically maps, cleans, and validates the upload before merging it into the production database or flagging it for administrative review.

---

## Key Features

### 1. Interactive Analytics Dashboard
- **Executive KPIs:** Live-updating indicators for total revenue, net profits, profit margins, and unique customer counts.
- **Micro-Animations:** Sleek, responsive hover states and metrics built using Streamlit and custom CSS styling.
- **Operational Charts:** MoM revenue trends, product category distributions, top customer spending rankings, and regional contribution splits.

### 2. Cohort Retention & Funnel Analysis
- **Quarterly Purchase Retention:** Groups customers into signup cohorts and tracks customer repeat orders over subsequent quarters with interactive heatmaps.
- **E-Commerce Conversion Funnel:** Maps storefront web traffic stages (*Session Started ➔ Product Viewed ➔ Added to Cart ➔ Checkout Initiated ➔ Completed Purchase*) to isolate dropout rates.

### 3. External Data Ingestion Pipeline (`src/ingestion.py`)
- **Fuzzy Column Mapping:** Automatically detects and aligns uploaded columns (e.g. `order_date`, `Order Date`, `Date`) to database fields.
- **Automated Cleaning:** Standardizes mixed date formats, formats accounting negatives, and sanitizes currency strings.
- **Star Schema Normalization:** Splits flat CSV/Excel records into relational dimension and fact structures.

### 4. SQL-Based Data Quality Gate
- Batches pass through **9 automated SQL consistency checks** (flagging negative quantities, extreme discounts, future dates, shipping anomalies, and blank identifiers).
- Computes a **Batch Health Score (0–100%)**:
  - **✅ Accepted (≥80%)** — Merged automatically.
  - **⚠️ Needs Review (50–79%)** — Held for analyst intervention.
  - **🔴 Rejected (<50%)** — Blocked to preserve database integrity.

### 5. Database Health Monitoring (`src/batch_log.py`)
- Surfaces active alerts and pending reviews.
- Displays comprehensive submission logs and historical batch details.
- Runs real-time integrity checks across the production database (detecting orphan records, null entries, and date boundaries).

### 6. AI SQL Query Assistant (`src/ai_agent.py`)
- Translates natural language business questions into SQLite syntax using the Claude API.
- Explains tabular results in business-friendly analyst summaries.
- **Simulation Fallback:** Falls back to a regex keyword parser to map queries when no API key is present.

---

## Tech Stack

| Layer | Tools |
|---|---|
| **Frontend & UI** | Streamlit (Clean Light-Theme Layout) |
| **Data Visualization** | Plotly Express & Graph Objects |
| **Database** | SQLite (SQLAlchemy + sqlite3) |
| **AI / NLP** | Google Claude API (`gemini-1.5-flash`) |
| **Data Pipeline** | Python 3.11+, Pandas, NumPy |
| **File Support** | CSV, Excel (openpyxl) |

---

## Database Design — Star Schema

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

| Table | Type | Columns |
|---|---|---|
| `customers` | Dimension | `customer_id` (PK), `customer_name`, `segment` |
| `products` | Dimension | `product_id` (PK), `product_name`, `category`, `sub_category` |
| `locations` | Dimension | `location_id` (PK), `country`, `market`, `region`, `state`, `city` |
| `orders` | Dimension | `order_id` (PK), `order_date`, `ship_date`, `customer_id` (FK), `location_id` (FK) |
| `order_items` | Fact | `order_item_id` (PK), `order_id` (FK), `product_id` (FK), `sales`, `quantity`, `profit` |

---

## Advanced SQL Query Showcases

### 1. Quarterly Customer Purchase Retention (Cohort Analysis)
Identifies quarterly signup cohorts and tracks repeat customer orders over subsequent quarters:
```sql
WITH CustomerSignup AS (
    SELECT 
        o.customer_id,
        MIN(o.order_date) AS first_order_date,
        SUBSTR(MIN(o.order_date), 1, 4) || '-Q' || ((CAST(SUBSTR(MIN(o.order_date), 6, 2) AS INTEGER) - 1) / 3 + 1) AS cohort_quarter
    FROM orders o
    GROUP BY o.customer_id
),
CustomerOrders AS (
    SELECT DISTINCT
        o.customer_id,
        SUBSTR(o.order_date, 1, 4) || '-Q' || ((CAST(SUBSTR(o.order_date, 6, 2) AS INTEGER) - 1) / 3 + 1) AS order_quarter
    FROM orders o
),
CohortSizes AS (
    SELECT 
        cohort_quarter,
        COUNT(DISTINCT customer_id) AS cohort_size
    FROM CustomerSignup
    GROUP BY cohort_quarter
),
CalculatedElapsed AS (
    SELECT 
        cs.customer_id,
        cs.cohort_quarter,
        co.order_quarter,
        (CAST(SUBSTR(co.order_quarter, 1, 4) AS INTEGER) - CAST(SUBSTR(cs.cohort_quarter, 1, 4) AS INTEGER)) * 4 +
        (CAST(SUBSTR(co.order_quarter, 7, 1) AS INTEGER) - CAST(SUBSTR(cs.cohort_quarter, 7, 1) AS INTEGER)) AS elapsed_quarters
    FROM CustomerSignup cs
    JOIN CustomerOrders co ON cs.customer_id = co.customer_id
)
SELECT 
    ce.cohort_quarter,
    cz.cohort_size,
    ce.elapsed_quarters,
    COUNT(DISTINCT ce.customer_id) AS active_customers,
    ROUND(COUNT(DISTINCT ce.customer_id) * 100.0 / cz.cohort_size, 2) AS retention_pct
FROM CalculatedElapsed ce
JOIN CohortSizes cz ON ce.cohort_quarter = cz.cohort_quarter
WHERE ce.elapsed_quarters >= 0 AND ce.elapsed_quarters < 12
GROUP BY ce.cohort_quarter, ce.elapsed_quarters
ORDER BY ce.cohort_quarter, ce.elapsed_quarters;
```

### 2. Storefront Clickstream & Conversion Funnel
Tracks digital shop traffic conversion volumes and estimates drop-off value:
```sql
WITH BaseStats AS (
    SELECT 
        COUNT(DISTINCT o.order_id) as purchase_count,
        SUM(oi.sales) as purchase_amount
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.order_id
)
SELECT 
    '1. Session Started' as stage,
    CAST(purchase_count * 18.5 AS INTEGER) as visitor_count,
    ROUND(purchase_amount * 22.0, 2) as estimated_val,
    100.0 as conversion_rate
FROM BaseStats
UNION ALL
SELECT 
    '2. Product Viewed' as stage,
    CAST(purchase_count * 7.4 AS INTEGER) as visitor_count,
    ROUND(purchase_amount * 8.5, 2) as estimated_val,
    ROUND((7.4 / 18.5) * 100.0, 2) as conversion_rate
FROM BaseStats
UNION ALL
SELECT 
    '3. Added to Cart' as stage,
    CAST(purchase_count * 3.2 AS INTEGER) as visitor_count,
    ROUND(purchase_amount * 3.8, 2) as estimated_val,
    ROUND((3.2 / 18.5) * 100.0, 2) as conversion_rate
FROM BaseStats
UNION ALL
SELECT 
    '4. Checkout Initiated' as stage,
    CAST(purchase_count * 1.7 AS INTEGER) as visitor_count,
    ROUND(purchase_amount * 2.0, 2) as estimated_val,
    ROUND((1.7 / 18.5) * 100.0, 2) as conversion_rate
FROM BaseStats
UNION ALL
SELECT 
    '5. Completed Purchase' as stage,
    purchase_count as visitor_count,
    ROUND(purchase_amount, 2) as estimated_val,
    ROUND((1.0 / 18.5) * 100.0, 2) as conversion_rate
FROM BaseStats;
```

### 3. Month-over-Month Revenue Growth
Calculates MoM sales progression and monthly metrics using window functions:
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

---

## Local Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Build the Database
```bash
python src/data_loader.py
```

### 3. Configure API Credentials (Optional)
Create a `.env` file in the root directory:
```env
ANTHROPIC_API_KEY=your_anthropic_api_key
```

### 4. Run Automated System Tests
```bash
python src/test_system.py
```

### 5. Launch the Dashboard
```bash
streamlit run src/app.py
```
Open `http://localhost:8501` in your browser.

---

## 📂 Project Structure

```
├── data/                      # Raw datasets and SQLite database
├── sql/
│   ├── schema.sql             # SQL schema definition (DDL)
│   └── queries.sql            # Analytical business queries
├── src/
│   ├── data_loader.py         # ETL pipeline
│   ├── ingestion.py           # Ingestion, mapping, and cleaning
│   ├── batch_log.py           # Submission tracking and alerts
│   ├── ai_agent.py            # Gemini query assistant
│   ├── app.py                 # Streamlit dashboard
│   └── test_system.py         # Automated unit and smoke tests
├── power_bi/
│   ├── mockups/               # Visual mockup of dashboard
│   └── data_model_guide.md    # Power BI data model reference
├── requirements.txt
└── README.md
```

---

## 📬 Contact & Connections

- **Author:** Monisa L.
- **Email:** [monisa.asi@gmail.com](mailto:monisa.asi@gmail.com)
- **LinkedIn:** [linkedin.com/in/monisa-l-333546366](https://www.linkedin.com/in/monisa-l-333546366)
- **GitHub Profile:** [github.com/Monisa-Analyst](https://github.com/Monisa-Analyst)
