from flask import Blueprint, jsonify, request
from utils.db import get_db
from auth_middleware import admin_required
import jwt
import datetime
from config import Config

bp = Blueprint('auth', __name__)

def create_token(user_id, role='participant'):
    payload = {
        'sub': user_id,
        'role': role,
        'iat': datetime.datetime.utcnow(),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm='HS256')

# ... (Participant Login kept as is, but I need to handle potential file truncation if I paste too much)
# Participant login is lines 18-66.

@bp.route('/participant/login', methods=['POST'])
def participant_login():
    data = request.get_json()
    pid = data.get('participant_id')
    
    if not pid:
        return jsonify({'error': 'Participant ID is required'}), 400

    db = get_db()
    
    try:
        # In our schema, we'll treat username as participant_id for now
        # or use internal user_id if pid is numeric
        query = db.table('users').select("*").eq("role", "participant")
        if pid.isdigit():
            query = query.eq("user_id", int(pid))
        else:
            query = query.eq("username", pid)
            
        user_query = query.execute()
        user_data = user_query.data
        
        if not user_data:
            return jsonify({'error': 'Participant not found'}), 404

        user = user_data[0]
        
        if user.get('status') == 'disqualified':
            return jsonify({'error': 'You have been disqualified for violations.'}), 403

        # Check Proctoring Table Disqualification (Crucial Fix)
        proc_status = db.table('participant_proctoring').select('is_disqualified').eq('participant_id', user['username']).execute()
        if proc_status.data and proc_status.data[0].get('is_disqualified'):
             return jsonify({'error': 'You have been permanently disqualified for proctoring violations.'}), 403

        if user.get('status') == 'held':
            return jsonify({'error': 'Your status is currently on hold. You have not qualified for the next level.'}), 403

        token = create_token(user['username'], 'participant')
        
        # --- PROCTORING INIT ---
        # Ensure user has a row in participant_proctoring so they show up in Admin dashboard immediately
        try:
             # Find active contest
            c_res = db.execute_query("SELECT contest_id FROM contests WHERE status='live' LIMIT 1")
            active_contest_id = c_res[0]['contest_id'] if c_res else 1
            
            # Check or Init
            proc_check = db.table('participant_proctoring').select("*").eq("participant_id", user['username']).eq("contest_id", active_contest_id).execute()
            if not proc_check.data:
                 import uuid
                 db.table('participant_proctoring').insert({
                    'id': str(uuid.uuid4()),
                    'participant_id': user['username'],
                    'user_id': user['user_id'],
                    'contest_id': active_contest_id,
                    'total_violations': 0,
                    'violation_score': 0, 
                    'risk_level': 'low',
                    'created_at': datetime.datetime.utcnow().isoformat()
                 }).execute()
        except Exception as ex:
            print(f"Proctoring init warning: {ex}")
        # -----------------------
        
        return jsonify({
            'success': True,
            'participant': {
                'id': user['user_id'],
                'participant_id': user['username'],
                'name': user['full_name'],
                'status': user['status']
            },
            'token': token
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/leader/login', methods=['POST'])
def leader_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Username and Password are required'}), 400

    db = get_db()
    try:
        import hashlib
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # Check for Leader role
        user_query = db.table('users').select("*")\
            .eq("username", username)\
            .eq("role", "leader")\
            .execute()
            
        if not user_query.data:
             return jsonify({'error': 'Invalid credentials or not authorized as LEADER'}), 401

        user = user_query.data[0]
        
        if user['password_hash'] != pwd_hash:
             return jsonify({'error': 'Invalid credentials'}), 401
             
        # Check status
        if user.get('admin_status') != 'APPROVED':
             return jsonify({'error': 'Your leader account is not approved.'}), 403
             
        token = create_token(user['username'], 'leader')
        
        return jsonify({
            'success': True, 
            'token': token,
            'leader': {
                'name': user['full_name'],
                'username': user['username']
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Username and Password are required'}), 400

    db = get_db()
    try:
        # We need to use SHA256 since that's what's in the example data
        import hashlib
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        
        user_query = db.table('users').select("*")\
            .eq("username", username)\
            .eq("role", "admin")\
            .execute()
            
        if user_query.data:
            user = user_query.data[0]
            
            # -- Status Check --
            status = user.get('admin_status', 'PENDING')
            if status == 'PENDING':
                return jsonify({'error': '⏳ Your admin request is pending approval.'}), 403
            if status == 'REJECTED':
                return jsonify({'error': '❌ Your admin request has been rejected.'}), 403
            
            # Compare hash
            if user['password_hash'] == pwd_hash:
                return jsonify({
                    'success': True,
                    'token': create_token(user['username'], 'admin'),
                    'user': {
                        'username': user['username'],
                        'name': user['full_name']
                    }
                })
            else:
                return jsonify({'error': 'Invalid credentials'}), 401
        else:
            return jsonify({'error': 'Invalid credentials'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/admin/register', methods=['POST'])
def register_admin():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    full_name = data.get('full_name')
    email = data.get('email')
    
    if not all([username, password, email]):
        return jsonify({'error': 'Username, password and email are required'}), 400
        
    db = get_db()
    
    # Check if exists
    chk = db.table('users').select('*').eq('username', username).execute()
    if chk.data:
        return jsonify({'error': 'Username already exists'}), 400
        
    import hashlib
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    
    try:
        db.table('users').insert({
            'username': username,
            'email': email,
            'password_hash': pwd_hash,
            'full_name': full_name or username,
            'role': 'admin',
            'admin_status': 'PENDING'
        })
        return jsonify({'success': True, 'message': 'Admin registration submitted. Waiting for approval.'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/admin/pending', methods=['GET'])
@admin_required
def get_pending_admins():
    db = get_db()
    try:
        # Fetch admins with PENDING status
        # Since MySQLBridge is limited, we might not have .eq for status if not added
        # But we can use db_manager directly or update bridge
        # Or better, just utilize our robust db_manager here for custom query
        from db_connection import db_manager
        query = "SELECT user_id, username, full_name, created_at, admin_status FROM users WHERE role='admin' AND admin_status='PENDING'"
        res = db_manager.execute_query(query)
        
        # Also maybe fetch all admins for management?
        # Requirement: "Register New Admin option in Admin panel" -> implied list management.
        return jsonify({'pending': res})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/admin/approve', methods=['POST'])
@admin_required
def approve_admin():
    data = request.get_json()
    target_id = data.get('user_id')
    action = data.get('action') # APPROVE or REJECT
    
    if not target_id or action not in ['APPROVE', 'REJECT']:
        return jsonify({'error': 'Invalid request'}), 400
        
    status_map = {'APPROVE': 'APPROVED', 'REJECT': 'REJECTED'}
    new_status = status_map[action]
    
    from db_connection import db_manager
    
    # Get approver ID
    auth_header = request.headers.get('Authorization')
    token = auth_header.split(" ")[1]
    token_data = jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
    approver_username = token_data['sub']
    
    # Get approver INT ID
    u_res = db_manager.execute_query("SELECT user_id FROM users WHERE username=%s", (approver_username,))
    approver_id = u_res[0]['user_id'] if u_res else None
    
    query = "UPDATE users SET admin_status=%s, approved_by=%s, approval_at=NOW() WHERE user_id=%s"
    db_manager.execute_update(query, (new_status, approver_id, target_id))
    
    return jsonify({'success': True, 'status': new_status})

@bp.route('/session', methods=['GET'])
def get_session():
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify(None), 401
    
    try:
        token_parts = auth_header.split(" ")
        if len(token_parts) != 2: return jsonify(None), 401
        token = token_parts[1]
        
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])
        user_id = payload['sub']
        
        db = get_db()
        try:
             u_res = db.table('users').select("*").eq("username", user_id).execute()
             if u_res.data:
                u = u_res.data[0]
                return jsonify({
                    'participant_id': u['user_id'],
                    'username': u['username'],
                    'full_name': u['full_name'],
                    'role': u['role'],
                    'status': u.get('status', 'active'),
                    'admin_status': u.get('admin_status', 'APPROVED') # expose this
                })
        except Exception as e: print(e)
             
        return jsonify(None), 404
    except Exception as e:
        print(f"Session Error: {e}")
        return jsonify(None), 401
