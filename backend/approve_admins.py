import mysql.connector
import configparser
import os

def approve_all_admins():
    print("Approving all admin users...")
    
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'db_config.ini')
    config.read(config_path)
    
    db_config = dict(config['mysql'])
    # Remove pool keys
    for key in ['pool_name', 'pool_size', 'pool_reset_session']:
        db_config.pop(key, None)

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # Update command
        cursor.execute("UPDATE users SET admin_status='APPROVED' WHERE role='admin'")
        conn.commit()
        
        print(f"Updated {cursor.rowcount} admin users to APPROVED status.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()

if __name__ == "__main__":
    approve_all_admins()
