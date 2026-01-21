import requests
import json

def test_get_questions():
    url = "http://127.0.0.1:5000/api/contest/questions?contest_id=1&level=1"
    try:
        print(f"Requesting: {url}")
        res = requests.get(url)
        print(f"Status Code: {res.status_code}")
        
        if res.status_code == 200:
            data = res.json()
            questions = data.get('questions', [])
            print(f"Question Count: {len(questions)}")
            for q in questions:
                 print(f"ID: {q['id']}, Title: {q['title']}, Level: {q.get('round_number')}, Difficulty: {q.get('difficulty')}")
        else:
            print("Response:", res.text)
            
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_get_questions()
