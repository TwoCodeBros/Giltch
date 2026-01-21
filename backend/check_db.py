from backend.db_connection import db_manager

def check():
    parts = db_manager.execute_query("SELECT count(*) as c FROM users WHERE role='participant'")
    print(f"Participant Count: {parts[0]['c']}")
    
    qs = db_manager.execute_query("SELECT count(*) as c FROM questions")
    print(f"Question Count: {qs[0]['c']}")

    all_users = db_manager.execute_query("SELECT username FROM users WHERE role='participant'")
    print(f"Usernames: {[u['username'] for u in all_users[:5]]} ...")

if __name__ == "__main__":
    check()
