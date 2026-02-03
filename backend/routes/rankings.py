
from flask import Blueprint, jsonify, request
from db_connection import db_manager
import datetime

bp = Blueprint('rankings', __name__)

@bp.route('/levels', methods=['GET'])
def get_levels():
    # Fetch all rounds/levels for the active or latest contest
    # We prioritize live contests, then the most recent one.
    c_query = "SELECT contest_id FROM contests WHERE status='live' LIMIT 1"
    c_res = db_manager.execute_query(c_query)
    
    contest_id = 1
    if c_res:
        contest_id = c_res[0]['contest_id']
    else:
        # Fallback to most recent
        c_res = db_manager.execute_query("SELECT contest_id FROM contests ORDER BY contest_id DESC LIMIT 1")
        if c_res: contest_id = c_res[0]['contest_id']

    # Fetch levels
    # The user wants "Data for all time", so we show all levels defined in the rounds table
    query = "SELECT round_number, round_name, status FROM rounds WHERE contest_id=%s ORDER BY round_number ASC"
    rows = db_manager.execute_query(query, (contest_id,))
    
    levels = []
    if rows:
        for r in rows:
            levels.append({
                'level': r['round_number'],
                'title': r['round_name'] or f"Level {r['round_number']}",
                'status': r['status']
            })
            
    return jsonify({'levels': levels})

@bp.route('/view', methods=['GET'])
def view_rankings():
    level = request.args.get('level', 1)
    
    # Identify Contest
    c_query = "SELECT contest_id FROM contests WHERE status='live' LIMIT 1"
    c_res = db_manager.execute_query(c_query)
    contest_id = 1
    if c_res:
        contest_id = c_res[0]['contest_id']
    else:
         c_res = db_manager.execute_query("SELECT contest_id FROM contests ORDER BY contest_id DESC LIMIT 1")
         if c_res: contest_id = c_res[0]['contest_id']

    # Query Stats
    query = """
        SELECT 
            u.username,
            u.full_name,
            u.department, 
            u.college,
            pls.level_score,
            pls.questions_solved,
            pls.status,
            pls.start_time, 
            pls.completed_at,
            TIMESTAMPDIFF(SECOND, pls.start_time, pls.completed_at) as time_taken_sec
        FROM participant_level_stats pls
        JOIN users u ON pls.user_id = u.user_id
        WHERE pls.contest_id = %s AND pls.level = %s AND u.role = 'participant'
        ORDER BY pls.level_score DESC, 
                 CASE WHEN pls.status = 'COMPLETED' THEN 0 ELSE 1 END ASC,
                 time_taken_sec ASC
    """
    
    res = db_manager.execute_query(query, (contest_id, level))
    
    rankings = []
    if res:
        for idx, row in enumerate(res):
            # Time Format
            seconds = row.get('time_taken_sec')
            if seconds is not None and row.get('status') == 'COMPLETED':
                m, s = divmod(int(seconds), 60)
                h, m = divmod(m, 60)
                time_str = "{:02d}:{:02d}:{:02d}".format(h, m, s)
            elif row.get('status') == 'IN_PROGRESS':
                time_str = "In Progress"
            else:
                time_str = "--"
            
            rankings.append({
                'rank': idx + 1,
                'name': row['full_name'] or row['username'],
                'id': row['username'],
                'department': row.get('department'),
                'college': row.get('college'),
                'score': float(row['level_score'] or 0),
                'time': time_str,
                'solved': row['questions_solved']
            })
            
    return jsonify({'rankings': rankings})
