
"""
Proctoring Module API Routes
Handles proctoring configuration, violation tracking, monitoring, and admin actions.
"""

from flask import Blueprint, jsonify, request
from utils.db import get_db
from auth_middleware import admin_required
import uuid
import datetime

bp = Blueprint('proctoring', __name__)

# ==================== CONSTANTS & DEFAULTS ====================

DEFAULT_CONFIG = {
    'enabled': True,
    'max_violations': 10,
    'auto_disqualify': True,
    'warning_threshold': 5,
    'grace_violations': 2,
    'tab_switch_penalty': 1,
    'copy_paste_penalty': 2,
    'screenshot_penalty': 3,
    'focus_loss_penalty': 1
}

# ==================== HELPERS ====================

def get_current_time():
    return datetime.datetime.utcnow().isoformat()

def get_config(contest_id):
    """Get proctoring config for a contest"""
    db = get_db()
    res = db.table('proctoring_config').select("*").eq("contest_id", contest_id).execute()
    if res.data:
        return res.data[0]
    
    # Return default struct if not in DB (mock/fallback)
    return {**DEFAULT_CONFIG, 'contest_id': contest_id}

def calculate_risk_level(total_violations):
    """
    Calculate risk level based on total violations.
    Logic: <=5 Low/Medium (implied), >5 High, >10 Critical.
    Refining to: 0-2 Low, 3-5 Medium, 6-10 High, >10 Critical (Disqualified usually)
    """
    if total_violations > 10: return 'critical'
    if total_violations > 5: return 'high'
    if total_violations > 2: return 'medium'
    return 'low'

