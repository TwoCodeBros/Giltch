import mysql.connector
import hashlib
import configparser
import os

def check_admin():
    print("Verifying Admin User in debug_marathon_v2...")
    
    # 1. Read Config to sure we are checking what the APP is checking
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'db_config.ini')
    config.read(config_path)
    db_name = config['mysql']['database']
    print(f"Configured Database: {db_name}")

    try:
        conn = mysql.connector.connect(
            user='root', 
            password='', 
            host='localhost', 
            database=db_name
        )
        cursor = conn.cursor(dictionary=True)
        
        # 2. Check Admin
        cursor.execute("SELECT * FROM users WHERE username='admin'")
        user = cursor.fetchone()
        
        if user:
            print(f"User 'admin' FOUND.")
            print(f"Role: {user['role']}")
            print(f"Admin Status: {user['admin_status']}")
            
            # 3. Check Hash
            input_pass = 'admin'
            calc_hash = hashlib.sha256(input_pass.encode()).hexdigest()
            db_hash = user['password_hash']
            
            print(f"Calculated Hash: {calc_hash}")
            print(f"DB Hash:         {db_hash}")
            
            if calc_hash == db_hash:
                print("MATCH: Password 'admin' is correct.")
            else:
                print("MISMATCH: Password hash does not match 'admin'.")
                
            # Update to be sure
            if calc_hash != db_hash or user['admin_status'] != 'APPROVED':
                print("Fixing admin user...")
                cursor.execute("UPDATE users SET password_hash=%s, admin_status='APPROVED', role='admin' WHERE username='admin'", (calc_hash,))
                conn.commit()
                print("Admin user updated.")
        else:
            print("User 'admin' NOT FOUND. Creating...")
            calc_hash = hashlib.sha256('admin'.encode()).hexdigest()
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, full_name, role, admin_status, status)
                VALUES ('admin', 'admin@debugmarathon.com', %s, 'Super Admin', 'admin', 'APPROVED', 'active')
            """, (calc_hash,))
            conn.commit()
            print("Admin user created.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()

if __name__ == "__main__":
    check_admin()
