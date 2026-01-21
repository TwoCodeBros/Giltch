"""
Proctoring Module API Routes
Handles all proctoring-related functionality including:
- Configuration management
- Violation tracking
- Participant monitoring
- Admin actions
- Real-time alerts
"""

from flask import Blueprint, jsonify, request
from utils.db import get_db
from auth_middleware import admin_required
import uuid
import datetime

bp = Blueprint('proctoring', __name__)

# ==================== PROCTORING CONFIGURATION ====================

@bp.route('/config/<contest_id>', methods=['GET'])
def get_proctoring_config(contest_id):
    """Get proctoring configuration for a contest"""
    db = get_db()
    
    try:
        # Try to get existing config from DB
        res = db.table('proctoring_config').select("*").eq("contest_id", contest_id).execute()
        config = res.data[0] if res.data else None
        
        if not config:
            # Create default config in DB
            config = create_default_config(contest_id)
            db.table('proctoring_config').insert(config).execute()
        
        return jsonify({'success': True, 'config': config})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/config/<contest_id>', methods=['PUT'])
@admin_required
def update_proctoring_config(contest_id):
    """Update proctoring configuration"""
    data = request.get_json()
    db = get_db()
    
    try:
        # Check if config exists
        res = db.table('proctoring_config').select("*").eq("contest_id", contest_id).execute()
        config = res.data[0] if res.data else None
        
        if config:
            db.table('proctoring_config').update(data).eq('contest_id', contest_id).execute()
        else:
            new_config = create_default_config(contest_id)
            new_config.update(data)
            db.table('proctoring_config').insert(new_config).execute()
            config = new_config
            
        # Log the configuration change
        log_proctoring_action(contest_id, None, 'config_updated', 'admin', {
            'changes': data
        })
        
        return jsonify({'success': True, 'config': config})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def create_default_config(contest_id):
    """Create default proctoring configuration"""
    return {
        'id': str(uuid.uuid4()),
        'contest_id': contest_id,
        'enabled': True,
        'max_violations': 10,
        'auto_disqualify': True,
        'warning_threshold': 5,
        'grace_violations': 2,
        'strict_mode': False,
        
        # Monitoring Settings
        'track_tab_switches': True,
        'track_focus_loss': True,
        'block_copy': True,
        'block_paste': True,
        'block_cut': True,
        'block_selection': False,
        'block_right_click': True,
        'detect_screenshot': True,
        
        # Violation Penalties
        'tab_switch_penalty': 1,
        'copy_paste_penalty': 2,
        'screenshot_penalty': 3,
        'focus_loss_penalty': 1,
        
        'created_at': datetime.datetime.utcnow().isoformat(),
        'updated_at': datetime.datetime.utcnow().isoformat()
    }

# ==================== HELPERS ====================

def get_config_for_contest(contest_id):
    """Helper to get config object"""
    db = get_db()
    res = db.table('proctoring_config').select("*").eq("contest_id", contest_id).execute()
    return res.data[0] if res.data else create_default_config(contest_id)

def get_participant_proctoring_status(participant_id):
    db = get_db()
    res = db.table('participant_proctoring').select("*").eq("participant_id", participant_id).execute()
    return res.data[0] if res.data else {'total_violations': 0, 'risk_level': 'low'}

def update_participant_proctoring_status(participant_id, contest_id, violation_type, points, config):
    db = get_db()
    res = db.table('participant_proctoring').select("*").eq("participant_id", participant_id).execute()
    status = res.data[0] if res.data else None
    
    if not status:
        status = {
            'participant_id': participant_id,
            'contest_id': contest_id,
            'total_violations': 0,
            'violation_score': 0,
            'risk_level': 'low',
            'tab_switches': 0,
            'focus_losses': 0,
            'copy_attempts': 0,
            'screenshot_attempts': 0
        }
    
    # Update Stats
    status['total_violations'] = status.get('total_violations', 0) + 1
    status['violation_score'] = status.get('violation_score', 0) + points
    
    if violation_type == 'TAB_SWITCH': status['tab_switches'] = status.get('tab_switches', 0) + 1
    if violation_type == 'FOCUS_LOST': status['focus_losses'] = status.get('focus_losses', 0) + 1
    if violation_type == 'COPY_ATTEMPT': status['copy_attempts'] = status.get('copy_attempts', 0) + 1
    if violation_type == 'SCREENSHOT_ATTEMPT': status['screenshot_attempts'] = status.get('screenshot_attempts', 0) + 1
    
    # Calculate Risk
    score = status['violation_score']
    if score >= config.get('max_violations', 10) or status['total_violations'] >= config.get('max_violations', 10):
        status['risk_level'] = 'critical'
        if config.get('auto_disqualify'):
            status['is_disqualified'] = True
            status['disqualification_reason'] = 'Auto: Max violations exceeded'
    elif score >= config.get('warning_threshold', 5):
        status['risk_level'] = 'high'
    elif score >= config.get('grace_violations', 2):
        status['risk_level'] = 'medium'
        
    # Save
    if res.data:
        db.table('participant_proctoring').update(status).eq("participant_id", participant_id).execute()
    else:
        # Need user_id for table if possible
        u_res = db.execute_query("SELECT user_id FROM users WHERE username=%s", (participant_id,))
        if u_res: status['user_id'] = u_res[0]['user_id']
        db.table('participant_proctoring').insert(status).execute()


