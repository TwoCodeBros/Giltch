from flask import Blueprint, jsonify, request
import subprocess
import tempfile
import os
import uuid
import datetime
import json
from db_connection import db_manager
from auth_middleware import admin_required

bp = Blueprint('contest', __name__)

# === Contest Management (Admin) ===

@bp.route('/', methods=['GET'])
def get_contests():
    query = "SELECT contest_id as id, contest_name as title, description, start_datetime, end_datetime, status, max_violations_allowed FROM contests ORDER BY start_datetime DESC"
    res = db_manager.execute_query(query)
    
    if not res:
        return jsonify({'contests': []})

    # Format dates
    for c in res:
        if c['start_datetime']: c['start_datetime'] = c['start_datetime'].isoformat()
        if c['end_datetime']: c['end_datetime'] = c['end_datetime'].isoformat()
        
    return jsonify({'contests': res})

@bp.route('/', methods=['POST'])
@admin_required
def create_contest():
    data = request.get_json()
    query = """
        INSERT INTO contests (contest_name, description, start_datetime, end_datetime, status, max_violations_allowed)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    params = (
        data.get('title'),
        data.get('description'),
        data.get('start_time'),
        data.get('end_time'),
        data.get('status', 'draft'),
        data.get('max_violations', 10)
    )
    try:
        res = db_manager.execute_update(query, params)
        return jsonify({'success': True, 'message': "Contest Created"}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<contest_id>', methods=['PUT'])
@admin_required
def update_contest(contest_id):
    data = request.get_json()
    fields = []
    params = []
    if 'title' in data:
        fields.append("contest_name=%s")
        params.append(data['title'])
    if 'status' in data:
        fields.append("status=%s")
        params.append(data['status'])
    if 'current_level' in data:
        fields.append("current_round=%s")
        params.append(data['current_level'])
        
    if not fields:
        return jsonify({'success': True})
        
    params.append(contest_id)
    query = f"UPDATE contests SET {', '.join(fields)} WHERE contest_id=%s"
    db_manager.execute_update(query, tuple(params))
    
    from extensions import socketio
    socketio.emit('contest:updated', {'contest_id': contest_id, 'data': data})
    
    return jsonify({'success': True})

@bp.route('/<contest_id>/countdown', methods=['GET', 'POST'])
@admin_required
def manage_countdown(contest_id):
    if request.method == 'POST':
        data = request.get_json()
        action = data.get('action') # 'start' or 'stop'
        duration = data.get('duration') # in minutes
        
        from extensions import socketio
        key_name = f"contest_{contest_id}_countdown"
        
        if action == 'start':
            # Calculate end time
            end_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=int(duration))
            val = json.dumps({'active': True, 'end_time': end_time.isoformat(), 'duration': duration})
            
            db_manager.execute_update(
                "INSERT INTO admin_state (key_name, value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE value=%s",
                (key_name, val, val)
            )
            socketio.emit('contest:countdown', {'contest_id': contest_id, 'active': True, 'end_time': end_time.isoformat(), 'duration': duration})
            
        elif action == 'stop':
            val = json.dumps({'active': False})
            db_manager.execute_update(
                "INSERT INTO admin_state (key_name, value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE value=%s",
                (key_name, val, val)
            )
            socketio.emit('contest:countdown', {'contest_id': contest_id, 'active': False})
            
        return jsonify({'success': True})
    else:
        key_name = f"contest_{contest_id}_countdown"
        res = db_manager.execute_query("SELECT value FROM admin_state WHERE key_name=%s", (key_name,))
        if res:
             try:
                 return jsonify(json.loads(res[0]['value']))
             except: pass
        return jsonify({'active': False})

# === Control ===

@bp.route('/<contest_id>/control/start', methods=['POST'])
@admin_required
def start_contest(contest_id):
    # Set status to live and update start time
    query = "UPDATE contests SET status='live', start_datetime=NOW() WHERE contest_id=%s"
    db_manager.execute_update(query, (contest_id,))
    
    from extensions import socketio
    socketio.emit('contest:started', {
        'contest_id': contest_id,
        'start_time': datetime.datetime.utcnow().isoformat(),
        'server_time': datetime.datetime.utcnow().isoformat()
    })
    return jsonify({'success': True})

@bp.route('/<contest_id>/control/pause', methods=['POST'])
@admin_required
def pause_contest(contest_id):
    query = "UPDATE contests SET status='paused' WHERE contest_id=%s"
    db_manager.execute_update(query, (contest_id,))
    from extensions import socketio
    socketio.emit('contest:paused', {'contest_id': contest_id})
    return jsonify({'success': True})

@bp.route('/<contest_id>/control/end', methods=['POST'])
@admin_required
def end_contest(contest_id):
    query = "UPDATE contests SET status='ended', end_datetime=NOW() WHERE contest_id=%s"
    db_manager.execute_update(query, (contest_id,))
    from extensions import socketio
    socketio.emit('contest:ended', {'contest_id': contest_id})
    return jsonify({'success': True})

@bp.route('/<contest_id>/level/<int:level_number>/activate', methods=['POST'])
@admin_required
def activate_level_admin(contest_id, level_number):
    # Set all active to pending
    db_manager.execute_update("UPDATE rounds SET status='pending' WHERE contest_id=%s AND status='active'", (contest_id,))
    
    # Set target to active
    db_manager.execute_update("UPDATE rounds SET status='active' WHERE contest_id=%s AND round_number=%s", (contest_id, level_number))
    
    from extensions import socketio
    socketio.emit('level:activated', {'contest_id': contest_id, 'level': level_number})
    # Also broadcast generic contest update to ensure all clients refresh state
    socketio.emit('contest:updated', {'contest_id': contest_id})
    
    return jsonify({'success': True})

@bp.route('/<contest_id>/level/<int:level_number>/pause', methods=['POST'])
@admin_required
def pause_level_admin(contest_id, level_number):
    db_manager.execute_update("UPDATE rounds SET status='paused' WHERE contest_id=%s AND round_number=%s", (contest_id, level_number))
    from extensions import socketio
    socketio.emit('level:paused', {'contest_id': contest_id, 'level': level_number})
    # Also broadcast generic contest update
    socketio.emit('contest:updated', {'contest_id': contest_id})
    return jsonify({'success': True})

@bp.route('/<contest_id>/level/<int:level_number>/complete', methods=['POST'])
@admin_required
def complete_level_admin(contest_id, level_number):
    # Set to completed
    db_manager.execute_update("UPDATE rounds SET status='completed' WHERE contest_id=%s AND round_number=%s", (contest_id, level_number))
    
    from extensions import socketio
    socketio.emit('level:completed', {'contest_id': contest_id, 'level': level_number})
    
    return jsonify({'success': True})

@bp.route('/<contest_id>/rounds/<int:round_number>', methods=['PUT'])
@admin_required
def update_round(contest_id, round_number):
    data = request.get_json()
    time_limit = data.get('time_limit')
    
    if time_limit is not None:
        db_manager.execute_update(
            "UPDATE rounds SET time_limit_minutes=%s WHERE contest_id=%s AND round_number=%s",
            (time_limit, contest_id, round_number)
        )
    
    # Handle Question Reordering
    # Expects: questions_order = [{'id': 123, 'number': 1}, ...]
    questions_order = data.get('questions_order')
    if questions_order:
         for q in questions_order:
             db_manager.execute_update(
                 "UPDATE questions SET question_number=%s WHERE question_id=%s",
                 (q['number'], q['id'])
             )

    return jsonify({'success': True})

@bp.route('/<contest_id>/rounds/<int:round_number>/question', methods=['POST'])
@admin_required
def create_round_question(contest_id, round_number):
    data = request.get_json()
    
    # 1. Get Round ID
    r_query = "SELECT round_id FROM rounds WHERE contest_id=%s AND round_number=%s"
    r_res = db_manager.execute_query(r_query, (contest_id, round_number))
    if not r_res:
        return jsonify({'error': 'Round not found'}), 404
    round_id = r_res[0]['round_id']
    
    # 2. Insert Question
    q_query = """
        INSERT INTO questions 
        (round_id, question_number, question_title, question_description, expected_output, buggy_code, difficulty_level, points, test_cases)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    # Default values
    points = data.get('points', 10)
    test_cases = json.dumps(data.get('test_cases', []))
    difficulty = data.get('difficulty', 'Level 1')
    language = data.get('language', 'python')
    time_limit = data.get('time_limit', 20)
    
    # Helper: Update Level Duration if provided
    if time_limit and int(time_limit) > 0:
        db_manager.execute_update(
            "UPDATE rounds SET time_limit_minutes=%s WHERE round_id=%s",
            (int(time_limit), round_id)
        )
    
    # Get next question number
    count_query = "SELECT MAX(question_number) as max_num FROM questions WHERE round_id=%s"
    count_res = db_manager.execute_query(count_query, (round_id,))
    next_num = (count_res[0]['max_num'] or 0) + 1
    
    # Use accurate boilerplate for language
    boilerplate = data.get('boilerplate', {}).get(language, '') or data.get('boilerplate', {}).get('python', '')
    
    db_manager.execute_update(q_query, (
        round_id, next_num, 
        data.get('title'), 
        data.get('description', ''), # Mapped to question_description
        data.get('expected_output'),
        boilerplate, 
        difficulty, 
        points, 
        test_cases
    ))
    
    return jsonify({'success': True})

