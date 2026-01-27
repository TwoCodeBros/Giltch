
from db_connection import db_manager
import json

qid = 15
query = """
    SELECT q.test_input, q.expected_output, q.test_cases, r.allowed_language
    FROM questions q
    LEFT JOIN rounds r ON q.round_id = r.round_id
    WHERE q.question_id = %s
"""

print(f"Testing Query with ID: {qid} (int)")
res = db_manager.execute_query(query, (qid,))
print(f"Result (int): {res}")

qid_str = "15"
print(f"Testing Query with ID: '{qid_str}' (str)")
res2 = db_manager.execute_query(query, (qid_str,))
print(f"Result (str): {res2}")
