import os
import sqlite3
import pandas as pd
from dotenv import load_dotenv
import anthropic

# Load environment variables
load_dotenv()

# Database Path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "sales.db")

# Table schemas as context for the model
DB_SCHEMA_CONTEXT = """
Database Schema:
1. customers (
    customer_id VARCHAR(50) PRIMARY KEY,
    customer_name VARCHAR(255),
    segment VARCHAR(50)
)
2. products (
    product_id VARCHAR(50) PRIMARY KEY,
    product_name VARCHAR(255),
    category VARCHAR(100),
    sub_category VARCHAR(100)
)
3. locations (
    location_id INTEGER PRIMARY KEY,
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    postal_code VARCHAR(20),
    market VARCHAR(50),
    region VARCHAR(50)
)
4. orders (
    order_id VARCHAR(50) PRIMARY KEY,
    order_date DATE, -- format: 'YYYY-MM-DD' (e.g. '2014-03-15')
    ship_date DATE, -- format: 'YYYY-MM-DD'
    ship_mode VARCHAR(50),
    customer_id VARCHAR(50) REFERENCES customers(customer_id),
    location_id INTEGER REFERENCES locations(location_id),
    shipping_cost REAL,
    order_priority VARCHAR(20)
)
5. order_items (
    order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id VARCHAR(50) REFERENCES orders(order_id),
    product_id VARCHAR(50) REFERENCES products(product_id),
    sales REAL,
    quantity INTEGER,
    discount REAL,
    profit REAL
)

Join Logic:
- Join customers to orders using `orders.customer_id = customers.customer_id`
- Join locations to orders using `orders.location_id = locations.location_id`
- Join orders to order_items using `order_items.order_id = orders.order_id`
- Join products to order_items using `order_items.product_id = products.product_id`

Date Querying Rules for SQLite:
- To match a month (e.g., March): Use `SUBSTR(o.order_date, 6, 2) = '03'` or `o.order_date LIKE '%-03-%'`
- To match a year (e.g., 2014): Use `SUBSTR(o.order_date, 1, 4) = '2014'` or `o.order_date LIKE '2014-%'`
- To group by month: Use `SUBSTR(o.order_date, 1, 7)` to format as 'YYYY-MM'.
"""

