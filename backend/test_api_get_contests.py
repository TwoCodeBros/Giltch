import requests
import json

def test_get_contests():
    url = "http://127.0.0.1:5000/api/contest"
    try:
        res = requests.get(url)
        print(json.dumps(res.json(), indent=2))
    except Exception as e:
        print(e)

if __name__ == "__main__":
    test_get_contests()