@bp.route('/<contest_id>/rounds/<int:round_number>/question/<int:question_id>', methods=['PUT'])
@admin_required
def update_round_question(contest_id, round_number, question_id):
    data = request.get_json()
    
    # Update Query
    update_fields = []
    params = []
    
    if 'title' in data:
        update_fields.append("question_title=%s")
        params.append(data['title'])
    if 'description' in data:
        update_fields.append("question_description=%s")
        params.append(data['description'])
    if 'expected_output' in data:
        update_fields.append("expected_output=%s")
        params.append(data['expected_output'])
    if 'boilerplate' in data:
        code = data['boilerplate'].get('python', '') if isinstance(data['boilerplate'], dict) else data['boilerplate']
        update_fields.append("buggy_code=%s")
        params.append(code)
    if 'difficulty' in data:
        update_fields.append("difficulty_level=%s")
        params.append(data['difficulty'])
    if 'test_cases' in data:
        update_fields.append("test_cases=%s")
        params.append(json.dumps(data['test_cases']))
        
    if not update_fields:
        return jsonify({'success': True}) # Nothing to update
        
    query = f"UPDATE questions SET {', '.join(update_fields)} WHERE question_id=%s"
    params.append(question_id)
    
    db_manager.execute_update(query, tuple(params))
    
    return jsonify({'success': True})

