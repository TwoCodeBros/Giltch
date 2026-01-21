-- populate_level1_questions.sql
-- Insert 10 Level 1 Python Questions

USE `debug_marathon`;

-- Ensure Round 1 exists
INSERT INTO `rounds` (`contest_id`, `round_name`, `round_number`, `time_limit_minutes`, `total_questions`, `status`)
SELECT 1, 'Level 1: Python Basics', 1, 30, 10, 'active'
FROM DUAL
WHERE NOT EXISTS (SELECT * FROM `rounds` WHERE `contest_id` = 1 AND `round_number` = 1);

-- IDs will be auto-incremented. We assume Round 1 has ID 1 for simplicity, or we fetch it.
-- For this script we'll just use a subquery for round_id

-- Question 1: Sum of N
INSERT INTO `questions` (round_id, question_number, question_title, question_description, difficulty_level, buggy_code, expected_code, test_input, expected_output)
VALUES (
    (SELECT round_id FROM rounds WHERE round_number = 1 LIMIT 1),
    1,
    'Sum of N Numbers',
    'Fix the code to calculate the sum of numbers from 0 to N.',
    'easy',
    'def solve(n):\n    sum = 0\n    for i in range(n):\n        sum += i\n    return sum\n\nif __name__ == "__main__":\n    n = int(input())\n    print(solve(n))',
    'def solve(n):\n    sum = 0\n    for i in range(n + 1):\n        sum += i\n    return sum\n\nif __name__ == "__main__":\n    n = int(input())\n    print(solve(n))',
    '5',
    '15'
);

-- Question 2: Factorial
INSERT INTO `questions` (round_id, question_number, question_title, question_description, difficulty_level, buggy_code, expected_code, test_input, expected_output)
VALUES (
    (SELECT round_id FROM rounds WHERE round_number = 1 LIMIT 1),
    2,
    'Factorial Fix',
    'Calculate the factorial of N. The current code returns 0 for everything.',
    'easy',
    'def factorial(n):\n    if n == 0:\n        return 0\n    return n * factorial(n-1)\n\nif __name__ == "__main__":\n    n = int(input())\n    print(factorial(n))',
    'def factorial(n):\n    if n == 0:\n        return 1\n    return n * factorial(n-1)\n\nif __name__ == "__main__":\n    n = int(input())\n    print(factorial(n))',
    '5',
    '120'
);

-- Question 3: Even Check
INSERT INTO `questions` (round_id, question_number, question_title, question_description, difficulty_level, buggy_code, expected_code, test_input, expected_output)
VALUES (
    (SELECT round_id FROM rounds WHERE round_number = 1 LIMIT 1),
    3,
    'Is Even?',
    'Return "True" if N is even, else "False". The logic is reversed.',
    'easy',
    'def is_even(n):\n    if n % 2 != 0:\n        return "True"\n    return "False"\n\nif __name__ == "__main__":\n    n = int(input())\n    print(is_even(n))',
    'def is_even(n):\n    if n % 2 == 0:\n        return "True"\n    return "False"\n\nif __name__ == "__main__":\n    n = int(input())\n    print(is_even(n))',
    '4',
    'True'
);

-- Question 4: String Reverse
INSERT INTO `questions` (round_id, question_number, question_title, question_description, difficulty_level, buggy_code, expected_code, test_input, expected_output)
VALUES (
    (SELECT round_id FROM rounds WHERE round_number = 1 LIMIT 1),
    4,
    'Reverse String',
    'Reverse the input string. The slice syntax is wrong.',
    'easy',
    'def reverse_str(s):\n    return s[1::-1]\n\nif __name__ == "__main__":\n    s = input()\n    print(reverse_str(s))',
    'def reverse_str(s):\n    return s[::-1]\n\nif __name__ == "__main__":\n    s = input()\n    print(reverse_str(s))',
    'hello',
    'olleh'
);

-- Question 5: List Max
INSERT INTO `questions` (round_id, question_number, question_title, question_description, difficulty_level, buggy_code, expected_code, test_input, expected_output)
VALUES (
    (SELECT round_id FROM rounds WHERE round_number = 1 LIMIT 1),
    5,
    'Find Maximum',
    'Find the maximum number in a list. The initial value is problematic.',
    'medium',
    'def find_max(arr):\n    max_val = 1000\n    for x in arr:\n        if x > max_val:\n            max_val = x\n    return max_val\n\nif __name__ == "__main__":\n    # Input: 1,5,3,9,2\n    import sys\n    input_str = sys.stdin.read().strip()\n    arr = list(map(int, input_str.split(",")))\n    print(find_max(arr))',
    'def find_max(arr):\n    max_val = arr[0]\n    for x in arr:\n        if x > max_val:\n            max_val = x\n    return max_val\n\nif __name__ == "__main__":\n    import sys\n    input_str = sys.stdin.read().strip()\n    arr = list(map(int, input_str.split(",")))\n    print(find_max(arr))',
    '1,5,3,9,2',
    '9'
);

