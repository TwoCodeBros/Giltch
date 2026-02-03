
from db_connection import db_manager

def update_schema():
    print("Starting schema update...")
    
    # 1. Expand standard columns
    expand_cmds = [
        "ALTER TABLE users MODIFY full_name VARCHAR(255) DEFAULT NULL",
        "ALTER TABLE users MODIFY department VARCHAR(255) DEFAULT NULL",
        "ALTER TABLE users MODIFY college VARCHAR(255) DEFAULT NULL",
        "ALTER TABLE users MODIFY email VARCHAR(255) NOT NULL"
    ]
    
    for cmd in expand_cmds:
        print(f"Executing: {cmd}")
        db_manager.execute_update(cmd)

    # 2. Add Phone Column (Handle existence check implicitly via try/catch in db wrapper, but we want to be sure)
    print("Attempting to add 'phone' column...")
    res = db_manager.execute_update("ALTER TABLE users ADD COLUMN phone VARCHAR(50) DEFAULT NULL")
    if res:
        print(" -> 'phone' column added.")
    else:
        print(" -> 'phone' column might already exist or error occurred.")

if __name__ == "__main__":
    update_schema()
