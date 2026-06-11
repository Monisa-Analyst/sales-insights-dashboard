# AI-Powered Sales Analytics Assistant

A complete end-to-end Business Intelligence (BI) and AI analytics application. This project cleans and normalizes a high-volume sales dataset (~50,000+ records), loads it into a relational database, performs advanced SQL calculations (CTEs, Joins, Window Functions), outlines a Power BI data model, and runs a **Streamlit Web Application** featuring an **AI Query Assistant** that translates natural language questions into database-executable SQL using the **Gemini API**.

---

## 🚀 Key Features

*   **Data Engineering**: Programmatically downloads and cleans the Global Superstore sales dataset (combining and standardizing dates, numeric strings, and handling missing items) and normalizes it from a flat CSV format into a normalized star schema (`customers`, `products`, `locations`, `orders`, and `order_items`).
*   **Relational Database**: Populates a local SQLite database with relational indexes for fast execution, and provides production-ready schema scripts compatible with PostgreSQL and MySQL.
*   **Advanced Analytical SQL**: Implements business queries using SQL Joins, Common Table Expressions (CTEs), and Window Functions (calculating MoM growth, category rankings, quarterly purchase retention cohorts, and storefront funnel stats).
*   **Power BI Integration**: Includes a database-to-Power BI schema relationship map, recommended DAX measures, and a custom dark-mode UI layout mockup.
*   **Executive Streamlit App**: A modern, dark-themed dashboard showing:
    *   Dynamic filters (Year, Market Region, Segment) that update KPIs and charts.
    *   Interactive Plotly visual graphs (Sales/Profit MoM trends, Category breakdowns, Top Customers, Best-selling items).
    *   **Cohorts & Funnels**: Interactive customer purchase retention cohorts heatmap and web clickstream conversion funnel chart.
*   **AI SQL Assistant**: Integrates with the Google Gemini API to translate natural language user questions (e.g., *"Show me the top 5 customers"* or *"What were the sales in March 2014?"*) into database queries, executes them, and returns tabular data accompanied by an analyst-grade written summary.

---

## 📐 Relational Database Schema

The flat dataset is normalized into the following relational structure:

```mermaid
erDiagram
    customers {
        varchar customer_id PK
        varchar customer_name
        varchar segment
    }
    products {
        varchar product_id PK
        varchar product_name
        varchar category
        varchar sub_category
    }
    locations {
        integer location_id PK
        varchar city
        varchar state
        varchar country
        varchar postal_code
        varchar market
        varchar region
    }
    orders {
        varchar order_id PK
        varchar order_date
        varchar ship_date
        varchar ship_mode
        varchar customer_id FK
        integer location_id FK
        float shipping_cost
        varchar order_priority
    }
    order_items {
        integer order_item_id PK
        varchar order_id FK
        varchar product_id FK
        float sales
        integer quantity
        float discount
        float profit
    }

    customers ||--o{ orders : "places"
    locations ||--o{ orders : "shipped_to"
    orders ||--|{ order_items : "contains"
    products ||--o{ order_items : "ordered_in"
```

---

## 📂 Project Structure

```
ai-powered-sales-analytics-assistant/
│
├── data/
│   ├── raw_sales_data.csv       # Original downloaded dataset (~13MB)
│   ├── cleaned_*.csv            # Normalized dimension/fact CSV files
│   └── sales.db                 # Local SQLite database
│
├── sql/
│   ├── schema.sql               # Production PostgreSQL/MySQL schema definitions
│   └── queries.sql              # Core analytical business queries
│
├── src/
│   ├── data_loader.py           # Ingestion, cleaning, and normalization script
│   ├── ai_agent.py              # LLM-to-SQL agent using Gemini API
│   ├── app.py                   # Streamlit multi-page dashboard application
│   └── test_system.py           # Automated unit/integration tests
│
├── power_bi/
│   ├── mockups/
│   │   └── sales_dashboard_mockup.png # Dashboard visualization mockup
│   └── data_model_guide.md      # Data model mapping and DAX calculations
│
├── .env.example                 # Template environment configuration
├── requirements.txt             # Python packages
└── README.md                    # This document
```

---

## 💡 Advanced SQL Query Showcases

### 1. Quarterly Customer Purchase Retention (CTEs & Elapsed Quarters math)
Identifies quarterly signup cohorts and tracks customer repeat purchase retention over subsequent quarters:

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

### 2. Storefront Clickstream & Conversion Funnel (CTEs & Union)
Aggregates digital shop visitors and estimates drop-off value relative to actual database purchases:

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

---

## 🛠️ Getting Started

### Prerequisites

Ensure you have Python 3.10+ and Git installed on your system.

### 1. Installation

Clone this repository or navigate into the project directory and install the dependencies:

```bash
pip install -r requirements.txt
```

### 2. Ingest and Normalize Data

Execute the data loader script to download the Global Superstore CSV, clean it, split it into relational tables, and load it into a local SQLite database:

```bash
python src/data_loader.py
```

### 3. Set Up API Credentials

Copy the `.env.example` file to `.env` and fill in your Gemini API key:

```env
GEMINI_API_KEY=your_gemini_api_key
```

> **Note**: If `GEMINI_API_KEY` is not provided, the Streamlit AI Query Assistant will run in an offline **Simulation Mode** using pre-configured mock questions to showcase features.

### 4. Run Automated System Tests

Verify that database tables, schemas, relations, and the AI agent translation loop are functioning correctly:

```bash
python src/test_system.py
```

### 5. Launch the Streamlit Web App

Start the dashboard web application:

```bash
streamlit run src/app.py
```

Open `http://localhost:8501` in your browser.

---

## 💻 Power BI Visualization Dashboard

The normalized files saved in the `data/` folder are formatted and ready for import. Replicate the visual mapping described in the [Power BI Guide](power_bi/data_model_guide.md) to build the dashboard.

Below is the visual mockup of the completed Power BI Dashboard:

![Power BI Sales Dashboard Mockup](power_bi/mockups/sales_dashboard_mockup.png)
