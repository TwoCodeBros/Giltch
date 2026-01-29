
import logging
import json
from datetime import datetime, timedelta
from db_connection import db_manager

logger = logging.getLogger(__name__)

def create_question_logic(contest_id, round_number, data):
    """
    Core logic to create a question.
    """
    try:
        r_query = "SELECT round_id, allowed_language FROM rounds WHERE contest_id=%s AND round_number=%s"
        r_res = db_manager.execute_query(r_query, (contest_id, round_number))
        
        if not r_res:
             raise ValueError(f"Round {round_number} for Contest {contest_id} not found.")
             
        round_id = r_res[0]['round_id']
        title = data.get('title')

        # Duplicate Check
        dup_check = db_manager.execute_query("SELECT question_id FROM questions WHERE round_id=%s AND question_title=%s", (round_id, title))
        if dup_check:
            raise ValueError(f"Question '{title}' already exists in Level {round_number}.")
        
        q_query = """
            INSERT INTO questions 
            (round_id, question_number, question_title, question_description, expected_output, buggy_code, difficulty_level, points, test_cases, test_input)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        points = data.get('points', 20)
        test_cases = json.dumps(data.get('test_cases', []))
        difficulty = data.get('difficulty', 'Level 1')
        
        allowed_lang = r_res[0].get('allowed_language') or data.get('language', 'python')
        time_limit = data.get('time_limit')
        
        if time_limit and int(time_limit) > 0:
            db_manager.execute_update(
                "UPDATE rounds SET time_limit_minutes=%s WHERE round_id=%s",
                (int(time_limit), round_id)
            )
        
        count_query = "SELECT MAX(question_number) as max_num FROM questions WHERE round_id=%s"
        count_res = db_manager.execute_query(count_query, (round_id,))
        next_num = (count_res[0]['max_num'] or 0) + 1
        
        boilerplate_raw = data.get('boilerplate', {})
        if isinstance(boilerplate_raw, dict):
            boilerplate = boilerplate_raw.get(allowed_lang, '') or boilerplate_raw.get('python', '')
        else:
            boilerplate = str(boilerplate_raw)
        
        res = db_manager.execute_update(q_query, (
            round_id, next_num, 
            title, 
            data.get('description', ''), 
            data.get('expected_output'),
            boilerplate, 
            difficulty, 
            points, 
            test_cases,
            data.get('test_input') or data.get('input') or data.get('expected_input')
        ))
        
        if not res:
            logger.error(f"DB Insert Failed for Question: {title}")
            raise Exception("Failed to insert question into database.")
            
        return {'success': True, 'question_number': next_num, 'id': res.get('last_id')}

    except Exception as e:
        logger.error(f"Create Question Logic Error: {e}")
        raise e

def activate_level_logic(contest_id, level, wait_time=0):
    start_time = datetime.utcnow()
    if wait_time > 0:
        start_time = start_time + timedelta(minutes=wait_time)
        
    u_q = "UPDATE rounds SET status='active', start_time=%s WHERE contest_id=%s AND round_number=%s"
    db_manager.execute_update(u_q, (start_time, contest_id, level))
    
    # Notify via SocketIO (Return info to caller or emit here if we import extensions)
    # Ideally service returns state, caller emits. But to centralized logic, we can emit here if extensions is safe.
    # To avoid circular imports, usually services don't import app/extensions dynamically?
    # Better: Return the payload, let route handler emit.
    return {'level': level, 'start_time': start_time}

def complete_level_logic(contest_id, level):
    u_q = "UPDATE rounds SET status='completed' WHERE contest_id=%s AND round_number=%s"
    db_manager.execute_update(u_q, (contest_id, level))
    return {'level': level}

def advance_level_logic(contest_id, wait_time=0):
    # Find next pending round
    q = "SELECT round_number FROM rounds WHERE contest_id=%s AND status='pending' ORDER BY round_number ASC LIMIT 1"
    res = db_manager.execute_query(q, (contest_id,))
    
    if not res:
         return None
         
    r_num = res[0]['round_number']
    return activate_level_logic(contest_id, r_num, wait_time)
