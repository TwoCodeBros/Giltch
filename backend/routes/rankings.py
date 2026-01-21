
from flask import Blueprint, jsonify, request
from db_connection import db_manager

bp = Blueprint('rankings', __name__)

@bp.route('/view', methods=['GET'])
def get_public_rankings():
    """
    Get finalized rankings for a specific level.
    Only shows data if the level is explicitly marked as finalized/completed by admin logic,
    OR if we simply query for scores.
    The requirement says: "become visible only after the admin clicks the ‘Finalize Level’ button".
    We can check the 'status' of the round in the 'rounds' table.
    """
    try:
        level = request.args.get('level', 1, type=int)
        
        # 1. Check Level Status
        # We assume active contest is the one we care about. Let's find active or latest.
        c_query = "SELECT contest_id FROM contests WHERE status IN ('live', 'active') OR status='ended' ORDER BY start_datetime DESC LIMIT 1"
        c_res = db_manager.execute_query(c_query)
        if not c_res:
            return jsonify({'error': 'No active contest found', 'rankings': []}), 404
            
        contest_id = c_res[0]['contest_id']
        
        # Check round status
        r_query = "SELECT status FROM rounds WHERE contest_id=%s AND round_number=%s"
        r_res = db_manager.execute_query(r_query, (contest_id, level))
        
        round_status = r_res[0]['status'] if r_res else 'pending'
        
        # Strict rule: "visible only after the admin clicks the ‘Finalize Level’". 
        # Mapping 'Finalize' to 'completed' status seems appropriate.
        if round_status != 'completed':
            return jsonify({
                'rankings': [],
                'status': 'pending', 
                'message': 'Results for this level are not yet finalized.'
            })
            
        # 2. Fetch Rankings
        # We need: P.ID, Name, Dept, College, Score, Time.
        # Sorted by Score DESC (Wait, user asked for ASCENDING based on score? Usually higher is better. 
        # "sorted in ascending order based on score" -> Lowest score first? Or Rank 1 (Highest) first?
        # Usually Rank 1 is highest score. "Ascending order of Rank" = Descending order of Score.
        # Interpreting "Ascending order based on score" literally would mean low scores first, which is weird for a contest.
        # BUT, if score is Time-based (golf?), then low is good.
        # "Score and Time Taken". Usually Score is Points.
        # I will assume "Descending Score, then Ascending Time" which is standard competitive programming.
        # If user insisted "ascending order based on score", I might clarify, but usually "Rank 1, 2, 3..." is implied.
        # Let's stick to standard: ORDER BY score DESC, time_taken ASC.
        
        query = """
            SELECT 
                u.username as participant_id,
                u.full_name,
                u.department,
                u.college,
                COALESCE(ls.points, 0) as score,
                COALESCE(ls.time_taken_seconds, 0) as time_taken,
                COALESCE(ls.questions_solved, 0) as solved_count
            FROM users u
            JOIN participant_level_stats ls ON u.user_id = ls.user_id
            WHERE ls.contest_id = %s AND ls.level = %s AND u.role = 'participant'
            ORDER BY ls.points DESC, ls.time_taken_seconds ASC
        """
        
        res = db_manager.execute_query(query, (contest_id, level))
        
        rankings = []
        for idx, row in enumerate(res):
            # Format time
            seconds = row['time_taken']
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            time_str = "{:02d}:{:02d}:{:02d}".format(int(h), int(m), int(s))
            
            rankings.append({
                'rank': idx + 1,
                'id': row['participant_id'],
                'name': row['full_name'],
                'department': row['department'],
                'college': row['college'],
                'score': row['score'],
                'time': time_str,
                'solved': row['solved_count']
            })
            
        return jsonify({'rankings': rankings, 'status': 'finalized'})
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@bp.route('/levels', methods=['GET'])
def get_finalized_levels():
    """
    Get a list of all finalized levels (status='completed') for the active/latest contest.
    Used for the dropdown selector.
    """
    try:
        # Get active contest
        c_query = "SELECT contest_id FROM contests WHERE status IN ('live', 'active') OR status='ended' ORDER BY start_datetime DESC LIMIT 1"
        c_res = db_manager.execute_query(c_query)
        if not c_res:
            return jsonify({'levels': []})
            
        contest_id = c_res[0]['contest_id']
        
        # Get completed rounds
        query = "SELECT round_number, title FROM rounds WHERE contest_id=%s AND status='completed' ORDER BY round_number ASC"
        res = db_manager.execute_query(query, (contest_id,))
        
        levels = []
        for r in res:
            levels.append({
                'level': r['round_number'],
                'title': r['title'] or f"Level {r['round_number']}"
            })
            
        return jsonify({'levels': levels})
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
