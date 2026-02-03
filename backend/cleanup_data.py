
from db_connection import db_manager

def clear_data():
    print("Starting data cleanup...")
    
    # 1. Clear Submissions (FK to Questions and Users)
    print("Clearing submissions...")
    db_manager.execute_update("DELETE FROM submissions")
    
    # 2. Clear Participant Data tables
    print("Clearing participant stats and violations...")
    db_manager.execute_update("DELETE FROM participant_level_stats")
    db_manager.execute_update("DELETE FROM participant_proctoring")
    db_manager.execute_update("DELETE FROM violations")
    db_manager.execute_update("DELETE FROM leaderboard")
    db_manager.execute_update("DELETE FROM shortlisted_participants")
    
    # 3. Clear Questions
    print("Clearing questions...")
    db_manager.execute_update("DELETE FROM questions")
    
    # 4. Clear Participants (Keep Admins/Leaders)
    print("Clearing participants...")
    # Get IDs first to be safe or just delete where role='participant'
    db_manager.execute_update("DELETE FROM users WHERE role='participant'")
    
    print("Cleanup complete!")

if __name__ == "__main__":
    clear_data()