# ==================== VIOLATION TRACKING ====================

@bp.route('/violation', methods=['POST'])
def report_violation():
    """Report a proctoring violation (called by participant frontend)"""
    data = request.get_json()
    db = get_db()
    
    participant_id_input = data.get('participant_id') # This is username/PID
    contest_id = data.get('contest_id')
    violation_type = data.get('violation_type')
    level = data.get('level')
    
    if not all([participant_id_input, contest_id, violation_type]):
        return jsonify({'error': 'Missing required fields'}), 400

    # User ID Lookup
    participant_id = participant_id_input
    if isinstance(participant_id_input, str) and not participant_id_input.isdigit():
        res = db.execute_query("SELECT user_id FROM users WHERE username=%s", (participant_id_input,))
        if res: participant_id = res[0]['user_id']

    
    try:
        # Get proctoring config
        config = get_config_for_contest(contest_id)
        
        if not config or not config.get('enabled'):
            return jsonify({'success': True, 'message': 'Proctoring disabled'})
        
        penalty_map = {
            'TAB_SWITCH': config.get('tab_switch_penalty', 1),
            'FOCUS_LOST': config.get('focus_loss_penalty', 1),
            'COPY_ATTEMPT': config.get('copy_paste_penalty', 2),
            'PASTE_ATTEMPT': config.get('copy_paste_penalty', 2),
            'CUT_ATTEMPT': config.get('copy_paste_penalty', 2),
            'SCREENSHOT_ATTEMPT': config.get('screenshot_penalty', 3),
            'RIGHT_CLICK': 1,
            'DEVTOOLS_ATTEMPT': 1,
            'KEY_LOCK_ATTEMPT': 1,
            'FULLSCREEN_EXIT': 1,
            'ESC_ATTEMPT': 1
        }
        
        penalty_points = penalty_map.get(violation_type, 1)
        severity = 'low'
        if penalty_points >= 3: severity = 'critical'
        elif penalty_points >= 2: severity = 'high'
        elif penalty_points >= 1: severity = 'medium'
        
        # Update Level Persistent Stats
        new_level_count = 0 # Default if no level or not found
        if level:
            # Check if row exists for participant, contest, level
            res = db.table('participant_level_stats').select("violation_count").eq("user_id", participant_id).eq("contest_id", contest_id).eq("level", level).execute()
            level_stat = res.data[0] if res.data else None

            if level_stat:
                # Increment existing count
                db.table('participant_level_stats').update({'violation_count': level_stat['violation_count'] + 1}).eq("user_id", participant_id).eq("contest_id", contest_id).eq("level", level).execute()
                new_level_count = level_stat['violation_count'] + 1
            else:
                # Insert new row
                db.table('participant_level_stats').insert({
                    'user_id': participant_id,
                    'contest_id': contest_id,
                    'level': level,
                    'violation_count': 1
                }).execute()
                new_level_count = 1
        
        # Save violation to DB
        violation = {
            'user_id': participant_id, # Mapping PID to user_id in violations
            'contest_id': contest_id,
            'round_id': data.get('round_id'),
            'violation_type': violation_type,
            'severity': severity,
            'penalty_points': penalty_points,
            'question_id': data.get('question_id'),
            'level': level,
            'description': f"Detected {violation_type} violation",
            'timestamp': datetime.datetime.utcnow().isoformat()
        }
        db.table('violations').insert(violation).execute()
        
        # Update participant status in DB (Global Stats)
        update_participant_proctoring_status(participant_id, contest_id, violation_type, penalty_points, config)
        
        # Get updated status
        participant_status = get_participant_proctoring_status(participant_id)
        
        response = {
            'success': True,
            'total_violations': participant_status.get('total_violations', 0),
            'violation_score': participant_status.get('violation_score', 0),
            'risk_level': participant_status.get('risk_level', 'low'),
            'is_disqualified': bool(participant_status.get('is_disqualified', False))
        }
        
        # Emit real-time event
        try:
            from extensions import socketio
            socketio.emit('proctoring:violation', {
                'participant_id': participant_id,
                'contest_id': contest_id,
                'violation_type': violation_type,
                'total_violations': response['total_violations'],
                'risk_level': response['risk_level'],
                'is_disqualified': response['is_disqualified']
            })
            
            if response['is_disqualified']:
                socketio.emit('proctoring:disqualified', {
                    'participant_id': participant_id,
                    'contest_id': contest_id,
                    'reason': 'Auto-disqualified: Violation limit exceeded'
                })
        except: pass
        
        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@bp.route('/violations/<contest_id>', methods=['GET'])