-- Question 6: Count Vowels
INSERT INTO `questions` (round_id, question_number, question_title, question_description, difficulty_level, buggy_code, expected_code, test_input, expected_output)
VALUES (
    (SELECT round_id FROM rounds WHERE round_number = 1 LIMIT 1),
    6,
    'Count Vowels',
    'Count the number of vowels in a string. Missing "u" and case sensitivity.',
    'medium',
    'def count_vowels(s):\n    count = 0\n    for char in s:\n        if char in "aeio":\n            count += 1\n    return count\n\nif __name__ == "__main__":\n    s = input()\n    print(count_vowels(s))',
    'def count_vowels(s):\n    count = 0\n    for char in s.lower():\n        if char in "aeiou":\n            count += 1\n    return count\n\nif __name__ == "__main__":\n    s = input()\n    print(count_vowels(s))',
    'Audio',
    '4'
);

-- Question 7: Palindrome
INSERT INTO `questions` (round_id, question_number, question_title, question_description, difficulty_level, buggy_code, expected_code, test_input, expected_output)
VALUES (
    (SELECT round_id FROM rounds WHERE round_number = 1 LIMIT 1),
    7,
    'Palindrome Check',
    'Check if string is palindrome. Logic is slightly off.',
    'medium',
    'def is_palindrome(s):\n    return s == s[::-1]\n\nif __name__ == "__main__":\n    s = input()\n    # Bug: Case sensitivity not handled\n    print(is_palindrome(s))',
    'def is_palindrome(s):\n    s = s.lower()\n    return s == s[::-1]\n\nif __name__ == "__main__":\n    s = input()\n    print(is_palindrome(s))',
    'Racecar',
    'True' -- Note: This creates boolean string
);

-- Question 8: Fibonacci
INSERT INTO `questions` (round_id, question_number, question_title, question_description, difficulty_level, buggy_code, expected_code, test_input, expected_output)
VALUES (
    (SELECT round_id FROM rounds WHERE round_number = 1 LIMIT 1),
    8,
    'Nth Fibonacci',
    'Return the Nth Fibonacci number (0-indexed). Logic error at base case.',
    'medium',
    'def fib(n):\n    if n <= 1: return 1\n    return fib(n-1) + fib(n-2)\n\nif __name__ == "__main__":\n    n = int(input())\n    print(fib(n))',
    'def fib(n):\n    if n == 0: return 0\n    if n == 1: return 1\n    return fib(n-1) + fib(n-2)\n\nif __name__ == "__main__":\n    n = int(input())\n    print(fib(n))',
    '6',
    '8'
);

-- Question 9: Positive Sum
INSERT INTO `questions` (round_id, question_number, question_title, question_description, difficulty_level, buggy_code, expected_code, test_input, expected_output)
VALUES (
    (SELECT round_id FROM rounds WHERE round_number = 1 LIMIT 1),
    9,
    'Positive Sum',
    'Sum only positive numbers. Indentation error.',
    'easy',
    'def sum_pos(arr):\n    total = 0\n    for x in arr:\n        if x > 0:\n        total += x\n    return total\n\nif __name__ == "__main__":\n    import sys\n    input_str = sys.stdin.read().strip()\n    arr = list(map(int, input_str.split(",")))\n    print(sum_pos(arr))',
    'def sum_pos(arr):\n    total = 0\n    for x in arr:\n        if x > 0:\n            total += x\n    return total\n\nif __name__ == "__main__":\n    import sys\n    input_str = sys.stdin.read().strip()\n    arr = list(map(int, input_str.split(",")))\n    print(sum_pos(arr))',
    '1,-2,3,4',
    '8'
);

-- Question 10: Square List
INSERT INTO `questions` (round_id, question_number, question_title, question_description, difficulty_level, buggy_code, expected_code, test_input, expected_output)
VALUES (
    (SELECT round_id FROM rounds WHERE round_number = 1 LIMIT 1),
    10,
    'Square Numbers',
    'Return list of squares. String concatenation error.',
    'medium',
    'def square_list(arr):\n    res = []\n    for x in arr:\n        res.append(x + x)\n    return res\n\nif __name__ == "__main__":\n    import sys\n    input_str = sys.stdin.read().strip()\n    arr = list(map(int, input_str.split(",")))\n    print(square_list(arr))',
    'def square_list(arr):\n    res = []\n    for x in arr:\n        res.append(x * x)\n    return res\n\nif __name__ == "__main__":\n    import sys\n    input_str = sys.stdin.read().strip()\n    arr = list(map(int, input_str.split(",")))\n    print(square_list(arr))',
    '2,3,4',
    '[4, 9, 16]'
);
