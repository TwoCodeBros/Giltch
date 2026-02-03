
# seed_data.py

from db_connection import db_manager
import datetime
import json
import traceback

def seed_data():
    print("Beginning Seed Data...")
    
    try:
        # Check if contest exists
        existing_contests = db_manager.execute_query("SELECT contest_id FROM contests")
        contest_id = 1
        if not existing_contests:
            print("Creating Contest...")
            res = db_manager.execute_update("""
                INSERT INTO contests (contest_name, description, start_datetime, end_datetime, status, max_violations_allowed)
                VALUES ('Debug Marathon 2026', 'Fix the glitches to win!', '2026-01-26 10:00:00', '2026-01-27 10:00:00', 'live', 50)
            """)
            contest_id = res['last_id']
        else:
            contest_id = existing_contests[0]['contest_id']
            print(f"Contest exists: ID {contest_id}")

        # Check if user exists
        existing_users = db_manager.execute_query("SELECT user_id FROM users WHERE username='PART001'")
        if not existing_users:
            print("Creating User PART001...")
            db_manager.execute_update("""
                INSERT INTO users (username, email, password_hash, full_name, role)
                VALUES ('PART001', 'part001@example.com', 'scrypt:32768:8:1$dummyhash', 'Participant One', 'participant')
            """)
        else:
            print("User PART001 exists")

        # Define 5 levels with 3 questions each
        levels = [
            {
                'name': 'Level 1 - Basics',
                'time': 20,
                'language': 'C',
                'questions': [
                    {
                        'title': 'Fix the Sum',
                        'description': 'The function should return the sum of two numbers, but it subtracts them.',
                        'buggy': 'int add(int a, int b) {\n    return a - b;  // Bug: should be a + b\n}\n\nint main() {\n    int a, b;\n    scanf("%d %d", &a, &b);\n    printf("%d", add(a, b));\n    return 0;\n}',
                        'test_input': '2 3',
                        'expected': '5',
                        'test_cases': [{"input": "2 3", "expected": "5"}, {"input": "10 5", "expected": "15"}],
                        'difficulty': 'Easy',
                        'points': 10
                    },
                    {
                        'title': 'Fix Factorial',
                        'description': 'Calculate factorial but loop condition is wrong.',
                        'buggy': 'int factorial(int n) {\n    int fact = 1;\n    for (int i = 1; i < n; i++) {  // Bug: should be i <= n\n        fact *= i;\n    }\n    return fact;\n}\n\nint main() {\n    int n;\n    scanf("%d", &n);\n    printf("%d", factorial(n));\n    return 0;\n}',
                        'test_input': '5',
                        'expected': '120',
                        'test_cases': [{"input": "5", "expected": "120"}, {"input": "3", "expected": "6"}],
                        'difficulty': 'Easy',
                        'points': 15
                    },
                    {
                        'title': 'Find Maximum',
                        'description': 'Find the maximum of two numbers but comparison is inverted.',
                        'buggy': 'int max(int a, int b) {\n    return (a < b) ? a : b;  // Bug: should be a > b\n}\n\nint main() {\n    int a, b;\n    scanf("%d %d", &a, &b);\n    printf("%d", max(a, b));\n    return 0;\n}',
                        'test_input': '10 20',
                        'expected': '20',
                        'test_cases': [{"input": "10 20", "expected": "20"}, {"input": "50 30", "expected": "50"}],
                        'difficulty': 'Easy',
                        'points': 10
                    }
                ]
            },
            {
                'name': 'Level 2 - Intermediate',
                'time': 20,
                'language': 'C',
                'questions': [
                    {
                        'title': 'Array Sum',
                        'description': 'Calculate sum of array elements but loop initializer is wrong.',
                        'buggy': 'int arraySum(int arr[], int n) {\n    int sum = 0;\n    for (int i = 1; i < n; i++) {  // Bug: should start from i = 0\n        sum += arr[i];\n    }\n    return sum;\n}\n\nint main() {\n    int arr[] = {1, 2, 3, 4};\n    printf("%d", arraySum(arr, 4));\n    return 0;\n}',
                        'test_input': '1 2 3 4',
                        'expected': '10',
                        'test_cases': [{"input": "1 2 3 4", "expected": "10"}, {"input": "5 5", "expected": "10"}],
                        'difficulty': 'Medium',
                        'points': 20
                    },
                    {
                        'title': 'String Length',
                        'description': 'Count string length but terminator check is wrong.',
                        'buggy': 'int strLength(char *str) {\n    int len = 0;\n    while (str[len] != "\\0") {  // Bug: character literal not string\n        len++;\n    }\n    return len;\n}\n\nint main() {\n    printf("%d", strLength("hello"));\n    return 0;\n}',
                        'test_input': 'hello',
                        'expected': '5',
                        'test_cases': [{"input": "hello", "expected": "5"}, {"input": "code", "expected": "4"}],
                        'difficulty': 'Medium',
                        'points': 20
                    },
                    {
                        'title': 'Reverse Array',
                        'description': 'Reverse array in place but pointer logic is incorrect.',
                        'buggy': 'void reverseArray(int arr[], int n) {\n    for (int i = 0; i < n / 2; i++) {\n        int temp = arr[i];\n        arr[i] = arr[i];  // Bug: should be arr[n-1-i]\n        arr[n-1-i] = temp;\n    }\n}',
                        'test_input': '1 2 3 4 5',
                        'expected': '5 4 3 2 1',
                        'test_cases': [{"input": "1 2 3 4 5", "expected": "5 4 3 2 1"}, {"input": "1 2 3", "expected": "3 2 1"}],
                        'difficulty': 'Medium',
                        'points': 15
                    }
                ]
            },
            {
                'name': 'Level 3 - Advanced',
                'time': 20,
                'language': 'Python',
                'questions': [
                    {
                        'title': 'Palindrome Check',
                        'description': 'Check if string is palindrome but comparison is incomplete.',
                        'buggy': 'def isPalindrome(s):\n    s = s.lower()\n    return s == s[::-1]\n\nprint(isPalindrome("racecar"))',
                        'test_input': 'racecar',
                        'expected': 'True',
                        'test_cases': [{"input": "racecar", "expected": "True"}, {"input": "hello", "expected": "False"}],
                        'difficulty': 'Medium',
                        'points': 20
                    },
                    {
                        'title': 'Prime Number',
                        'description': 'Find if number is prime but loop condition is wrong.',
                        'buggy': 'def isPrime(n):\n    if n < 2:\n        return False\n    for i in range(2, n):\n        if n % i == 0:\n            return False\n    return True\n\nprint(isPrime(17))',
                        'test_input': '17',
                        'expected': 'True',
                        'test_cases': [{"input": "17", "expected": "True"}, {"input": "20", "expected": "False"}],
                        'difficulty': 'Medium',
                        'points': 25
                    },
                    {
                        'title': 'List Average',
                        'description': 'Calculate average but denominator is wrong.',
                        'buggy': 'def average(lst):\n    return sum(lst) / len(lst) if len(lst) > 0 else 0\n\nprint(average([1, 2, 3, 4, 5]))',
                        'test_input': '1 2 3 4 5',
                        'expected': '3.0',
                        'test_cases': [{"input": "1 2 3 4 5", "expected": "3.0"}, {"input": "10 20", "expected": "15.0"}],
                        'difficulty': 'Easy',
                        'points': 15
                    }
                ]
            },
            {
                'name': 'Level 4 - Expert',
                'time': 30,
                'language': 'Java',
                'questions': [
                    {
                        'title': 'Binary Search',
                        'description': 'Binary search implementation but mid calculation is wrong.',
                        'buggy': 'public class BinarySearch {\n    public static int search(int[] arr, int target) {\n        int left = 0, right = arr.length - 1;\n        while (left <= right) {\n            int mid = (left + right) / 2;\n            if (arr[mid] == target) return mid;\n            else if (arr[mid] < target) left = mid + 1;\n            else right = mid - 1;\n        }\n        return -1;\n    }\n}',
                        'test_input': '1 3 5 7 9',
                        'expected': '2',
                        'test_cases': [{"input": "1 3 5 7 9", "expected": "2"}, {"input": "2 4 6 8", "expected": "-1"}],
                        'difficulty': 'Hard',
                        'points': 30
                    },
                    {
                        'title': 'Merge Sort',
                        'description': 'Merge sort implementation but merge logic has a bug.',
                        'buggy': 'public class MergeSort {\n    public static void merge(int[] arr, int left, int mid, int right) {\n        // Bug: merge logic implementation issue\n    }\n    public static void sort(int[] arr, int left, int right) {\n        if (left < right) {\n            int mid = (left + right) / 2;\n            sort(arr, left, mid);\n            sort(arr, mid + 1, right);\n            merge(arr, left, mid, right);\n        }\n    }\n}',
                        'test_input': '5 2 8 1 9',
                        'expected': '1 2 5 8 9',
                        'test_cases': [{"input": "5 2 8 1 9", "expected": "1 2 5 8 9"}],
                        'difficulty': 'Hard',
                        'points': 35
                    },
                    {
                        'title': 'HashMap Operations',
                        'description': 'HashMap operations but key collision handling is incorrect.',
                        'buggy': 'import java.util.HashMap;\npublic class HashMapBug {\n    public static void main(String[] args) {\n        HashMap<String, Integer> map = new HashMap<>();\n        map.put("a", 1);\n        map.put("b", 2);\n    }\n}',
                        'test_input': 'a b',
                        'expected': '1 2',
                        'test_cases': [{"input": "a b", "expected": "1 2"}],
                        'difficulty': 'Medium',
                        'points': 25
                    }
                ]
            },
            {
                'name': 'Level 5 - Championship',
                'time': 45,
                'language': 'Java',
                'questions': [
                    {
                        'title': 'Graph DFS',
                        'description': 'Depth-first search implementation but visited tracking is incomplete.',
                        'buggy': 'public class GraphDFS {\n    public void dfs(int node, boolean[] visited) {\n        System.out.print(node + " ");\n        for (int neighbor : graph.get(node)) {\n            if (!visited[neighbor]) {\n                dfs(neighbor, visited);\n            }\n        }\n    }\n}',
                        'test_input': '0 1 2 3',
                        'expected': '0 1 2 3',
                        'test_cases': [{"input": "0 1 2 3", "expected": "0 1 2 3"}],
                        'difficulty': 'Hard',
                        'points': 40
                    },
                    {
                        'title': 'Dynamic Programming - LCS',
                        'description': 'Longest Common Subsequence but recurrence relation is wrong.',
                        'buggy': 'public class LCS {\n    public static int lcs(String s1, String s2) {\n        int m = s1.length(), n = s2.length();\n        int[][] dp = new int[m+1][n+1];\n        for (int i = 1; i <= m; i++) {\n            for (int j = 1; j <= n; j++) {\n                if (s1.charAt(i-1) == s2.charAt(j-1))\n                    dp[i][j] = dp[i-1][j-1] + 1;\n                else\n                    dp[i][j] = Math.max(dp[i-1][j], dp[i][j-1]);\n            }\n        }\n        return dp[m][n];\n    }\n}',
                        'test_input': 'abcd acbd',
                        'expected': '3',
                        'test_cases': [{"input": "abcd acbd", "expected": "3"}],
                        'difficulty': 'Hard',
                        'points': 45
                    },
                    {
                        'title': 'Dijkstra Algorithm',
                        'description': 'Shortest path using Dijkstra but distance update is incorrect.',
                        'buggy': 'public class Dijkstra {\n    public int[] shortestPath(int[][] graph, int start) {\n        int n = graph.length;\n        int[] dist = new int[n];\n        for (int i = 0; i < n; i++) dist[i] = Integer.MAX_VALUE;\n        dist[start] = 0;\n        return dist;\n    }\n}',
                        'test_input': '0',
                        'expected': '0',
                        'test_cases': [{"input": "0", "expected": "0"}],
                        'difficulty': 'Hard',
                        'points': 50
                    }
                ]
            }
        ]

        # Create rounds and questions
        for level_idx, level in enumerate(levels, 1):
            round_num = level_idx
            
            # Check if round exists
            existing_rounds = db_manager.execute_query(
                "SELECT round_id FROM rounds WHERE contest_id=%s AND round_number=%s", 
                (contest_id, round_num)
            )
            
            if existing_rounds:
                print(f"Round {round_num} ({level['name']}) exists")
                round_id = existing_rounds[0]['round_id']
            else:
                print(f"Creating Round {round_num} ({level['name']})...")
                res = db_manager.execute_update(
                    "INSERT INTO rounds (contest_id, round_name, round_number, time_limit_minutes, total_questions, status, is_locked, allowed_language) VALUES (%s, %s, %s, %s, %s, 'active', 0, %s)",
                    (contest_id, level['name'], round_num, level['time'], len(level['questions']), level['language'])
                )
                round_id = res['last_id']
            
            # Check and create questions
            existing_q = db_manager.execute_query("SELECT COUNT(*) as cnt FROM questions WHERE round_id=%s", (round_id,))
            q_count = existing_q[0]['cnt'] if existing_q else 0
            
            if q_count == 0:
                print(f"  Creating {len(level['questions'])} questions for Round {round_num}...")
                for q_idx, question in enumerate(level['questions'], 1):
                    tcs = json.dumps(question['test_cases'])
                    
                    db_manager.execute_update(
                        """INSERT INTO questions (round_id, question_number, question_title, question_description, buggy_code, 
                           expected_output, test_cases, difficulty_level, points, test_input)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (round_id, q_idx, question['title'], question['description'], question['buggy'],
                         question['expected'], tcs, question['difficulty'], question['points'], question['test_input'])
                    )
                    print(f"    ✓ Question {q_idx}: {question['title']}")
            else:
                print(f"  Round {round_num} has {q_count} questions already")
            
        print("Seed Data Completed Successfully.")
    except Exception as e:
        print(f"Seed Data Failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    seed_data()