
# seed_data.py

from db_connection import db_manager
import datetime
import json
import traceback

def seed_data():
    print("Beginning Seed Data...")
    
    # Define Queries
    queries = {
        'create_contest': """
            INSERT INTO contests (contest_name, description, start_datetime, end_datetime, status, max_violations_allowed)
            VALUES ('Debug Marathon 2026', 'Fix the glitches to win!', '2026-01-26 10:00:00', '2026-01-27 10:00:00', 'live', 50)
        """,
        'create_round': """
            INSERT INTO rounds (contest_id, round_name, round_number, time_limit_minutes, total_questions, status, is_locked, allowed_language)
            VALUES (?, 'Level 1 - Basics', 1, 60, 2, 'active', 0, 'python')
        """,
        'create_user': """
            INSERT INTO users (username, email, password_hash, full_name, role)
            VALUES ('PART001', 'part001@example.com', 'scrypt:32768:8:1$dummyhash', 'Participant One', 'participant')
        """,
        'create_question_1': """
            INSERT INTO questions (round_id, question_number, question_title, question_description, buggy_code, expected_output, test_cases, difficulty_level, points)
            VALUES (?, 1, 'Fix the Sum', 'The function should return the sum of two numbers, but it subtracts them.', 
            'def solve(a, b):\n    return a - b\n\nif __name__ == "__main__":\n    import sys\n    input = sys.stdin.read\n    data = input().split()\n    # Assume inputs are provided line by line or space separated\n    # For simplicity of test runner:\n    pass', 
            '5', 
            ?, 
            'Easy', 10)
        """,
        'create_question_2': """
            INSERT INTO questions (round_id, question_number, question_title, question_description, buggy_code, expected_output, test_cases, difficulty_level, points)
            VALUES (?, 2, 'Array Reverse', 'Reverse the array but it returns sorted array.', 
            'def solve(arr):\n    return sorted(arr)\n', 
            '[3, 2, 1]', 
            ?, 
            'Easy', 20)
        """
    }

    try:
        # Check if contest exists
        existing_contests = db_manager.execute_query("SELECT contest_id FROM contests")
        contest_id = 1
        if not existing_contests:
            print("Creating Contest...")
            res = db_manager.execute_update(queries['create_contest'])
            contest_id = res['last_id']
        else:
            contest_id = existing_contests[0]['contest_id']
            print(f"Contest exists: ID {contest_id}")

        # Check if round exists
        existing_rounds = db_manager.execute_query("SELECT round_id FROM rounds WHERE contest_id=%s AND round_number=1", (contest_id,))
        round_id = 1
        if not existing_rounds:
            print("Creating Round 1...")
            # For SQLite, use params as tuple
            res = db_manager.execute_update("INSERT INTO rounds (contest_id, round_name, round_number, time_limit_minutes, total_questions, status, is_locked, allowed_language) VALUES (%s, 'Level 1 - Basics', 1, 60, 2, 'active', 0, 'python')", (contest_id,))
            round_id = res['last_id']
        else:
            round_id = existing_rounds[0]['round_id']
            print(f"Round 1 exists: ID {round_id}")

        # Check if user exists
        existing_users = db_manager.execute_query("SELECT user_id FROM users WHERE username='PART001'")
        if not existing_users:
            print("Creating User PART001...")
            db_manager.execute_update(queries['create_user'])
        else:
            print("User PART001 exists")

        # Check questions
        existing_q = db_manager.execute_query("SELECT question_id FROM questions WHERE round_id=%s", (round_id,))
        
        if not existing_q:
            print("Creating Questions...")
            # Q1 Test Cases
            tcs1 = json.dumps([
                {"input": "2 3", "expected": "5"},
                {"input": "10 5", "expected": "15"}
            ])
            # Buggy Code for Q1
            buggy1 = "import sys\n\ndef solve(a, b):\n    return a - b  # Bug: should be a + b\n\nif __name__ == '__main__':\n    # Simple runner\n    line = sys.stdin.read().strip()\n    if line:\n        parts = line.split()\n        if len(parts) >= 2:\n            print(solve(int(parts[0]), int(parts[1])))"
            
            db_manager.execute_update("""
                INSERT INTO questions (round_id, question_number, question_title, question_description, buggy_code, expected_output, test_cases, difficulty_level, points, test_input)
                VALUES (%s, 1, 'Fix the Sum', 'The function should return the sum of two numbers, but it subtracts them.', %s, '5', %s, 'Easy', 10, '2 3')
            """, (round_id, buggy1, tcs1))

            # Q2
            tcs2 = json.dumps([
                {"input": "1,2,3", "expected": "[3, 2, 1]"},
                {"input": "5,1,9", "expected": "[9, 1, 5]"}
            ])
            buggy2 = "import sys\nimport ast\n\ndef solve(arr):\n    return sorted(arr) # Bug: should reverse\n\nif __name__ == '__main__':\n    input_str = sys.stdin.read().strip()\n    if input_str:\n        arr = [int(x) for x in input_str.split(',')]\n        print(solve(arr))"

            db_manager.execute_update("""
                INSERT INTO questions (round_id, question_number, question_title, question_description, buggy_code, expected_output, test_cases, difficulty_level, points, test_input)
                VALUES (%s, 2, 'Array Reverse', 'Reverse the array.', %s, '[3, 2, 1]', %s, 'Easy', 20, '1,2,3')
            """, (round_id, buggy2, tcs2))
            
        else:
            print("Questions exist")
            
        print("Seed Data Completed Successfully.")

    except Exception as e:
        print(f"Seed Data Failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    seed_data()
