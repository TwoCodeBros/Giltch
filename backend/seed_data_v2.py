
import hashlib
import time
import random
import uuid
import json
from db_connection import db_manager

def get_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()

def seed_data_v2():
    print("--- SEEDING EXTENDED SAMPLE DATA (V2) ---")
    
    # 1. USERS
    print("1. Seeding Users...")
    
    # --- ADMIN ---
    db_manager.upsert(
        'users',
        {
            'username': 'admin',
            'email': 'admin@debug.com',
            'password_hash': get_hash('admin123'),
            'role': 'admin',
            'full_name': 'Chief Administrator',
            'admin_status': 'APPROVED',
            'status': 'active'
        },
        ['username'] 
    )
    
    # --- LEADER (Department/College Leader) ---
    db_manager.upsert(
        'users',
        {
            'username': 'leader',
            'email': 'leader@debug.com',
            'password_hash': get_hash('leader123'),
            'role': 'leader',
            'full_name': 'Dr. Alan Turing',
            'admin_status': 'APPROVED',
            'status': 'active',
            'department': 'CSE',
            'college': 'Karunya Inst. of Tech'
        },
        ['username']
    )

    # --- PARTICIPANTS ---
    # Register Number mapped to username
    participants = [
        # (RegNo, Name, Dept, College, Status)
        ('URK23CS1001', 'John Doe', 'CSE', 'Karunya Inst. of Tech', 'active'),
        ('URK23CS1002', 'Jane Smith', 'CSE', 'Karunya Inst. of Tech', 'active'),
        ('URK23AI2001', 'Alice Wonderland', 'AI & DS', 'Karunya Inst. of Tech', 'active'),
        ('URK23EC3001', 'Bob Builder', 'ECE', 'Karunya Inst. of Tech', 'active'),
        ('URK23ME4001', 'Charlie Chaplin', 'Mech', 'Karunya Inst. of Tech', 'active'),
        ('URK23CS1003', 'Eve Hacker', 'CSE', 'Karunya Inst. of Tech', 'disqualified'), # One disqualified
        ('URK23BT5001', 'Grace Hopper', 'Biotech', 'Karunya Inst. of Tech', 'active'),
    ]

    user_map = {} # username -> user_id

    for p in participants:
        reg_no, name, dept, college, status = p
        email = f"{reg_no.lower()}@karunya.edu.in"
        
        # Insert/Update User
        db_manager.upsert(
            'users',
            {
                'username': reg_no,
                'email': email,
                'password_hash': get_hash('password'), # Default password
                'role': 'participant',
                'full_name': name,
                'department': dept,
                'college': college,
                'status': status,
                'is_active': 1 if status == 'active' else 0
            },
            ['username']
        )
        
        # Fetch back the ID
        res = db_manager.execute_query("SELECT user_id FROM users WHERE username=%s", (reg_no,))
        if res:
            user_map[reg_no] = res[0]['user_id']
        
    print(f"Seeded {len(participants)} participants and admin/leader.")

    # 2. CONTEST
    print("2. Seeding Contest...")
    contest_id = 1
    # Check for existing live contest
    res = db_manager.execute_query("SELECT contest_id FROM contests WHERE status='live' LIMIT 1")
    if res:
        contest_id = res[0]['contest_id']
        print(f"Using existing contest ID: {contest_id}")
    else:
        # Create one
        start = time.strftime('%Y-%m-%d %H:%M:%S')
        end = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + 86400*30)) # 30 days
        ret = db_manager.execute_update("""
            INSERT INTO contests (contest_name, description, start_datetime, end_datetime, status, is_active)
            VALUES ('Debug Marathon 2026', 'National Level Coding & Debugging Championship', %s, %s, 'live', 1)
        """, (start, end))
        
        # Attempt to get ID
        res = db_manager.execute_query("SELECT contest_id FROM contests ORDER BY contest_id DESC LIMIT 1")
        if res: contest_id = res[0]['contest_id']
        print(f"Created new contest ID: {contest_id}")

    # 3. ROUNDS & QUESTIONS
    print(f"3. Seeding Rounds & Questions for Contest {contest_id}...")
    
    levels_data = [
        {
            'level': 1, 'name': 'Syntax Sprint', 'time': 45, 
            'questions': [
                {'num': 1, 'title': 'Syntax Error in Loop', 'desc': 'Fix the syntax error in the for loop.', 'code': "def print_nums():\n  for i in range(10)\n    print(i)", 'diff': 'easy', 'out': '0\n1\n2\n3\n4\n5\n6\n7\n8\n9', 'pts': 10},
                {'num': 2, 'title': 'Missing Colon', 'desc': 'Find the missing colon.', 'code': "if True\n  print('Yes')", 'diff': 'easy', 'out': 'Yes', 'pts': 10}
            ]
        },
        {
            'level': 2, 'name': 'Logic Lab', 'time': 60,
            'questions': [
                {'num': 1, 'title': 'Off-by-One Error', 'desc': 'Fix the array indexing.', 'code': "arr = [1,2,3]\nprint(arr[3])", 'diff': 'medium', 'out': 'IndexError caught or fixed', 'pts': 20},
                {'num': 2, 'title': 'Infinite Loop', 'desc': 'Prevent the infinite loop.', 'code': "i=0\nwhile i<10:\n  print(i)", 'diff': 'medium', 'out': '0...9', 'pts': 20}
            ]
        },
        {
            'level': 3, 'name': 'Algorithm Arena', 'time': 90,
            'questions': [
                {'num': 1, 'title': 'Binary Search Bug', 'desc': 'Fix the binary search implementation.', 'code': "def binary_search(arr, x):\n  # Buggy implementation...", 'diff': 'hard', 'out': 'index', 'pts': 30}
            ]
        }
    ]

    for lvl in levels_data:
        # Create Round
        db_manager.upsert(
            'rounds',
            {
                'contest_id': contest_id,
                'round_name': lvl['name'],
                'round_number': lvl['level'],
                'time_limit_minutes': lvl['time'],
                'total_questions': len(lvl['questions']),
                'status': 'active',
                'is_locked': 0
            },
            ['contest_id', 'round_number']
        )
        
        # Get Round ID
        r_res = db_manager.execute_query("SELECT round_id FROM rounds WHERE contest_id=%s AND round_number=%s", (contest_id, lvl['level']))
        if not r_res: continue
        round_id = r_res[0]['round_id']
        
        # Create Questions
        for q in lvl['questions']:
            db_manager.upsert(
                'questions',
                {
                    'round_id': round_id,
                    'question_number': q['num'],
                    'question_title': q['title'],
                    'question_description': q['desc'],
                    'buggy_code': q['code'],
                    'difficulty_level': q['diff'],
                    'points': q['pts'],
                    'expected_output': q['out']
                },
                ['round_id', 'question_number']
            )

    # 4. SIMULATION: SCORES, RESULTS, PROCTORING
    print("4. Seeding Simulation Data (Scores, Results, Proctoring)...")
    
    # Simulation Config
    # user_reg -> { 'levels_completed': [1,2], 'total_score': 50, 'violations': 2 }
    sim_profiles = [
        {'reg': 'URK23CS1001', 'levels': [1, 2], 'score': 60, 'vios': 1},
        {'reg': 'URK23CS1002', 'levels': [1], 'score': 15, 'vios': 5}, 
        {'reg': 'URK23AI2001', 'levels': [1, 2, 3], 'score': 100, 'vios': 0}, # Topper
        {'reg': 'URK23EC3001', 'levels': [], 'score': 0, 'vios': 0}, # Just started
        {'reg': 'URK23CS1003', 'levels': [1], 'score': 10, 'vios': 12}, # Disqualified guy
    ]

    for sim in sim_profiles:
        reg_no = sim['reg']
        uid = user_map.get(reg_no)
        if not uid: continue
        
        # Proctoring Record
        # Check if exists first to avoid overwriting IDs unnecessarily
        proc_check = db_manager.execute_query("SELECT id FROM participant_proctoring WHERE participant_id=%s AND contest_id=%s", (reg_no, contest_id))
        
        if not proc_check:
            db_manager.execute_update("""
                INSERT INTO participant_proctoring 
                (id, participant_id, user_id, contest_id, total_violations, violation_score, risk_level, is_disqualified)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()), 
                reg_no, 
                uid, 
                contest_id, 
                sim['vios'], 
                sim['vios'] * 5, 
                'critical' if sim['vios'] > 10 else ('medium' if sim['vios'] > 3 else 'low'),
                1 if sim['vios'] > 10 else 0
            ))
        
        # Level Stats & Submissions (Simplified)
        current_total_score = 0
        questions_solved_total = 0
        
        for lvl_num in sim['levels']:
            # Assume full score for level for simplicity
            level_points = 20 if lvl_num == 1 else (40 if lvl_num == 2 else 30)
            
            db_manager.upsert(
                'participant_level_stats',
                {
                    'user_id': uid,
                    'contest_id': contest_id,
                    'level': lvl_num,
                    'status': 'COMPLETED',
                    'questions_solved': 2, # Assume 2 qs solved per level
                    'level_score': level_points,
                    'violation_count': 0, # Distributed vaguely
                    'start_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'completed_at': time.strftime('%Y-%m-%d %H:%M:%S')
                },
                ['user_id', 'contest_id', 'level']
            )
            current_total_score += level_points
            questions_solved_total += 2
        
        # Leaderboard
        db_manager.upsert(
            'leaderboard',
            {
                'user_id': uid,
                'contest_id': contest_id,
                'total_score': current_total_score,
                'questions_correct': questions_solved_total,
                'questions_attempted': questions_solved_total, # approximate
                'current_round': (max(sim['levels']) + 1) if sim['levels'] else 1,
                'violations_count': sim['vios'],
                'rank_position': 0 # To be calculated by app logic usually, but set 0 for now
            },
            ['user_id', 'contest_id']
        )
        
    print("Seeding Complete (V2)!")

if __name__ == "__main__":
    seed_data_v2()
