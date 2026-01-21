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
    # Fetch participants with total score
    query = """
        SELECT u.user_id, u.username, u.full_name, u.status, COALESCE(SUM(s.score_awarded), 0) as score
        FROM users u
        LEFT JOIN submissions s ON u.user_id = s.user_id
        WHERE u.role = 'participant'
        GROUP BY u.user_id, u.username, u.full_name, u.status
        ORDER BY score DESC
    """
    res = db_manager.execute_query(query)
    
    participants = []
    for r in res:
        participants.append({
            'id': r['username'], # Frontend expects username as ID string
            'participant_id': r['username'],
            'name': r['full_name'] or r['username'],
            'status': r['status'],
            'score': float(r['score'])
        })
        
    return jsonify({'participants': participants})

@bp.route('/participants', methods=['POST'])
@admin_required
def create_participant():
    db = get_db()
    data = request.get_json()
    
    # Map to 'users' table schema
    username = data.get('participant_id') or f"PART{str(uuid.uuid4())[:4].upper()}"
    full_name = data.get('name', 'Unknown')
    
    new_user = {
        'username': username,
        'email': f"{username}@example.com", # Placeholder
        'password_hash': 'sha256_placeholder', # Real apps would need a password or random gen
        'full_name': full_name,
        'role': 'participant',
        'status': 'active'
    }
    
    db.table('users').insert(new_user).execute()
    # Return matched format for frontend
    new_user['id'] = username # Mock ID for immediate return
    new_user['participant_id'] = username
    new_user['name'] = full_name
    
    return jsonify({'success': True, 'participant': new_user})

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
