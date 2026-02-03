from flask import Blueprint, jsonify, request, Response
from utils.db import get_db
import datetime
import io
import csv

bp = Blueprint('leaderboard', __name__)

@bp.route('/', methods=['GET'])
def get_leaderboard():
    db = get_db()
    level = request.args.get('level', 1, type=int) # Default to Level 1
    
    # Check if we are querying for a specific level
    # Use participant_level_stats
    query = """
        SELECT 
            u.username as participant_id, 
            u.full_name, 
            u.department, 
            u.college,
            pls.level_score as total_score,
            pls.questions_solved,
            pls.status,
            pls.start_time, 
            pls.completed_at,
            TIMESTAMPDIFF(SECOND, pls.start_time, pls.completed_at) as time_taken_sec
        FROM participant_level_stats pls
        JOIN users u ON pls.user_id = u.user_id
        WHERE u.role = 'participant' AND pls.level = %s
        ORDER BY pls.level_score DESC, 
                 CASE WHEN pls.status = 'COMPLETED' THEN 0 ELSE 1 END ASC,
                 time_taken_sec ASC
    """
    
    # We use db_manager via get_db() which returns the bridge or manager
    # execute_query supports params
    res = db.execute_query(query, (level,))
    
    data = []
    if res:
        for idx, row in enumerate(res):
            # Format time
            seconds = row.get('time_taken_sec')
            if seconds is not None:
                m, s = divmod(int(seconds), 60)
                h, m = divmod(m, 60)
                time_str = "{:02d}:{:02d}:{:02d}".format(h, m, s)
            else:
                # If not completed or calculated, show -- or duration so far?
                # Usually leaderboard shows finalized time.
                time_str = "--:--:--"
                if row.get('status') == 'IN_PROGRESS' and row.get('start_time'):
                    # Optional: Could show current running time, but cache implications.
                    # Let's keep it simple: -- for incomplete.
                    pass

            data.append({
                'id': row['participant_id'],
                'rank': idx + 1,
                'name': row['full_name'],
                'department': row.get('department'),
                'college': row.get('college'),
                'score': float(row['total_score']),
                'time': time_str,
                'solved': row['questions_solved'],
                'status': row['status']
            })
            
    # Fetch Total Questions for this level
    q_count_query = """
        SELECT COUNT(*) as count 
        FROM questions q
        JOIN rounds r ON q.round_id = r.round_id
        WHERE r.round_number = %s
    """
    total_q_res = db.execute_query(q_count_query, (level,))
    total_questions = total_q_res[0]['count'] if total_q_res else 0

    return jsonify({
        "leaderboard": data,
        "level": level,
        "total_questions": total_questions,
        "generated_at": datetime.datetime.utcnow().isoformat()
    })

@bp.route('/report', methods=['GET'])
def download_leaderboard_report():
    db = get_db()
    level = request.args.get('level', 1, type=int)
    
    query = """
        SELECT 
            u.username as participant_id, 
            u.full_name, 
            u.department, 
            u.college,
            pls.level_score as total_score,
            pls.questions_solved,
            pls.status,
            TIMESTAMPDIFF(SECOND, pls.start_time, pls.completed_at) as time_taken_sec
        FROM participant_level_stats pls
        JOIN users u ON pls.user_id = u.user_id
        WHERE u.role = 'participant' AND pls.level = %s
        ORDER BY pls.level_score DESC, 
                 CASE WHEN pls.status = 'COMPLETED' THEN 0 ELSE 1 END ASC,
                 time_taken_sec ASC
    """
    res = db.execute_query(query, (level,))
    
    data = []
    if res:
        for idx, row in enumerate(res):
            seconds = row.get('time_taken_sec')
            if seconds is not None:
                m, s = divmod(int(seconds), 60)
                h, m = divmod(m, 60)
                time_str = "{:02d}:{:02d}:{:02d}".format(h, m, s)
            else:
                time_str = "In Progress"
            
            data.append({
                'rank': idx + 1,
                'id': row['participant_id'],
                'name': row['full_name'],
                'department': row.get('department', ''),
                'college': row.get('college', ''),
                'score': float(row['total_score']),
                'time': time_str,
                'solved': row['questions_solved']
            })
    
    export_format = request.args.get('format', 'json')
    
    if export_format == 'csv':
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['rank', 'id', 'name', 'department', 'college', 'score', 'time', 'solved'])
        writer.writeheader()
        writer.writerows(data)
        
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename=leaderboard_level_{level}.csv"}
        )
    
    return jsonify({"report": data})