def update_participant_aggregates(participant_id, contest_id, violation_points, violation_col=None, level=1):
    """
    Update participant_proctoring table with strict category incrementing.
    violation_col: specific column to increment (e.g. 'tab_switches')
    Enforces rules LEVEL-WISE (resetting limits per level).
    """
    db = get_db()
    
    # 1. Get Current State
    try:
        res = db.table('participant_proctoring').select("*").eq("participant_id", participant_id).eq("contest_id", contest_id).execute()
        
        if not res.data:
            # Create initial record
            current = {
                'id': str(uuid.uuid4()),
                'participant_id': participant_id,
                'contest_id': contest_id,
                'total_violations': 0,
                'violation_score': 0,
                'extra_violations': 0,
                'risk_level': 'low',
                'is_disqualified': False,
                'created_at': get_current_time(),
                'tab_switches': 0,
                'copy_attempts': 0,
                'screenshot_attempts': 0,
                'focus_losses': 0
            }
            db.table('participant_proctoring').insert(current).execute()
            state = current
        else:
            state = res.data[0]

        # 2. Get Config
        config = get_config(contest_id)
        
        # Helper to safely get current counter value
        def get_stat(key):
            val = state.get(key)
            if val is None: return 0
            try: return int(val)
            except: return 0

        # 3. Calculate New Values (Global Stats still accumulate)
        new_total_global = get_stat('total_violations') + 1
        new_score = get_stat('violation_score') + violation_points
        
        # Level-Wise Violation Count Calculation
        # We need to count violations for THIS level to enforce the limit
        # Since the current violation hasn't been inserted into 'violations' table yet (it's done after this function in original code),
        # we calculate existing + 1.
        # However, checking the DB is safer. But existing code inserts into violations AFTER this function.
        # So we query count, then add 1.
        
        # NOTE: db.table('violations') query might be slow if many violations. 
        # Ideally we should have 'participant_level_stats' tracking violations per level.
        # For now, we query.
        
        level_violations = 1 # Start with current one
        try:
             # Need to find user_id for the query? 'participant_id' in violations is 'user_id' (INT) or 'participant_id' string?
             # The schema says 'user_id' (INT). But this function takes 'participant_id' (Username string).
             # We need to resolve user_id presumably, OR 'violations' table uses user_id.
             # In report_violation, we resolve user_id.
             pass 
        except: 
             pass

        # To avoid resolving user_id again here, let's rely on the caller or just count from 'violations' if we can.
        # Given we don't have user_id here easily without query, and 'participant_proctoring' uses 'participant_id' (username).
        # Let's fallback to Global enforcement if we can't easily filter, OR simpler:
        # Just use Global Total for now but mention we want level wise?
        # No, "Change it level wise" implies we MUST do it.
        # The 'violations' table has 'level'. 
        
        # Strategy: Query 'violations' table for this level.
        # issue: we need user_id for violations table. 'participant_id' param here is username. 
        # We'll do a quick lookup.
        u_res = db.table('users').select('user_id').eq('username', participant_id).execute()
        if u_res.data:
            uid = u_res.data[0]['user_id']
            # Count violations for this level
            # Note: The current violation is NOT in table yet.
            v_res = db.execute_query(
                "SELECT COUNT(*) as cnt FROM violations WHERE user_id=%s AND contest_id=%s AND level=%s", 
                (uid, contest_id, level)
            )
            existing_level_count = v_res[0]['cnt'] if v_res else 0
            level_violations = existing_level_count + 1
        else:
            level_violations = new_total_global # Fallback
            
        
        # Risk Level (Based on Level Violations now? Or Global? usually Global Risk is better for Dashboard)
        # Let's keep Risk Level Global for admin visibility, but Disqualification Level-Wise.
        risk = calculate_risk_level(new_total_global) 
        
        # 4. Prepare Update Data
        update_data = {
            'total_violations': new_total_global,
            'violation_score': new_score,
            'last_violation_at': get_current_time(),
            'updated_at': get_current_time()
        }
        
        # Increment Specific Column
        if violation_col:
            valid_cols = ['tab_switches', 'copy_attempts', 'screenshot_attempts', 'focus_losses']
            if violation_col in valid_cols:
                update_data[violation_col] = get_stat(violation_col) + 1
        
        # 5. Auto Disqualify Check (LEVEL WISE)
        is_disqualified = bool(state.get('is_disqualified', False))
        disq_reason = state.get('disqualification_reason')
        disq_at = state.get('disqualified_at')
        
        max_allowed = config.get('max_violations', 10) + get_stat('extra_violations')
        
        if config.get('auto_disqualify') and level_violations > max_allowed and not is_disqualified:
            is_disqualified = True
            risk = 'critical'
            disq_reason = f'Auto: Exceeded max violations for Level {level}'
            disq_at = get_current_time()
            
            # Emit Disqualified Event
            try:
                from extensions import socketio
                socketio.emit('proctoring:disqualified', {
                    'participant_id': participant_id,
                    'contest_id': contest_id,
                    'reason': disq_reason
                })
            except: pass

        # Update DB
        update_data['risk_level'] = risk
        update_data['is_disqualified'] = is_disqualified
        if is_disqualified:
            update_data['disqualification_reason'] = disq_reason
            update_data['disqualified_at'] = disq_at
        
        db.table('participant_proctoring').update(update_data).eq("participant_id", participant_id).eq("contest_id", contest_id).execute()
        
        return {**state, **update_data, 'level_violations': level_violations}
        
    except Exception as e:
        print(f"Error in update_participant_aggregates: {e}")
        import traceback
        traceback.print_exc()
        raise e

# ==================== CONFIG ROUTES ====================

@bp.route('/config/<contest_id>', methods=['GET'])
def get_proctoring_config(contest_id):
    """Get proctoring configuration"""
    try:
        config = get_config(contest_id)
        if 'id' not in config:
             pass
        return jsonify({'success': True, 'config': config})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/config/<contest_id>', methods=['POST', 'PUT'])
