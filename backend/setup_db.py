
from db_connection import db_manager
from seed_data import seed_data
import os

def setup():
    # Detect Schema based on Manager Type
    manager_type = db_manager.__class__.__name__
    print(f"Database Manager: {manager_type}")
    
    if 'SQLite' in manager_type:
        print("Using SQLite Mode.")
        schema_path = os.path.join(os.path.dirname(__file__), 'sqlite_schema.sql')
    else:
        print("Using MySQL Mode.")
        schema_path = os.path.join(os.path.dirname(__file__), 'database_setup.sql')

    print(f"Initializing Database from {os.path.basename(schema_path)}...")
    if db_manager.init_database(schema_path):
        print("Database initialized.")
        try:
            seed_data()
            print("Seeding complete.")
        except Exception as e:
            print(f"Seeding failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Database initialization failed.")

if __name__ == "__main__":
    setup()