class SalesAIAgent:
    def __init__(self):
        # Retrieve the API key from environment variables
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.initialized = False
        
        if self.api_key and self.api_key.strip() and not self.api_key.startswith("YOUR_"):
            try:
                self.client = anthropic.Anthropic(api_key=self.api_key)
                self.initialized = True
                print("[+] Anthropic Claude API client configured successfully.")
            except Exception as e:
                print(f"[-] Failed to configure Anthropic Claude API client: {e}")
        else:
            print("[-] ANTHROPIC_API_KEY not found or default placeholder. AI queries will operate in simulation/mock mode.")

    def _clean_sql_query(self, raw_sql):
        """Remove markdown syntax wrapper (```sql ... ```) if returned by LLM."""
        sql = raw_sql.strip()
        # Remove code blocks if present
        if sql.startswith("```"):
            lines = sql.split("\n")
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            sql = "\n".join(lines).strip()
        # Remove any leading 'sql' keyword
        if sql.lower().startswith("sql"):
            sql = sql[3:].strip()
        # Remove trailing semicolons
        if sql.endswith(";"):
            sql = sql[:-1].strip()
        return sql

    def translate_to_sql(self, question):
        """Generate SQL query from natural language question using Claude API."""
        if not self.initialized:
            return self._mock_sql_generator(question)
            
        system_instruction = (
            "You are an expert SQL analyst. Write standard SQL (SQLite syntax) to answer the user's question.\n"
            f"{DB_SCHEMA_CONTEXT}\n"
            "Rules:\n"
            "1. Output ONLY the raw SQL query. Do not include markdown blocks, explanation, or code styling.\n"
            "2. Ensure all column names and table names match the schema exactly.\n"
            "3. Use appropriate joins, groupings, and filters.\n"
            "4. Always format numeric fields (sales, profit) nicely in summaries, but use exact column names in calculations.\n"
            "5. Limit long lists to 5-10 rows unless the user asks for more."
        )
        
        try:
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                system=system_instruction,
                messages=[
                    {"role": "user", "content": f"Question: {question}"}
                ]
            )
            sql_query = self._clean_sql_query(message.content[0].text)
            return sql_query
        except Exception as e:
            print(f"[-] Claude API SQL generation failed: {e}. Falling back to simulation.")
            return self._mock_sql_generator(question)

    def execute_query(self, sql_query):
        """Execute the SQL query on SQLite and return a pandas DataFrame."""
        if not os.path.exists(DB_PATH):
            return None, "Error: Local SQLite database not found. Please run the data loader first."
            
        try:
            conn = sqlite3.connect(DB_PATH)
            df = pd.read_sql_query(sql_query, conn)
            conn.close()
            return df, None
        except Exception as e:
            return None, str(e)

    def generate_explanation(self, question, sql_query, result_df):
        """Generate a natural language explanation of the query results using Claude."""
        if not self.initialized:
            return self._mock_explanation_generator(question, result_df)
            
        if result_df is None or result_df.empty:
            return "No data was returned for this query. It's possible there are no matching records."

        data_summary = result_df.to_string(index=False)
        
        prompt = (
            f"You are a professional business intelligence analyst.\n"
            f"The user asked: '{question}'\n"
            f"You ran this SQL query:\n```sql\n{sql_query}\n```\n"
            f"And got this database output:\n{data_summary}\n\n"
            f"Write a concise, professional summary explaining the result. Highlight key takeaways, "
            f"compare values if necessary, and use formatted bold text, lists, or tables as appropriate."
        )
        
        try:
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return message.content[0].text.strip()
        except Exception as e:
            print(f"[-] Claude API explanation failed: {e}. Returning default summary.")
            return self._mock_explanation_generator(question, result_df)

    def _mock_sql_generator(self, question):
        """Fallback mock generator if Claude API key is missing."""
        q_lower = question.lower()
        if "top 5 customers" in q_lower or "best customers" in q_lower:
            return (
                "SELECT c.customer_name, SUM(oi.sales) AS total_sales, SUM(oi.profit) AS total_profit\n"
                "FROM customers c\n"
                "JOIN orders o ON c.customer_id = o.customer_id\n"
                "JOIN order_items oi ON o.order_id = oi.order_id\n"
                "GROUP BY c.customer_name\n"
                "ORDER BY total_sales DESC\n"
                "LIMIT 5"
            )
        elif "sales in march" in q_lower or "march sales" in q_lower:
            return (
                "SELECT SUBSTR(o.order_date, 1, 7) AS sales_month, SUM(oi.sales) AS total_sales, SUM(oi.profit) AS total_profit\n"
                "FROM orders o\n"
                "JOIN order_items oi ON o.order_id = oi.order_id\n"
                "WHERE SUBSTR(o.order_date, 6, 2) = '03'\n"
                "GROUP BY sales_month"
            )
        elif "best selling product" in q_lower or "top product" in q_lower:
            return (
                "SELECT p.product_name, SUM(oi.quantity) AS quantity_sold, SUM(oi.sales) AS total_sales\n"
                "FROM products p\n"
                "JOIN order_items oi ON p.product_id = oi.product_id\n"
                "GROUP BY p.product_name\n"
                "ORDER BY quantity_sold DESC\n"
                "LIMIT 5"
            )
        else:
            # General fallback query
            return (
                "SELECT o.order_date, SUM(oi.sales) AS daily_sales, SUM(oi.profit) AS daily_profit\n"
                "FROM orders o\n"
                "JOIN order_items oi ON o.order_id = oi.order_id\n"
                "GROUP BY o.order_date\n"
                "ORDER BY o.order_date DESC\n"
                "LIMIT 10"
            )

    def _mock_explanation_generator(self, question, result_df):
        """Fallback mock explanation generator if Claude API key is missing."""
        if result_df is None or result_df.empty:
            return "No data was returned."
            
        columns = result_df.columns.tolist()
        num_rows = len(result_df)
        
        summary = (
            f"**Query Results Analysis (Simulated Mode)**\n\n"
            f"Here are the top results answering your question: *\"{question}\"*\n\n"
        )
        
        for idx, row in result_df.iterrows():
            row_desc = " - " + ", ".join([f"**{col}**: {row[col]}" for col in columns])
            summary += row_desc + "\n"
            
        summary += (
            f"\n*Note: To enable active AI reflections and summaries, configure your `ANTHROPIC_API_KEY` in the `.env` file.*"
        )
        return summary
