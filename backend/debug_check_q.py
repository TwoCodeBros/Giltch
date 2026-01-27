
from db_connection import db_manager
import json

def check():
    print("Checking Database via Manager...")
    try:
        # Check rounds
        print("--- Rounds ---")
        rounds = db_manager.execute_query("SELECT round_id, round_name, allowed_language FROM rounds")
        for r in rounds:
            print(f"R{r['round_id']}: {r['round_name']} ({r.get('allowed_language')})")
            
        # Check questions
        print("\n--- Questions ---")
        # Do not select 'allowed_language' from questions as it doesn't exist
        questions = db_manager.execute_query("SELECT question_id, round_id, question_number, question_title FROM questions")
        if questions:
            for q in questions:
                print(f"Q{q['question_id']} (Round {q['round_id']}, Num {q['question_number']}): {q['question_title']}")
        else:
            print("No questions found or query failed.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check()
