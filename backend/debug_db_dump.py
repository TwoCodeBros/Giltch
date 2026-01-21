import mysql.connector
import configparser
import json

def debug_db_state():
    config = configparser.ConfigParser()
    config.read('db_config.ini')
    db_config = dict(config['mysql'])
    for k in list(db_config.keys()):
        if k.startswith('pool_'): del db_config[k]
        
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        print("=== CONTESTS ===")
        cursor.execute("SELECT contest_id, contest_name, status FROM contests")
        contests = cursor.fetchall()
        for c in contests:
            print(c)
            
        print("\n=== ROUNDS ===")
        cursor.execute("SELECT round_id, contest_id, round_number, round_name, status, total_questions FROM rounds")
        rounds = cursor.fetchall()
        for r in rounds:
            print(r)
            
        print("\n=== QUESTIONS ===")
        cursor.execute("SELECT question_id, round_id, question_number, question_title, difficulty_level FROM questions")
        questions = cursor.fetchall()
        for q in questions:
            print(q)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()

if __name__ == "__main__":
    debug_db_state()
