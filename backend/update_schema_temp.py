import sqlite3
import os

DB_PATH = os.path.join(os.getcwd(), 'backend', 'debug_marathon.db')

def update_schema():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(users)")
    columns = [info[1] for info in cursor.fetchall()]
    print("Current columns:", columns)
    
    updates = [
        "ALTER TABLE users ADD COLUMN college TEXT",
        "ALTER TABLE users ADD COLUMN department TEXT",
        "ALTER TABLE users ADD COLUMN phone TEXT"
    ]
    
    for sql in updates:
        col_name = sql.split(" ADD COLUMN ")[1].split(" ")[0]
        if col_name not in columns:
            try:
                cursor.execute(sql)
                print(f"Executed: {sql}")
            except Exception as e:
                print(f"Error {sql}: {e}")
        else:
            print(f"Skipping {col_name} (already exists)")
            
    conn.commit()
    conn.close()
    print("Schema update complete.")

if __name__ == '__main__':
    update_schema()
