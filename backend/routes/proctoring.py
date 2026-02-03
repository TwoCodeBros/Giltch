
from flask import Blueprint, jsonify, request
from db_connection import db_manager
import datetime
import uuid

bp = Blueprint('proctoring', __name__)

# --- HELPERS ---

def get_config(contest_id):
    query = "SELECT * FROM proctoring_config WHERE contest_id = %s"
    result = db_manager.execute_query(query, (contest_id,))
    if result: return result[0]
    return {
        "enabled": False, 
        "max_violations": 20, 
        "warning_threshold": 5,
        "auto_disqualify": False
    }

# --- ROUTES ---

@bp.route('/config/<int:contest_id>', methods=['GET'])
def get_proctoring_config(contest_id):
    config = get_config(contest_id)
    return jsonify({"config": config}), 200

@bp.route('/config/<int:contest_id>', methods=['PUT'])
def update_proctoring_config(contest_id):
    data = request.get_json()
    
    # Check if exists
    check_query = "SELECT 1 FROM proctoring_config WHERE contest_id = %s"
    exists = db_manager.execute_query(check_query, (contest_id,))
    
    if exists:
        query = """
            UPDATE proctoring_config 
            SET enabled=%s, max_violations=%s, warning_threshold=%s, auto_disqualify=%s,
                track_tab_switches=%s, track_focus_loss=%s, block_copy=%s, block_paste=%s, detect_screenshot=%s
            WHERE contest_id=%s
        """
        params = (
            data.get('enabled', False),
            data.get('max_violations', 10),
            data.get('warning_threshold', 5),
            data.get('auto_disqualify', False),
            data.get('track_tab_switches', True),
            data.get('track_focus_loss', True),
            data.get('block_copy', True),
            data.get('block_paste', True),
            data.get('detect_screenshot', True),
            contest_id
        )
        db_manager.execute_update(query, params)
    else:
        query = """
            INSERT INTO proctoring_config 
            (id, contest_id, enabled, max_violations, warning_threshold, auto_disqualify, 
             track_tab_switches, track_focus_loss, block_copy, block_paste, detect_screenshot)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            str(uuid.uuid4()),
            contest_id,
            data.get('enabled', False),
            data.get('max_violations', 10),
            data.get('warning_threshold', 5),
            data.get('auto_disqualify', False),
            data.get('track_tab_switches', True),
            data.get('track_focus_loss', True),
            data.get('block_copy', True),
            data.get('block_paste', True),
            data.get('detect_screenshot', True)
        )
        db_manager.execute_update(query, params)
        
    return jsonify({'success': True})

@bp.route('/stats/<int:contest_id>', methods=['GET'])
def get_proctoring_stats(contest_id):
    query = """
        SELECT 
            SUM(total_violations) as total_violations,
            COUNT(CASE WHEN risk_level IN ('high', 'critical') THEN 1 END) as active_risky_participants,
            COUNT(CASE WHEN is_disqualified=1 AND disqualification_reason LIKE 'Auto%' THEN 1 END) as auto_disqualifications,
            COUNT(CASE WHEN is_disqualified=1 AND disqualification_reason NOT LIKE 'Auto%' THEN 1 END) as manual_disqualifications
        FROM participant_proctoring
        WHERE contest_id = %s
    """
    res = db_manager.execute_query(query, (contest_id,))
    stats = res[0] if res else {
        'total_violations': 0,
        'active_risky_participants': 0,
        'auto_disqualifications': 0,
        'manual_disqualifications': 0
    }
    # Handle None from SUM
    for k, v in stats.items():
        if v is None: stats[k] = 0
        
    return jsonify({"stats": stats})

@bp.route('/status/<int:contest_id>', methods=['GET'])
def get_proctoring_status(contest_id):
    level = request.args.get('level')
    
    query = """
        SELECT 
            pp.*,
            u.full_name as participant_name,
            u.username as participant_handle
        FROM participant_proctoring pp
        LEFT JOIN users u ON pp.user_id = u.user_id
        WHERE pp.contest_id = %s
    """
    params = [contest_id]
    
    if level:
        query = """
            SELECT 
                pp.*,
                u.full_name as participant_name,
                u.username as participant_handle
            FROM participant_proctoring pp
            LEFT JOIN users u ON pp.user_id = u.user_id
            JOIN participant_level_stats pls ON pp.user_id = pls.user_id AND pp.contest_id = pls.contest_id
            WHERE pp.contest_id = %s AND pls.level = %s
        """
        params.append(level)
        
    res = db_manager.execute_query(query, tuple(params))
    return jsonify({"statuses": res})

@bp.route('/violation', methods=['POST'])
def report_violation():
    """
    Core Logic for Violation Tracking
    - Logs raw violation
    - Updates aggregate stats
    - Calculates Risk Level
    - Enforces Auto-Disqualification
    """
    data = request.get_json()
    
    contest_id = data.get('contest_id')
    participant_id_str = data.get('participant_id') # "PART001"
    violation_type = data.get('violation_type')
    description = data.get('description')
    level = data.get('level')
    
    # 1. Resolve User ID
    u_res = db_manager.execute_query("SELECT user_id, username FROM users WHERE username=%s", (participant_id_str,))
    if not u_res:
        return jsonify({'error': 'User not found'}), 404
        
    user_id = u_res[0]['user_id']
    username = u_res[0]['username']
    
    # 2. Log Raw Violation (Source of Truth for Audit)
    query_log = """
        INSERT INTO violations 
        (user_id, contest_id, round_id, violation_type, description, severity, penalty_points, level, timestamp)
        VALUES (%s, %s, %s, %s, %s, 'medium', 1, %s, %s)
    """
    db_manager.execute_update(query_log, (user_id, contest_id, None, violation_type, description, level, datetime.datetime.utcnow()))
    
    # 3. Determine Field Updates based on Type
    field_map = {
        'TAB_SWITCH': 'tab_switches',
        'TAB_SWITCH_ATTEMPT': 'tab_switches',
        'FOCUS_LOST': 'focus_losses',
        'CLIPBOARD_SHORTCUT': 'copy_attempts',
        'SCREENSHOT_ATTEMPT': 'screenshot_attempts',
        'DEVTOOLS_DETECTED': 'screenshot_attempts', # Grouping for simplicity or add column? Schema has limited columns.
        'RIGHT_CLICK': 'copy_attempts'
    }
    
    inc_field = field_map.get(violation_type)
    
    # 4. Upsert Participant Stats (Single Source of Truth for State)
    # Check existence
    check_pp = "SELECT total_violations FROM participant_proctoring WHERE user_id=%s AND contest_id=%s"
    pp_res = db_manager.execute_query(check_pp, (user_id, contest_id))
    
    if pp_res:
        # Update
        base_update = """
            UPDATE participant_proctoring 
            SET total_violations = total_violations + 1,
                last_violation_at = NOW()
        """
        if inc_field:
            base_update += f", {inc_field} = {inc_field} + 1"
            
        base_update += " WHERE user_id = %s AND contest_id = %s"
        db_manager.execute_update(base_update, (user_id, contest_id))
        
        current_violations = pp_res[0]['total_violations'] + 1
    else:
        # Insert
        inc_val_map = {
            'tab_switches': 0, 'focus_losses': 0, 'copy_attempts': 0, 'screenshot_attempts': 0
        }
        if inc_field: inc_val_map[inc_field] = 1
        
        query_insert = """
            INSERT INTO participant_proctoring 
            (id, participant_id, user_id, contest_id, total_violations, risk_level, last_violation_at,
             tab_switches, focus_losses, copy_attempts, screenshot_attempts)
            VALUES (%s, %s, %s, %s, 1, 'low', NOW(), %s, %s, %s, %s)
        """
        db_manager.execute_update(query_insert, (
            str(uuid.uuid4()), 
            username, 
            user_id, 
            contest_id,
            inc_val_map['tab_switches'],
            inc_val_map['focus_losses'],
            inc_val_map['copy_attempts'],
            inc_val_map['screenshot_attempts']
        ))
        current_violations = 1

    # 5. Check Thresholds & Enforce Disqualification (Backend Driver)
    config = get_config(contest_id)
    
    # Calculate Risk Level
    new_risk = 'low'
    if current_violations > 20: new_risk = 'critical'
    elif current_violations > 10: new_risk = 'high'
    elif current_violations > 5: new_risk = 'medium'
    
    update_risk_q = "UPDATE participant_proctoring SET risk_level=%s WHERE user_id=%s AND contest_id=%s"
    db_manager.execute_update(update_risk_q, (new_risk, user_id, contest_id))
    
    # Disqualification Logic
    if config.get('enabled') and config.get('auto_disqualify'):
        max_v = config.get('max_violations', 20)
        if current_violations >= max_v:
             dq_reason = f"Auto-Disqualified: Exceeded maximum violations ({max_v})"
             dq_q = """
                UPDATE participant_proctoring 
                SET is_disqualified=1, disqualification_reason=%s, disqualified_at=NOW()
                WHERE user_id=%s AND contest_id=%s AND (is_disqualified=0 OR is_disqualified IS NULL)
             """
             db_manager.execute_update(dq_q, (dq_reason, user_id, contest_id))
             return jsonify({'success': True, 'disqualified': True, 'reason': dq_reason})

    return jsonify({'success': True, 'disqualified': False})

@bp.route('/export/<int:contest_id>', methods=['GET'])
def export_proctoring_report(contest_id):
    import io
    import csv
    from flask import Response
    
    level = request.args.get('level')
    
    query = """
        SELECT 
            pp.participant_id, 
            u.username,
            u.full_name,
            pp.risk_level,
            pp.total_violations,
            pp.tab_switches,
            pp.copy_attempts,
            pp.screenshot_attempts,
            pp.focus_losses,
            pp.is_disqualified,
            pp.disqualification_reason,
            pp.last_violation_at
        FROM participant_proctoring pp
        LEFT JOIN users u ON pp.user_id = u.user_id
        WHERE pp.contest_id = %s
    """
    params = [contest_id]
    
    if level:
        query = """
            SELECT 
                pp.participant_id, 
                u.username,
                u.full_name,
                pp.risk_level,
                pp.total_violations,
                pp.tab_switches,
                pp.copy_attempts,
                pp.screenshot_attempts,
                pp.focus_losses,
                pp.is_disqualified,
                pp.disqualification_reason,
                pp.last_violation_at
            FROM participant_proctoring pp
            LEFT JOIN users u ON pp.user_id = u.user_id
            JOIN participant_level_stats pls ON pp.user_id = pls.user_id AND pp.contest_id = pls.contest_id
            WHERE pp.contest_id = %s AND pls.level = %s
        """
        params.append(level)
        
    results = db_manager.execute_query(query, tuple(params))
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['Participant ID', 'Username', 'Full Name', 'Risk Level', 'Total Violations', 'Tab Switches', 'Copy Attempts', 'Screenshots', 'Focus Lost', 'Disqualified?', 'Reason', 'Last Violation Time'])
    
    if results:
        for row in results:
            writer.writerow([
                row['participant_id'],
                row['username'],
                row['full_name'],
                row['risk_level'],
                row['total_violations'],
                row['tab_switches'],
                row['copy_attempts'],
                row['screenshot_attempts'],
                row['focus_losses'],
                'Yes' if row['is_disqualified'] else 'No',
                row['disqualification_reason'] or '',
                row['last_violation_at']
            ])
            
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=proctoring_report_contest_{contest_id}.csv"}
    )
