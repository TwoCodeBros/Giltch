from flask import Blueprint, jsonify, request
from utils.db import get_db
import uuid
from auth_middleware import admin_required

bp = Blueprint('admin', __name__)

@bp.route('/dashboard', methods=['GET'])
@admin_required
def get_stats():
    db = get_db()
    
    # Calculate stats from DB - filter by role
    participants = db.table('users').select("*").eq("role", "participant").execute().data
    questions = db.table('questions').select("*").execute().data
    submissions = db.table('submissions').select("*").execute().data
    active = [p for p in participants if p.get('status') == 'active']
    violations = db.table('violations').select("*").execute().data

    return jsonify({
        "total_participants": len(participants),
        "active_contestants": len(active),
        "violations_detected": len(violations),
        "questions_solved": len([s for s in submissions if s.get('is_correct') == True])
    })

# === Participant Management ===

@bp.route('/participants', methods=['GET'])
@admin_required
def get_participants():
    from db_connection import db_manager
    # Fetch participants with detailed info
    query = """
        SELECT u.user_id, u.username, u.full_name, u.email, u.college, u.department, u.status, COALESCE(SUM(s.score_awarded), 0) as score
        FROM users u
        LEFT JOIN submissions s ON u.user_id = s.user_id
        WHERE u.role = 'participant'
        GROUP BY u.user_id, u.username, u.full_name, u.email, u.college, u.department, u.status
        ORDER BY score DESC
    """
    res = db_manager.execute_query(query)
    
    participants = []
    for r in res:
        participants.append({
            'id': r['username'], 
            'participant_id': r['username'],
            'name': r['full_name'] or r['username'],
            'email': r.get('email'),
            'phone': r.get('phone', ''),
            'college': r.get('college'),
            'department': r.get('department'),
            'status': r['status'],
            'score': float(r['score'])
        })
        
    return jsonify({'participants': participants})

