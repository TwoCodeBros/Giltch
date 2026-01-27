
from db_connection import db_manager

try:
    cols = db_manager.execute_query("SHOW COLUMNS FROM questions")
    print("--- QUESTIONS COLUMNS ---")
    pad = 20
    print(f"{'Field':<{pad}} | {'Type':<{pad}}")
    print("-" * 50)
    for c in cols:
        print(f"{c['Field']:<{pad}} | {str(c['Type']):<{pad}}")
except Exception as e:
    print(e)
