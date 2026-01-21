-- populate_level2_questions.sql
-- Sample questions for Round 2 (Level 2)
-- Assuming round_id=2 corresponds to Level 2

USE `debug_marathon`;

INSERT IGNORE INTO `questions` (`round_id`, `question_number`, `question_title`, `question_description`, `buggy_code`, `expected_code`, `test_cases`, `difficulty_level`, `points`, `time_estimate_minutes`) VALUES
(2, 1, 'Recursive Factorial Bug', 'Fix the recursive factorial function to handle base cases properly.', 
'def factorial(n):\n    return n * factorial(n-1)', 
'def factorial(n):\n    if n == 0 or n == 1: return 1\n    return n * factorial(n-1)', 
'[{"input": "5", "expected": "120"}, {"input": "0", "expected": "1"}]', 
'medium', 20, 10
),
(2, 2, 'Palindrome Check', 'The function should return True if string is palindrome. Fix the indexing.', 
'def is_palindrome(s):\n    return s == s[1:]', 
'def is_palindrome(s):\n    return s == s[::-1]', 
'[{"input": "\\"madam\\"", "expected": "True"}, {"input": "\\"hello\\"", "expected": "False"}]', 
'medium', 20, 10
);
