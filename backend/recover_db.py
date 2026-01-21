import mysql.connector
from mysql.connector import Error
import configparser
import os
import hashlib

def recover_database():
    NEW_DB_NAME = 'debug_marathon_v2'
    print(f"Starting Database Recovery (Target: {NEW_DB_NAME})...")
    
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'db_config.ini')
    
    db_config = {
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "",
    }
    
    # Connect
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # 1. DROP (if exists) and CREATE new DB
        print(f"Deep cleaning: Dropping {NEW_DB_NAME} if exists...")
        cursor.execute(f"DROP DATABASE IF EXISTS {NEW_DB_NAME}")
        
        print(f"Creating {NEW_DB_NAME}...")
        cursor.execute(f"CREATE DATABASE {NEW_DB_NAME} DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.execute(f"USE {NEW_DB_NAME}")
        
        # 2. Import Schema (Dynamically replacing DB name)
        print("Importing Schema...")
        schema_path = os.path.join(os.path.dirname(__file__), 'debug_marathon_schema.sql')
        if os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                sql = f.read()
                
            # Replace DB name references
            sql = sql.replace('`debug_marathon`', f'`{NEW_DB_NAME}`')
            sql = sql.replace('USE debug_marathon', f'USE {NEW_DB_NAME}')
            # Note: The schema file has statements separated by ;
            # We must parse carefully or just run basic statements.
            
            statements = sql.split(';')
            for stmt in statements:
                stmt = stmt.strip()
                if stmt:
                    # Skip CREATE DATABASE / USE lines from the file itself if we already did them, 
                    # but replacing them ensures compatibility if they run.
                    try:
                        cursor.execute(stmt)
                    except Error as e:
                        # Ignore "database exists" errors if we just created it
                        if "database exists" not in str(e).lower():
                             print(f"Schema Warning: {e}")
            print("Schema imported.")
        else:
            print("Error: schema file not found.")

        # 3. Import Example Data
        print("Importing Example Data...")
        data_path = os.path.join(os.path.dirname(__file__), 'populate_example_data.sql')
        if os.path.exists(data_path):
            with open(data_path, 'r') as f:
                sql = f.read()
                
            sql = sql.replace('`debug_marathon`', f'`{NEW_DB_NAME}`')
            sql = sql.replace('USE debug_marathon', f'USE {NEW_DB_NAME}')
            
            statements = sql.split(';')
            for stmt in statements:
                stmt = stmt.strip()
                if stmt:
                    try:
                        cursor.execute(stmt)
                    except Error as e:
                        print(f"Data Warning: {e}")
            print("Example data imported.")

        # 4. Ensure 'admin' user
        print("Ensuring 'admin' user exists...")
        cursor.execute("SELECT * FROM users WHERE username='admin'")
        if not cursor.fetchone():
            pwd_hash = hashlib.sha256('admin'.encode()).hexdigest()
            query = """
                INSERT INTO users (username, email, password_hash, full_name, role, admin_status, status)
                VALUES ('admin', 'admin@debugmarathon.com', %s, 'Super Admin', 'admin', 'APPROVED', 'active')
            """
            cursor.execute(query, (pwd_hash,))
            print("Created user 'admin' with password 'admin'")

        conn.commit()
        print("SUCCESS! Database recovered to new instance.")
        
    except Error as e:
        print(f"Critical Error: {e}")
    finally:
         if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    recover_database()
