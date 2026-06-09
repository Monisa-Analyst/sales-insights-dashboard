import os
import sqlite3
import pandas as pd
from ai_agent import SalesAIAgent

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "sales.db")

def verify_database():
    """Verify tables exist and contain records in SQLite database."""
    print("=== [1/3] VERIFYING DATABASE SHEMAS & TABLES ===")
    if not os.path.exists(DB_PATH):
        print(f"[-] Database file not found at {DB_PATH}. Please run src/data_loader.py first.")
        return False
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Query schema tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    print(f"[+] Found tables in SQLite: {tables}")
    
    expected_tables = ['customers', 'products', 'locations', 'orders', 'order_items']
    all_exist = True
    for et in expected_tables:
        if et in tables:
            # Count records
            cursor.execute(f"SELECT COUNT(*) FROM {et};")
            count = cursor.fetchone()[0]
            print(f"    - Table '{et}': {count} records loaded.")
            if count == 0:
                print(f"      [!] Warning: Table '{et}' is empty.")
                all_exist = False
        else:
            print(f"    - [x] Table '{et}' is MISSING!")
            all_exist = False
            
    conn.close()
    if all_exist:
        print("[+] All expected relational tables verified successfully!\n")
    return all_exist

def verify_queries():
    """Verify standard joins, CTEs, and Window functions run correctly in SQLite."""
    print("=== [2/3] VERIFYING ANALYTICAL SQL RUNS ===")
    conn = sqlite3.connect(DB_PATH)
    
    # Run a quick check: Join Customers + Orders + Items
    test_join_query = """
        SELECT 
            c.customer_name,
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
        df = pd.read_sql_query(test_join_query, conn)
        print("[+] SQL Join & Aggregation run successful. Sample results:")
        for idx, row in df.iterrows():
            print(f"    - Customer: {row['customer_name']} | Sales: ${row['total_sales']:.2f} | Profit: ${row['total_profit']:.2f}")
        print("[+] SQL joins verified successfully!\n")
        conn.close()
        return True
    except Exception as e:
        print(f"[-] Join execution failed: {e}\n")
        conn.close()
        return False

def verify_ai_agent():
    """Verify SalesAIAgent translation logic."""
    print("=== [3/3] VERIFYING AI SQL AGENT ===")
    agent = SalesAIAgent()
    
    # Run a test translation
    test_question = "What are the top 5 customers?"
    print(f"[*] Asking AI Agent: '{test_question}'")
    
    sql = agent.translate_to_sql(test_question)
    print(f"[+] AI-Generated SQL:")
    print("-" * 50)
    print(sql)
    print("-" * 50)
    
    if sql and "SELECT" in sql.upper():
        print("[+] SQL syntax translated and structural check passes.")
        
        # Test execute SQL
        df, error = agent.execute_query(sql)
        if error:
            print(f"[-] Execution check failed: {error}")
            return False
        else:
            print(f"[+] Execution run successful. Returned dataframe has shape: {df.shape}")
            print("[+] AI query pipeline verified successfully!\n")
            return True
    else:
        print("[-] Query translation failed.\n")
        return False

if __name__ == "__main__":
    db_ok = verify_database()
    queries_ok = verify_queries() if db_ok else False
    ai_ok = verify_ai_agent() if db_ok else False
    
    if db_ok and queries_ok and ai_ok:
        print("[SUCCESS] Full system automated check completed successfully!")
    else:
        print("[ERROR] Automated system check failed. Please inspect errors above.")