@admin_required
def update_proctoring_config(contest_id):
    """Update proctoring configuration"""
    data = request.get_json()
    db = get_db()
    
    try:
        res = db.table('proctoring_config').select("*").eq("contest_id", contest_id).execute()
        
        if res.data:
            db.table('proctoring_config').update(data).eq("contest_id", contest_id).execute()
        else:
            data['contest_id'] = contest_id
            data['id'] = str(uuid.uuid4())
            db.table('proctoring_config').insert(data).execute()
            
        return jsonify({'success': True, 'message': 'Config updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== VIOLATION LOGIC ====================

@bp.route('/violation', methods=['POST'])
def report_violation():
    """
    Logic to receive a violation, lookup the contest penalty weights, 
    update the individual log, increment the participant's total_violations, 
    and calculate if they should be auto_disqualified.
    """
    data = request.get_json()
    participant_id_input = data.get('participant_id') 
    contest_id = data.get('contest_id')
    violation_type = data.get('violation_type')
    
    if not all([participant_id_input, contest_id, violation_type]):
        return jsonify({'error': 'Missing required fields'}), 400
        
    db = get_db()
    
    try:
        # 1. Resolve User ID
        user_id = None
        username = participant_id_input
        
        u_res = db.execute_query("SELECT user_id, username FROM users WHERE username=%s OR user_id=%s", (username, username))
        if u_res:
             user_id = u_res[0]['user_id']
             username = u_res[0]['username'] 
        
        if not user_id:
            return jsonify({'error': 'User not found'}), 404

        # 2. Get Config & Weights
        config = get_config(contest_id)
        if not config.get('enabled', True):
             return jsonify({'success': True, 'ignored': True})

        # Weights Map
        weights = {
            'TAB_SWITCH': config.get('tab_switch_penalty', 1),
            'COPY_ATTEMPT': config.get('copy_paste_penalty', 2),
            'PASTE_ATTEMPT': config.get('copy_paste_penalty', 2),
            'CUT_ATTEMPT': config.get('copy_paste_penalty', 2),
            'SCREENSHOT_ATTEMPT': config.get('screenshot_penalty', 3),
            'FOCUS_LOST': config.get('focus_loss_penalty', 1),
            # Backwards compatibility
            'copy': config.get('copy_paste_penalty', 2), 
            'paste': config.get('copy_paste_penalty', 2),
            'cut': config.get('copy_paste_penalty', 2),
            'unknown': 1
        }
        
        points = weights.get(violation_type, 1) # Default to 1
        if points == 1 and violation_type.upper() in weights:
             points = weights[violation_type.upper()]
        
        # 3. Update Aggregate Stats with explicit mapping
        # violation_type comes from frontend e.g. 'TAB_SWITCH' or 'COPY_ATTEMPT'
        
        mapping_col = None
        vt_upper = str(violation_type).upper().strip()
        
        if 'TAB' in vt_upper: mapping_col = 'tab_switches'
        elif any(x in vt_upper for x in ['COPY', 'PASTE', 'CUT']): mapping_col = 'copy_attempts'
        elif 'SCREEN' in vt_upper: mapping_col = 'screenshot_attempts'
        elif 'FOCUS' in vt_upper: mapping_col = 'focus_losses'
        
        # We pass this decided column to the updater
        # Extract level from data, default to 1.
        current_level = data.get('level', 1) 
        try: current_level = int(current_level)
        except: current_level = 1

        updated_state = update_participant_aggregates(username, contest_id, points, mapping_col, level=current_level)
        
        # 4. Log Individual Violation
        violation_log = {
            'user_id': user_id,
            'contest_id': contest_id,
            'violation_type': violation_type,
            'penalty_points': points,
            'description': data.get('description', f'Detected {violation_type}'),
            'timestamp': get_current_time(),
            'round_id': data.get('round_id'),
            'level': current_level, # Added level
            'question_id': data.get('question_id'),
            'severity': updated_state['risk_level']
        }
        violation_log['severity'] = 'critical' if points >= 3 else ('medium' if points >= 2 else 'low')
        
        db.table('violations').insert(violation_log).execute()
        
        # 6. Real-time Alert
        try:
            from extensions import socketio
            socketio.emit('proctoring:violation', {
                'participant_id': username,
                'contest_id': contest_id,
                'violation_type': violation_type,
                'total_violations': updated_state['total_violations'],
                'risk_level': updated_state['risk_level'],
                'is_disqualified': updated_state['is_disqualified']
            })
        except: pass

        return jsonify({
            'success': True,
            'total_violations': updated_state['total_violations'],
            'risk_level': updated_state['risk_level'],
            'is_disqualified': updated_state['is_disqualified']
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ==================== MONITORING & ACTIONS ====================

@bp.route('/stats/<contest_id>', methods=['GET'])
@admin_required
def get_stats(contest_id):
    """
    Returns object with: total_violations, active_risky_participants, auto_disqualifications
    """
    db = get_db()
    try:
        # SQL Aggregations
        stats = {
            'total_violations': 0,
            'active_risky_participants': 0,
            'auto_disqualifications': 0
        }
        
        res1 = db.execute_query("SELECT SUM(total_violations) as val FROM participant_proctoring WHERE contest_id=%s", (contest_id,))
        if res1 and res1[0]['val']: stats['total_violations'] = float(res1[0]['val']) # Safe cast
        
        # Active Risky: Count of participants with risk high/critical who are NOT disqualified
        res2 = db.execute_query("SELECT COUNT(*) as val FROM participant_proctoring WHERE contest_id=%s AND risk_level IN ('high', 'critical') AND is_disqualified=0", (contest_id,))
        if res2: stats['active_risky_participants'] = int(res2[0]['val'])
        
        # Disqualified
        res3 = db.execute_query("SELECT COUNT(*) as val FROM participant_proctoring WHERE contest_id=%s AND is_disqualified=1", (contest_id,))
        if res3: stats['auto_disqualifications'] = int(res3[0]['val'])
        
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@bp.route('/status/<contest_id>', methods=['GET'])
@admin_required
def get_status(contest_id):
    """
    Returns a list of all participants sorted by risk level.
    """
    db = get_db()
    try:
        query = """
            SELECT 
                u.username as participant_id,
                u.full_name,
                pp.risk_level,
                pp.total_violations,
                pp.violation_score,
                pp.is_disqualified,
                pp.last_violation_at,
                pp.extra_violations,
                pp.tab_switches,
                pp.copy_attempts,
                pp.screenshot_attempts,
                pp.focus_losses
            FROM users u
            LEFT JOIN participant_proctoring pp ON u.user_id = pp.user_id AND pp.contest_id = %s
            WHERE u.role = 'participant'
        """
        rows = db.execute_query(query, (contest_id,))
        
        risk_priority = {'critical': 5, 'high': 4, 'medium': 3, 'low': 1, None: 0}
        
        participants = []
        for r in rows:
            risk = r.get('risk_level', 'low')
            if r.get('is_disqualified'): risk = 'critical'
            
            p = {
                'participant_id': r['participant_id'],
                'name': r['full_name'],
                'risk_level': r.get('risk_level', 'low'),
                'total_violations': r.get('total_violations', 0),
                'score': r.get('violation_score', 0),
                'is_disqualified': bool(r.get('is_disqualified')),
                'last_violation': r.get('last_violation_at'),
                'tab_switches': r.get('tab_switches') or 0,
                'copy_attempts': r.get('copy_attempts') or 0,
                'screenshot_attempts': r.get('screenshot_attempts') or 0,
                'focus_losses': r.get('focus_losses') or 0,
                'raw_priority': risk_priority.get(r.get('risk_level', 'low'), 0)
            }
            if r.get('is_disqualified'): p['raw_priority'] = 10 
            
            participants.append(p)
            
        participants.sort(key=lambda x: (x['raw_priority'], x['score']), reverse=True)
        
        return jsonify({'success': True, 'statuses': participants})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/action/allow-extra', methods=['POST'])
@admin_required
def allow_extra():
    """
    Logic to increase the violation limit.
    """
    data = request.get_json()
    participant_id = data.get('participant_id')
    contest_id = data.get('contest_id')
    amount = data.get('amount', 5)
    
    if not participant_id or not contest_id:
        return jsonify({'error': 'Missing required fields'}), 400
        
    db = get_db()
    try:
        res = db.table('participant_proctoring').select("*").eq("participant_id", participant_id).eq("contest_id", contest_id).execute()
        if not res.data:
            return jsonify({'error': 'No record found for participant'}), 404
            
        current = res.data[0]
        new_extra = (current.get('extra_violations') or 0) + amount
        
        update_data = {
            'extra_violations': new_extra,
            'is_disqualified': False,
            'disqualified_at': None,
            'disqualification_reason': None,
            'risk_level': 'high'
        }
        
        db.table('participant_proctoring').update(update_data).eq("participant_id", participant_id).eq("contest_id", contest_id).execute()
        
        try:
             log_entry = {
                 'contest_id': contest_id,
                 'participant_id': participant_id,
                 'alert_type': 'admin_action',
                 'severity': 'info',
                 'message': f'Admin allowed {amount} extra violations.',
                 'created_at': get_current_time()
             }
             db.table('proctoring_alerts').insert(log_entry).execute()
        except: pass

        return jsonify({'success': True, 'new_extra_violations': new_extra})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