@bp.route('/<contest_id>/status', methods=['GET'])
def get_contest_status(contest_id):
    # Get Contest Status
    c_query = "SELECT * FROM contests WHERE contest_id=%s"
    c_res = db_manager.execute_query(c_query, (contest_id,))
    if not c_res:
        return jsonify({'error': 'Not found'}), 404
    
    contest = c_res[0]
    
    # Get stats/config
    # We also might want the current active round/level duration
    # Assuming 'active' round is based on time or manual flow, here we just return config.
    
    return jsonify({
        'status': contest['status'],
        'start_time': contest['start_datetime'].isoformat() if contest['start_datetime'] else None,
        'end_time': contest['end_datetime'].isoformat() if contest['end_datetime'] else None,
        'server_time': datetime.datetime.utcnow().isoformat(),
        'config': {
            'max_violations': contest.get('max_violations_allowed', 10)
        }
    })

# === Questions & Execution ===

@bp.route('/questions', methods=['GET'])
def get_questions():
    contest_id = request.args.get('contest_id')
    level = request.args.get('level', 1)

    # Robustness: If contest_id is missing, find the LIVE one
    if not contest_id or contest_id == 'null' or contest_id == 'undefined':
        l_res = db_manager.execute_query("SELECT contest_id FROM contests WHERE status='live' LIMIT 1")
        if l_res:
            contest_id = l_res[0]['contest_id']
        else:
            # Fallback to id=1
            contest_id = 1

    query = """
        SELECT q.*, r.round_number, r.time_limit_minutes 
        FROM questions q
        JOIN rounds r ON q.round_id = r.round_id
        WHERE r.contest_id = %s AND r.round_number = %s
    """
    
    # Using strict filtering
    query += " ORDER BY q.question_number"
    
    res = db_manager.execute_query(query, (contest_id, level))
    
    questions = []
    for q in res:
        # Construct useful object for frontend
        tcs = []
        try:
            if q['test_cases']: tcs = json.loads(q['test_cases'])
        except: pass
        
        # Ensure only buggy_code is sent, NO expected code or hidden details
        questions.append({
            'id': q['question_id'],
            'round_number': q['round_number'],
            'number': q['question_number'],
            'title': q['question_title'],
            'description': q.get('question_description', ''), 
            'expected_output': q.get('expected_output'),
            'boilerplate': {'python': q['buggy_code']},
            'test_cases': tcs, 
            'difficulty': q['difficulty_level'],
            'time_limit_minutes': q['time_limit_minutes']
        })
        
    return jsonify({'questions': questions})

