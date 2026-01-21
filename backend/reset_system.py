
import mysql.connector
import hashlib
import os
import datetime

# Configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': ''
}
DB_NAME = 'debug_marathon'

def get_connection(db=None):
    config = DB_CONFIG.copy()
    if db:
        config['database'] = db
    return mysql.connector.connect(**config)

def run_sql_file(cursor, filename):
    print(f"Running {filename}...")
    with open(filename, 'r') as f:
        sql = f.read()
        statements = sql.split(';')
        for statement in statements:
            if statement.strip():
                try:
                    cursor.execute(statement)
                except Exception as e:
                    print(f"Error executing statement: {e}")

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def reset_database():
    print("--- 1. Resetting Database ---")
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
    cursor.execute(f"CREATE DATABASE {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    print(f"Database {DB_NAME} (re)created.")
    
    cursor.close()
    conn.close()
    
    # Connect to new DB
    conn = get_connection(DB_NAME)
    cursor = conn.cursor()
    
    # Run Schemas
    # Use absolute paths or relative to script execution. I will assume execution from backend dir.
    # But since I am writing this to backend/reset_system.py, I should use relative to it.
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    schema_1 = os.path.join(base_dir, 'debug_marathon_schema.sql')
    schema_2 = os.path.join(base_dir, 'proctoring_mysql_schema.sql')
    
    run_sql_file(cursor, schema_1)
    run_sql_file(cursor, schema_2)
    conn.commit()


    print("--- 2. Populating Data ---")
    
    # 2.1 Admin
    admin_pass = "admin123"
    cursor.execute("""
        INSERT INTO users (username, email, password_hash, full_name, role, admin_status)
        VALUES (%s, %s, %s, %s, 'admin', 'APPROVED')
    """, ("admin", "admin@debugmarathon.com", hash_password(admin_pass), "Super Admin"))
    
    # 2.2 Participants
    participants = []
    for i in range(1, 11):
        pid = f"PART{i:03d}"
        name = f"Participant {i}"
        pw = "pass123"
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, full_name, role, status)
            VALUES (%s, %s, %s, %s, 'participant', 'active')
        """, (pid, f"{pid.lower()}@example.com", hash_password(pw), name))
        participants.append({'id': pid, 'pass': pw})
        
    # 2.3 Contest
    start_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    end_time = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        INSERT INTO contests (contest_name, description, start_datetime, end_datetime, status, is_active, max_violations_allowed)
        VALUES ('Debug Marathon 2025', 'The ultimate debugging challenge.', %s, %s, 'live', 1, 10)
    """, (start_time, end_time))
    contest_id = cursor.lastrowid
    
    # 2.4 Rounds (Levels)
    for i in range(1, 6):
        cursor.execute("""
            INSERT INTO rounds (contest_id, round_name, round_number, time_limit_minutes, total_questions, status)
            VALUES (%s, %s, %s, 30, 2, %s)
        """, (contest_id, f"Level {i}", i, 'active' if i==1 else 'pending'))
        round_id = cursor.lastrowid
        
        # 2.5 Questions per Round
        for q in range(1, 3):
            cursor.execute("""
                INSERT INTO questions (round_id, question_number, question_title, question_description, buggy_code, difficulty_level)
                VALUES (%s, %s, %s, 'Fix the bug in this code.', 'def solve():\n    pass # Bug here', 'medium')
            """, (round_id, q, f"L{i} Question {q}"))
            
    # 2.6 Proctoring Config
    cursor.execute("""
        INSERT INTO proctoring_config 
        (contest_id, enabled, max_violations, warning_threshold, track_tab_switches, track_focus_loss, block_copy, block_paste, detect_screenshot)
        VALUES (%s, 1, 10, 5, 1, 1, 1, 1, 1)
    """, (contest_id,))
    
    conn.commit()
    conn.close()
    
    # 3. Create TXT File
    print("--- 3. Creating Info File ---")
    info_path = os.path.join(base_dir, '..', 'FRESH_DATA_INFO.txt')
    with open(info_path, 'w') as f:
        f.write("DEBUG MARATHON - SYSTEM RESET INFO\n")
        f.write("==================================\n\n")
        f.write(f"Reset Date: {datetime.datetime.now()}\n\n")
        
        f.write("ADMIN ACCOUNT\n")
        f.write("-------------\n")
        f.write(f"Username: admin\n")
        f.write(f"Password: {admin_pass}\n\n")
        
        f.write("CONTEST\n")
        f.write("-------\n")
        f.write(f"ID: {contest_id}\n")
        f.write("Name: Debug Marathon 2025\n")
        f.write("Status: Live\n")
        f.write("Levels: 5 (Level 1 Active)\n\n")
        
        f.write("SAMPLE PARTICIPANTS\n")
        f.write("-------------------\n")
        for p in participants:
            f.write(f"ID: {p['id']}  |  Pass: {p['pass']}\n")
            
        f.write("\nCONFIGURATION\n")
        f.write("-------------\n")
        f.write("Proctoring: Enabled\n")
        f.write("Max Violations: 10\n")
        f.write("Violations Reset: YES (Tables Cleared)\n")
        
    print(f"Reset Complete. Info written to {info_path}")

if __name__ == "__main__":
    reset_database()
