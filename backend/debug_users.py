
from db_connection import db_manager

def check_users():
    print("Checking users table...")
    users = db_manager.execute_query("SELECT user_id, username, role FROM users WHERE role='participant'")
    if users:
        print(f"Found {len(users)} participants.")
        for u in users[:5]:
            print(u)
    else:
        print("No participants found in DB.")

if __name__ == "__main__":
    check_users()