@bp.route('/run', methods=['POST'])
def run_code():
    data = request.get_json()
    code = data.get('code')
    language = data.get('language', 'python')
    question_id = data.get('question_id')
    user_id = data.get('user_id')
    contest_id = data.get('contest_id', 1) 
    level = data.get('level', 1)
    
    if not question_id:
        return jsonify({'error': 'Question ID missing'}), 400

    # 1. Fetch Question details (Inputs)
    query = "SELECT test_input, expected_output, test_cases FROM questions WHERE question_id=%s"
    q_res = db_manager.execute_query(query, (question_id,))
    
    if not q_res:
        return jsonify({'error': 'Question not found'}), 404
        
    question = q_res[0]
    
    # Determine input/expected (Priority: Explicit Cols -> JSON)
    inputs = []
    if question.get('test_input') is not None:
        inputs.append({
            'input': question['test_input'], 
            'expected': question['expected_output']
        })
    elif question.get('test_cases'):
        try:
            tcs = json.loads(question['test_cases'])
            inputs = tcs if isinstance(tcs, list) else []
        except: pass
        
    if not inputs:
        inputs = [{'input': '', 'expected': ''}] # Fallback

    # 2. Track Execution (Run Count)
    if user_id:
        # We try to get the integer ID. If string, assume lookup needed or use as is if schema allows.
        # Our schema uses INT for user_id. If 'PART001' passed, we need lookup.
        # For simplicity, we assume frontend provides correct ID or we do lookup:
        
        uid = user_id
        if isinstance(user_id, str) and not user_id.isdigit():
             # Lookup
             u_res = db_manager.execute_query("SELECT user_id FROM users WHERE username=%s", (user_id,))
             if u_res: uid = u_res[0]['user_id']
        
        track_query = """
            INSERT INTO participant_level_stats (user_id, contest_id, level, run_count)
            VALUES (%s, %s, %s, 1)
            ON DUPLICATE KEY UPDATE run_count = run_count + 1
        """
        try:
            db_manager.execute_update(track_query, (uid, contest_id, level))
        except Exception as e:
            print(f"Stats error: {e}")

    # 3. Execute against inputs
    results = []
    for tc in inputs:
        inp_str = str(tc.get('input', ''))
        exp_str = str(tc.get('expected', '')).replace('\r\n', '\n').strip()
        
        exec_res = execute_code_secure(code, language, inp_str)
        actual = exec_res['output'].replace('\r\n', '\n').strip()
        
        def normalize(s):
            return "\n".join([line.strip() for line in s.splitlines() if line.strip()])
        
        passed = (normalize(actual) == normalize(exp_str))
        
        results.append({
            'input': inp_str,
            'expected': exp_str,
            'output': actual,
            'passed': passed,
            'error': exec_res['error']
        })

    return jsonify({
        'success': True,
        'test_results': results
    })

