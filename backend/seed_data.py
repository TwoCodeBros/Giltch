
import hashlib
import time
import random
from db_connection import db_manager

def get_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()

def seed_data():
    print("--- SEEDING SAMPLE DATA ---")
    
    # 1. Clean existing sample data (optional, but good for consistency as requested)
    # We won't truncate all tables to preserve manual changes, but we'll ensure our sample users exist with correct data
    
    print("1. Seeding Users...")
    
    # --- ADMIN ---
    db_manager.execute_update("""
        INSERT INTO users (username, email, password_hash, role, full_name, admin_status, status)
        VALUES ('admin', 'admin@debug.com', %s, 'admin', 'System Administrator', 'APPROVED', 'active')
        ON DUPLICATE KEY UPDATE 
        password_hash = VALUES(password_hash), admin_status='APPROVED', status='active'
    """, (get_hash('admin123'),))
    
    # --- LEADER ---
    db_manager.execute_update("""
        INSERT INTO users (username, email, password_hash, role, full_name, admin_status, status, department, college)
        VALUES ('leader', 'leader@debug.com', %s, 'leader', 'Contest Leader', 'APPROVED', 'active', 'Coordinator', 'Main Campus')
        ON DUPLICATE KEY UPDATE 
        password_hash = VALUES(password_hash), admin_status='APPROVED'
    """, (get_hash('leader123'),))

    # --- PARTICIPANTS ---
    participants = [
        ('URK23CS101', 'Alice Johnson', 'CSE', 'Karunya Inst. of Tech', 'active'),
        ('URK23CS102', 'Bob Smith', 'CSE', 'Karunya Inst. of Tech', 'active'),
        ('URK23AI201', 'Charlie Brown', 'AI & DS', 'Karunya Inst. of Tech', 'active'),
        ('URK23EC305', 'David Wilson', 'ECE', 'Karunya Inst. of Tech', 'disqualified'),
        ('URK23CS103', 'Eve Anderson', 'CSE', 'Karunya Inst. of Tech', 'active'),
        ('URK23ME401', 'Frank Miller', 'Mech', 'Karunya Inst. of Tech', 'active'),
    ]

    for p in participants:
         # Using Register Number as Username
        pid, name, dept, college, status = p
        email = f"{pid.lower()}@example.com"
        db_manager.execute_update("""
            INSERT INTO users (username, email, password_hash, role, full_name, department, college, status)
            VALUES (%s, %s, %s, 'participant', %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            full_name=VALUES(full_name), department=VALUES(department), college=VALUES(college), status=VALUES(status)
        """, (pid, email, get_hash('pass123'), name, dept, college, status))
        
    print("Users seeded.")

    # 2. Contest
    print("2. Seeding Contest...")
    # Ensure at least one live contest
    contest_id = 1
    res = db_manager.execute_query("SELECT contest_id FROM contests WHERE status='live' LIMIT 1")
    if res:
        contest_id = res[0]['contest_id']
    else:
        # Create one
        start = time.strftime('%Y-%m-%d %H:%M:%S')
        end = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + 86400*30))
        ret = db_manager.execute_update("""
            INSERT INTO contests (contest_name, description, start_datetime, end_datetime, status, is_active)
            VALUES ('Debug Marathon 2026', 'End-to-End Test Contest', %s, %s, 'live', 1)
        """, (start, end))
        if ret: contest_id = ret['last_id']

    # 3. Rounds & Questions
    print(f"3. Seeding Rounds & Questions for Contest {contest_id}...")
    
    # Create 3 Levels
    for level in range(1, 4):
        # Round
        status = 'active' if level == 1 else 'active' # Make all active for testing ease
        db_manager.execute_update("""
            INSERT INTO rounds (contest_id, round_name, round_number, time_limit_minutes, total_questions, status, is_locked)
            VALUES (%s, %s, %s, 45, 2, %s, 0)
            ON DUPLICATE KEY UPDATE status=VALUES(status), is_locked=0
        """, (contest_id, f"Level {level}", level, status))
        
        # Get Round ID
        r_res = db_manager.execute_query("SELECT round_id FROM rounds WHERE contest_id=%s AND round_number=%s", (contest_id, level))
        round_id = r_res[0]['round_id']
        
        # Questions (2 per level)
        questions = [
            {
                "num": 1, 
                "title": f"L{level} - Syntax Fix", 
                "desc": "Fix the syntax error.", 
                "code": "def solve():\n  print 'hello'", 
                "diff": "easy",
                "out": "hello"
            },
            {
                "num": 2, 
                "title": f"L{level} - Logic Bug", 
                "desc": "Fix the logic.", 
                "code": "def add(a,b):\n  return a-b", 
                "diff": "medium",
                "out": "3"
            }
        ]
        
        for q in questions:
            db_manager.execute_update("""
                INSERT INTO questions (round_id, question_number, question_title, question_description, buggy_code, difficulty_level, points, expected_output)
                VALUES (%s, %s, %s, %s, %s, %s, 10, %s)
                ON DUPLICATE KEY UPDATE question_title=VALUES(question_title)
            """, (round_id, q['num'], q['title'], q['desc'], q['code'], q['diff'], q['out']))

    # 4. Simulation: Submissions & Props
    print("4. Seeding Submissions & Results...")
    
    # Get User IDs
    u_map = {} # username -> id
    u_res = db_manager.execute_query("SELECT user_id, username FROM users WHERE role='participant'")
    for u in u_res:
        u_map[u['username']] = u['user_id']
        
    participant_data = [
        # Alice: High performer, done level 1 & 2
        {'user': 'URK23CS101', 'levels': [1, 2], 'score_base': 10, 'violations': 0},
        # Bob: Average, done level 1 with violations
        {'user': 'URK23CS102', 'levels': [1], 'score_base': 8, 'violations': 3},
        # Eve: Just started
        {'user': 'URK23CS103', 'levels': [], 'score_base': 0, 'violations': 0},
        # David: Disqualified
        {'user': 'URK23EC305', 'levels': [1], 'score_base': 5, 'violations': 15} # High violations
    ]

    for p in participant_data:
        uid = u_map.get(p['user'])
        if not uid: continue
        
        total_score = 0
        
        # Create Proctoring Record
        db_manager.execute_update("""
            INSERT INTO participant_proctoring (id, participant_id, user_id, contest_id, total_violations, violation_score, risk_level, is_disqualified)
            VALUES (UUID(), %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE total_violations=VALUES(total_violations)
        """, (
            p['user'], uid, contest_id, 
            p['violations'], p['violations']*2, 
            'critical' if p['violations'] > 10 else ('medium' if p['violations'] > 2 else 'low'),
            1 if p['violations'] > 10 else 0
        ))
        
        for lvl in p['levels']:
            # Add Level Stat (Completed)
            score = p['score_base'] * 2 # 2 questions
            total_score += score
            
            db_manager.execute_update("""
                INSERT INTO participant_level_stats (user_id, contest_id, level, status, questions_solved, level_score, violation_count)
                VALUES (%s, %s, %s, 'COMPLETED', 2, %s, %s)
                ON DUPLICATE KEY UPDATE status='COMPLETED', level_score=VALUES(level_score)
            """, (uid, contest_id, lvl, score, 0 if p['user'] == 'Alice' else p['violations']))
            
            # Submissions for this level
            # Get round_id
            r_row = db_manager.execute_query("SELECT round_id FROM rounds WHERE contest_id=%s AND round_number=%s", (contest_id, lvl))
            if r_row:
                rid = r_row[0]['round_id']
                # Create 2 submissions
                for qnum in [1, 2]:
                     # Get qid
                    q_row = db_manager.execute_query("SELECT question_id FROM questions WHERE round_id=%s AND question_number=%s", (rid, qnum))
                    if q_row:
                        qid = q_row[0]['question_id']
                        db_manager.execute_update("""
                            INSERT INTO submissions (user_id, contest_id, round_id, question_id, submitted_code, is_correct, score_awarded, status, time_taken_seconds)
                            VALUES (%s, %s, %s, %s, '# Solved', 1, %s, 'evaluated', 120)
                        """, (uid, contest_id, rid, qid, p['score_base']))

        # Update Leaderboard
        db_manager.execute_update("""
            INSERT INTO leaderboard (user_id, contest_id, total_score, current_round, violations_count)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE total_score=VALUES(total_score), current_round=VALUES(current_round)
        """, (uid, contest_id, total_score, max(p['levels']) + 1 if p['levels'] else 1, p['violations']))

    print("Seeding Complete!")

if __name__ == "__main__":
    seed_data()
