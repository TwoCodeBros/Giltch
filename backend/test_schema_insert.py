import requests
import json
import configparser
import os
import mysql.connector

def test_add_question():
    print("Testing Manual Question Insert to verify Schema...")
    
    config = configparser.ConfigParser()
    config.read('db_config.ini')
    db_config = dict(config['mysql'])
    # clean config
    for k in list(db_config.keys()):
        if k.startswith('pool_'): del db_config[k]
        
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # 1. Ensure Round 1 exists
        cursor.execute("SELECT round_id FROM rounds WHERE round_number=1 LIMIT 1")
        r = cursor.fetchone()
        if not r:
            print("Creating Round 1...")
            # Need a contest
            cursor.execute("SELECT contest_id FROM contests LIMIT 1")
            c = cursor.fetchone()
            if not c:
                 cursor.execute("INSERT INTO contests (contest_name, start_datetime, end_datetime, status) VALUES ('Debug Marathon', NOW(), NOW() + INTERVAL 2 HOUR, 'live')")
                 contest_id = cursor.lastrowid
            else:
                 contest_id = c['contest_id']
                 
            cursor.execute(f"INSERT INTO rounds (contest_id, round_name, round_number, time_limit_minutes, total_questions, status) VALUES ({contest_id}, 'Round 1', 1, 30, 5, 'active')")
            round_id = cursor.lastrowid
        else:
            round_id = r['round_id']
            
        print(f"Using Round ID: {round_id}")
        
        # 2. Try Insert (Simulate Backend Logic)
        query = """
        INSERT INTO questions 
        (round_id, question_number, question_title, question_description, expected_output, buggy_code, difficulty_level, points, test_cases)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        # Next Num
        cursor.execute("SELECT MAX(question_number) as m FROM questions WHERE round_id=%s", (round_id,))
        res = cursor.fetchone()
        next_num = (res['m'] or 0) + 1
        
        vals = (
            round_id,
            next_num,
            "Test Question Schema",
            "This is a test description",
            "Output",
            "print('hello')",
            "easy",
            10,
            json.dumps([])
        )
        
        cursor.execute(query, vals)
        conn.commit()
        print("SUCCESS: Question Inserted.")
        
    except Exception as e:
        print(f"FAILED: {e}")
    finally:
         if 'conn' in locals() and conn.is_connected():
            conn.close()

if __name__ == "__main__":
    test_add_question()
