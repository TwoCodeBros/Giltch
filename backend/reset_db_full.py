
import mysql.connector
import os
import time
import hashlib
import json

# DB Config
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
}
DB_NAME = 'debug_marathon_v3'

def reset_db():
    print("--- FULL SYSTEM RESET & SEEDING (v3) ---")
    
    # 1. Connect and Create Database (Fresh Start)
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Drop if exists (clean start)
        try:
            cursor.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
        except Exception as e:
            print(f"Warning dropping DB: {e}")
            
        cursor.execute(f"CREATE DATABASE {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.execute(f"USE {DB_NAME}")
        print(f"Database {DB_NAME} created/selected.")
        
    except Exception as e:
        print(f"CRITICAL ERROR: Connection/Creation failed: {e}")
        return

    # 2. Apply Schemas
    try:
        # Main Schema
        schema_path = os.path.join(os.path.dirname(__file__), 'debug_marathon_schema.sql')
        if not os.path.exists(schema_path):
            print(f"Error: Schema file not found at {schema_path}")
            return
            
        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        for result in cursor.execute(schema_sql, multi=True):
            pass
        print("Main Schema applied.")

        # Proctoring Schema
        proc_path = os.path.join(os.path.dirname(__file__), 'proctoring_schema_mysql.sql')
        if os.path.exists(proc_path):
            with open(proc_path, 'r') as f:
                proc_sql = f.read()
            for result in cursor.execute(proc_sql, multi=True):
                pass
            print("Proctoring Schema applied.")
            
    except Exception as e:
        print(f"Schema Execution Error: {e}")
        conn.close()
        return

    # 3. Seed Data
    report_lines = []
    report_lines.append("=== DEBUG MARATHON - DATA RESET REPORT ===")
    report_lines.append(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Database: {DB_NAME}")
    report_lines.append("-" * 40)

    try:
        # A. Admin
        admin_pass = "admin123"
        admin_hash = hashlib.sha256(admin_pass.encode()).hexdigest()
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, role, full_name, admin_status) 
            VALUES ('admin', 'admin@debug.com', %s, 'admin', 'System Administrator', 'APPROVED')
        """, (admin_hash,))
        report_lines.append("\n[ADMIN ACCOUNT]")
        report_lines.append(f"Username: admin")
        report_lines.append(f"Password (raw): {admin_pass}") # Clarity for user

        # B. Leader
        leader_pass = "leader123"
        leader_hash = hashlib.sha256(leader_pass.encode()).hexdigest()
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, role, full_name, status) 
            VALUES ('leader', 'leader@debug.com', %s, 'leader', 'Contest Leader', 'active')
        """, (leader_hash,))
        
        # Check for leaders table
        cursor.execute("SHOW TABLES LIKE 'leaders'")
        if cursor.fetchone():
             # Fetch ID of inserted user
            cursor.execute("SELECT user_id FROM users WHERE username='leader'")
            l_uid = cursor.fetchone()[0]
            cursor.execute("INSERT INTO leaders (user_id, name) VALUES (%s, 'Contest Leader')", (l_uid,))

        report_lines.append("\n[LEADER ACCOUNT]")
        report_lines.append(f"Username: leader")
        report_lines.append(f"Password (raw): {leader_pass}")

        # C. Participants
        report_lines.append("\n[PARTICIPANTS]")
        for i in range(1, 6): # 5 Participants
            pid = f"PART{i:03d}"
            name = f"Participant {i}"
            email = f"part{i}@debug.com"
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, role, full_name, status) 
                VALUES (%s, %s, 'pass123', 'participant', %s, 'active')
            """, (pid, email, name))
            report_lines.append(f"{pid} - {name}")

        # D. Contest
        start_t = time.strftime('%Y-%m-%d %H:%M:%S')
        end_t = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + 86400 * 7))
        cursor.execute("""
            INSERT INTO contests (contest_name, description, start_datetime, end_datetime, status, max_violations_allowed) 
            VALUES ('Debug Marathon 2026', 'Freshly reset contest environment (v3).', %s, %s, 'live', 50)
        """, (start_t, end_t))
        contest_id = cursor.lastrowid
        report_lines.append(f"\n[CONTEST]")
        report_lines.append(f"ID: {contest_id}")
        report_lines.append("Name: Debug Marathon 2026")
        report_lines.append("Status: LIVE")

        # E. Levels & Questions
        sample_questions = [
             {"title": "Syntax Error Fix", "desc": "Fix the syntax error in the loop.", "code": "def solve():\n    for i in range(10)\n        print(i)", "out": "0\n1\n2..."},
             {"title": "Logic Error: Sum", "desc": "Sum is calculating incorrectly.", "code": "def sum(a, b):\n    return a - b", "out": "5"},
             {"title": "Array Index OOB", "desc": "Fix index out of bounds.", "code": "def get_last(arr):\n    return arr[len(arr)]", "out": "Correct Element"},
             {"title": "Infinite Loop", "desc": "Loop never ends.", "code": "def loop():\n    i = 0\n    while i < 10:\n        print(i)", "out": "0..9"},
             {"title": "Type Mismatch", "desc": "Adding string to int.", "code": "def add(x):\n    return x + '1'", "out": "11"}
        ]
        
        report_lines.append("\n[ROUNDS & QUESTIONS]")
        
        for level in range(1, 6):
            status = 'active' if level == 1 else 'pending'
            cursor.execute("""
                INSERT INTO rounds (contest_id, round_name, round_number, time_limit_minutes, total_questions, status) 
                VALUES (%s, %s, %s, 30, 2, %s)
            """, (contest_id, f"Level {level}", level, status))
            round_id = cursor.lastrowid
            report_lines.append(f"Round {level} (ID: {round_id}, Status: {status})")
            
            # Add 2 questions
            for q_num in range(1, 3):
                q_data = sample_questions[(level + q_num) % len(sample_questions)]
                cursor.execute("""
                    INSERT INTO questions 
                    (round_id, question_number, question_title, question_description, buggy_code, difficulty_level, points, expected_output, test_cases)
                    VALUES (%s, %s, %s, %s, %s, 'medium', 20, %s, '[]')
                """, (round_id, q_num, q_data['title'], q_data['desc'], q_data['code'], q_data['out']))
                report_lines.append(f"  - Q{q_num}: {q_data['title']}")

        conn.commit()
        print("Data Seeding Complete.")
        
        report_path = os.path.join(os.path.dirname(__file__), 'new_data_report.txt')
        with open(report_path, 'w') as f:
            f.write('\n'.join(report_lines))
        print(f"Report generated at: {report_path}")

    except Exception as e:
        print(f"Seeding Error: {e}")
        conn.rollback()
    
    finally:
        if conn.is_connected():
            conn.close()

if __name__ == "__main__":
    reset_db()
