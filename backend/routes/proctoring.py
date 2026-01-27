
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

def update_participant_aggregates(participant_id, user_db_id, contest_id, violation_points, violation_col=None, level=1):
    """
    Update participant_proctoring table with strict category incrementing.
    Now accepts user_db_id as required int/string ID to avoid re-lookup failures.
    """
    db = get_db()
    
    # 1. Get Current State (Fresh Read)
    try:
        # Check if record exists
        res = db.table('participant_proctoring').select("*").eq("participant_id", participant_id).eq("contest_id", contest_id).execute()
        
        state = {}
        if not res.data:
            # Create fresh
            state = {
                'id': str(uuid.uuid4()),
                'user_id': user_db_id, # Ensure we link user_id if column exists
                'participant_id': participant_id,
                'contest_id': contest_id,
                'total_violations': 0,
                'violation_score': 0,
                'risk_level': 'low',
                'is_disqualified': False,
                'created_at': get_current_time(),
                'tab_switches': 0,
                'copy_attempts': 0,
                'screenshot_attempts': 0,
                'focus_losses': 0,
                'extra_violations': 0,
                'updated_at': get_current_time()
            }
            # Attempt insert
            try:
                db.table('participant_proctoring').insert(state).execute()
            except Exception as e:
                # Race condition handling: if insert fails, assume exists and re-read
                print(f"Insert race caught: {e}")
                res = db.table('participant_proctoring').select("*").eq("participant_id", participant_id).eq("contest_id", contest_id).execute()
                if res.data: state = res.data[0]
        else:
            state = res.data[0]

        # 2. Config
        config = get_config(contest_id)
        
        # 3. Calculate New Values
        # Note: We do "Read-Modify-Write". 
        current_total = int(state.get('total_violations') or 0)
        current_score = int(state.get('violation_score') or 0)
        
        new_total = current_total + 1
        new_score = current_score + violation_points
        
        # Update specific column text
        col_update = {}
        if violation_col:
             current_val = int(state.get(violation_col) or 0)
             col_update[violation_col] = current_val + 1
        
        # 4. Level-Wise Count (Robust Query)
        # Count existing violations in 'violations' table for this level + 1 (the current one)
        v_res = db.execute_query(
            "SELECT COUNT(*) as cnt FROM violations WHERE user_id=%s AND contest_id=%s AND level=%s", 
            (user_db_id, contest_id, level)
        )
        existing_level_count = v_res[0]['cnt'] if v_res else 0
        level_violations = existing_level_count + 1
        
        # 5. Risk & Disqualification Logic
        risk = calculate_risk_level(new_total)
        is_disqualified = bool(state.get('is_disqualified', False))
        disq_reason = state.get('disqualification_reason')
        disq_at = state.get('disqualified_at')
        
        extra = int(state.get('extra_violations') or 0)
        max_allowed = config.get('max_violations', 10) + extra
        
        # Auto-DQ Logic (Trigger only if not already DQ'd)
        if config.get('auto_disqualify') and level_violations > max_allowed and not is_disqualified:
            is_disqualified = True
            risk = 'critical'
            disq_reason = f'Auto: Exceeded max violations ({max_allowed}) for Level {level}'
            disq_at = get_current_time()
            
            # Emit Socket Event
            try:
                from extensions import socketio
                socketio.emit('proctoring:disqualified', {
                    'participant_id': participant_id,
                    'contest_id': contest_id,
                    'reason': disq_reason
                })
            except: pass

        # 6. Execute Update
        # Prepare payload
        update_payload = {
            'total_violations': new_total,
            'violation_score': new_score,
            'risk_level': risk,
            'is_disqualified': is_disqualified,
            'last_violation_at': get_current_time(),
            'updated_at': get_current_time()
        }
        if is_disqualified:
            update_payload['disqualification_reason'] = disq_reason
            update_payload['disqualified_at'] = disq_at
            
        # Merge column update
        update_payload.update(col_update)
        
        db.table('participant_proctoring').update(update_payload).eq("participant_id", participant_id).eq("contest_id", contest_id).execute()
        
        return {**state, **update_payload, 'level_violations': level_violations}
        
    except Exception as e:
        print(f"Error updating proctoring aggregates: {e}")
        return {} # Safe fallback

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
    Logic to receive a violation, check thresholds, update DB, and notify admin.
    """
    data = request.get_json()
    participant_id_input = data.get('participant_id') 
    contest_id = data.get('contest_id')
    violation_type = data.get('violation_type')
    
    if not all([participant_id_input, contest_id, violation_type]):
        return jsonify({'error': 'Missing required fields'}), 400
        
    db = get_db()
    
    try:
        # 1. Resolve User ID (Crucial step)
        user_id = None
        username = participant_id_input
        
        # Try finding by username first (exact match)
        u_res = db.execute_query("SELECT user_id, username FROM users WHERE username=%s", (username,))
        # If not, try by user_id string
        if not u_res:
             u_res = db.execute_query("SELECT user_id, username FROM users WHERE user_id=%s", (username,))
             
        if u_res:
             user_id = u_res[0]['user_id']
             username = u_res[0]['username'] # Normalize case
        else:
            return jsonify({'error': 'User not found'}), 404

        # 2. Check Config
        config = get_config(contest_id)
        if not config.get('enabled', True):
             return jsonify({'success': True, 'ignored': True})

        # 3. Map Violation to Weights and Columns
        weights = {
            'TAB_SWITCH': config.get('tab_switch_penalty', 1),
            'COPY_ATTEMPT': config.get('copy_paste_penalty', 2),
            'PASTE_ATTEMPT': config.get('copy_paste_penalty', 2),
            'CUT_ATTEMPT': config.get('copy_paste_penalty', 2),
            'SCREENSHOT_ATTEMPT': config.get('screenshot_penalty', 3),
            'FOCUS_LOST': config.get('focus_loss_penalty', 1),
            # Keys from frontend might vary
            'RIGHT_CLICK': 0 # Usually no penalty or low
        }
        
        # Normalize Input
        vt_norm = str(violation_type).upper().strip()
        points = weights.get(vt_norm, 1)
        
        # Column Mapping
        mapping_col = None
        if 'TAB' in vt_norm: mapping_col = 'tab_switches'
        elif any(x in vt_norm for x in ['COPY', 'PASTE', 'CUT']): mapping_col = 'copy_attempts'
        elif 'SCREEN' in vt_norm: mapping_col = 'screenshot_attempts'
        elif 'FOCUS' in vt_norm: mapping_col = 'focus_losses'
        
        # 4. Update Aggregates (Returns new state)
        current_level = data.get('level', 1) 
        try: current_level = int(current_level)
        except: current_level = 1

        updated_state = update_participant_aggregates(
            participant_id=username, 
            user_db_id=user_id,
            contest_id=contest_id, 
            violation_points=points, 
            violation_col=mapping_col, 
            level=current_level
        )
        
        # 5. Log Individual Violation
        violation_log = {
            'user_id': user_id,
            'contest_id': contest_id,
            'violation_type': vt_norm,
            'penalty_points': points,
            'description': data.get('description', f'Detected {vt_norm}'),
            'timestamp': get_current_time(),
            'round_id': data.get('round_id'), # Optional
            'level': current_level,
            'question_id': data.get('question_id'),
            'severity': updated_state.get('risk_level', 'low')
        }
        # Refine severity for the individual log
        if points >= 3: violation_log['severity'] = 'critical'
        elif points >= 2: violation_log['severity'] = 'medium'
        
        db.table('violations').insert(violation_log).execute()
        
        # 6. Real-time Alert
        try:
            from extensions import socketio
            socketio.emit('proctoring:violation', {
                'participant_id': username,
                'contest_id': contest_id,
                'violation_type': vt_norm,
                'total_violations': updated_state.get('total_violations', 0),
                'risk_level': updated_state.get('risk_level', 'low'),
                'is_disqualified': updated_state.get('is_disqualified', False)
            })
        except: pass

        return jsonify({
            'success': True,
            'total_violations': updated_state.get('total_violations', 0),
            'risk_level': updated_state.get('risk_level', 'low'),
            'is_disqualified': updated_state.get('is_disqualified', False)
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
        level_filter = request.args.get('level')
        
        query_base = """
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
        rows = db.execute_query(query_base, (contest_id,))
        
        # If level filter is active, we need to fetch VIOLATION COUNTS per user for this level
        level_counts = {}
        if level_filter and level_filter.lower() != 'all levels':
            try:
                l_int = int(level_filter.replace('Level ', '').strip())
                # Count violations in 'violations' table for this level
                v_res = db.execute_query(
                    "SELECT user_id, COUNT(*) as cnt FROM violations WHERE contest_id=%s AND level=%s GROUP BY user_id", 
                    (contest_id, l_int)
                )
                for v in v_res:
                    level_counts[v['user_id']] = v['cnt']
            except: pass
            
        risk_priority = {'critical': 5, 'high': 4, 'medium': 3, 'low': 1, None: 0}
        
        participants = []
        for r in rows:
            risk = r.get('risk_level', 'low')
            if r.get('is_disqualified'): risk = 'critical'
            
            # If filtering by level, replace total_violations with the level count
            disp_violations = r.get('total_violations', 0)
            if level_filter and level_filter.lower() != 'all levels':
                # Map via user_id (lookup ID first if needed, but rows are from users table so we have user_id?)
                # In query above: u.user_id is not selected? Wait, u.user_id is in join condition but not select list?
                # Ah, we need to ensure we have the ID to map.
                # Actually, the join `ON u.user_id` implies we have it. Let's rely on `participant_id` (username) if we don't have int ID.
                # But `violations` table uses `user_id` (INT). We need u.user_id in SELECT.
                # The SELECT above uses `u.username as participant_id`.
                # We need to fetch u.user_id. The query should be updated.
                pass 
                
            # Quick fix: Re-fetch correct user object or trust typical iteration
            # Let's clean this up by adding u.user_id to the query above in next iteration if needed.
            # But wait, I'm replacing the whole block. I can fix the query itself.
            
            pass 
        
        # CORRECTED BLOCK
        query = """
            SELECT 
                u.user_id,
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
        
        level_counts = {}
        if level_filter and level_filter.lower() != 'all levels':
            try:
                l_int = int(str(level_filter).replace('Level ', '').strip())
                v_res = db.execute_query(
                    "SELECT user_id, COUNT(*) as cnt FROM violations WHERE contest_id=%s AND level=%s GROUP BY user_id", 
                    (contest_id, l_int)
                )
                for v in v_res:
                    level_counts[v['user_id']] = v['cnt']
            except: pass

        participants = []
        for r in rows:
            risk = r.get('risk_level', 'low')
            if r.get('is_disqualified'): risk = 'critical'
            
            # Determine count to show
            eff_violations = r.get('total_violations', 0)
            if level_filter and level_filter.lower() != 'all levels':
                eff_violations = level_counts.get(r['user_id'], 0)
                
            p = {
                'participant_id': r['participant_id'],
                'name': r['full_name'],
                'risk_level': r.get('risk_level', 'low'),
                'total_violations': eff_violations,
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

@bp.route('/action/disqualify', methods=['POST'])
@admin_required
def disqualify_participant():
    """
    Manually disqualify a participant.
    """
    data = request.get_json()
    participant_id = data.get('participant_id')
    contest_id = data.get('contest_id')
    reason = data.get('reason', 'Manual Disqualification by Admin')
    
    if not participant_id or not contest_id:
        return jsonify({'error': 'Missing required fields'}), 400
        
    db = get_db()
    try:
        # Check if record exists
        res = db.table('participant_proctoring').select("*").eq("participant_id", participant_id).eq("contest_id", contest_id).execute()
        
        update_data = {
            'is_disqualified': True,
            'disqualification_reason': reason,
            'disqualified_at': get_current_time(),
            'risk_level': 'critical'
        }
        
        if res.data:
            db.table('participant_proctoring').update(update_data).eq("participant_id", participant_id).eq("contest_id", contest_id).execute()
        else:
            # Create if not exists
            update_data.update({
                'id': str(uuid.uuid4()),
                'participant_id': participant_id,
                'contest_id': contest_id,
                'total_violations': 0,
                'created_at': get_current_time(),
                'updated_at': get_current_time()
            })
            db.table('participant_proctoring').insert(update_data).execute()
            
        # Emit Socket Event
        try:
            from extensions import socketio
            socketio.emit('proctoring:disqualified', {
                'participant_id': participant_id,
                'contest_id': contest_id,
                'reason': reason
            })
        except: pass

        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/action/reset-violations', methods=['POST'])
@admin_required
def reset_violations():
    """
    Reset violations for a participant.
    """
    data = request.get_json()
    participant_id = data.get('participant_id')
    # If contest_id is missing, we might need it, but frontend code shows:
    # API.request('/proctoring/action/reset-violations', 'POST', { participant_id: participantId });
    # Admin State often knows activeContestId, but let's see if we can deduce or if we need to fix frontend.
    # Frontend passes ONLY participant_id in resetViolations() call in admin.js.
    # We should probably fix frontend to send contest_id, OR find the active contest here.
    # Let's try to assume active or find it via participant record if possible, 
    # BUT safe bet is to Require contest_id and update frontend in next step if needed. 
    # Actually, looking at admin.js:
    # async resetViolations(participantId) { ... API.request(..., { participant_id: participantId }) ... }
    # It misses contest_id. I will fix admin.js next.
    # For now, I'll write the backend to accept it.
    
    contest_id = data.get('contest_id')
    
    # If contest_id is missing, try to find the active PROCTORING contest for this user?
    # Or just return error.
    if not participant_id: 
         return jsonify({'error': 'Missing participant_id'}), 400

    db = get_db()
    try:
        # If contest_id not provided, try to update ALL active records for this user? Unsafe.
        # Let's assume we fix frontend.
        
        if not contest_id:
             # Try to resolve. 
             # SELECT contest_id FROM contests WHERE status='live' LIMIT 1
             c_res = db.execute_query("SELECT contest_id FROM contests WHERE status='live' LIMIT 1")
             if c_res: contest_id = c_res[0]['contest_id']
             else: return jsonify({'error': 'No live contest found and contest_id not provided'}), 400

        update_data = {
            'total_violations': 0,
            'violation_score': 0,
            'risk_level': 'low',
            'is_disqualified': False,
            'disqualification_reason': None,
            'tab_switches': 0,
            'copy_attempts': 0,
            'screenshot_attempts': 0,
            'focus_losses': 0,
            'extra_violations': 0,
            'updated_at': get_current_time()
        }
        
        db.table('participant_proctoring').update(update_data).eq("participant_id", participant_id).eq("contest_id", contest_id).execute()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/action/reset-progress', methods=['POST'])
@admin_required
def reset_progress():
    """
    Fully reset a participant's progress (Levels, Submissions) for a contest.
    Useful for debugging or re-runs.
    """
    data = request.get_json()
    participant_id = data.get('participant_id')
    contest_id = data.get('contest_id')
    
    if not participant_id:
        return jsonify({'error': 'Missing participant_id'}), 400

    db = get_db()
    try:
        # Resolve User ID Integer
        user_id = None
        u_res = db.execute_query("SELECT user_id FROM users WHERE username=%s OR user_id=%s", (participant_id, participant_id))
        if u_res: user_id = u_res[0]['user_id']
        else: return jsonify({'error': 'User not found'}), 404
        
        # If contest_id not provided, try live
        if not contest_id:
             c_res = db.execute_query("SELECT contest_id FROM contests WHERE status='live' LIMIT 1")
             if c_res: contest_id = c_res[0]['contest_id']
             else: return jsonify({'error': 'Contest not found'}), 400

        # Delete Stats
        db.execute_update("DELETE FROM participant_level_stats WHERE user_id=%s AND contest_id=%s", (user_id, contest_id))
        
        # Delete Submissions
        db.execute_update("DELETE FROM submissions WHERE user_id=%s AND contest_id=%s", (user_id, contest_id))
        
        # Also Reset Proctoring Violations? Yes, makes sense for a full reset.
        update_data = {
            'total_violations': 0,
            'violation_score': 0,
            'risk_level': 'low',
            'is_disqualified': False,
            'disqualification_reason': None,
            'tab_switches': 0,
            'copy_attempts': 0,
            'screenshot_attempts': 0,
            'focus_losses': 0,
            'extra_violations': 0,
            'updated_at': get_current_time()
        }
        db.table('participant_proctoring').update(update_data).eq("participant_id", participant_id).eq("contest_id", contest_id).execute()

        # Emit update
        try:
             from extensions import socketio
             socketio.emit('admin:stats_update', {'contest_id': contest_id})
        except: pass

        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
