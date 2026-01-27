
from db_connection import db_manager
import json

print("--- QUESTIONS ---")
try:
    questions = db_manager.execute_query("SELECT question_id, round_id, question_number, question_title FROM questions")
    for q in questions:
        print(f"ID: {q['question_id']} (Type: {type(q['question_id'])}) | Round: {q['round_id']} | Num: {q['question_number']} | Title: {q['question_title']}")
except Exception as e:
    print(f"Error fetching questions: {e}")

print("\n--- ROUNDS ---")
try:
    rounds = db_manager.execute_query("SELECT round_id, round_number, contest_id FROM rounds")
    for r in rounds:
        print(f"ID: {r['round_id']} | Num: {r['round_number']} | Contest: {r['contest_id']}")
except Exception as e:
    print(f"Error fetching rounds: {e}")
