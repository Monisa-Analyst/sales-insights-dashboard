"""
test_system.py
Quick smoke tests to make sure the database, queries, and AI agent work.
Run: python src/test_system.py
"""

import os
import sqlite3
import pandas as pd
from ai_agent import SalesAIAgent

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "sales.db")


def check_tables():
    """make sure all tables exist and have data"""
    print("--- checking database tables ---")
    if not os.path.exists(DB):
        print(f"database not found at {DB}, run data_loader.py first")
        return False

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    print(f"found tables: {tables}")

    expected = ['customers', 'products', 'locations', 'orders', 'order_items']
    ok = True
    for name in expected:
        if name in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {name};")
            count = cursor.fetchone()[0]
            print(f"  {name}: {count} rows")
            if count == 0:
                print(f"  warning: {name} is empty!")
                ok = False
        else:
            print(f"  MISSING: {name}")
            ok = False

    conn.close()
    if ok:
        print("all tables look good\n")
    return ok


def check_queries():
    """run a test join to make sure the schema works"""
    print("--- testing sql queries ---")
    conn = sqlite3.connect(DB)

    sql = """
        SELECT c.customer_name,
               COUNT(DISTINCT o.order_id) AS orders_placed,
               SUM(oi.sales) AS total_sales,
               SUM(oi.profit) AS total_profit
        FROM customers c
        JOIN orders o ON c.customer_id = o.customer_id
        JOIN order_items oi ON o.order_id = oi.order_id
        GROUP BY c.customer_name
        ORDER BY total_sales DESC
        LIMIT 3;
    """

    try:
        df = pd.read_sql_query(sql, conn)
        print("join query ran successfully, top 3 customers:")
        for _, row in df.iterrows():
            print(f"  {row['customer_name']}: ${row['total_sales']:.2f} sales, ${row['total_profit']:.2f} profit")
        print("sql queries working\n")
        conn.close()
        return True
    except Exception as e:
        print(f"query failed: {e}\n")
        conn.close()
        return False


def check_agent():
    """test the ai agent's query translation"""
    print("--- testing ai agent ---")
    agent = SalesAIAgent()

    question = "What are the top 5 customers?"
    print(f"asking: '{question}'")

    sql = agent.translate_to_sql(question)
    print(f"generated sql:\n{sql}")

    if sql and "SELECT" in sql.upper():
        print("sql looks valid")
        df, err = agent.execute_query(sql)
        if err:
            print(f"execution error: {err}")
            return False
        else:
            print(f"got {len(df)} rows back")
            print("agent pipeline working\n")
            return True
    else:
        print("translation failed\n")
        return False


if __name__ == "__main__":
    db_ok = check_tables()
    sql_ok = check_queries() if db_ok else False
    ai_ok = check_agent() if db_ok else False

    print("=" * 40)
    if db_ok and sql_ok and ai_ok:
        print("all checks passed!")
    else:
        print("some checks failed, see above")
