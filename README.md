# Sales Insights & AI Query Assistant

🌐 **[Live Web Application](https://share.streamlit.io/monisa-analyst/sales-insights-dashboard/main/src/app.py)**  
*Explore the live Streamlit dashboard directly in your browser. If the database is not initialized, it builds automatically from raw sales records on first run.*

---

## Project Overview

This is an end-to-end data engineering and business intelligence project. It normalizes a flat e-commerce transaction dataset (~50,000 records) into a robust SQL database, provides interactive visual insights, and integrates a conversational AI assistant that translates natural language queries into executable SQLite SQL.

I built this project to demonstrate core competencies in:
1.  **Data Cleaning & ETL Pipelines:** Parsing and cleaning real-world transaction logs using Python and Pandas.
2.  **Relational Database Design:** Normalizing flat file databases into a clean star schema with relational integrity and indexes.
3.  **Analytical SQL:** Querying data using complex joins, subqueries, Common Table Expressions (CTEs), and window functions.
4.  **Generative AI Integration:** Using the Gemini API to build a natural language interface for data querying.
5.  **Interactive Visualizations:** Designing interactive dashboards using Streamlit and Plotly.

---

## Tech Stack & Tools

*   **Frontend & UI:** Streamlit (Custom HSL Dark-Mode theme styling)
*   **Data Visualization:** Plotly Express & Plotly Graph Objects
*   **Database:** SQLite (via SQLAlchemy and standard sqlite3)
*   **AI/NLP:** Google Gemini API (`gemini-2.0-flash`)
*   **Data Pipeline & Analysis:** Python 3.11+, Pandas, NumPy

---

## Database Design & Star Schema

The raw dataset contains flat records of transaction history. To optimize query performance and data organization, the dataset is normalized into a **Star Schema** consisting of 4 Dimension tables and 1 Fact table:

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

### Table Definitions

*   **`customers` (Dimension):** `customer_id` (PK), `customer_name`, `segment`
*   **`products` (Dimension):** `product_id` (PK), `product_name`, `category`, `sub_category`
*   **`locations` (Dimension):** `location_id` (PK), `country`, `market`, `region`, `state`, `city`, `postal_code`
*   **`orders` (Dimension):** `order_id` (PK), `order_date`, `ship_date`, `ship_mode`, `customer_id` (FK), `location_id` (FK), `shipping_cost`, `order_priority`
*   **`order_items` (Fact):** `order_item_id` (PK), `order_id` (FK), `product_id` (FK), `sales`, `quantity`, `discount`, `profit`

---

## Key Features

### 1. Automated ETL Pipeline (`src/data_loader.py`)
- Programmatically downloads the Global Superstore CSV.
- Parses dates and handles currency formatting, negative numbers represented by parentheses, and missing keys.
- Deduplicates and splits records to form the relational schema tables.
- Exports cleaned CSVs (ready for Power BI imports) and populates the SQLite database with database indexes for fast query speeds.

### 2. Analytical Dashboard (`src/app.py`)
- **Key KPIs:** Real-time metrics tracking Revenue, Profits, Net Margins, and Customer Counts.
- **Visual Trends:** Line charts with shaded area curves showing sales and profits over time.
- **Segment Breakdown:** Donut charts highlighting product category distributions.
- **Performance Tables:** Horizontal bar charts plotting top customers, popular products, and revenue splits across geographical markets.

### 3. AI Query Assistant (`src/ai_agent.py`)
- Translates conversational questions (e.g. *"What was the revenue growth in 2014?"*) into SQLite-compliant queries.
- Connects to the Gemini API using `system_instruction` settings specifying database schemas and rules.
- **Smart Fallback Engine:** If the API key is missing or hits a quota limit (e.g., HTTP 429), the assistant falls back to a regex parser that extracts keywords (years, months, customer names, limit ranges) and matches them to SQL templates.
- Explains the query results in simple, business-friendly bullet points.

---

## Analytical SQL Examples (`sql/queries.sql`)

The project includes pre-built analytical scripts to demonstrate advanced SQL queries:

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
       ROUND(((total_sales - LAG(total_sales, 1) OVER (ORDER BY month)) / LAG(total_sales, 1) OVER (ORDER BY month)) * 100, 2) AS mom_growth_pct
FROM MonthlySales;
```

### Top 5 Performing Customers per Segment
```sql
WITH CustomerSpend AS (
    SELECT c.customer_name,
           c.segment,
           SUM(oi.sales) AS total_spent,
           DENSE_RANK() OVER (PARTITION BY c.segment ORDER BY SUM(oi.sales) DESC) as rank
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    JOIN order_items oi ON o.order_id = oi.order_id
    GROUP BY c.customer_name, c.segment
)
SELECT customer_name, segment, total_spent
FROM CustomerSpend
WHERE rank <= 5;
```

---

## Local Setup & Installation

### 1. Prerequisites
Ensure you have Python 3.11 or later installed.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Build the Database
Run the ingestion and ETL script to download the source dataset and create the local SQLite database:
```bash
python src/data_loader.py
```

### 4. Configure API Keys (Optional)
Copy `.env.example` to `.env` and add your Google Gemini API Key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```
*Note: If no API key is specified, the application will run using the smart regex fallback query parser.*

### 5. Launch the Dashboard
```bash
streamlit run src/app.py
```
Open `http://localhost:8501` in your browser.

---

## Project Structure

```
├── data/                      # Raw datasets, cleaned tables, and SQLite DB
├── sql/
│   ├── schema.sql             # SQL Schema definition scripts
│   └── queries.sql            # Core analytical business queries
├── src/
│   ├── data_loader.py         # Ingestion, cleaning, and normalization script
│   ├── ai_agent.py            # Natural Language SQL engine using Gemini API
│   ├── app.py                 # Streamlit analytical dashboard
│   └── test_system.py         # Automated smoke tests
├── power_bi/
│   └── data_model_guide.md    # Power BI modeling reference guide
├── requirements.txt           # Python packages list
└── README.md                  # Project documentation
```

---

## License

This project is licensed under the MIT License.
