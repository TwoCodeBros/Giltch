import requests
import json

def test_get_questions_fallback():
    # Sending 'null' string as it might appear from JS template literals if not careful, or just omitting it.
    # Frontend says: `/contest/questions?contest_id=${this.activeContestId}...`
    # If activeContestId is user's null, it becomes string "null".
    
    url = "http://127.0.0.1:5000/api/contest/questions?contest_id=null&level=1"
    try:
        print(f"Requesting: {url}")
        res = requests.get(url)
        print(f"Status Code: {res.status_code}")
        
        if res.status_code == 200:
            data = res.json()
            questions = data.get('questions', [])
            print(f"Question Count: {len(questions)}")
        else:
            print("Response:", res.text)
            
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_get_questions_fallback()
