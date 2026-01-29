from flask import Blueprint, jsonify, request
import uuid
import datetime
import time
import json
import traceback
from db_connection import db_manager
from auth_middleware import admin_required
from utils.logic import execute_code_internal
from utils.contest_service import activate_level_logic, complete_level_logic, advance_level_logic

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

@bp.route('/<contest_id>', methods=['GET'])
@admin_required
def get_contest_detail(contest_id):
    query = "SELECT contest_id as id, contest_name as title, description, start_datetime, end_datetime, status FROM contests WHERE contest_id=%s"
    res = db_manager.execute_query(query, (contest_id,))
    
    if not res:
        return jsonify({'error': 'Contest not found'}), 404
        
    contest = res[0]
    # Format dates
    if contest['start_datetime']: contest['start_time'] = contest['start_datetime'].isoformat() # admin.js expects start_time
    if contest['end_datetime']: contest['end_time'] = contest['end_datetime'].isoformat()
    
    return jsonify({'contest': contest})

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
            target_level = data.get('target_level')
            val = json.dumps({'active': True, 'end_time': end_time.isoformat(), 'duration': duration, 'target_level': target_level})
            
            db_manager.execute_update(
                "INSERT INTO admin_state (key_name, value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE value=%s",
                (key_name, val, val)
            )
            socketio.emit('contest:countdown', {'contest_id': contest_id, 'active': True, 'end_time': end_time.isoformat(), 'duration': duration, 'target_level': target_level})
            
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
    socketio.emit('contest:stats_update', {'contest_id': contest_id})
    return jsonify({'success': True})

@bp.route('/<contest_id>/control/pause', methods=['POST'])
@admin_required
def pause_contest(contest_id):
    query = "UPDATE contests SET status='paused' WHERE contest_id=%s"
    db_manager.execute_update(query, (contest_id,))
    from extensions import socketio
    socketio.emit('contest:paused', {'contest_id': contest_id})
    socketio.emit('contest:stats_update', {'contest_id': contest_id})
    return jsonify({'success': True})

@bp.route('/<contest_id>/control/end', methods=['POST'])
@admin_required
def end_contest(contest_id):
    query = "UPDATE contests SET status='ended', end_datetime=NOW() WHERE contest_id=%s"
    db_manager.execute_update(query, (contest_id,))
    from extensions import socketio
    socketio.emit('contest:ended', {'contest_id': contest_id})
    socketio.emit('contest:stats_update', {'contest_id': contest_id})
    return jsonify({'success': True})

