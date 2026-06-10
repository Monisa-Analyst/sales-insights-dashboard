"""
ai_agent.py
Handles the AI side - takes a user question, converts to SQL using Gemini,
runs it, explains results. Falls back to smart pattern matching if no API key.
"""

import os, re
import sqlite3
import pandas as pd
from dotenv import load_dotenv

# load .env from project root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

try:
    import google.generativeai as genai
except ImportError:
    genai = None

DB_FILE = os.path.join(ROOT, "data", "sales.db")

SCHEMA_INFO = """
Tables:
customers(customer_id, customer_name, segment)
products(product_id, product_name, category, sub_category)
locations(location_id, city, state, country, postal_code, market, region)
orders(order_id, order_date, ship_date, ship_mode, customer_id, location_id, shipping_cost, order_priority)
order_items(order_item_id, order_id, product_id, sales, quantity, discount, profit)

Joins:
- orders.customer_id -> customers.customer_id
- orders.location_id -> locations.location_id
- order_items.order_id -> orders.order_id
- order_items.product_id -> products.product_id

Dates are strings in YYYY-MM-DD format.
- filter month: SUBSTR(order_date, 6, 2) = '03'
- filter year: SUBSTR(order_date, 1, 4) = '2014'
- group monthly: SUBSTR(order_date, 1, 7)
"""

MONTH_MAP = {
    'january': '01', 'february': '02', 'march': '03', 'april': '04',
    'may': '05', 'june': '06', 'july': '07', 'august': '08',
    'september': '09', 'october': '10', 'november': '11', 'december': '12',
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
    'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09',
    'oct': '10', 'nov': '11', 'dec': '12'
}


def _extract_year(text):
    """pull a 4-digit year from the question, if any"""
    match = re.search(r'\b(20\d{2})\b', text)
    return match.group(1) if match else None

def _extract_month(text):
    """pull a month name from the question, if any"""
    for name, num in MONTH_MAP.items():
        if name in text.lower():
            return num
    return None

def _extract_limit(text):
    """pull 'top N' from the question"""
    match = re.search(r'top\s+(\d+)', text.lower())
    return int(match.group(1)) if match else 5