@admin_required
def get_violations(contest_id):
    """Get all violations for a contest"""
    db = get_db()
    
    try:
        res = db.table('violations').select("*").eq("contest_id", contest_id).execute()
        violations = res.data or []
        # Sort by timestamp descending
        violations.sort(key=lambda x: str(x.get('timestamp', '')), reverse=True)
        
        return jsonify({'success': True, 'violations': violations})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/violations/participant/<participant_id>', methods=['GET'])
@admin_required
def get_participant_violations(participant_id):
    """Get violations for a specific participant"""
    db = get_db()
    
    try:
        if hasattr(db, 'data') and 'violations' in db.data:
            violations = [v for v in db.data['violations'] if v['participant_id'] == participant_id]
            violations.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            return jsonify({'success': True, 'violations': violations})
        
        return jsonify({'success': True, 'violations': []})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== PARTICIPANT MONITORING ====================

@bp.route('/status/<contest_id>', methods=['GET'])
@admin_required
def get_all_participant_status(contest_id):
    """Get proctoring status for all participants in a contest.
       Ensures cumulative violations are shown regardless of level filter.
    """
    db = get_db()
    
    try:
        # 1. Get ALL Participants from Users table
        users_res = db.table('users').select("*").eq("role", "participant").execute()
        participants = users_res.data or []
        
        # 2. Get Global Proctoring Records (Source of Truth for Counts)
        proc_res = db.table('participant_proctoring').select("*").eq("contest_id", contest_id).execute()
        proc_map = {str(p.get('participant_id')): p for p in proc_res.data} if proc_res.data else {}
        
        # 3. Merge Data
        final_statuses = []
        for p in participants:
            # Match by username (participant_id in proctoring table is username)
            pid = p.get('username') 
            
            # Get existing record or create default view
            record = proc_map.get(str(pid))
            
            if not record:
                # No record yet? Should have been created on login, but handle grace case
                record = {
                    'participant_id': pid,
                    'contest_id': contest_id,
                    'total_violations': 0,
                    'violation_score': 0,
                    'risk_level': 'low'
                }

            # Map to response format
            status_obj = {
                'participant_id': pid,
                'participant_name': p.get('full_name', 'Unknown'),
                'total_violations': record.get('total_violations', 0),
                'violation_score': record.get('violation_score', 0),
                'risk_level': record.get('risk_level', 'low'),
                'is_disqualified': record.get('is_disqualified', False),
                'is_suspended': record.get('is_suspended', False),
                'tab_switches': record.get('tab_switches', 0),
                'copy_attempts': record.get('copy_attempts', 0),
                'screenshot_attempts': record.get('screenshot_attempts', 0),
                'focus_losses': record.get('focus_losses', 0)
            }
            
            final_statuses.append(status_obj)

        # 4. Sort (Disqualified > Critical > High > Medium > Low > Violation Score)
        risk_rank = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
        
        def sort_key(s):
            # DQ is highest priority
            if s['is_disqualified']: return (10, s['total_violations'])
            return (risk_rank.get(s['risk_level'], 0), s['total_violations'])
            
        final_statuses.sort(key=sort_key, reverse=True)
        
        return jsonify({'success': True, 'statuses': final_statuses})

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@bp.route('/status/participant/<participant_id>', methods=['GET'])
def get_participant_status(participant_id):
    """Get proctoring status for a specific participant"""
    try:
        status = get_participant_proctoring_status(participant_id)
        return jsonify({'success': True, 'status': status})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ADMIN ACTIONS ====================

