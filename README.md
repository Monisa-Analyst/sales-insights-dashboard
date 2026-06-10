# Sales Analytics Dashboard

👉 **[Launch Live Web Application](https://share.streamlit.io/monisa-analyst/sales-insights-dashboard/main/src/app.py)**

An interactive sales analytics dashboard built with Streamlit that lets you explore e-commerce sales data through visualizations and ask questions in plain English using Google's Gemini API.

I built this project to practice working with real-world messy data, building ETL pipelines, writing analytical SQL, and integrating LLMs into a practical application.

## What it does

- **Data pipeline** — Downloads the Global Superstore dataset (~50k records), cleans it up (parsing dates, handling currency strings, filling gaps), and normalizes it into a proper star schema with 5 relational tables.
- **SQLite database** — Everything gets loaded into a local SQLite DB with indexes for fast queries. Also generates cleaned CSVs ready for Power BI import.
- **Interactive dashboard** — Streamlit app with filterable KPI cards, monthly trend charts, category breakdowns, top customers, and market comparisons. All built with Plotly.
- **AI query assistant** — Type a question like "who are the top 5 customers in 2015?" and Gemini converts it to SQL, runs it, and explains the results. Falls back to a smart pattern-matching engine when the API isn't available.
- **Analytical SQL** — Includes standalone SQL scripts demonstrating joins, CTEs, window functions (LAG for MoM growth, DENSE_RANK for rankings, running totals).
- **Power BI ready** — Comes with a data model guide and DAX measure definitions if you want to recreate the dashboard in Power BI.

## Tech stack

| Layer | Tools |
|-------|-------|
| Frontend | Streamlit, Plotly |
| Backend | Python, SQLite |
| AI/NLP | Google Gemini API |
| Data | Pandas, SQLAlchemy |
| SQL | Joins, CTEs, Window Functions |

## Database schema

The raw CSV gets normalized into a star schema:

```
customers ──┐
            ├── orders ──── order_items ──── products
locations ──┘
```

- `customers` (customer_id, customer_name, segment)
- `products` (product_id, product_name, category, sub_category)
- `locations` (location_id, city, state, country, market, region)
- `orders` (order_id, order_date, ship_date, ship_mode, customer_id, location_id)
- `order_items` (order_item_id, order_id, product_id, sales, quantity, discount, profit)

## Project structure

```
├── data/                  # raw csv, cleaned csvs, sqlite db
├── sql/
│   ├── schema.sql         # production-ready schema (PostgreSQL/MySQL)
│   └── queries.sql        # analytical queries with CTEs & window functions
├── src/
│   ├── data_loader.py     # ETL pipeline
│   ├── ai_agent.py        # Gemini-powered SQL translator
│   ├── app.py             # Streamlit dashboard
│   └── test_system.py     # automated tests
├── power_bi/
│   └── data_model_guide.md
├── requirements.txt
└── .env.example
```

## Getting started

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Load the data

This downloads the dataset, cleans it, and builds the SQLite database:

```bash
python src/data_loader.py
```

### 3. Set up Gemini API (optional)

Copy `.env.example` to `.env` and add your API key:

```
GEMINI_API_KEY=your_key_here
```

You can get a free key from [Google AI Studio](https://aistudio.google.com/apikey). The app works without it too — the AI assistant falls back to a built-in query engine.

### 4. Run the app

```bash
streamlit run src/app.py
```

Open http://localhost:8501 in your browser.

### 5. Run tests (optional)

```bash
python src/test_system.py
```

Verifies the database tables, SQL queries, and AI agent pipeline.

## SQL highlights

Some of the analytical queries included:

- **Month-over-month growth** using `LAG()` window function
- **Running totals** with `SUM() OVER (ORDER BY ...)`
- **Category rankings** using `DENSE_RANK() OVER (PARTITION BY ...)`
- **Multi-table joins** across the full star schema
- **CTEs** for readable, modular query logic

## License

MIT