@bp.route('/<contest_id>/level/<int:level_number>/activate', methods=['POST'])
@admin_required
def activate_level_admin(contest_id, level_number):
    try:
        # 1. Set all currently active rounds to pending
        db_manager.execute_update("UPDATE rounds SET status='pending' WHERE contest_id=%s AND status='active'", (contest_id,))
        
        # 2. Check if the target round exists
        check_query = "SELECT round_id FROM rounds WHERE contest_id=%s AND round_number=%s"
        existing = db_manager.execute_query(check_query, (contest_id, level_number))
        
        if not existing:
            # Create the round on the fly if it's missing (e.g. Level 4/5)
            insert_query = """
                INSERT INTO rounds (contest_id, round_name, round_number, time_limit_minutes, total_questions, status, is_locked)
                VALUES (%s, %s, %s, 45, 0, 'active', 0)
            """
            db_manager.execute_update(insert_query, (contest_id, f"Level {level_number}", level_number))
        else:
            # Set target to active
            db_manager.execute_update("UPDATE rounds SET status='active' WHERE contest_id=%s AND round_number=%s", (contest_id, level_number))
        
        from extensions import socketio
        socketio.emit('level:activated', {'contest_id': contest_id, 'level': level_number})
        # Also broadcast generic contest update to ensure all clients refresh state
        socketio.emit('contest:updated', {'contest_id': contest_id})
        
        return jsonify({'success': True})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

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
    allowed_language = data.get('allowed_language') # NEW
    
    if time_limit is not None:
        db_manager.execute_update(
            "UPDATE rounds SET time_limit_minutes=%s WHERE contest_id=%s AND round_number=%s",
            (time_limit, contest_id, round_number)
        )

    if allowed_language: # NEW
        db_manager.execute_update(
            "UPDATE rounds SET allowed_language=%s WHERE contest_id=%s AND round_number=%s",
            (allowed_language, contest_id, round_number)
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


from utils.logic import execute_code_internal
from utils.contest_service import create_question_logic

# ... (Imports)

@bp.route('/<contest_id>/rounds/<int:round_number>/question', methods=['POST'])
@admin_required
def create_round_question(contest_id, round_number):
    try:
        data = request.get_json()
        result = create_question_logic(contest_id, round_number, data)
        return jsonify(result), 201
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ...

# (Removing local execute_code_internal definition completely)


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

    # 1. Fetch Round Config strictly first (for Language)
    round_query = "SELECT allowed_language, time_limit_minutes FROM rounds WHERE contest_id=%s AND round_number=%s"
    r_res = db_manager.execute_query(round_query, (contest_id, level))
    
    allowed_lang = 'python' # Global Default
    if r_res and r_res[0].get('allowed_language'):
        allowed_lang = r_res[0]['allowed_language']

    # 2. Fetch Questions
    query = """
        SELECT q.*, r.round_number
        FROM questions q
        JOIN rounds r ON q.round_id = r.round_id
        WHERE r.contest_id = %s AND r.round_number = %s
        ORDER BY q.question_number ASC
    """
    
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
            'buggy_code': q['buggy_code'], # Send directly 
            'boilerplate': {allowed_lang: q['buggy_code']}, # Use correct lang key
            'test_cases': tcs, 
            'difficulty': q['difficulty_level'],
            # If question has specific override (unlikely in current schema but possible), use it? 
            # No, strictly follow Round language.
            'allowed_language': allowed_lang
        })
        
    return jsonify({'questions': questions, 'allowed_language': allowed_lang})

@bp.route('/run', methods=['POST'])
def run_code():
    data = request.get_json()
    code = data.get('code')
    # language param from frontend is trust-but-verify. We prefer DB config.
    requested_language = data.get('language', 'python') 
    question_id = data.get('question_id')
    user_id = data.get('user_id')
    contest_id = data.get('contest_id', 1) 
    level = data.get('level', 1)
    
    if not question_id:
        return jsonify({'error': 'Question ID missing'}), 400

    print(f"RUN CODE: Fetching Question ID: {question_id} (Type: {type(question_id)})")

    # 1. Fetch Question & Config
    # Join with rounds to get allowed_language STRICTLY
    query = """
        SELECT q.test_input, q.expected_output, q.test_cases, r.allowed_language
        FROM questions q
        LEFT JOIN rounds r ON q.round_id = r.round_id
        WHERE q.question_id = %s
    """
    
    # Attempt 1: As provided
    q_res = db_manager.execute_query(query, (question_id,))
    
    # Attempt 2: If not found, try type juggle (Int <-> String)
    if not q_res:
        try:
            if str(question_id).isdigit():
                q_res = db_manager.execute_query(query, (int(question_id),))
            else:
                q_res = db_manager.execute_query(query, (str(question_id),))
        except: pass
        
    if not q_res:
        print(f"RUN CODE WARN: Question ID {question_id} NOT FOUND in DB.")
        return jsonify({'error': 'Question not found', 'success': False})
    
    question = q_res[0]

    # Enforce Allowed Language STRICTLY
    allowed = question.get('allowed_language')
    if allowed:
        language = allowed.lower()
    else:
        language = requested_language # Fallback only if DB empty

    # Normalize Language String
    if language in ['c', 'gcc']: language = 'c'
    if language in ['cpp', 'g++']: language = 'cpp'
    if language in ['py', 'python3']: language = 'python'
    if language in ['java', 'jdk']: language = 'java'
    if language in ['javascript', 'js', 'node']: language = 'javascript'
    
    # 2. Determine input/expected (Inputs)
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
        # Fallback for RUN only - warn user
        inputs = [{'input': '', 'expected': ''}] 
        print(f"WARN: No inputs found for QID {question_id}, running with empty input.")

    # 2. Track Execution (Run Count)
    if user_id:
        uid = user_id
        if isinstance(user_id, str) and not user_id.isdigit():
             u_res = db_manager.execute_query("SELECT user_id FROM users WHERE username=%s", (user_id,))
             if u_res: uid = u_res[0]['user_id']
        
        try:
            track_query = """
                INSERT INTO participant_level_stats (user_id, contest_id, level, run_count)
                VALUES (%s, %s, %s, 1)
                ON DUPLICATE KEY UPDATE run_count = run_count + 1
            """
            db_manager.execute_update(track_query, (uid, contest_id, level))
        except: pass

    # 3. Execute Code (Sandbox Interface)
    test_results = []
    
    # Run first 3 sample cases
    sample_inputs = inputs[:3] 
    
    for i, case in enumerate(sample_inputs):
        inp = case.get('input', '')
        exp = case.get('expected', '')
        
        start_t = time.time()
        result = execute_code_internal(code, language, inp)
        duration = time.time() - start_t
        
        # Normalize for comparison
        def normalize(s):
            if not s: return ""
            return "\n".join([line.strip() for line in s.splitlines() if line.strip()])

        passed = False
        if result['success']:
            output = result['output'].replace('\r\n', '\n').strip()
            passed = (normalize(output) == normalize(exp))
        else:
            output = result['error']
            
        test_results.append({
            'passed': passed,
            'input': inp,
            'output': output,
            'expected': exp,
            'error': result.get('error') if not result['success'] else None,
            'duration': duration,
            'warnings': result.get('warnings')
        })

    # Summary Execution Time
    total_time = sum(r['duration'] for r in test_results)
    
    # Collect warnings (unique)
    warnings = list(set([r['warnings'] for r in test_results if r.get('warnings')]))
    warnings_str = "\n".join(warnings) if warnings else None

    return jsonify({
        'success': True,
        'test_results': test_results,
        'execution_time': f"{total_time:.3f}s",
        'warnings': warnings_str
    })

