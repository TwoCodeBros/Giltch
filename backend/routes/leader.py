
from flask import Blueprint, jsonify, request
from db_connection import db_manager
import datetime

bp = Blueprint('leader', __name__)

@bp.route('/live-stats', methods=['GET'])
def live_stats():
    # 1. Get Active Contest
    c_query = "SELECT contest_id, contest_name as title, status, start_datetime FROM contests WHERE status='live' LIMIT 1"
    c_res = db_manager.execute_query(c_query)
    
    contest = None
    cid = 1
    if c_res:
        contest = c_res[0]
        cid = contest['contest_id']
        contest['start_datetime'] = contest['start_datetime'].isoformat() if contest['start_datetime'] else None
    else:
        # Fallback to any contest
        all_c = db_manager.execute_query("SELECT contest_id, contest_name as title, status, start_datetime FROM contests ORDER BY start_datetime DESC LIMIT 1")
        if all_c:
            contest = all_c[0]
            contest['start_datetime'] = contest['start_datetime'].isoformat() if contest['start_datetime'] else None
            cid = contest['contest_id']
    
    if not contest:
        return jsonify({'contest': None})

    # 2. Get Participants & Status
    # Join users with proctoring for heartbeat, and level_stats for current level
    # We want max level per user
    query = """
        SELECT 
            u.user_id, u.username, u.full_name, u.department, u.college,
            MAX(p.last_heartbeat) as last_heartbeat,
            MAX(p.client_ip) as client_ip,
            MAX(ls.level) as current_level
        FROM users u
        LEFT JOIN participant_proctoring p ON u.user_id = p.user_id AND p.contest_id = %s
        LEFT JOIN participant_level_stats ls ON u.user_id = ls.user_id AND ls.contest_id = %s
        WHERE u.role = 'participant'
        GROUP BY u.user_id, u.username, u.full_name, u.department, u.college
    """
    p_res = db_manager.execute_query(query, (cid, cid))
    
    participants = []
    total_p = 0
    online_p = 0
    
    now = datetime.datetime.utcnow()
    
    for row in p_res:
        total_p += 1
        
        # Check online (heartbeat within 30s)
        is_online = False
        last_hb = row['last_heartbeat']
        if last_hb and (now - last_hb).total_seconds() < 60: # 60s tolerance
            is_online = True
            online_p += 1
            
        participants.append({
            'user_id': row['user_id'],
            'username': row['username'],
            'full_name': row['full_name'],
            'department': row.get('department', ''),
            'college': row.get('college', ''),
            'current_level': row['current_level'] or 1,
            'is_online': is_online,
            'last_heartbeat': last_hb.isoformat() if last_hb else None,
            'client_ip': row['client_ip']
        })
        
    return jsonify({
        'contest': contest,
        'stats': {
            'total_participants': total_p,
            'online_participants': online_p
        },
        'participants': participants
    })
