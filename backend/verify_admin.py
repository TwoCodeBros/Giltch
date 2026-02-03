import sys
sys.path.insert(0, '.')
from db_connection import db_manager

# Check admin user status
result = db_manager.execute_query('SELECT username, role, admin_status FROM users WHERE role=%s', ('admin',))
if result:
    for row in result:
        print(f'Admin user - Username: {row.get("username")}, Role: {row.get("role")}, Status: {row.get("admin_status")}')
else:
    print("No admin user found")