@bp.route('/submit-question', methods=['POST'])
def submit_question():
    data = request.get_json()
    user_id = data.get('user_id')
    question_id = data.get('question_id')
    code = data.get('code')
    contest_id = data.get('contest_id', 1)
    
    # Validation
    if not user_id: return jsonify({'error': 'User ID missing'}), 400
    if not question_id: return jsonify({'error': 'Question ID missing'}), 400
    if code is None: return jsonify({'error': 'Code missing'}), 400

    # User ID Resolution
    uid = user_id
    if isinstance(user_id, str) and not user_id.isdigit():
         u_res = db_manager.execute_query("SELECT user_id FROM users WHERE username=%s", (user_id,))
         if u_res: uid = u_res[0]['user_id']
         else: return jsonify({'error': 'User not found'}), 404

    # 1. Authoritative Question Lookup (Left Join to be safe)
    query = """
        SELECT q.question_id, q.round_id, q.test_input, q.expected_output, q.test_cases, q.points, r.allowed_language
        FROM questions q
        LEFT JOIN rounds r ON q.round_id = r.round_id
        WHERE q.question_id = %s
    """
    
    # Robust ID Handling (Int/Str)
    q_res = db_manager.execute_query(query, (question_id,))
    if not q_res:
        # Try type conversion retry
        try:
            if str(question_id).isdigit():
                q_res = db_manager.execute_query(query, (int(question_id),))
            else:
                q_res = db_manager.execute_query(query, (str(question_id),))
        except: pass

    if not q_res: 
        return jsonify({'error': f'Question {question_id} not found in database'}), 404
        
    question = q_res[0]
    
    # 2. Check for Duplicate Submission (Success Only)
    check_query = "SELECT is_correct FROM submissions WHERE user_id=%s AND question_id=%s AND is_correct=1"
    check_res = db_manager.execute_query(check_query, (uid, question['question_id']))
    if check_res:
         return jsonify({'error': 'Already submitted successfully', 'submitted': True}), 400

    # 3. Language Handling
    allowed = question.get('allowed_language')
    if allowed:
        language = allowed.lower()
    else:
        language = data.get('language', 'python')

    if language in ['c', 'gcc']: language = 'c'
    if language in ['cpp', 'g++']: language = 'cpp'
    if language in ['py', 'python3']: language = 'python'
    if language in ['java', 'jdk']: language = 'java'
    if language in ['javascript', 'js', 'node']: language = 'javascript'

    # 4. Input Preparation
    inputs = []
    if question.get('test_input') is not None:
        inputs.append({'input': question['test_input'], 'expected': question['expected_output']})
    elif question.get('test_cases'):
        try:
            tcs = json.loads(question['test_cases'])
            inputs = tcs if isinstance(tcs, list) else []
        except: pass
    
    if not inputs:
        # Critical Data Error
        return jsonify({'error': 'System Error: Question has no test cases configured'}), 500

    # 5. Execution (Strict)
    all_passed = True
    test_results = []
    start_time = time.time()
    
    for tc in inputs:
        inp = str(tc.get('input', ''))
        exp = str(tc.get('expected', '')).replace('\r\n', '\n').strip()
        
        res = execute_code_internal(code, language, inp)
        
        if res['success']:
            actual = res['output'].replace('\r\n', '\n').strip()
        else:
            actual = ""
        
        def normalize(s):
            if not s: return ""
            return "\n".join([line.strip() for line in s.splitlines() if line.strip()])
        
        passed = False
        if res['success']:
             passed = (normalize(actual) == normalize(exp))
             
        if not passed: all_passed = False
        
        test_results.append({
            'input': inp, 'expected': exp, 'output': actual, 'passed': passed, 
            'error': res['error'] if not res['success'] else None,
            'warnings': res.get('warnings')
        })

    execution_duration = int(time.time() - start_time)

    # 6. Persistence (Guaranteed Insert)
    status = 'evaluated'
    is_correct = 1 if all_passed else 0
    score_val = float(question.get('points') or 10.0)
    score = score_val if all_passed else 0.0
    
    # Collect Warnings
    warnings = list(set([r['warnings'] for r in test_results if r.get('warnings')]))
    warnings_str = "\n".join(warnings) if warnings else None

    save_query = """
        INSERT INTO submissions 
        (user_id, contest_id, round_id, question_id, submitted_code, status, is_correct, test_results, score_awarded, time_taken_seconds)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    # Use Authoritative Question Data
    final_round_id = question.get('round_id')
    final_qid = question['question_id']
    
    try:
        insert_res = db_manager.execute_update(save_query, (
            uid, contest_id, final_round_id, final_qid, code, status, is_correct, json.dumps(test_results), score, execution_duration
        ))
        
        if not insert_res:
            print(f"SUBMIT DATA LOSS: Insert returned False for UID {uid} QID {final_qid}")
            # Try to fetch last error from db manager if possible, or just fail hard.
            return jsonify({'error': 'Database Error: Submission could not be saved. Please retry.'}), 500
            
    except Exception as e:
        print(f"SUBMIT EXCEPTION: {e}")
        return jsonify({'error': f'Submission Persistence Failed: {str(e)}'}), 500

    # 7. Level Stats Update
    if all_passed:
        level = data.get('level', 1)
        # Update Participant Stats
        recalc_query = """
            UPDATE participant_level_stats ps
            SET 
                questions_solved = (SELECT COUNT(*) FROM submissions s WHERE s.user_id=ps.user_id AND s.is_correct=1),
                level_score = (SELECT SUM(score_awarded) FROM submissions s WHERE s.user_id=ps.user_id)
            WHERE ps.user_id=%s AND ps.contest_id=%s AND ps.level=%s
        """
        db_manager.execute_update("INSERT IGNORE INTO participant_level_stats (user_id, contest_id, level) VALUES (%s, %s, %s)", (uid, contest_id, level))
        db_manager.execute_update(recalc_query, (uid, contest_id, level))

        # Real-time Broadcast
        from extensions import socketio
        socketio.emit('admin:stats_update', {'user_id': uid, 'contest_id': contest_id})
        socketio.emit('participant:submitted', {
            'participant_id': uid,
            'name': user_id,
            'question': f"Q{question_id}",
            'contest_id': contest_id
        })
        
    return jsonify({
        'success': all_passed,
        'status': status,
        'warnings': warnings_str,
        'message': 'Solution Submitted' if all_passed else 'Solution Incorrect',
        'score': score,
        'execution_time': f"{execution_duration}s"
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

        # Fetch ALL Round Statuses (Single Source of Truth)
        rounds_query = "SELECT round_number, status FROM rounds WHERE contest_id=%s ORDER BY round_number ASC"
        rounds_res = db_manager.execute_query(rounds_query, (contest_id,))
        rounds_map = {r['round_number']: r['status'] for r in rounds_res} if rounds_res else {}
        
        if rounds_map.get(1) == 'pending' or 1 not in rounds_map:
             rounds_map[1] = 'active'

        # Fetch Global Active Level
        gl_query = "SELECT round_number, status FROM rounds WHERE contest_id=%s AND status='active' ORDER BY round_number ASC LIMIT 1"
        gl_res = db_manager.execute_query(gl_query, (contest_id,))
        global_active_level = gl_res[0]['round_number'] if gl_res else 1
        
        current_state = res[0] if res else None
        
        # CLAMP: Ensure user cannot be ahead of the global active round
        if current_state and current_state['level'] > global_active_level:
            current_state['level'] = global_active_level
            # Reset status for this view to avoid confusion
            current_state['status'] = 'NOT_STARTED' # Force them to 'enter' again if needed
        
        # QUALIFICATION CHECK:
        # If the global active level is > 1, we must verify if the user is in the 'shortlisted_participants' for this level.
        # This handles the case where a user completed Level X but was not selected for Level X+1.
        if global_active_level > 1:
            # Check if user is allowed for this level
            q_check = "SELECT is_allowed FROM shortlisted_participants WHERE contest_id=%s AND level=%s AND user_id=%s AND is_allowed=1"
            q_res = db_manager.execute_query(q_check, (contest_id, global_active_level, uid))
            
            if not q_res:
                # User is NOT Shortlisted for this Active Level.
                # However, we must be careful:
                # If they are currently playing Level < Global Level, that's fine (maybe they are lagging behind?) 
                # BUT the user request implies strict "if not select for next level block that id".
                # Usually, if Level 3 is Active, everyone who passed Level 2 should have been shortlisted OR eliminated.
                
                # Check if they have completed the PREVIOUS level
                prev_completed = False
                if current_state:
                     # If they are seemingly on the previous level completed?
                     if current_state['level'] == global_active_level - 1 and current_state['status'] == 'COMPLETED':
                         prev_completed = True
                     # Or if they are on global level but not started yet?
                     elif current_state['level'] == global_active_level:
                         prev_completed = True # They reached it somehow?
                
                # If they are "at the door" of the global active level but not allowed:
                is_disqualified_state = True
                disq_reason = f"Not selected for Level {global_active_level}"

        # RESTORE: Needed for JSON response
        global_level_data = {'round_number': global_active_level, 'status': 'active'}
        
        cd_key = f"contest_{contest_id}_countdown"
        cd_res = db_manager.execute_query("SELECT value FROM admin_state WHERE key_name=%s", (cd_key,))


        
        # 1. Fetch TOTAL Violations and Disqualification Status
        pr_query = "SELECT total_violations, is_disqualified, disqualification_reason FROM participant_proctoring WHERE participant_id=%s AND contest_id=%s"
        p_res = db_manager.execute_query(pr_query, (user_id if isinstance(user_id, str) and not user_id.isdigit() else (u_res[0]['username'] if u_res else ''), contest_id))
        
        total_violations = 0
        is_disqualified_state = False
        disq_reason = None
        
        if p_res:
             total_violations = p_res[0]['total_violations'] if p_res[0]['total_violations'] is not None else 0
             is_disqualified_state = bool(p_res[0]['is_disqualified'])
             disq_reason = p_res[0]['disqualification_reason']

        # 2. Get Duration (With Strict Defaults + Admin Override)
        def get_default_duration(l):
            if l <= 3: return 20
            if l == 4: return 30
            if l == 5: return 45
            return 45

        level_duration = get_default_duration(current_state['level'] if current_state else 1)
        if current_state:
            lvl = current_state['level']
            rd_res = db_manager.execute_query("SELECT time_limit_minutes FROM rounds WHERE contest_id=%s AND round_number=%s", (contest_id, lvl))
            if rd_res and rd_res[0]['time_limit_minutes'] and rd_res[0]['time_limit_minutes'] > 0:
                 level_duration = rd_res[0]['time_limit_minutes']

        # 3. Decode Countdown State
        countdown_data = {'active': False}
        if cd_res:
             try:
                 countdown_data = json.loads(cd_res[0]['value'])
             except: pass

        # 4. Solved Question IDs
        s_query = "SELECT question_id FROM submissions WHERE user_id=%s AND contest_id=%s AND is_correct=1"
        s_res = db_manager.execute_query(s_query, (uid, contest_id))
        solved_ids = [str(r['question_id']) for r in s_res] if s_res else []

        # 5. Format Start Time (Strict UTC with Z to prevent browser drift)
        def format_utc(dt):
            if not dt: return None
            # Ensure it's treated as UTC. 
            # If the DB returned a naive object, we just add Z.
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        return jsonify({
            'success': True,
            'level': current_state['level'] if current_state else 1,
            'level_duration_minutes': level_duration,
            'violations': total_violations,
            'solved': current_state['questions_solved'] if current_state else 0,
            'solved_ids': solved_ids,
            'status': current_state['status'] or 'NOT_STARTED' if current_state else 'NOT_STARTED',
            'start_time': format_utc(current_state['start_time']) if current_state else None,
            'global_level': global_level_data['round_number'],
            'global_level_status': global_level_data['status'],
            'rounds_map': rounds_map,
            'countdown': countdown_data,
            'is_eliminated': is_disqualified_state,
            'disqualification_reason': disq_reason
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500

@bp.route('/start-level', methods=['POST'])
def start_level():
    try:
        data = request.get_json()
        if not data: return jsonify({'error': 'No input data provided'}), 400
            
        user_id = data.get('user_id')
        contest_id = data.get('contest_id', 1)
        level = data.get('level')
        
        if not user_id or not level: return jsonify({'error': 'Missing fields'}), 400
        
        # 1. Resolve User ID
        uid = user_id
        if isinstance(user_id, str) and not user_id.isdigit():
             u_res = db_manager.execute_query("SELECT user_id FROM users WHERE username=%s", (user_id,))
             if u_res: uid = u_res[0]['user_id']
             else: return jsonify({'error': f'User {user_id} not found'}), 404
        
        # 2. Ensure Row Exists
        # Use Python UTC time for consistency across systems
        now_utc = datetime.datetime.utcnow()
        
        db_manager.execute_update(
            "INSERT IGNORE INTO participant_level_stats (user_id, contest_id, level, status, start_time) VALUES (%s, %s, %s, 'NOT_STARTED', %s)",
            (uid, contest_id, level, now_utc)
        )
        
        # 3. Start Level (Update Status & Time ONLY if new)
        db_manager.execute_update(
            "UPDATE participant_level_stats SET start_time = %s, status = 'IN_PROGRESS' WHERE user_id=%s AND contest_id=%s AND level=%s AND (status='NOT_STARTED' OR status IS NULL OR status='PAUSED')",
            (now_utc, uid, contest_id, level)
        )
        
        # 4. Fetch Actual Start Time & Duration
        stats_query = "SELECT start_time FROM participant_level_stats WHERE user_id=%s AND contest_id=%s AND level=%s"
        stats_res = db_manager.execute_query(stats_query, (uid, contest_id, level))
        # Ensure UTC suffix
        start_time = stats_res[0]['start_time'] if stats_res and stats_res[0]['start_time'] else now_utc

        dur_query = "SELECT time_limit_minutes FROM rounds WHERE contest_id=%s AND round_number=%s"
        dur_res = db_manager.execute_query(dur_query, (contest_id, level))
        
        # Requested Defaults
        def get_default_duration(l):
            if l <= 3: return 20
            if l == 4: return 30
            if l == 5: return 45
            return 45

        duration = get_default_duration(level)
        if dur_res and dur_res[0]['time_limit_minutes'] and dur_res[0]['time_limit_minutes'] > 0:
            duration = dur_res[0]['time_limit_minutes']
        
        from extensions import socketio
        socketio.emit('admin:stats_update', {'contest_id': contest_id})
        socketio.emit('participant:level_start', {'user_id': uid, 'level': level, 'contest_id': contest_id})
        
        return jsonify({
            'success': True, 
            'level': level, 
            'status': 'IN_PROGRESS',
            'start_time': start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            'level_duration_minutes': duration
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

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
    # Set completion time
    now_utc = datetime.datetime.utcnow()
    db_manager.execute_update(
        "UPDATE participant_level_stats SET status='COMPLETED', completed_at=%s WHERE user_id=%s AND contest_id=%s AND level=%s", 
        (now_utc, uid, contest_id, level)
    )
    
    # Fetch Updated Stats for Broadccast
    stats_q = "SELECT level_score, violation_count, completed_at, start_time FROM participant_level_stats WHERE user_id=%s AND contest_id=%s AND level=%s"
    stats = db_manager.execute_query(stats_q, (uid, contest_id, level))
    
    score = 0
    violations = 0
    time_taken = 0
    if stats:
        s = stats[0]
        score = s.get('level_score', 0)
        violations = s.get('violation_count', 0)
        if s.get('completed_at') and s.get('start_time'):
            time_taken = int((s['completed_at'] - s['start_time']).total_seconds())

    from extensions import socketio
    socketio.emit('admin:stats_update', {'contest_id': contest_id})
    socketio.emit('participant:level_complete', {
        'user_id': uid, 
        'level': level, 
        'contest_id': contest_id,
        'score': float(score),
        'time_taken': time_taken,
        'violations': violations
    })
    
    # 2. Automatically Unlock Next Level
    next_level = int(level) + 1
    
    # Check if next level exists in Rounds
    r_check = db_manager.execute_query("SELECT round_id FROM rounds WHERE contest_id=%s AND round_number=%s", (contest_id, next_level))
    if r_check:
        db_manager.execute_update(
            "INSERT IGNORE INTO participant_level_stats (user_id, contest_id, level, status) VALUES (%s, %s, %s, 'NOT_STARTED')",
            (uid, contest_id, next_level)
        )
    
    return jsonify({
        "success": True,
        "message": "Level finalized.",
        "next_level": next_level,
        "locked": False
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
    # Logic: Find *next* pending/locked round and Activate it
    data = request.get_json()
    wait_time = int(data.get('wait_time', 0))
    
    result = advance_level_logic(contest_id, wait_time)
    
    if not result:
         return jsonify({'success': False, 'message': 'No pending rounds found.'})
    
    # Emit Event
    from extensions import socketio
    socketio.emit('level:activated', {'level': result['level'], 'start_time': result['start_time'].isoformat()})
    socketio.emit('contest:updated', {'contest_id': contest_id})
    
    return jsonify({'success': True, 'message': f"Level {result['level']} Activated (Wait: {wait_time}m)"})


@bp.route('/<contest_id>/level/<int:level>/activate', methods=['POST'])
@admin_required
def activate_specific_level(contest_id, level):
    result = activate_level_logic(contest_id, level)
    
    from extensions import socketio
    socketio.emit('level:activated', {'level': level, 'start_time': result['start_time'].isoformat()})
    socketio.emit('contest:updated', {'contest_id': contest_id})
    return jsonify({'success': True})

@bp.route('/<contest_id>/level/<int:level>/complete', methods=['POST'])
@admin_required
def complete_specific_level(contest_id, level):
    complete_level_logic(contest_id, level)
    
    from extensions import socketio
    socketio.emit('level:completed', {'level': level})
    socketio.emit('contest:updated', {'contest_id': contest_id})
    return jsonify({'success': True})



@bp.route('/<contest_id>/finalize-round', methods=['POST'])
@admin_required
def finalize_round(contest_id):
    # Mark CURRENT active round as completed
    # 1. Find active round
    q = "SELECT round_number FROM rounds WHERE contest_id=%s AND status='active' LIMIT 1"
    res = db_manager.execute_query(q, (contest_id,))
    
    if res:
        r_num = res[0]['round_number']
        # 2. Update to completed
        u_q = "UPDATE rounds SET status='completed' WHERE contest_id=%s AND round_number=%s"
        db_manager.execute_update(u_q, (contest_id, r_num))
        
        # 3. Notify
        from extensions import socketio
        socketio.emit('level:completed', {'level': r_num})
        socketio.emit('contest:updated', {'contest_id': contest_id})
        
        return jsonify({'success': True, 'message': f'Level {r_num} Finalized'})
    
    return jsonify({'success': False, 'message': 'No active round to finalize'})

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


