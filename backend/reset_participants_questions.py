import sys
from backend.db_connection import db_manager
import uuid
import random

def reset_and_populate():
    print("Resetting Participants and Questions...")
    
    # 1. Clear relevant tables
    db_manager.execute_update("DELETE FROM users WHERE role='participant'")
    # Note: deleting from users cascades to submissions, violations, participant_level_stats, shortlisted_participants
    
    db_manager.execute_update("DELETE FROM questions")
    # Cascades to submissions
    
    # 2. Add New Participants (PART001 to PART050)
    print("Adding 50 Participants...")
    participant_creds = []
    
    for i in range(1, 51):
        username = f"PART{i:03d}"
        password_plain = f"pass{i:03d}"
        # Ideally hash, but for dev we use plain in this simple setup or hashed
        # Using a simple hash function or specific string if needed. 
        # For this system, let's assume raw or a known hash. 
        # The Auth system uses check_password_hash. 
        # Let's generate a hash using werkzeug
        from werkzeug.security import generate_password_hash
        pwd_hash = generate_password_hash(password_plain)
        
        db_manager.execute_update(
            "INSERT INTO users (username, email, password_hash, full_name, role) VALUES (%s, %s, %s, %s, 'participant')",
            (username, f"{username}@debug.com", pwd_hash, f"Participant {i}")
        )
        participant_creds.append(f"{username} | {password_plain}")
        
    # 3. Add Questions (3 per Level x 5 Levels)
    print("Adding Questions...")
    
    questions_data = []

    # Level 1: Basics (Python/C)
    q1_c_stack = {
        'level': 1,
        'title': 'Stack Implementation Bug',
        'language': 'c',
        'difficulty': 'Level 1',
        'buggy_code': """#include <stdio.h>
#define MAX 100
struct Stack {
    int arr[MAX];
    int top;
};

void push(struct Stack *s, int val) {
    if(s->top == MAX-1) {
        printf("Stack Overflow\\n");
    } else {
        s->arr[s->top] = val;   // ❌ BUG: should increment top first
        s->top++;
    }
}

int pop(struct Stack *s) {
    if(s->top == -1) {
        printf("Stack Underflow\\n");
        return -1;
    } else {
        int val = s->arr[s->top];  // ❌ BUG: should decrement top first
        s->top--;
        return val;
    }
}

int main() {
    struct Stack s;
    s.top = -1;
    push(&s, 10);
    push(&s, 20);
    printf("%d ", pop(&s));
    printf("%d", pop(&s));
    return 0;
}""",
        'expected_output': "20 10",
        'input': ""
    }
    
    q_l1_2 = {
        'level': 1,
        'title': 'Sum of Array',
        'language': 'python',
        'difficulty': 'Level 1',
        'buggy_code': """def sum_array(arr):
    total = 0
    for i in range(len(arr) + 1): # Bug: Index out of range
        total += arr[i]
    return total

if __name__ == "__main__":
    import sys
    nums = list(map(int, sys.stdin.read().split()))
    print(sum_array(nums))""",
        'expected_output': "15",
        'input': "1 2 3 4 5"
    }

    q_l1_3 = {
        'level': 1,
        'title': 'Even Checker',
        'language': 'python',
        'difficulty': 'Level 1',
        'buggy_code': """def is_even(n):
    if n % 2 = 0: # Syntax Error
        return True
    return False

if __name__ == "__main__":
    n = int(input())
    print(is_even(n))""",
        'expected_output': "True",
        'input': "4"
    }
    
    # Generic filler for other levels
    levels = [1, 2, 3, 4, 5]
    
    # We add the specific ones first
    all_qs = [q1_c_stack, q_l1_2, q_l1_3]
    
    # Generate remaining (Total 15 needed, we have 3. Need 12 more. 
    # Distribute: L2(3), L3(3), L4(3), L5(3)
    
    for l in range(2, 6):
        for k in range(1, 4):
            all_qs.append({
                'level': l,
                'title': f'Level {l} Question {k}',
                'language': 'python',
                'difficulty': f'Level {l}',
                'buggy_code': f"# Buggy Code for Level {l} Q{k}\ndef solve():\n    pass\nif __name__=='__main__': print('Output')",
                'expected_output': "Output",
                'input': "Input"
            })
            
    # Insert
    for q in all_qs:
        # Get Round ID
        contest_id = 1 # Default
        r_res = db_manager.execute_query("SELECT round_id FROM rounds WHERE contest_id=%s AND round_number=%s", (contest_id, q['level']))
        if not r_res: continue
        rid = r_res[0]['round_id']
        
        # Get Num
        c_res = db_manager.execute_query("SELECT MAX(question_number) as m FROM questions WHERE round_id=%s", (rid,))
        next_n = (c_res[0]['m'] or 0) + 1
        
        db_manager.execute_update("""
            INSERT INTO questions 
            (round_id, question_number, question_title, expected_input, expected_output, buggy_code, difficulty_level, points, language)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 10, %s)
        """, (rid, next_n, q['title'], q['input'], q['expected_output'], q['buggy_code'], q['difficulty'], q['language']))
        
        questions_data.append(f"Level {q['level']} - Q{next_n}: {q['title']} ({q['language']})\nInput: {q['input']}\nOutput: {q['expected_output']}\n")

    # Write to File
    with open('NEW_DATA.txt', 'w', encoding='utf-8') as f:
        f.write("=== NEW PARTICIPANTS ===\n")
        f.write("\n".join(participant_creds))
        f.write("\n\n=== NEW QUESTIONS ===\n")
        f.write("\n".join(questions_data))
        
    print("Done. Check NEW_DATA.txt")

if __name__ == "__main__":
    reset_and_populate()