@bp.route('/participants', methods=['POST'])
@admin_required
def create_participant():
    db = get_db()
    data = request.get_json()
    from db_connection import db_manager
    
    # 1. Determine ID
    pid = data.get('participant_id')
    manual_mode = False
    
    if pid and str(pid).strip():
        # Excel Import or Manual Override
        username = str(pid).strip()
    else:
        # Auto-Generate Mode: SHCCSGF001 pattern
        # Find latest ID
        q = "SELECT username FROM users WHERE username LIKE 'SHCCSGF%' ORDER BY length(username) DESC, username DESC LIMIT 1"
        res = db_manager.execute_query(q)
        last_id = res[0]['username'] if res else "SHCCSGF000"
        
        try:
            # Extract number
            num_part = int(last_id.replace("SHCCSGF", ""))
            new_num = num_part + 1
        except:
            new_num = 1
            
        username = f"SHCCSGF{new_num:03d}"
        manual_mode = True

    full_name = data.get('name', 'Unknown')
    
    new_user = {
        'username': username,
        'email': data.get('email') or f"{username}@example.com", 
        'password_hash': 'sha256_placeholder', 
        'full_name': full_name,
        'college': data.get('college'),
        'department': data.get('department'),
        'phone': data.get('phone'),
        'role': 'participant',
        'status': 'active'
    }
    
    try:
        # Check duplication
        chk = db_manager.execute_query("SELECT user_id FROM users WHERE username=%s", (username,))
        if chk:
            if manual_mode:
                # If auto-gen collided (rare), try one more time? Or fail.
                return jsonify({'error': 'System generated duplicate ID. Please try again.'}), 409
            else:
                return jsonify({'error': f"Participant ID '{username}' already exists."}), 409

        # Insert - Using explicit query to ensure columns are hit (and to avoid table object limitations if cols missing in schema def)
        # Note: If college/dept cols don't exist in DB, this will fail. We should ideally ensure they exist.
        # But 'db.table().insert()' usually handles mapped schema. Let's use db_manager for safety.
        
        cols = ['username', 'email', 'password_hash', 'full_name', 'role', 'status', 'college', 'department']
        vals = [new_user[c] for c in cols]
        placeholders = ', '.join(['%s'] * len(cols))
        col_str = ', '.join(cols)
        
        insert_q = f"INSERT INTO users ({col_str}) VALUES ({placeholders})"
        db_manager.execute_update(insert_q, tuple(vals))
        
        return jsonify({'success': True, 'participant': new_user})
        
    except Exception as e:
        print(f"Create Part Error: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/participants/<pid>', methods=['DELETE'])
@admin_required
def delete_participant(pid):
    db = get_db()
    # Now that we have a real delete in the bridge, let's use it
    db.table('users').delete().eq('username', pid).execute()
    return jsonify({'success': True})


# === Question Management ===

@bp.route('/questions', methods=['GET'])
@admin_required
def get_questions():
    db = get_db()
    data = db.table('questions').select("*").execute().data
    return jsonify({'questions': data})

@bp.route('/questions', methods=['POST'])
@admin_required
def create_question():
    db = get_db()
    data = request.get_json()
    
    new_q = {
        'id': str(uuid.uuid4()),
        'title': data.get('title'),
        'difficulty': data.get('difficulty'),
        'language': data.get('language', 'python'),
        'time_limit': data.get('time_limit', 20),
        'expected_input': data.get('expected_input'),
        'expected_output': data.get('expected_output'),
        'test_cases': data.get('test_cases', []), 
        'boilerplate': data.get('boilerplate', {})
    }
    
    # Logic: Assign to Contest 1
    # Determine Round Number from Difficulty String "Level X"
    diff_str = new_q['difficulty']
    round_num = 1
    if diff_str.startswith('Level '):
        try:
            round_num = int(diff_str.split(' ')[1])
        except:
             round_num = 1

    contest.create_round_question(1, round_num, new_q)
    return jsonify({'success': True, 'question': new_q})

@bp.route('/questions/bulk', methods=['POST'])
@admin_required
def create_questions_bulk():
    db = get_db()
    data = request.get_json()
    questions = data.get('questions', [])
    
    new_qs = []
    for q in questions:
        new_q = {
            'id': str(uuid.uuid4()),
            'title': q.get('title'),
            'difficulty': q.get('difficulty', 'Level 1'),
            'expected_input': q.get('expected_input'),
            'expected_output': q.get('expected_output'),
            'test_cases': q.get('test_cases', []),
            'boilerplate': q.get('boilerplate', {})
        }
        new_qs.append(new_q)
        db.table('questions').insert(new_q).execute()
        
    return jsonify({'success': True, 'count': len(new_qs)})

@bp.route('/questions/<qid>', methods=['DELETE'])
@admin_required
def delete_question(qid):
    db = get_db()
    db.table('questions').delete().eq('id', qid).execute()
    return jsonify({'success': True})


# === Leader Management ===

@bp.route('/leaders', methods=['GET'])
@admin_required
def get_leaders():
    db = get_db()
    # Fetch users with role 'leader'
    leaders = db.table('users').select("user_id", "username", "full_name", "department", "college", "admin_status")\
        .eq("role", "leader").execute().data
        
    # Format for frontend
    formatted = []
    for l in leaders:
        formatted.append({
            'leader_id': l['username'], # Use username as ID for frontend
            'user_id': l['username'],
            'name': l['full_name'],
            'department': l.get('department', ''),
            'college': l.get('college', ''),
            'status': l.get('admin_status', 'APPROVED') # Default approved if not set? Or use status
        })
    return jsonify({'leaders': formatted})

@bp.route('/leaders', methods=['POST'])
@admin_required
def create_leader():
    db = get_db()
    data = request.get_json()
    
    username = data.get('user_id') 
    password = data.get('password')
    full_name = data.get('name')
    department = data.get('department')
    college = data.get('college')
    
    if not username or not password:
        return jsonify({'error': 'User ID and Password are required'}), 400
        
    import hashlib
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        
    # Insert into users table
    new_leader = {
        'username': username,
        'email': f"{username}@leader.com",
        'password_hash': pwd_hash,
        'full_name': full_name,
        'role': 'leader',
        'status': 'active',
        'admin_status': 'APPROVED', # Auto-approve leaders added by Admin
        'department': department,
        'college': college
    }
    
    try:
        # Check exist
        chk = db.table('users').select("*").eq("username", username).execute()
        if chk.data:
             return jsonify({'error': 'User ID already exists'}), 400

        db.table('users').insert(new_leader).execute()
        
        return jsonify({'success': True, 'leader': {
            'leader_id': username,
            'user_id': username,
            'name': full_name,
            'department': department,
            'college': college
        }})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/leaders/<lid>', methods=['DELETE'])
@admin_required
def delete_leader(lid):
    db = get_db()
    # lid is username
    db.table('users').delete().eq('username', lid).eq('role', 'leader').execute()
    return jsonify({'success': True})
