from flask import Blueprint, jsonify, request
from db_connection import db_manager
import uuid
from auth_middleware import admin_required
from werkzeug.security import generate_password_hash
from utils.contest_service import create_question_logic

bp = Blueprint('admin', __name__)

@bp.route('/dashboard', methods=['GET'])
@admin_required
def get_stats():
    # Calculate stats from DB
    participants = db_manager.execute_query("SELECT user_id FROM users WHERE role='participant'")
    questions = db_manager.execute_query("SELECT question_id FROM questions")
    submissions = db_manager.execute_query("SELECT submission_id, is_correct FROM submissions")
    active = db_manager.execute_query("SELECT user_id FROM users WHERE role='participant' AND status='active'")
    violations = db_manager.execute_query("SELECT id FROM violations")

    solved_count = len([s for s in submissions if s['is_correct']]) if submissions else 0

    return jsonify({
        "total_participants": len(participants) if participants else 0,
        "active_contestants": len(active) if active else 0,
        "violations_detected": len(violations) if violations else 0,
        "questions_solved": solved_count
    })

# === Participant Management ===

@bp.route('/participants', methods=['GET'])
@admin_required
def get_participants():
    # Fetch participants with detailed info
    query = """
        SELECT u.user_id, u.username, u.full_name, u.email, u.phone, u.college, u.department, u.status, COALESCE(SUM(s.score_awarded), 0) as score
        FROM users u
        LEFT JOIN submissions s ON u.user_id = s.user_id
        WHERE u.role = 'participant'
        GROUP BY u.user_id, u.username, u.full_name, u.email, u.phone, u.college, u.department, u.status
        ORDER BY score DESC
    """
    res = db_manager.execute_query(query)
    
    participants = []
    if res:
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
    data = request.get_json()
    
    # 1. Determine ID
    pid = data.get('participant_id')
    manual_mode = False
    
    if pid and str(pid).strip():
        # Excel Import or Manual Override
        username = str(pid).strip()
    else:
        # Auto-Generate Mode: SHCCSGF001 pattern
        q = "SELECT username FROM users WHERE username LIKE 'SHCCSGF%' ORDER BY length(username) DESC, username DESC LIMIT 1"
        res = db_manager.execute_query(q)
        last_id = res[0]['username'] if res else "SHCCSGF000"
        
        try:
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
        
        update_existing = data.get('update_existing', False)

        if chk:
            if update_existing:
                # Update existing user
                update_cols = []
                update_vals = []
                if full_name:
                    update_cols.append("full_name=%s")
                    update_vals.append(full_name)
                if data.get('college'):
                    update_cols.append("college=%s")
                    update_vals.append(data.get('college'))
                if data.get('department'):
                    update_cols.append("department=%s")
                    update_vals.append(data.get('department'))
                if data.get('phone'):
                    update_cols.append("phone=%s")
                    update_vals.append(data.get('phone'))
                if data.get('email'):
                    update_cols.append("email=%s")
                    update_vals.append(data.get('email'))
                
                if update_cols:
                    update_q = f"UPDATE users SET {', '.join(update_cols)} WHERE username=%s"
                    update_vals.append(username)
                    db_manager.execute_update(update_q, tuple(update_vals))
                    return jsonify({'success': True, 'participant': new_user, 'status': 'updated'})
                else:
                    return jsonify({'success': True, 'participant': new_user, 'status': 'no_changes'})

            if manual_mode:
                return jsonify({'error': 'System generated duplicate ID. Please try again.'}), 409
            else:
                return jsonify({'error': f"Participant ID '{username}' already exists."}), 409

        cols = ['username', 'email', 'password_hash', 'full_name', 'role', 'status', 'college', 'department', 'phone']
        vals = [
            new_user['username'], 
            new_user['email'], 
            new_user['password_hash'], 
            new_user['full_name'], 
            new_user['role'], 
            new_user['status'], 
            new_user['college'], 
            new_user['department'],
            new_user.get('phone')
        ]
        placeholders = ', '.join(['%s'] * len(cols))
        col_str = ', '.join(cols)
        
        insert_q = f"INSERT INTO users ({col_str}) VALUES ({placeholders})"
        db_res = db_manager.execute_update(insert_q, tuple(vals))
        
        if not db_res:
            return jsonify({'error': 'Database insert failed. See logs.'}), 500
        
        return jsonify({'success': True, 'participant': new_user})
        
    except Exception as e:
        print(f"Create Part Error: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/participants/<pid>', methods=['DELETE'])
@admin_required
def delete_participant(pid):
    # pid is username key in frontend 
    db_manager.execute_update("DELETE FROM users WHERE username=%s", (pid,))
    return jsonify({'success': True})


# === Question Management ===

@bp.route('/questions', methods=['GET'])
@admin_required
def get_questions():
    raw_data = db_manager.execute_query("SELECT * FROM questions")
    
    formatted = []
    if raw_data:
        for q in raw_data:
            formatted.append({
                'id': q.get('question_id'),
                'title': q.get('question_title'),
                'description': q.get('question_description'),
                'difficulty': q.get('difficulty_level'),
                'expected_output': q.get('expected_output'),
                'test_cases': q.get('test_cases'),
                'round_number': q.get('round_id'), # Simplified
                'round_id': q.get('round_id')
            })
        
    return jsonify({'questions': formatted})

@bp.route('/questions', methods=['POST'])
@admin_required
def create_question():
    data = request.get_json()
    
    # Determine Round Number from Difficulty String "Level X"
    diff_str = data.get('difficulty', 'Level 1')
    round_num = 1
    if diff_str.startswith('Level '):
        try:
            round_num = int(diff_str.split(' ')[1])
        except:
            round_num = 1

    try:
        # Uses Logic Utility to avoid circular import and NameError
        # Assuming Contest 1 always for now
        res = create_question_logic(1, round_num, data)
        return jsonify({'success': True, 'question_id': res['id']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/questions/bulk', methods=['POST'])
@admin_required
def create_questions_bulk():
    data = request.get_json()
    questions = data.get('questions', [])
    
    count = 0
    errors = []
    for q in questions:
        diff_str = q.get('difficulty', 'Level 1')
        round_num = 1
        if diff_str.startswith('Level '):
            try: round_num = int(diff_str.split(' ')[1])
            except: pass
        
        try:
            create_question_logic(1, round_num, q)
            count += 1
        except Exception as e:
            errors.append(f"Title {q.get('title')}: {str(e)}")
        
    return jsonify({'success': True, 'count': count, 'errors': errors})

@bp.route('/questions/<qid>', methods=['GET'])
@admin_required
def get_question(qid):
    """Fetch a single question's details for editing"""
    query = "SELECT * FROM questions WHERE question_id=%s"
    res = db_manager.execute_query(query, (qid,))
    
    if not res:
        return jsonify({'error': 'Question not found'}), 404
    
    q = res[0]
    formatted = {
        'id': q.get('question_id'),
        'title': q.get('question_title'),
        'description': q.get('question_description'),
        'difficulty': q.get('difficulty_level'),
        'expected_input': q.get('test_input'),
        'expected_output': q.get('expected_output'),
        'test_cases': q.get('test_cases'),
        'buggy_code': q.get('buggy_code'),
        'round_number': q.get('round_id'),
        'round_id': q.get('round_id'),
        'language': 'python'  # Default, could be extracted from boilerplate if available
    }
    
    return jsonify({'question': formatted})

@bp.route('/questions/<qid>', methods=['PUT'])
@admin_required
def update_question(qid):
    """Update an existing question"""
    data = request.get_json()
    
    # Build dynamic update query based on provided fields
    fields = []
    params = []
    
    if 'title' in data:
        fields.append("question_title=%s")
        params.append(data['title'])
    
    if 'expected_input' in data:
        fields.append("test_input=%s")
        params.append(data['expected_input'])
    
    if 'expected_output' in data:
        fields.append("expected_output=%s")
        params.append(data['expected_output'])
    
    if 'buggy_code' in data:
        fields.append("buggy_code=%s")
        params.append(data['buggy_code'])
    
    if 'round_number' in data:
        # Need to get the round_id from round_number
        round_query = "SELECT round_id FROM rounds WHERE round_number=%s LIMIT 1"
        round_res = db_manager.execute_query(round_query, (data['round_number'],))
        if round_res:
            fields.append("round_id=%s")
            params.append(round_res[0]['round_id'])
    
    if not fields:
        return jsonify({'success': True, 'message': 'No fields to update'})
    
    # Add the question ID to the params
    params.append(qid)
    
    # Execute update
    query = f"UPDATE questions SET {', '.join(fields)} WHERE question_id=%s"
    try:
        db_manager.execute_update(query, tuple(params))
        return jsonify({'success': True, 'message': 'Question updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/questions/<qid>', methods=['DELETE'])
@admin_required
def delete_question(qid):
    db_manager.execute_update("DELETE FROM questions WHERE question_id=%s", (qid,))
    return jsonify({'success': True})


# === Leader Management ===

@bp.route('/leaders', methods=['GET'])
@admin_required
def get_leaders():
    query = "SELECT user_id, username, full_name, department, college, admin_status FROM users WHERE role='leader'"
    leaders = db_manager.execute_query(query)
    
    formatted = []
    if leaders:
        for l in leaders:
            formatted.append({
                'leader_id': l['username'],
                'user_id': l['username'],
                'name': l['full_name'],
                'department': l.get('department', ''),
                'college': l.get('college', ''),
                'status': l.get('admin_status', 'APPROVED')
            })
    return jsonify({'leaders': formatted})

@bp.route('/leaders', methods=['POST'])
@admin_required
def create_leader():
    data = request.get_json()
    
    username = data.get('user_id') 
    password = data.get('password')
    full_name = data.get('name')
    department = data.get('department')
    college = data.get('college')
    
    if not username or not password:
        return jsonify({'error': 'User ID and Password are required'}), 400
        
    # SECURE HASHING
    pwd_hash = generate_password_hash(password)
        
    new_leader = {
        'username': username,
        'email': f"{username}@leader.com",
        'password_hash': pwd_hash,
        'full_name': full_name,
        'role': 'leader',
        'status': 'active',
        'admin_status': 'APPROVED',
        'department': department,
        'college': college
    }
    
    try:
        # Check exist
        chk = db_manager.execute_query("SELECT user_id FROM users WHERE username=%s", (username,))
        if chk:
             return jsonify({'error': 'User ID already exists'}), 400

        cols = ['username', 'email', 'password_hash', 'full_name', 'role', 'status', 'admin_status', 'department', 'college']
        vals = [new_leader[c] for c in cols]
        placeholders = ', '.join(['%s'] * len(cols))
        query = f"INSERT INTO users ({', '.join(cols)}) VALUES ({placeholders})"
        
        db_manager.execute_update(query, tuple(vals))
        
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
    db_manager.execute_update("DELETE FROM users WHERE username=%s AND role='leader'", (lid,))
    return jsonify({'success': True})