@bp.route('/submit-question', methods=['POST'])
def submit_question():
    data = request.get_json()
    user_id = data.get('user_id')
    question_id = data.get('question_id')
    code = data.get('code')
    language = data.get('language', 'python')
    contest_id = data.get('contest_id', 1)
    
    if not all([user_id, question_id, code]):
        return jsonify({'error': 'Missing data'}), 400

    # User ID Handling
    uid = user_id
    if isinstance(user_id, str) and not user_id.isdigit():
         u_res = db_manager.execute_query("SELECT user_id FROM users WHERE username=%s", (user_id,))
         if u_res: uid = u_res[0]['user_id']
         else: return jsonify({'error': 'User not found'}), 404

    # 1. Check if already passed/submitted
    check_query = "SELECT is_correct FROM submissions WHERE user_id=%s AND question_id=%s AND is_correct=1"
    check_res = db_manager.execute_query(check_query, (uid, question_id))
    if check_res:
         return jsonify({'error': 'Already submitted successfully', 'submitted': True}), 400

    # 2. Fetch Question & Inputs
    query = "SELECT test_input, expected_output, test_cases, time_limit_minutes FROM questions WHERE question_id=%s"
    q_res = db_manager.execute_query(query, (question_id,))
    if not q_res: return jsonify({'error': 'Question not found'}), 404
    question = q_res[0]

    # Prepare Inputs
    inputs = []
    if question.get('test_input') is not None:
        inputs.append({'input': question['test_input'], 'expected': question['expected_output']})
    elif question.get('test_cases'):
        try:
            tcs = json.loads(question['test_cases'])
            inputs = tcs if isinstance(tcs, list) else []
        except: pass
    if not inputs: inputs = [{'input': '', 'expected': ''}]

    # 3. Secure Execution (Strict Mode)
    # Passed only if ALL inputs match
    all_passed = True
    test_results = []
    
    for tc in inputs:
        inp = str(tc.get('input', ''))
        exp = str(tc.get('expected', '')).replace('\r\n', '\n').strip()
        res = execute_code_secure(code, language, inp)
        actual = res['output'].replace('\r\n', '\n').strip()
        
        # Normalize for comparison
        def normalize(s):
            return "\n".join([line.strip() for line in s.splitlines() if line.strip()])
            
        passed = (normalize(actual) == normalize(exp))
        if not passed: all_passed = False
        
        test_results.append({
            'input': inp, 'expected': exp, 'output': actual, 'passed': passed, 'error': res['error']
        })

    status = 'evaluated'
    is_correct = 1 if all_passed else 0
    score = 10.0 if all_passed else 0.0

    # 4. Save Submission
    save_query = """
        INSERT INTO submissions 
        (user_id, contest_id, round_id, question_id, submitted_code, status, is_correct, test_results, score_awarded)
        VALUES (%s, %s, (SELECT round_id FROM questions WHERE question_id=%s), %s, %s, %s, %s, %s, %s)
    """
    # Note: round_id subquery added to match schema requirements if strictly enforced, or we can fetch it earlier.
    # Schema says submissions has round_id NOT NULL.
    # We didn't fetch round_id in step 2. Let's do a quick lookup or subquery.
    
    db_manager.execute_update(save_query, (
        uid, contest_id, question_id, question_id, code, status, is_correct, json.dumps(test_results), score
    ))

    # 5. Update Level Stats
    if all_passed:
        level = data.get('level', 1)
        recalc_query = """
            UPDATE participant_level_stats ps
            SET 
                questions_solved = (SELECT COUNT(*) FROM submissions s WHERE s.user_id=ps.user_id AND s.is_correct=1),
                level_score = (SELECT SUM(score_awarded) FROM submissions s WHERE s.user_id=ps.user_id)
            WHERE ps.user_id=%s AND ps.contest_id=%s AND ps.level=%s
        """
        db_manager.execute_update("INSERT IGNORE INTO participant_level_stats (user_id, contest_id, level) VALUES (%s, %s, %s)", (uid, contest_id, level))
        db_manager.execute_update(recalc_query, (uid, contest_id, level))

        # Real-time Admin Update
        from extensions import socketio
        socketio.emit('admin:stats_update', {'user_id': uid, 'contest_id': contest_id})
        
    return jsonify({
        'success': all_passed,
        'status': status,
        'message': 'Solution Submitted' if all_passed else 'Solution Failed',
        'score': score
    })

