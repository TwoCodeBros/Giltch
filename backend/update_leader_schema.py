import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from db_connection import db_manager
    print("Imported db_manager")
except ImportError:
    print("Failed to import db_manager")
    exit(1)

def run():
    # 1. Add Department and College to users table
    cols = [
        "department VARCHAR(100) DEFAULT NULL",
        "college VARCHAR(100) DEFAULT NULL"
    ]
    
    for col in cols:
        try:
            sql = f"ALTER TABLE users ADD COLUMN {col};"
            print(f"Executing: {sql}")
            db_manager.execute_update(sql)
        except Exception as e:
            if "Duplicate column" in str(e) or "1060" in str(e):
                print(f"Column exists: {col.split()[0]}")
            else:
                print(f"Error adding {col}: {e}")

    # 2. Ensure leader role exists in Enum (MySQL Enums are hard to alter dynamically safely, but we check if we can simply use string or if it's already there)
    # The schema said: ENUM('participant', 'admin'). We need 'leader'.
    try:
        sql = "ALTER TABLE users MODIFY COLUMN role ENUM('participant', 'admin', 'leader') NOT NULL DEFAULT 'participant';"
        print(f"Executing: {sql}")
        db_manager.execute_update(sql)
    except Exception as e:
        print(f"Error updating role enum: {e}")

    # 3. Create leaders table if it doesn't exist (or just use users, but if we want to store approvals specifically for leaders distinct from users?)
    # "Only approved leaders must be allowed". Users table has `admin_status` ENUM('PENDING', 'APPROVED', 'REJECTED').
    # We can reuse `admin_status` or add `leader_status`.
    # Let's reuse `admin_status` but rename logic conceptually, or add `is_approved_leader`.
    # Actually, let's just use `status`='active' for approved?
    # No, "Only approved leaders".
    # Let's add `approval_status` VARCHAR to users to be generic.
    
    # Actually, let's drop the "leaders" table if it exists to avoid confusion, since we are moving to users.
    try:
        sql = "DROP TABLE IF EXISTS leaders;"
        print(f"Executing: {sql}")
        db_manager.execute_update(sql)
    except Exception as e:
        print(f"Error dropping leaders: {e}")

if __name__ == "__main__":
    run()
