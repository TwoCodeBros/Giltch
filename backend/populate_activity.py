
import random
import datetime
import os
import sys

# Ensure backend path is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db_connection import db_manager

def populate_activity():
    print("Populating Test Activity...")
    
    # 1. Get Context
    contest_id = 1
    # Ensure contest exists
    c = db_manager.execute_query("SELECT contest_id FROM contests WHERE contest_id=%s LIMIT 1", (contest_id,))
    if not c:
        print("Contest 1 not found. Run reset_project.py first.")
        return

    # 2. Get Participants
    parts = db_manager.execute_query("SELECT user_id, username FROM users WHERE role='participant'")
    if not parts:
        print("No participants found.")
        return

    # 3. Get Round 1 Questions
    qs = db_manager.execute_query("SELECT question_id, round_id FROM questions WHERE round_id=(SELECT round_id FROM rounds WHERE contest_id=%s AND round_number=1 LIMIT 1)", (contest_id,))
    
    if not qs:
        print("No questions found for Round 1.")
        # Proceeding might fail if we try to submit
        
    print(f"Found {len(parts)} participants and {len(qs) if qs else 0} questions.")

    # 4. Simulate Activity
    for p in parts:
        uid = p['user_id']
        uname = p['username']
        
        # Random Status: 20% Not Started, 30% In Progress, 50% Completed
        status_roll = random.random()
        status = 'NOT_STARTED'
        if status_roll > 0.2: status = 'IN_PROGRESS'
        if status_roll > 0.5: status = 'COMPLETED'
        
        if status == 'NOT_STARTED': continue
        
        # Start Time
        start_time = datetime.datetime.utcnow() - datetime.timedelta(minutes=random.randint(10, 50))
        completed_at = None
        
        score = 0
        solved = 0
        
        # Violations (Random)
        v_count = 0
        if random.random() > 0.7:
             v_count = random.randint(1, 4)
             # Insert Violations
             for _ in range(v_count):
                 # Use INSERT - violations are just log
                 db_manager.execute_update("""
                    INSERT INTO violations (user_id, contest_id, violation_type, description, severity, penalty_points, level)
                    VALUES (%s, %s, 'TAB_SWITCH', 'Switched tab during exam', 'medium', 1, 1)
                 """, (uid, contest_id))
        
        # Update Proctoring Summary (participant_proctoring)
        # Using REPLACE INTO for compatibility
        db_manager.execute_update("""
            REPLACE INTO participant_proctoring (id, participant_id, user_id, contest_id, risk_level, total_violations, violation_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (f"{uid}_proc", uname, uid, contest_id, 'medium' if v_count > 2 else 'low', v_count, v_count))

        # Submissions
        if qs:
            for q in qs:
                qid = q['question_id']
                # Randomly attempt
                if random.random() > 0.1: # 90% attempt rate
                    # Randomly correct
                    is_correct = (random.random() > 0.3) # 70% success chance
                    
                    # Failed attempts
                    if is_correct:
                        # Maybe 1-2 failed before success
                        fails = random.randint(0, 2)
                        for _ in range(fails):
                            db_manager.execute_update("""
                                INSERT INTO submissions (user_id, contest_id, round_id, question_id, submitted_code, is_correct, score_awarded, status)
                                VALUES (%s, %s, %s, %s, 'def fail(): pass', 0, 0, 'evaluated')
                            """, (uid, contest_id, q['round_id'], qid))
                        
                        # Success
                        db_manager.execute_update("""
                            INSERT INTO submissions (user_id, contest_id, round_id, question_id, submitted_code, is_correct, score_awarded, status)
                            VALUES (%s, %s, %s, %s, 'def success(): return True', 1, 10, 'evaluated')
                        """, (uid, contest_id, q['round_id'], qid))
                        score += 10
                        solved += 1
                    else:
                        # Just failed
                        db_manager.execute_update("""
                            INSERT INTO submissions (user_id, contest_id, round_id, question_id, submitted_code, is_correct, score_awarded, status)
                            VALUES (%s, %s, %s, %s, 'def fail_final(): pass', 0, 0, 'evaluated')
                        """, (uid, contest_id, q['round_id'], qid))

        if status == 'COMPLETED':
            if qs and solved < len(qs): status = 'IN_PROGRESS' # Logic check: if not all solved, maybe not complete? Or gave up.
            else:
                completed_at = start_time + datetime.timedelta(minutes=random.randint(5, 20))

        # Insert Stats
        # REPLACE INTO to handle existing rows
        db_manager.execute_update("""
            REPLACE INTO participant_level_stats (user_id, contest_id, level, status, questions_solved, level_score, violation_count, start_time, completed_at)
            VALUES (%s, %s, 1, %s, %s, %s, %s, %s, %s)
        """, (uid, contest_id, status, solved, score, v_count, start_time, completed_at))
        
        # Update Leaderboard
        time_taken = 0
        if completed_at:
            time_taken = int((completed_at - start_time).total_seconds())
        else:
             time_taken = int((datetime.datetime.utcnow() - start_time).total_seconds())

        db_manager.execute_update("""
            REPLACE INTO leaderboard (user_id, contest_id, rank_position, total_score, total_time_taken_seconds, questions_correct, violations_count, current_round)
            VALUES (%s, %s, 0, %s, %s, %s, %s, 1)
        """, (uid, contest_id, score, time_taken, solved, v_count))
        
        print(f"Processed {uname}: {status}, Score={score}")

    print("Activity Population Complete.")
    
if __name__ == '__main__':
    populate_activity()
