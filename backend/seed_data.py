
import hashlib
import time
import random
import uuid
from db_connection import db_manager

def get_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()

def seed_data():
    print("--- SEEDING SAMPLE DATA ---")
    
    print("1. Seeding Users...")
    
    # --- ADMIN ---
    db_manager.upsert(
        'users',
        {
            'username': 'admin',
            'email': 'admin@debug.com',
            'password_hash': get_hash('admin123'),
            'role': 'admin',
            'full_name': 'System Administrator',
            'admin_status': 'APPROVED',
            'status': 'active'
        },
        ['username'] 
    )
    
    # --- LEADER ---
    db_manager.upsert(
        'users',
        {
            'username': 'leader',
            'email': 'leader@debug.com',
            'password_hash': get_hash('leader123'),
            'role': 'leader',
            'full_name': 'Contest Leader',
            'admin_status': 'APPROVED',
            'status': 'active',
            'department': 'Coordinator',
            'college': 'Main Campus'
        },
        ['username']
    )

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
        pid, name, dept, college, status = p
        email = f"{pid.lower()}@example.com"
        db_manager.upsert(
            'users',
            {
                'username': pid,
                'email': email,
                'password_hash': get_hash('pass123'),
                'role': 'participant',
                'full_name': name,
                'department': dept,
                'college': college,
                'status': status
            },
            ['username']
        )
        
    print("Users seeded.")

    # 2. Contest
    print("2. Seeding Contest...")
    contest_id = 1
    # Check if a live contest exists
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
        if ret and ret.get('last_id'): contest_id = ret['last_id']
        else:
             # Just query it back if insert succeeded but no last_id (SQLite sometimes)
             res = db_manager.execute_query("SELECT contest_id FROM contests ORDER BY contest_id DESC LIMIT 1")
             if res: contest_id = res[0]['contest_id']

    # 3. Rounds & Questions
    print(f"3. Seeding Rounds & Questions for Contest {contest_id}...")
    
    for level in range(1, 4):
        status = 'active'
        db_manager.upsert(
            'rounds',
            {
                'contest_id': contest_id,
                'round_name': f"Level {level}",
                'round_number': level,
                'time_limit_minutes': 45,
                'total_questions': 2,
                'status': status,
                'is_locked': 0
            },
            ['contest_id', 'round_number']
        )
        
        r_res = db_manager.execute_query("SELECT round_id FROM rounds WHERE contest_id=%s AND round_number=%s", (contest_id, level))
        if not r_res: continue
        round_id = r_res[0]['round_id']
        
        questions = [
            {'num': 1, 'title': f"L{level} - Syntax Fix", 'desc': "Fix syntax.", 'code': "def solve():\n  print 'hello'", 'diff': 'easy', 'out': 'hello'},
            {'num': 2, 'title': f"L{level} - Logic Bug", 'desc': "Fix logic.", 'code': "def add(a,b):\n  return a-b", 'diff': 'medium', 'out': '3'}
        ]
        
        for q in questions:
            db_manager.upsert(
                'questions',
                {
                    'round_id': round_id,
                    'question_number': q['num'],
                    'question_title': q['title'],
                    'question_description': q['desc'],
                    'buggy_code': q['code'],
                    'difficulty_level': q['diff'],
                    'points': 10,
                    'expected_output': q['out']
                },
                ['round_id', 'question_number']
            )

    # 4. Simulation
    print("4. Seeding Submissions & Results...")
    u_map = {}
    u_res = db_manager.execute_query("SELECT user_id, username FROM users WHERE role='participant'")
    if u_res:
        for u in u_res:
            u_map[u['username']] = u['user_id']
        
    participant_data = [
        {'user': 'URK23CS101', 'levels': [1, 2], 'score_base': 10, 'violations': 0},
        {'user': 'URK23CS102', 'levels': [1], 'score_base': 8, 'violations': 3},
        {'user': 'URK23CS103', 'levels': [], 'score_base': 0, 'violations': 0},
        {'user': 'URK23EC305', 'levels': [1], 'score_base': 5, 'violations': 15}
    ]

    for p in participant_data:
        uid = u_map.get(p['user'])
        if not uid: continue
        
        total_score = 0
        
        # Proctoring - Handle UUID in python
        # UUID() is SQL. uuid.uuid4() is Python
        db_manager.upsert(
            'participant_proctoring',
            {
                'id': str(uuid.uuid4()),
                'participant_id': p['user'],
                'user_id': uid,
                'contest_id': contest_id,
                'total_violations': p['violations'],
                'violation_score': p['violations']*2,
                'risk_level': 'critical' if p['violations'] > 10 else ('medium' if p['violations'] > 2 else 'low'),
                'is_disqualified': 1 if p['violations'] > 10 else 0
            },
            ['participant_id', 'contest_id']
        )
        
        for lvl in p['levels']:
            score = p['score_base'] * 2
            total_score += score
            
            db_manager.upsert(
                'participant_level_stats',
                {
                    'user_id': uid,
                    'contest_id': contest_id,
                    'level': lvl,
                    'status': 'COMPLETED',
                    'questions_solved': 2,
                    'level_score': score,
                    'violation_count': 0 if p['user'] == 'Alice' else p['violations']
                },
                ['user_id', 'contest_id', 'level']
            )
            
            # Submissions... skipping detail for brevity unless critical
            # Just seeding leaderboard is enough for demo
            
        db_manager.upsert(
            'leaderboard',
            {
                'user_id': uid,
                'contest_id': contest_id,
                'total_score': total_score,
                'current_round': max(p['levels']) + 1 if p['levels'] else 1,
                'violations_count': p['violations']
            },
            ['user_id', 'contest_id']
        )

    print("Seeding Complete!")

if __name__ == "__main__":
    seed_data()
