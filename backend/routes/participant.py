from flask import Blueprint, jsonify, request
from utils.db import get_db
import datetime
from extensions import socketio

bp = Blueprint('participant_routes', __name__)

@bp.route('/levels/<participant_id>', methods=['GET'])
def get_participant_levels(participant_id):
    """
    Get the status of all levels for a specific participant.
    Checks both global round status and individual participant progress.
    """
    db = get_db()
    contest_id = request.args.get('contest_id', 1) 

    try:
        # 1. Resolve User ID
        user_id = None
        username = participant_id
        
        u_res = db.execute_query("SELECT user_id, username FROM users WHERE username=%s OR user_id=%s", (username, username))
        if u_res:
             user_id = u_res[0]['user_id']
        else:
            return jsonify({'error': 'User not found'}), 404

        # 2. Get Rounds & Stats
        rounds_query = "SELECT round_number, round_name, status, is_locked FROM rounds WHERE contest_id=%s ORDER BY round_number ASC"
        rounds = db.execute_query(rounds_query, (contest_id,)) or []
        
        stats_query = "SELECT level, status, questions_solved FROM participant_level_stats WHERE user_id=%s AND contest_id=%s"
        stats = db.execute_query(stats_query, (user_id, contest_id))
        stats_map = {s['level']: s for s in stats} if stats else {}

        levels_data = []
        for r in rounds:
            r_num = r['round_number']
            p_stat = stats_map.get(r_num, {})
            p_status = p_stat.get('status', 'NOT_STARTED')
            
            is_locked = True
            if r['status'] == 'active': is_locked = False
            if p_status in ['IN_PROGRESS', 'COMPLETED']: is_locked = False
                
            levels_data.append({
                'level': r_num,
                'name': r['round_name'],
                'status': p_status, 
                'global_status': r['status'],
                'is_locked': is_locked,
                'solved': p_stat.get('questions_solved', 0)
            })

        return jsonify({'success': True, 'levels': levels_data})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/start-level', methods=['POST'])
def start_level():
    return unlock_level_logic(request.get_json())

@bp.route('/unlock-level', methods=['POST'])
def unlock_level_endpoint():
    return unlock_level_logic(request.get_json())

def unlock_level_logic(data):
    """
    Shared logic to unlock/activate a level.
    """
    if not data: return jsonify({'error': 'No data'}), 400
    
    participant_id = data.get('participant_id') or data.get('user_id')
    level = data.get('level') or data.get('level_number')
    contest_id = data.get('contest_id', 1)
    
    if not participant_id or not level:
        return jsonify({'error': 'Missing required fields'}), 400

    db = get_db()
    try:
        # Resolve ID
        user_id = None
        u_res = db.execute_query("SELECT user_id FROM users WHERE username=%s OR user_id=%s", (participant_id, participant_id))
        if u_res:
             user_id = u_res[0]['user_id']
        else:
             return jsonify({'error': 'User not found'}), 404
             
        now_iso = datetime.datetime.utcnow().isoformat()
        
        # Check Existing
        check_q = "SELECT start_time, status FROM participant_level_stats WHERE user_id=%s AND contest_id=%s AND level=%s"
        existing = db.execute_query(check_q, (user_id, contest_id, level))
        
        start_time = now_iso
        
        if existing and existing[0]['start_time']:
            start_time = existing[0]['start_time']
            if isinstance(start_time, datetime.datetime):
                start_time = start_time.isoformat()
            
            # If status is NOT_STARTED but time exists (weird?), or we just need to ensure STATUS is IN_PROGRESS
            if existing[0]['status'] == 'NOT_STARTED':
                 db.execute_update(
                    "UPDATE participant_level_stats SET status='IN_PROGRESS' WHERE user_id=%s AND contest_id=%s AND level=%s",
                    (user_id, contest_id, level)
                )
        else:
            # Insert New
             db.execute_update(
                "INSERT INTO participant_level_stats (user_id, contest_id, level, status, start_time) VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE status='IN_PROGRESS', start_time=VALUES(start_time)",
                (user_id, contest_id, level, 'IN_PROGRESS', now_iso)
            )
        
        # Fetch Duration
        d_res = db.execute_query("SELECT time_limit_minutes FROM rounds WHERE contest_id=%s AND round_number=%s", (contest_id, level))
        duration = 45
        if d_res and d_res[0]['time_limit_minutes']:
             duration = d_res[0]['time_limit_minutes']
        
        # Notify Admin
        socketio.emit('admin:stats_update', {'contest_id': contest_id})
        socketio.emit('participant:started_level', {'participant_id': participant_id, 'level': level, 'contest_id': contest_id})
        
        return jsonify({
            'success': True, 
            'level': level, 
            'status': 'active',
            'start_time': start_time,
            'level_duration_minutes': duration
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
