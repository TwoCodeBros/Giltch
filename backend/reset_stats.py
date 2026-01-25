from db_connection import db_manager

def reset_stats():
    print("Resetting all participant stats to 0 (Live Mode)...")
    
    # Clear Stats/Activity Tables
    tables = [
        'submissions',
        'participant_level_stats',
        'leaderboard',
        'participant_proctoring',
        'violations',
        'proctoring_alerts'
    ]
    
    for t in tables:
        print(f"Clearing {t}...")
        db_manager.execute_update(f"DELETE FROM {t}")
        
    # Reset Round Status (Optional: Keep L1 active, others pending)
    # db_manager.execute_update("UPDATE rounds SET status='pending'")
    # db_manager.execute_update("UPDATE rounds SET status='active' WHERE round_number=1")
    
    print("Done! Leaderboard and Stats are now empty and ready for Live data.")

if __name__ == "__main__":
    reset_stats()