@bp.route('/action/disqualify', methods=['POST'])
@admin_required
def manual_disqualify():
    """Manually disqualify a participant"""
    data = request.get_json()
    participant_id = data.get('participant_id')
    contest_id = data.get('contest_id')
    reason = data.get('reason', 'Manual disqualification by admin')
    
    if not participant_id or not contest_id:
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        db = get_db()
        
        # Update participant status
        if hasattr(db, 'data'):
            if 'participants' in db.data:
                for p in db.data['participants']:
                    if p.get('participant_id') == participant_id or p.get('id') == participant_id:
                        p['status'] = 'disqualified'
                        break
            
            # Update proctoring status
            if 'participant_proctoring' not in db.data:
                db.data['participant_proctoring'] = []
            
            status = next((s for s in db.data['participant_proctoring'] 
                          if s['participant_id'] == participant_id), None)
            
            if status:
                status['is_disqualified'] = True
                status['disqualified_at'] = datetime.datetime.utcnow().isoformat()
                status['disqualification_reason'] = reason
                status['risk_level'] = 'critical'
            else:
                # Create new status
                status = {
                    'id': str(uuid.uuid4()),
                    'participant_id': participant_id,
                    'contest_id': contest_id,
                    'is_disqualified': True,
                    'disqualified_at': datetime.datetime.utcnow().isoformat(),
                    'disqualification_reason': reason,
                    'risk_level': 'critical',
                    'total_violations': 0,
                    'violation_score': 0,
                    'created_at': datetime.datetime.utcnow().isoformat()
                }
                db.data['participant_proctoring'].append(status)
            
            # Log action
            log_proctoring_action(contest_id, participant_id, 'manual_disqualification', 'admin', {
                'reason': reason
            })
            
            # Emit real-time event
            try:
                from extensions import socketio
                socketio.emit('proctoring:disqualified', {
                    'participant_id': participant_id,
                    'contest_id': contest_id,
                    'reason': reason
                })
            except:
                pass
            
            return jsonify({'success': True, 'status': status})
        
        return jsonify({'error': 'Database error'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/action/reset-violations', methods=['POST'])
@admin_required
def reset_violations():
    """Reset violations for a participant"""
    data = request.get_json()
    participant_id = data.get('participant_id')
    
    if not participant_id:
        return jsonify({'error': 'Missing participant_id'}), 400
    
    try:
        db = get_db()
        
        if hasattr(db, 'data'):
            # Reset proctoring status
            if 'participant_proctoring' in db.data:
                for status in db.data['participant_proctoring']:
                    if status['participant_id'] == participant_id:
                        status['total_violations'] = 0
                        status['violation_score'] = 0
                        status['risk_level'] = 'low'
                        status['tab_switches'] = 0
                        status['focus_losses'] = 0
                        status['copy_attempts'] = 0
                        status['paste_attempts'] = 0
                        status['screenshot_attempts'] = 0
                        status['last_violation_at'] = None
                        status['updated_at'] = datetime.datetime.utcnow().isoformat()
                        break
            
            # Log action
            log_proctoring_action(None, participant_id, 'violations_reset', 'admin', {})
            
            return jsonify({'success': True, 'message': 'Violations reset successfully'})
        
        return jsonify({'error': 'Database error'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/action/suspend', methods=['POST'])
@admin_required
def suspend_participant():
    """Temporarily suspend a participant"""
    data = request.get_json()
    participant_id = data.get('participant_id')
    contest_id = data.get('contest_id')
    reason = data.get('reason', 'Suspended by admin')
    
    if not participant_id or not contest_id:
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        db = get_db()
        
        if hasattr(db, 'data'):
            if 'participant_proctoring' not in db.data:
                db.data['participant_proctoring'] = []
            
            status = next((s for s in db.data['participant_proctoring'] 
                          if s['participant_id'] == participant_id), None)
            
            if status:
                status['is_suspended'] = True
                status['suspended_at'] = datetime.datetime.utcnow().isoformat()
                status['suspension_reason'] = reason
            
            # Log action
            log_proctoring_action(contest_id, participant_id, 'suspended', 'admin', {
                'reason': reason
            })
            
            return jsonify({'success': True, 'status': status})
        
        return jsonify({'error': 'Database error'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/action/reinstate', methods=['POST'])
@admin_required
def reinstate_participant():
    """Reinstate a suspended participant"""
    data = request.get_json()
    participant_id = data.get('participant_id')
    contest_id = data.get('contest_id')
    
    if not participant_id:
        return jsonify({'error': 'Missing participant_id'}), 400
    
    try:
        db = get_db()
        
        if hasattr(db, 'data'):
            # Update participant status
            if 'participants' in db.data:
                for p in db.data['participants']:
                    if p.get('participant_id') == participant_id or p.get('id') == participant_id:
                        if p.get('status') == 'disqualified':
                            p['status'] = 'active'
                        break
            
            # Update proctoring status
            if 'participant_proctoring' in db.data:
                for status in db.data['participant_proctoring']:
                    if status['participant_id'] == participant_id:
                        status['is_suspended'] = False
                        status['is_disqualified'] = False
                        status['suspended_at'] = None
                        status['disqualified_at'] = None
                        status['suspension_reason'] = None
                        status['disqualification_reason'] = None
                        if status['risk_level'] == 'critical':
                            status['risk_level'] = 'high'
                        break
            
            # Log action
            log_proctoring_action(contest_id, participant_id, 'reinstated', 'admin', {})
            
            return jsonify({'success': True, 'message': 'Participant reinstated'})
        
        return jsonify({'error': 'Database error'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/action/allow-extra', methods=['POST'])
@admin_required
def allow_extra_violations():
    """Allow participant extra violations and reinstate them"""
    data = request.get_json()
    participant_id = data.get('participant_id')
    contest_id = data.get('contest_id')
    extra_amount = data.get('amount', 5)
    
    if not participant_id:
        return jsonify({'error': 'Missing participant_id'}), 400
    
    try:
        db = get_db()
        
        # 1. Update User Status in Users Table
        # Update status to active if it was disqualified
        db.table('users').update({'status': 'active'}).eq('username', participant_id).execute()
        
        # 2. Update Proctoring Status
        # Get current status to verify existence
        res = db.table('participant_proctoring').select("*").eq("participant_id", participant_id).execute()
        
        if res.data:
            current_status = res.data[0]
            current_extra = current_status.get('extra_violations', 0)
            if current_extra is None: current_extra = 0
            
            new_extra = current_extra + extra_amount
            
            update_data = {
                'extra_violations': new_extra,
                'is_disqualified': False,
                'is_suspended': False,
                'disqualified_at': None,
                'disqualification_reason': None,
                'risk_level': 'high' # Reinstated users are high risk but not critical/blocked
            }
            
            db.table('participant_proctoring').update(update_data).eq('participant_id', participant_id).execute()
            
            # Log action
            log_proctoring_action(contest_id, participant_id, 'allowed_extra_violations', 'admin', {
                'amount': extra_amount,
                'total_extra': new_extra
            })
            
            # Emit Socket Event
            try:
                from extensions import socketio
                socketio.emit('proctoring:allow_extra', {
                    'participant_id': participant_id,
                    'contest_id': contest_id,
                    'extra_added': extra_amount,
                    'message': f'You have been allowed {extra_amount} extra violations. Be careful!'
                })
            except: pass
            
            return jsonify({'success': True, 'message': f'Allowed {extra_amount} extra violations', 'new_extra': new_extra})
        else:
            return jsonify({'error': 'Participant proctoring record not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== STATISTICS & REPORTS ====================

@bp.route('/stats/<contest_id>', methods=['GET'])
@admin_required
def get_proctoring_stats(contest_id):
    """Get proctoring statistics for a contest"""
    db = get_db()
    
    try:
        stats = {
            'total_violations': 0,
            'active_risky_participants': 0,
            'auto_disqualifications': 0,
            'manual_disqualifications': 0,
            'violation_breakdown': {},
            'severity_breakdown': {'low': 0, 'medium': 0, 'high': 0, 'critical': 0},
            'top_violators': []
        }
        
        if hasattr(db, 'data'):
            # Count violations
            if 'violations' in db.data:
                contest_violations = [v for v in db.data['violations'] if v['contest_id'] == contest_id]
                stats['total_violations'] = len(contest_violations)
                
                # Breakdown by type
                for v in contest_violations:
                    v_type = v.get('violation_type', 'unknown')
                    stats['violation_breakdown'][v_type] = stats['violation_breakdown'].get(v_type, 0) + 1
                    
                    severity = v.get('severity', 'medium')
                    stats['severity_breakdown'][severity] += 1
            
            # Count risky participants and disqualifications
            if 'participant_proctoring' in db.data:
                contest_statuses = [s for s in db.data['participant_proctoring'] 
                                   if s['contest_id'] == contest_id]
                
                for status in contest_statuses:
                    if status.get('risk_level') in ['high', 'critical']:
                        stats['active_risky_participants'] += 1
                    
                    if status.get('is_disqualified'):
                        if status.get('disqualification_reason', '').startswith('Auto'):
                            stats['auto_disqualifications'] += 1
                        else:
                            stats['manual_disqualifications'] += 1
                
                # Top violators
                top = sorted(contest_statuses, 
                           key=lambda x: x.get('violation_score', 0), 
                           reverse=True)[:10]
                
                # Enrich with participant names
                if 'participants' in db.data:
                    for status in top:
                        participant = next((p for p in db.data['participants'] 
                                          if p.get('id') == status['participant_id'] or 
                                             p.get('participant_id') == status['participant_id']), None)
                        if participant:
                            stats['top_violators'].append({
                                'participant_id': status['participant_id'],
                                'name': participant.get('name', 'Unknown'),
                                'total_violations': status.get('total_violations', 0),
                                'violation_score': status.get('violation_score', 0),
                                'risk_level': status.get('risk_level', 'low')
                            })
        
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/export/<contest_id>', methods=['GET'])
@admin_required
def export_violations(contest_id):
    """Export violation report for a contest as Excel"""
    db = get_db()
    
    try:
        from openpyxl import Workbook
        from io import BytesIO
        from flask import send_file
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Proctoring Report"
        
        # Headers
        ws.append(['Participant ID', 'Name', 'Level', 'Status', 'Risk Level', 'Violations', 'Tab Switches', 'Copy Attempts', 'Screenshots', 'Score'])
        
        # Fetch Data
        query = """
            SELECT 
                u.user_id, u.username, u.full_name,
                pp.risk_level, pp.total_violations, pp.tab_switches, pp.copy_attempts, pp.screenshot_attempts, pp.is_disqualified, pp.is_suspended,
                pls.level, pls.level_score
            FROM users u
            LEFT JOIN participant_proctoring pp ON u.user_id = pp.user_id AND pp.contest_id = %s
            LEFT JOIN participant_level_stats pls ON u.user_id = pls.user_id AND pls.contest_id = %s
            WHERE u.role = 'participant'
        """
        # Note: Left Join might result in multiple rows per user if multiple level stats? 
        # Actually pls has (user_id, contest_id, level). We might want the MAX level or list each.
        # User requirement: "Level". Probably current/latest level.
        # Let's group by user and take max level.
        
        # Improved query to get latest level
        query = """
            SELECT 
                u.username, u.full_name,
                pp.risk_level, pp.total_violations, pp.tab_switches, pp.copy_attempts, pp.screenshot_attempts, pp.is_disqualified, pp.is_suspended,
                (SELECT MAX(level) FROM participant_level_stats WHERE user_id=u.user_id AND contest_id=%s) as current_level,
                (SELECT SUM(level_score) FROM participant_level_stats WHERE user_id=u.user_id AND contest_id=%s) as total_score
            FROM users u
            LEFT JOIN participant_proctoring pp ON u.user_id = pp.user_id AND pp.contest_id = %s
            WHERE u.role = 'participant'
        """
        
        res = db.execute_query(query, (contest_id, contest_id, contest_id))
        
        for row in res:
            status = 'Active'
            if row.get('is_disqualified'): status = 'Disqualified'
            elif row.get('is_suspended'): status = 'Suspended'
            
            ws.append([
                row.get('username'),
                row.get('full_name'),
                row.get('current_level', 1),
                status,
                row.get('risk_level', 'low'),
                row.get('total_violations', 0) or 0,
                row.get('tab_switches', 0) or 0,
                row.get('copy_attempts', 0) or 0,
                row.get('screenshot_attempts', 0) or 0,
                row.get('total_score', 0) or 0
            ])
            
        out = BytesIO()
        wb.save(out)
        out.seek(0)
        
        return send_file(
            out,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'proctoring_report_{contest_id}_{datetime.datetime.now().strftime("%Y%m%d%H%M")}.xlsx'
        )

    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


# ==================== HELPER FUNCTIONS ====================

def get_config_for_contest(contest_id):
    """Get proctoring config for a contest"""
    db = get_db()
    res = db.table('proctoring_config').select("*").eq("contest_id", contest_id).execute()
    return res.data[0] if res.data else None

def get_participant_proctoring_status(participant_id):
    """Get or create proctoring status for a participant"""
    db = get_db()
    # In mapping: participant_id is the username/string.
    res = db.table('participant_proctoring').select("*").eq("participant_id", participant_id).execute()
    return res.data[0] if res.data else {}

def update_participant_proctoring_status(participant_id, contest_id, violation_type, penalty_points, config):
    """Update participant proctoring status after a violation"""
    db = get_db()
    
    # In mapping, MySQLBridge will handle username -> participant_id if we filtered by it
    res = db.table('participant_proctoring').select("*").eq("participant_id", participant_id).execute()
    status = res.data[0] if res.data else None
    
    if not status:
        status = {
            'participant_id': participant_id,
            'contest_id': contest_id,
            'total_violations': 1,
            'violation_score': penalty_points,
            'risk_level': 'low',
            'is_disqualified': False,
            'is_suspended': False,
            'tab_switches': 1 if violation_type == 'tab_switch' else 0,
            'focus_losses': 1 if violation_type == 'focus_loss' else 0,
            'copy_attempts': 1 if violation_type in ['copy', 'paste', 'cut'] else 0,
            'screenshot_attempts': 1 if violation_type == 'screenshot' else 0
        }
        db.table('participant_proctoring').insert(status).execute()
    else:
        # Update counts
        update_data = {
            'total_violations': status['total_violations'] + 1,
            'violation_score': status['violation_score'] + penalty_points,
            'last_violation_at': datetime.datetime.utcnow().isoformat()
        }
        
        # Update specific counters
        if violation_type == 'tab_switch': update_data['tab_switches'] = status.get('tab_switches', 0) + 1
        elif violation_type == 'focus_loss': update_data['focus_losses'] = status.get('focus_losses', 0) + 1
        elif violation_type in ['copy', 'paste', 'cut']: update_data['copy_attempts'] = status.get('copy_attempts', 0) + 1
        elif violation_type == 'screenshot': update_data['screenshot_attempts'] = status.get('screenshot_attempts', 0) + 1
        
        # Risk level logic
        new_total = update_data['total_violations']
        grace = config.get('grace_violations', 2)
        warning_t = config.get('warning_threshold', 5)
        
        # Calculate Max Violations including Extra Allowance
        base_max = config.get('max_violations', 10)
        extra_allowed = status.get('extra_violations', 0) 
        # Note: status might be stale if we just inserted, but here we are in 'else' block
        # However, status from DB might not have 'extra_violations' if we used a mock DB or if key is missing.
        # But we added the column.
        if extra_allowed is None: extra_allowed = 0
        
        effective_max = base_max + extra_allowed
        
        if new_total > effective_max: update_data['risk_level'] = 'critical'
        elif new_total > warning_t: update_data['risk_level'] = 'high'
        elif new_total > grace: update_data['risk_level'] = 'medium'
        else: update_data['risk_level'] = 'low'
        
        # Auto-disqualify
        if config.get('auto_disqualify') and new_total > effective_max:
             update_data['is_disqualified'] = True
             update_data['disqualification_reason'] = 'Exceeded maximum violations'
             update_data['disqualified_at'] = datetime.datetime.utcnow().isoformat()
             
        db.table('participant_proctoring').update(update_data).eq('participant_id', participant_id).execute()
        return db.table('participant_proctoring').select("*").eq("participant_id", participant_id).execute().data[0]



def create_proctoring_alert(contest_id, participant_id, alert_type, severity, message):
    """Create a proctoring alert"""
    db = get_db()
    alert = {
        'contest_id': contest_id,
        'participant_id': participant_id,
        'alert_type': alert_type,
        'severity': severity,
        'message': message,
        'is_read': False
    }
    db.table('proctoring_alerts').insert(alert).execute()
    try:
        from extensions import socketio
        socketio.emit('proctoring:alert', alert)
    except: pass

def log_proctoring_action(contest_id, participant_id, action_type, action_by, details):
    """Log proctoring action (using alerts table for simplicity in this bridge)"""
    create_proctoring_alert(contest_id, participant_id, action_type, 'info', str(details))

# ==================== ALERTS ====================

@bp.route('/alerts/<contest_id>', methods=['GET'])
@admin_required
def get_alerts(contest_id):
    """Get proctoring alerts for a contest"""
    db = get_db()
    try:
        res = db.table('proctoring_alerts').select("*").eq("contest_id", contest_id).execute()
        alerts = res.data or []
        alerts.sort(key=lambda x: str(x.get('created_at', '')), reverse=True)
        return jsonify({'success': True, 'alerts': alerts})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/alerts/<alert_id>/read', methods=['POST'])
@admin_required
def mark_alert_read(alert_id):
    """Mark an alert as read"""
    db = get_db()
    try:
        db.table('proctoring_alerts').update({'is_read': True, 'read_at': datetime.datetime.utcnow().isoformat()}).eq('id', alert_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== EXPORT ====================

@bp.route('/export/<contest_id>', methods=['GET'])
def export_proctoring_report(contest_id):
    """Export proctoring report as CSV"""
    import io
    import csv
    from flask import Response, stream_with_context

    db = get_db()
    
    level = request.args.get('level')
    
    # Check Token if passed (Loose validation)
    token = request.args.get('token')

    if level:
        # LEVEL SPECIFIC EXPORT
        query = """
            SELECT 
                u.full_name, u.username,
                COUNT(v.violation_id) as total_violations,
                SUM(v.penalty_points) as violation_score,
                SUM(CASE WHEN v.violation_type='tab_switch' THEN 1 ELSE 0 END) as tab_switches,
                SUM(CASE WHEN v.violation_type IN ('copy', 'paste', 'cut') THEN 1 ELSE 0 END) as copy_attempts,
                SUM(CASE WHEN v.violation_type='focus_loss' THEN 1 ELSE 0 END) as focus_losses,
                SUM(CASE WHEN v.violation_type='screenshot' THEN 1 ELSE 0 END) as screenshot_attempts,
                pp.risk_level, pp.is_disqualified, pp.disqualification_reason
            FROM users u
            LEFT JOIN violations v ON u.user_id = v.user_id AND v.contest_id = %s AND v.level = %s
            LEFT JOIN participant_proctoring pp ON u.user_id = pp.user_id AND pp.contest_id = %s
            WHERE u.role = 'participant'
            GROUP BY u.user_id, u.full_name, u.username, pp.risk_level, pp.is_disqualified, pp.disqualification_reason
            ORDER BY total_violations DESC, u.full_name ASC
        """
        res = db.execute_query(query, (contest_id, level, contest_id))
    else:
        # GLOBAL EXPORT
        query = """
            SELECT 
                u.full_name, u.username,
                COALESCE(pp.total_violations, 0) as total_violations, 
                COALESCE(pp.violation_score, 0) as violation_score, 
                COALESCE(pp.risk_level, 'low') as risk_level, 
                COALESCE(pp.is_disqualified, 0) as is_disqualified, 
                COALESCE(pp.tab_switches, 0) as tab_switches, 
                COALESCE(pp.focus_losses, 0) as focus_losses, 
                COALESCE(pp.copy_attempts, 0) as copy_attempts, 
                COALESCE(pp.screenshot_attempts, 0) as screenshot_attempts,
                pp.disqualification_reason
            FROM users u
            LEFT JOIN participant_proctoring pp ON u.user_id = pp.user_id AND pp.contest_id = %s
            WHERE u.role = 'participant'
            ORDER BY total_violations DESC, u.full_name ASC
        """
        res = db.execute_query(query, (contest_id,))
    
    # Generate CSV Stream
    def generate():
        data = io.StringIO()
        w = csv.writer(data)
        
        # Write BOM for Excel UTF-8 compatibility
        yield '\ufeff'
        
        # Header
        base_header = ['Full Name', 'Participant ID', 'Total Violations', 'Score', 'Risk Level', 'Disqualified', 'Reason', 'Tab Switches', 'Focus Losses', 'Copy Attempts', 'Screenshots']
        if level:
            base_header.insert(2, 'Level')
            
        w.writerow(base_header)
        yield data.getvalue()
        data.seek(0)
        data.truncate(0)
        
        if res:
            for r in res:
                row = [
                    r.get('full_name', 'Unknown'),
                    r.get('username', 'Unknown'), 
                    r.get('total_violations', 0),
                    r.get('violation_score', 0),
                    r.get('risk_level', 'low'),
                    'YES' if r.get('is_disqualified') else 'NO',
                    r.get('disqualification_reason', '') if r.get('is_disqualified') else '',
                    r.get('tab_switches', 0),
                    r.get('focus_losses', 0),
                    r.get('copy_attempts', 0),
                    r.get('screenshot_attempts', 0)
                ]
                if level:
                    row.insert(2, level)
                    
                w.writerow(row)
                yield data.getvalue()
                data.seek(0)
                data.truncate(0)

    filename = f'proctoring_report_{contest_id}_level_{level}.csv' if level else f'proctoring_report_{contest_id}_global.csv'
    headers = {
        'Content-Disposition': f'attachment; filename={filename}',
        'Content-Type': 'text/csv; charset=utf-8'
    }
    return Response(stream_with_context(generate()), headers=headers)
