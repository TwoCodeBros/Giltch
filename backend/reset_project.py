import os
import sys
import json
import uuid
import datetime
import hashlib

# Ensure we can import from parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_connection import db_manager

def reset_database():
    print(">>> STARTING PROJECT RESET <<<")
    report = []

    # 0. UPDATE SCHEMA (Ensure allowed_language exists)
    print("... Updating Schema ...")
    try:
        db_manager.execute_update("ALTER TABLE rounds ADD COLUMN allowed_language VARCHAR(50) DEFAULT 'python'")
    except Exception as e:
        # Ignore if exists (Duplicate column name)
        pass

    # 1. CLEANUP DATA
    print("... Cleaning Tables ...")
    tables_to_clear = [
        'violations', 
        'submissions', 
        'participant_level_stats',
        'questions',
        'rounds',
        'contests',
        'users',
        'admin_state'
    ]
    
    # Disable FK checks temporarily for MySQL if needed, but for safe deletion we usually just order correctly.
    # However, to be nuclear, we will delete in order.
    
    deleted_counts = {}
    try:
        # Check if using MySQL or SQLite to handle FK constraints disable if needed
        # Assuming MySQL per 'db_config.ini' usually, but 'db_sqlite.py' exists.
        # User prompt implies "DatabaseManager", let's trust execute_update.
        
        db_manager.execute_update("SET FOREIGN_KEY_CHECKS = 0") # MySQL specific, safety
        
        for t in tables_to_clear:
            try:
                db_manager.execute_update(f"DELETE FROM {t}")
                # Reset Auto Increment
                db_manager.execute_update(f"ALTER TABLE {t} AUTO_INCREMENT = 1")
                deleted_counts[t] = "Cleared"
            except Exception as e:
                deleted_counts[t] = f"Error: {e}"
                
        db_manager.execute_update("SET FOREIGN_KEY_CHECKS = 1")
        
        report.append("DATA CLEANUP:")
        for t, s in deleted_counts.items():
            report.append(f" - {t}: {s}")
            
    except Exception as e:
        print(f"Cleanup Error: {e}")
        report.append(f"Cleanup Error: {e}")

    # 2. SEED ADMIN
    print("... Seeding Admin ...")
    admin_id = str(uuid.uuid4())
    admin_pass = hashlib.sha256("admin123".encode()).hexdigest()
    db_manager.execute_update(
        "INSERT INTO users (user_id, username, password_hash, full_name, email, role, status, admin_status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (admin_id, "admin", admin_pass, "Super Admin", "admin@debugmarathon.com", "admin", "active", "APPROVED")
    )
    report.append(f"Admin Created: username='admin', password='admin123'")

    # 3. SEED LEADER
    print("... Seeding Leader ...")
    leader_id = str(uuid.uuid4())
    leader_pass = hashlib.sha256("leader123".encode()).hexdigest()
    db_manager.execute_update(
        "INSERT INTO users (user_id, username, password_hash, full_name, email, role, status, department, college, admin_status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (leader_id, "leader1", leader_pass, "Leader One", "leader1@college.edu", "leader", "active", "CSE", "Tech Institute", "APPROVED")
    )
    report.append(f"Leader Created: username='leader1', password='leader123'")

    # 4. SEED PARTICIPANTS
    print("... Seeding Participants ...")
    participants = []
    for i in range(1, 11):
        pid = f"PART{i:03d}"
        uid = str(uuid.uuid4()) # ID is int in some schemas, UUID in others? 
        # Checking previous errors, 'user_id' in schema seems to be int or string. 
        # Using string UUID is safer if schema allows, but if it expects auto-inc INT, we insert without ID?
        # Let's assume user_id is PK. 
        # Wait, in get_participants we select user_id.
        # Let's check schema via insertion outcome. If user_id is AI, we shouldn't insert it.
        # But for 'users', usually it's explicit or UUID. Let's try explicit integer for simple participant matching if needed, 
        # OR just use the loop index + 1000?
        # Let's go with UUID for user_id, and PARTxxx for username.
        
        name = f"Participant {i}"
        email = f"p{i}@student.com"
        dept = "CSE"
        col = "Engineering College"
        
        # Insert
        q = "INSERT INTO users (username, password_hash, full_name, email, role, status, department, college, phone) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        # Note: phone removed in previous step? No, in 'admin.py' we removed it. 
        # But if we did not ALTER TABLE, the column might still exist in DB, just hidden.
        # OR it might not exist.
        # Safest: Don't insert phone.
        
        q_safe = "INSERT INTO users (username, password_hash, full_name, email, role, status, department, college) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        db_manager.execute_update(q_safe, (pid, 'sha256_placeholder', name, email, 'participant', 'active', dept, col))
        participants.append(pid)
        
    report.append(f"Participants Created: {len(participants)} (PART001 - PART010)")

    # 5. SEED CONTEST
    print("... Seeding Contest ...")
    # Tricky: we need the ID.
    contest_id = 1 
    # insert with explicit ID to make it predictable
    start = datetime.datetime.now()
    end = start + datetime.timedelta(hours=5)
    
    c_q = "INSERT INTO contests (contest_id, contest_name, description, start_datetime, end_datetime, status, max_violations_allowed) VALUES (%s, %s, %s, %s, %s, %s, %s)"
    db_manager.execute_update(c_q, (contest_id, "Debug Marathon 2026", "The ultimate coding challenge.", start, end, "live", 10))
    report.append("Contest Created: 'Debug Marathon 2026' (ID: 1, Status: LIVE)")

    # 6. SEED ROUNDS & QUESTIONS
    print("... Seeding Rounds & Questions ...")
    
    rounds_data = [
        {"num": 1, "time": 45, "lang": "python", "qs": 2},
        {"num": 2, "time": 45, "lang": "python", "qs": 2},
        {"num": 3, "time": 60, "lang": "c", "qs": 1},
        {"num": 4, "time": 60, "lang": "cpp", "qs": 1},
        {"num": 5, "time": 90, "lang": "java", "qs": 1}
    ]
    
    q_counter = 1
    
    for r in rounds_data:
        # Insert Round (Let Auto Inc handle ID)
        r_q_sql = "INSERT INTO rounds (contest_id, round_number, round_name, time_limit_minutes, total_questions, status, allowed_language) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        
        # Using execute_update for insert
        db_manager.execute_update(r_q_sql, (contest_id, r['num'], f"Level {r['num']}", r['time'], r['qs'], 'pending' if r['num']>1 else 'active', r['lang']))
        
        # Fetch the generated ID
        id_res = db_manager.execute_query("SELECT round_id FROM rounds WHERE contest_id=%s AND round_number=%s", (contest_id, r['num']))
        
        if not id_res:
            print(f"CRITICAL: Could not fetch round ID for Level {r['num']}")
            continue
            
        r_id = id_res[0]['round_id']
        report.append(f"Round Created: Level {r['num']} (ID: {r_id}, {r['lang']}, {r['time']}m)")
        
        # Insert Questions
        for k in range(r['qs']):
            q_title = f"Fix the Bug - L{r['num']} Q{k+1}"
            q_desc = f"Find the bug in this {r['lang']} code."
            
            boilerplate = {
                "python": "def solve():\n    # Buggy code here\n    return 0",
                "c": "#include <stdio.h>\nint main() { return 1; }",
                "cpp": "#include <iostream>\nusing namespace std;\nint main() { return 1; }",
                "java": "public class Main { public static void main(String[] args) {} }",
                "javascript": "function solve() { return 0; }"
            }
            
            bp = boilerplate.get(r['lang'], "Code here")
            
            # Note: question_id is AUTO_INCREMENT in schema, so we omit it
            ques_sql = """
                INSERT INTO questions 
                (round_id, question_number, question_title, question_description, difficulty_level, points, buggy_code, test_cases, expected_output)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            tcs = json.dumps([{"input": "1", "expected": "1"}])
            
            db_manager.execute_update(ques_sql, (
                r_id, q_counter, q_title, q_desc, f"Level {r['num']}", 100, bp, tcs, "1"
            ))
            q_counter += 1
            
    report.append(f"Questions Created: {q_counter-1} Total Questions across 5 Levels")

    # 7. GENERATE REPORT FILE
    with open('RESET_REPORT.txt', 'w') as f:
        f.write("PROJECT RESET REPORT\n")
        f.write("====================\n")
        f.write(f"Date: {datetime.datetime.now()}\n\n")
        for line in report:
            f.write(line + "\n")
            
    print("\n>>> RESET COMPLETE. Check RESET_REPORT.txt <<<")

if __name__ == "__main__":
    reset_database()