class SalesAIAgent:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.initialized = False

        if genai and self.api_key and self.api_key.strip():
            try:
                genai.configure(api_key=self.api_key)
                self.initialized = True
                print("gemini api connected")
            except Exception as e:
                print(f"couldn't set up gemini: {e}")
        else:
            print("no api key - demo mode")

    def _strip_markdown(self, raw):
        """clean up gemini output - remove ```sql blocks etc"""
        sql = raw.strip()
        if sql.startswith("```"):
            lines = sql.split("\n")
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            sql = "\n".join(lines).strip()
        if sql.lower().startswith("sql"):
            sql = sql[3:].strip()
        if sql.endswith(";"):
            sql = sql[:-1].strip()
        return sql

    def translate_to_sql(self, question):
        """convert question to SQL - uses gemini if available, otherwise smart fallback"""
        if not self.initialized:
            return self._smart_fallback(question)

        instructions = (
            "You are a SQL expert. Write SQLite SQL to answer the user's question.\n"
            f"{SCHEMA_INFO}\n"
            "Rules:\n"
            "- Output ONLY raw SQL, no markdown or explanation\n"
            "- Use exact column/table names from schema\n"
            "- Limit to 10 rows unless asked otherwise\n"
            "- Use proper joins"
        )

        try:
            model = genai.GenerativeModel(
                model_name="gemini-2.0-flash",
                system_instruction=instructions
            )
            resp = model.generate_content(f"Question: {question}")
            return self._strip_markdown(resp.text)
        except Exception as e:
            print(f"gemini failed: {e}, using fallback")
            return self._smart_fallback(question)

    def execute_query(self, sql):
        """run sql on the database"""
        if not os.path.exists(DB_FILE):
            return None, "database not found - run data_loader.py first"
        try:
            conn = sqlite3.connect(DB_FILE)
            result = pd.read_sql_query(sql, conn)
            conn.close()
            return result, None
        except Exception as e:
            return None, str(e)

    def generate_explanation(self, question, sql, df):
        """explain results using gemini or fallback"""
        if not self.initialized:
            return self._fallback_explanation(question, df)

        if df is None or df.empty:
            return "No results for this query."

        prompt = (
            f"You're a business analyst. User asked: '{question}'\n"
            f"SQL:\n```sql\n{sql}\n```\n"
            f"Results:\n{df.to_string(index=False)}\n\n"
            f"Give a short clear summary. Highlight key findings. Use bold and bullet points."
        )

        try:
            model = genai.GenerativeModel("gemini-2.0-flash")
            resp = model.generate_content(prompt)
            return resp.text.strip()
        except Exception as e:
            print(f"explanation failed: {e}")
            return self._fallback_explanation(question, df)

    def _smart_fallback(self, question):
        """generate sql by parsing the question - handles years, months, limits"""
        q = question.lower()
        year = _extract_year(question)
        month = _extract_month(question)
        limit = _extract_limit(question)

        # build optional date filters
        date_filters = []
        if year:
            date_filters.append(f"SUBSTR(o.order_date, 1, 4) = '{year}'")
        if month:
            date_filters.append(f"SUBSTR(o.order_date, 6, 2) = '{month}'")

        date_where = " AND ".join(date_filters)

        # top customers
        if any(kw in q for kw in ["top", "best", "highest"]) and "customer" in q:
            where = f"WHERE {date_where}" if date_where else ""
            return (
                f"SELECT c.customer_name, SUM(oi.sales) AS total_sales, SUM(oi.profit) AS total_profit\n"
                f"FROM customers c\n"
                f"JOIN orders o ON c.customer_id = o.customer_id\n"
                f"JOIN order_items oi ON o.order_id = oi.order_id\n"
                f"{where}\n"
                f"GROUP BY c.customer_name\n"
                f"ORDER BY total_sales DESC\n"
                f"LIMIT {limit}"
            )

        # sales in a specific month/year
        elif "sales" in q and (month or year):
            where_parts = []
            if month:
                where_parts.append(f"SUBSTR(o.order_date, 6, 2) = '{month}'")
            if year:
                where_parts.append(f"SUBSTR(o.order_date, 1, 4) = '{year}'")
            where = "WHERE " + " AND ".join(where_parts)
            return (
                f"SELECT SUBSTR(o.order_date, 1, 7) AS month, SUM(oi.sales) AS total_sales, SUM(oi.profit) AS total_profit\n"
                f"FROM orders o\n"
                f"JOIN order_items oi ON o.order_id = oi.order_id\n"
                f"{where}\n"
                f"GROUP BY month\n"
                f"ORDER BY month"
            )

        # best selling product
        elif "product" in q or "selling" in q:
            where = f"WHERE {date_where}" if date_where else ""
            return (
                f"SELECT p.product_name, SUM(oi.quantity) AS qty_sold, SUM(oi.sales) AS total_sales\n"
                f"FROM products p\n"
                f"JOIN order_items oi ON p.product_id = oi.product_id\n"
                f"JOIN orders o ON oi.order_id = o.order_id\n"
                f"{where}\n"
                f"GROUP BY p.product_name\n"
                f"ORDER BY qty_sold DESC\n"
                f"LIMIT {limit}"
            )

        # profit by market/region
        elif "profit" in q and ("market" in q or "region" in q):
            where = f"WHERE {date_where}" if date_where else ""
            return (
                f"SELECT l.market, SUM(oi.sales) AS total_sales, SUM(oi.profit) AS total_profit\n"
                f"FROM locations l\n"
                f"JOIN orders o ON l.location_id = o.location_id\n"
                f"JOIN order_items oi ON o.order_id = oi.order_id\n"
                f"{where}\n"
                f"GROUP BY l.market\n"
                f"ORDER BY total_profit DESC"
            )

        # revenue/growth by year or month
        elif "revenue" in q or "growth" in q:
            if year:
                return (
                    f"SELECT SUBSTR(o.order_date, 1, 7) AS month, SUM(oi.sales) AS revenue, SUM(oi.profit) AS profit\n"
                    f"FROM orders o\n"
                    f"JOIN order_items oi ON o.order_id = oi.order_id\n"
                    f"WHERE SUBSTR(o.order_date, 1, 4) = '{year}'\n"
                    f"GROUP BY month\n"
                    f"ORDER BY month"
                )
            else:
                return (
                    f"SELECT SUBSTR(o.order_date, 1, 4) AS year, SUM(oi.sales) AS revenue, SUM(oi.profit) AS profit\n"
                    f"FROM orders o\n"
                    f"JOIN order_items oi ON o.order_id = oi.order_id\n"
                    f"GROUP BY year\n"
                    f"ORDER BY year"
                )

        # generic fallback with date filters
        else:
            where = f"WHERE {date_where}" if date_where else ""
            return (
                f"SELECT o.order_date, SUM(oi.sales) AS daily_sales, SUM(oi.profit) AS daily_profit\n"
                f"FROM orders o\n"
                f"JOIN order_items oi ON o.order_id = oi.order_id\n"
                f"{where}\n"
                f"GROUP BY o.order_date\n"
                f"ORDER BY o.order_date DESC\n"
                f"LIMIT 10"
            )

    def _fallback_explanation(self, question, df):
        """text summary when AI analysis isn't available"""
        if df is None or df.empty:
            return "No data returned."

        cols = df.columns.tolist()
        lines = [f"**Results for:** *\"{question}\"*\n"]
        for _, row in df.iterrows():
            parts = [f"**{c}**: {row[c]}" for c in cols]
            lines.append("- " + ", ".join(parts))

        if self.initialized:
            lines.append(f"\n*AI analysis temporarily unavailable (rate limit). Results generated using built-in query engine.*")
        else:
            lines.append(f"\n*Add GEMINI_API_KEY to .env for AI-powered analysis.*")
        return "\n".join(lines)
