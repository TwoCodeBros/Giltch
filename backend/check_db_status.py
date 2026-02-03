
from db_connection import db_manager, USE_SQLITE
import os

print("-" * 50)
print("DATABASE CONNECTION STATUS CHECK")
print("-" * 50)

if USE_SQLITE:
    print("WARNING: Application is using SQLite (Fallback mode).")
    print(f"Database File: {os.path.abspath('debug_marathon.db')}")
else:
    print("SUCCESS: Application is using MySQL.")
    try:
        conn = db_manager.get_connection()
        if conn:
            print("MySQL Connection: ESTABLISHED")
            cursor = conn.cursor()
            cursor.execute("SELECT DATABASE()")
            db_name = cursor.fetchone()[0]
            print(f"Connected to Database: {db_name}")
            
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            print(f"User Count in MySQL: {count}")
            
            print("-" * 30)
            print("Sample Users:")
            cursor.execute("SELECT user_id, username, email, role FROM users LIMIT 5")
            users = cursor.fetchall()
            for u in users:
                print(f"ID: {u[0]} | User: {u[1]} | Role: {u[3]}")
                
            conn.close()
        else:
             print("MySQL Connection: FAILED (Pool returned None)")
    except Exception as e:
        print(f"MySQL Connection Error: {e}")

print("-" * 50)
