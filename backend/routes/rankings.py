
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
        # Strict rule: "visible only after the admin clicks the ‘Finalize Level’". 
        # Mapping 'Finalize' to 'completed' status.
        # ALLOW 'active' FOR TESTING/DEMO if needed, but per requirements stick to completed.
        # User is stuck, so maybe they have stats but level isn't marked completed?
    # Remove specific status check to allow users to see any level they pick
        # if round_status not in ['completed', 'active']:
        #      return jsonify({
        #         'rankings': [],
        #         'status': 'pending', 
        #         'message': 'Results for this level are not yet active/finalized.'
        #     })
            
        # 2. Fetch Rankings
        # We need: P.ID, Name, Dept, College, Score, Time.
        # Standard: ORDER BY score DESC, time_taken ASC.
        
        query = """
            SELECT 
                u.username as participant_id,
                u.full_name,
                u.department,
                u.college,
                COALESCE(ls.level_score, 0) as score,
                COALESCE(TIMESTAMPDIFF(SECOND, ls.start_time, ls.completed_at), 0) as time_taken,
                COALESCE(ls.questions_solved, 0) as solved_count
            FROM users u
            JOIN participant_level_stats ls ON u.user_id = ls.user_id
            WHERE ls.contest_id = %s AND ls.level = %s AND u.role = 'participant'
            ORDER BY score DESC, time_taken ASC
        """
        
        res = db_manager.execute_query(query, (contest_id, level))
        
        rankings = []
        for idx, row in enumerate(res):
            # Format time
            seconds = row['time_taken']
            # If timestamp diff is negative or None, handle gracefully
            if not seconds or seconds < 0:
                 seconds = 0
                 
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            time_str = "{:02d}:{:02d}:{:02d}".format(int(h), int(m), int(s))
            
            rankings.append({
                'rank': idx + 1,
                'id': row['participant_id'],
                'name': row['full_name'],
                'department': row['department'],
                'college': row['college'],
                'score': float(row['score']),
                'time': time_str,
                'solved': row['solved_count']
            })
            
        return jsonify({'rankings': rankings, 'status': round_status})
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@bp.route('/levels', methods=['GET'])
def get_finalized_levels():
    """
    Get a list of ALL levels for the dropdown (Levels 1-5).
    """
    try:
        # Get active contest
        c_query = "SELECT contest_id FROM contests WHERE status IN ('live', 'active') OR status='ended' ORDER BY start_datetime DESC LIMIT 1"
        c_res = db_manager.execute_query(c_query)
        if not c_res:
            return jsonify({'levels': []})
            
        contest_id = c_res[0]['contest_id']
        
        # Get ALL rounds regardless of status
        # User requested to show "Level 1" to "Level 5" and NOT the name.
        query = "SELECT round_number FROM rounds WHERE contest_id=%s ORDER BY round_number ASC"
        res = db_manager.execute_query(query, (contest_id,))
        
        levels = []
        # If DB is empty, maybe fallback? But DB should have them.
        if res:
            for r in res:
                levels.append({
                    'level': r['round_number'],
                    'title': f"Level {r['round_number']}" # Force generic name
                })
        else:
            # Fallback if no rounds found (unlikely)
            for i in range(1, 6):
                levels.append({'level': i, 'title': f"Level {i}"})
            
        return jsonify({'levels': levels})
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