def execute_code_secure(code, language, input_data):
    ext_map = {'python': '.py', 'javascript': '.js'}
    ext = ext_map.get(language, '.txt')
    
    with tempfile.NamedTemporaryFile(mode='w', suffix=ext, delete=False) as f:
        f.write(code)
        f_name = f.name
    
    try:
        cmd = []
        if language == 'python':
            cmd = ['python', f_name]
        elif language == 'javascript':
            cmd = ['node', f_name]
        else:
            return {'output': '', 'error': 'Unsupported Language'}

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=input_data, timeout=5)
        
        # If there is valid stdout, use it even if stderr has content (e.g. warnings)
        return {'output': stdout, 'error': stderr}
        
    except subprocess.TimeoutExpired:
        return {'output': '', 'error': 'Time Limit Exceeded'}
    except Exception as e:
        return {'output': '', 'error': str(e)}
    finally:
        if os.path.exists(f_name):
            os.remove(f_name)

@bp.route('/participant-state', methods=['POST'])
def get_participant_state():
    try:
        # Persistent State Fetch
        data = request.get_json()
        user_id = data.get('user_id')
        contest_id = data.get('contest_id', 1)
        
        uid = user_id
        if isinstance(user_id, str) and not user_id.isdigit():
             u_res = db_manager.execute_query("SELECT user_id FROM users WHERE username=%s", (user_id,))
             if u_res: uid = u_res[0]['user_id']
             else: return jsonify({'error': 'User not found'}), 404
             
        # Fetch latest level
        query = "SELECT level, violation_count, questions_solved, start_time, status FROM participant_level_stats WHERE user_id=%s AND contest_id=%s ORDER BY level DESC LIMIT 1"
        res = db_manager.execute_query(query, (uid, contest_id))

        # Fetch Global State (Active Level & Countdown) - Needed for everyone
        gl_query = "SELECT round_number, status FROM rounds WHERE contest_id=%s AND status IN ('active', 'paused') ORDER BY round_number DESC LIMIT 1"
        gl_res = db_manager.execute_query(gl_query, (contest_id,))
        global_level_data = gl_res[0] if gl_res else {'round_number': 1, 'status': 'pending'}
        
        cd_key = f"contest_{contest_id}_countdown"
        cd_res = db_manager.execute_query("SELECT value FROM admin_state WHERE key_name=%s", (cd_key,))
        
        # Check for Unlock Condition (Shortlist) if COMPLETED
        current_state = res[0] if res else None
        
        if current_state and current_state['status'] == 'COMPLETED':
            current_lvl = current_state['level']
            next_lvl = current_lvl + 1
            
            # Check Shortlist
            # Logic: If Shortlist table has entries for this level, strict check.
            # If table is empty for this level, assume OPEN ROUND (everyone progresses).
            
            sl_check_q = "SELECT COUNT(*) as cnt FROM shortlisted_participants WHERE contest_id=%s AND level=%s"
            sl_check_res = db_manager.execute_query(sl_check_q, (contest_id, next_lvl))
            has_shortlist = (sl_check_res and sl_check_res[0]['cnt'] > 0)
            
            allowed = False
            if not has_shortlist:
                allowed = True # Open Round
            else:
                sl_q = "SELECT is_allowed FROM shortlisted_participants WHERE contest_id=%s AND level=%s AND user_id=%s"
                sl_res = db_manager.execute_query(sl_q, (contest_id, next_lvl, uid))
                if sl_res and sl_res[0]['is_allowed']:
                    allowed = True
            
            if allowed:
                 # Auto-create next level state
                 db_manager.execute_update(
                     "INSERT IGNORE INTO participant_level_stats (user_id, contest_id, level, violation_count, status) VALUES (%s, %s, %s, 0, 'NOT_STARTED')",
                     (uid, contest_id, next_lvl)
                 )
                 # Refresh Res to get new level
                 res = db_manager.execute_query(query, (uid, contest_id))
                 current_state = res[0] if res else None

        # Fetch Solved Questions
        solved_query = "SELECT question_id FROM submissions WHERE user_id=%s AND contest_id=%s AND is_correct=1"
        solved_res = db_manager.execute_query(solved_query, (uid, contest_id))
        solved_ids = [s['question_id'] for s in solved_res] if solved_res else []
        
        # Decode Countdown State properly
        countdown_data = {'active': False}
        if cd_res:
             try:
                 countdown_data = json.loads(cd_res[0]['value'])
             except: pass

        return jsonify({
            'success': True,
            'level': current_state['level'] if current_state else 1,
            'violations': current_state['violation_count'] or 0 if current_state else 0,
            'solved': current_state['questions_solved'] if current_state else 0,
            'solved_ids': solved_ids,
            'status': current_state['status'] or 'NOT_STARTED' if current_state else 'NOT_STARTED',
            'start_time': current_state['start_time'].isoformat() if current_state and current_state['start_time'] else None,
            'global_level': global_level_data['round_number'],
            'global_level_status': global_level_data['status'],
            'countdown': countdown_data,
            'is_eliminated': (global_level_data['round_number'] > (current_state['level'] if current_state else 1) and (not current_state or current_state['status'] == 'COMPLETED'))
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500

@bp.route('/start-level', methods=['POST'])
def start_level():
    data = request.get_json()
    user_id = data.get('user_id')
    contest_id = data.get('contest_id', 1)
    level = data.get('level')
    
    uid = user_id
    if isinstance(user_id, str) and not user_id.isdigit():
         u_res = db_manager.execute_query("SELECT user_id FROM users WHERE username=%s", (user_id,))
         if u_res: uid = u_res[0]['user_id']
    
    db_manager.execute_update(
        "UPDATE participant_level_stats SET start_time = NOW(), status = 'IN_PROGRESS' WHERE user_id=%s AND contest_id=%s AND level=%s AND (status='NOT_STARTED' OR status IS NULL)",
        (uid, contest_id, level)
    )
    return jsonify({'success': True})

@bp.route('/submit-level', methods=['POST'])
def submit_level():
    # Master Submit / Level Finalization
    data = request.get_json()
    user_id = data.get('user_id') 
    contest_id = data.get('contest_id', 1)
    level = data.get('level', 1)
    
    if not user_id: return jsonify({'success': True})

    # Get User INT ID
    uid = user_id
    if isinstance(user_id, str) and not user_id.isdigit():
         u_res = db_manager.execute_query("SELECT user_id FROM users WHERE username=%s", (user_id,))
         if u_res: uid = u_res[0]['user_id']
    
    # 1. Update Status to COMPLETED
    db_manager.execute_update(
        "UPDATE participant_level_stats SET status='COMPLETED' WHERE user_id=%s AND contest_id=%s AND level=%s", 
        (uid, contest_id, level)
    )
    
    # 2. DO NOT Unlock Next Level automatically (Wait for Admin Shortlist)
    # The next level row will be created by 'get_participant_state' once the user is Shortlisted.
    
    return jsonify({
        "success": True,
        "message": "Level finalized. Waiting for approval.",
        "next_level": int(level) + 1,
        "locked": True
    })

@bp.route('/heartbeat', methods=['POST'])
def heartbeat():
    # Keep alive
    return jsonify({'success': True})


@bp.route('/<contest_id>/qualify-participants', methods=['POST'])
@admin_required
def qualify_participants(contest_id):
    data = request.get_json()
    participant_ids = data.get('participant_ids', [])
    level = data.get('level')
    
    if not level:
         # Need better logic: find NEXT level. For now, try manual or default
         level = 2 

    # 1. Reset selection for this level (Requirement: Uncheck others)
    # We set all is_allowed=0 for this contest+level first
    db_manager.execute_update("UPDATE shortlisted_participants SET is_allowed=0 WHERE contest_id=%s AND level=%s", (contest_id, level))

    count = 0
    for pid in participant_ids:
        # pid could be int or string
        uid = pid
        if isinstance(pid, str) and not pid.isdigit():
             res = db_manager.execute_query("SELECT user_id FROM users WHERE username=%s", (pid,))
             if res: uid = res[0]['user_id']
        
        db_manager.execute_update(
            "INSERT INTO shortlisted_participants (contest_id, level, user_id, is_allowed) VALUES (%s, %s, %s, 1) ON DUPLICATE KEY UPDATE is_allowed=1",
            (contest_id, level, uid)
        )
        count += 1

    return jsonify({'success': True, 'count': count})

@bp.route('/<contest_id>/shortlisted-participants', methods=['GET'])
@admin_required
def get_shortlisted_participants(contest_id):
    level = request.args.get('level', 2)
    query = """
        SELECT u.username as id, u.full_name as name
        FROM shortlisted_participants sp
        JOIN users u ON sp.user_id = u.user_id
        WHERE sp.contest_id=%s AND sp.level=%s AND sp.is_allowed=1
    """
    res = db_manager.execute_query(query, (contest_id, level))
    return jsonify({'participants': res})


@bp.route('/<contest_id>/notify-progression', methods=['POST'])
@admin_required
def notify_progression(contest_id):
    from extensions import socketio
    socketio.emit('contest:progression_update', {'contest_id': contest_id})
    return jsonify({'success': True})

@bp.route('/<contest_id>/advance-level', methods=['POST'])
@admin_required
def advance_level(contest_id):
    # This might be "Start Next Level"
    data = request.get_json()
    wait_time = data.get('wait_time', 0)
    
    # Emit event to start logic
    from extensions import socketio
    socketio.emit('contest:level_start', {'contest_id': contest_id, 'wait_time': wait_time})
    return jsonify({'success': True})

@bp.route('/<contest_id>/countdown', methods=['POST'])
@admin_required
def toggle_countdown(contest_id):
    # Toggle global countdown for this contest
    k = f"contest_{contest_id}_countdown"
    res = db_manager.execute_query("SELECT value FROM admin_state WHERE key_name=%s", (k,))
    curr = res[0]['value'] if res else 'stopped'
    
    new_state = 'started' if curr != 'started' else 'stopped'
    
    # Update DB
    db_manager.execute_update("INSERT INTO admin_state (key_name, value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE value=%s", (k, new_state, new_state))
    
    from extensions import socketio
    socketio.emit('contest:countdown', {'contest_id': contest_id, 'state': new_state})
    
    return jsonify({'success': True, 'state': new_state})

@bp.route('/<contest_id>/finalize-round', methods=['POST'])
@admin_required
def finalize_round(contest_id):
    # Mark round as finalized (logic if needed)
    return jsonify({'success': True})

@bp.route('/<contest_id>/rounds', methods=['GET'])
@admin_required
def get_rounds(contest_id):
    query = "SELECT * FROM rounds WHERE contest_id=%s ORDER BY round_number"
    rounds = db_manager.execute_query(query, (contest_id,))
    return jsonify({'rounds': rounds})

@bp.route('/<contest_id>/stats', methods=['GET'])
def get_contest_stats(contest_id):
    # Calculate stats for the specific contest
    
    # 1. Total Participants (Registered)
    p_query = "SELECT COUNT(*) as count FROM users WHERE role='participant'"
    p_res = db_manager.execute_query(p_query)
    total = p_res[0]['count'] if p_res else 0
    
    # 2. Active (Online/Heartbeat recently or In Progress status)
    # let's assume 'IN_PROGRESS' in level stats means active
    a_query = "SELECT COUNT(DISTINCT user_id) as count FROM participant_level_stats WHERE contest_id=%s AND status='IN_PROGRESS'"
    a_res = db_manager.execute_query(a_query, (contest_id,))
    active = a_res[0]['count'] if a_res else 0
    
    # 3. Violations (Total in this contest)
    v_query = "SELECT COUNT(*) as count FROM violations WHERE contest_id=%s"
    v_res = db_manager.execute_query(v_query, (contest_id,))
    viols = v_res[0]['count'] if v_res else 0
    
    # 4. Solved (Total passed submissions)
    s_query = "SELECT COUNT(*) as count FROM submissions WHERE contest_id=%s AND is_correct=1"
    s_res = db_manager.execute_query(s_query, (contest_id,))
    solved = s_res[0]['count'] if s_res else 0
    
    # Get Configured Wait Time + Countdown Status
    cd_key = f"contest_{contest_id}_countdown"
    cd_res = db_manager.execute_query("SELECT value FROM admin_state WHERE key_name=%s", (cd_key,))
    countdown_state = cd_res[0]['value'] if cd_res else 'stopped'

    return jsonify({
        'total_participants': total,
        'active_participants': active,
        'violations_detected': viols,
        'questions_solved': solved,
        'average_score': 0,
        'countdown_state': countdown_state
    })
