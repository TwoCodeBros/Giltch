# Debug Marathon Platform - Complete System Documentation

## 1. Project Overview
**Debug Marathon** is a full-stack competitive coding platform designed for hosting coding contests (marathons) with multiple levels, real-time code evaluation, and strict proctoring (anti-cheating) mechanisms. It features a modern "Glassmorphism" UI and separates roles into **Admins**, **Participants**, and **Leaders**.

### Technology Stack
- **Frontend**: HTML5, CSS3 (Vanilla + Custom Variables), JavaScript (ES6).
  - Uses `ACE Editor` for code input.
  - Uses `Socket.IO Client` for real-time updates.
- **Backend**: Python Flask.
  - **Database**: MySQL (accessed via `mysql-connector-python`).
  - **Real-time**: `Flask-SocketIO` for event broadcasting.
  - **Execution**: Python `subprocess` for secure code compilation and execution.

## 2. Directory Structure

```
debug-marathon/
├── backend/
│   ├── app.py                  # Application Entry Point & Config
│   ├── db_connection.py        # Database Manager (Connection Pool)
│   ├── auth_middleware.py      # Decorators for route protection
│   ├── debug_marathon_schema.sql # Database Schema
│   └── routes/
│       ├── auth.py             # Login/Register & Token Management
│       ├── admin.py            # Admin Dashboard APIs
│       ├── contest.py          # Core Contest Logic (Levels, Q&A, Subs)
│       ├── proctoring.py       # Anti-cheat Logic & Stats
│       ├── leader.py           # Leader Dashboard Logic
│       └── leaderboard.py      # Public Ranking Logic
├── frontend/
│   ├── index.html              # Landing Page & Login
│   ├── participant.html        # Main Contest Interface
│   ├── admin.html              # Admin Control Panel
│   ├── leaderboard.html        # Public Scoreboard
│   ├── js/                     # Client-side Logic
│   │   ├── main.js, api.js     # Common Utilities
│   │   ├── auth.js             # Authentication Handlers
│   │   ├── editor.js           # Ace Editor Config
│   │   └── proctoring.js       # Client Violation Detector
│   └── css/                    # Stylesheets
```

## 3. Database Schema
The system uses **MySQL**. Key tables include:

1.  **`users`**: Stores Admins and Participants.
    - Fields: `user_id`, `username`, `password_hash`, `role` ('admin', 'participant'), `status` (active/disqualified), `admin_status` (PENDING/APPROVED).
2.  **`contests`**: Configuration for a contest event.
    - Fields: `start_datetime`, `end_datetime`, `status` (draft/live/paused/ended), `max_violations_allowed`.
3.  **`rounds`** (Levels): Sequential stages of a contest.
    - Fields: `round_number`, `time_limit_minutes`, `status` (pending/active/completed).
4.  **`questions`**: Coding problems assigned to rounds.
    - Fields: `buggy_code` (boilerplate), `expected_output`, `test_cases` (JSON), `difficulty_level`.
5.  **`submissions`**: History of code attempts.
    - Fields: `submitted_code`, `is_correct`, `score_awarded`, `test_results` (JSON detailed logs).
6.  **`participant_level_stats`**: Tracks user progress per level.
    - Fields: `level`, `violation_count`, `questions_solved`, `status` (NOT_STARTED/IN_PROGRESS/COMPLETED).
7.  **`participant_proctoring`** (referenced int code): Stores global proctoring risk states.
    - Fields: `risk_level`, `total_violations`, `is_disqualified`.
8.  **`violations`**: Log of every specific anti-cheat event.
    - Fields: `violation_type` (tab_switch, copy, etc.), `severity`, `timestamp`.
9.  **`shortlisted_participants`**: Control table for level advancement.
    - Only users in this table with `is_allowed=1` can access the next level.

## 4. User Roles & Flows

### A. Administrator
- **Login**: `/api/auth/admin/login`. Admins must be `APPROVED` by another admin to log in.
- **Contest Control**:
  - **Start/Pause/End Contest**: Updates global state.
  - **Level Management**: Can "Activate" a specific level (Round 1, 2, etc.). Only one level is active at a time generally.
  - **Countdown**: Can start a global timer for the current level.
- **User Management**:
  - **Qualify Users**: Manually selects users to move from Level 1 -> Level 2 via `/api/contest/<id>/qualify-participants`.
  - **Proctoring Review**: Sees a live table of "Risky" users. Can Reset Violations, Suspend, or Disqualify users.

### B. Participant
- **Login**: `/api/auth/participant/login`. Uses `username` (e.g., "PART001").
- **Dashboard (`participant.html`)**:
  - **State Sync**: Polls `/api/contest/participant-state` to know if the contest is Live and which Level they are on.
  - **Waiting Room**: If the global level hasn't started or they aren't shortlisted, they see a waiting screen.
  - **Question View**: Fetches questions for the current level.
  - **Editor**: Writes code. "Run" button tests against sample inputs. "Submit" button runs against hidden test cases.
  - **Completion**: Once all questions are solved, the level is marked `COMPLETED`. They wait for Admin approval for the next level.

### C. Leader (Observer)
- **Login**: Separate login for observers.
- **View**: Access to `leader_dashboard.html` to see real-time "Online" status and "Current Level" of all participants.

## 5. Core Modules & Logic

### 1. Code Execution Engine (`backend/routes/contest.py`)
- **Security**: Uses `subprocess` to run code in an isolated process. 
- **Flow**:
  1. Creates a temporary file (`tempfile`) with the user's code.
  2. Spawns a process (`python` or `node`) with constrained timeouts (5s).
  3. Feeds `input_data` via `stdin`.
  4. Captures `stdout` and compares it with `expected_output` (ignoring whitespace).
- **Submission**: If all test cases pass, the question is marked solved in `submissions` and `participant_level_stats`.

### 2. Proctoring System (`backend/routes/proctoring.py`)
- **Client-Side**: `frontend/js/proctoring.js` listens for:
  - `visibilitychange` (Tab switching).
  - `window.onblur` (Focus loss).
  - `copy`/`paste`/`cut` events.
  - `contextmenu` (Right click).
  - `keyup` (PrintScreen detection).
- **Server-Side**:
  - Receives violation report.
  - **Scoring**: Calculates penalty points based on type (e.g., Screenshot = 3pts, Tab Switch = 1pt).
  - **Risk Assessment**: `Low` -> `Medium` -> `High` -> `Critical`.
  - **Auto-Action**: If violations > `max_violations`, the user is **Disqualified** automatically.
  - **Socket Events**: Emits `proctoring:violation` to Admin immediately.

### 3. Level Progression Logic
This is a "Marathon" style contest, meaning stages are sequential.
1. **Global Control**: Admin sets Round 1 as `ACTIVE`.
2. **Participation**: Users enter Round 1.
3. **Completion**: User solves all Qs -> Status `COMPLETED`.
4. **Gatekeeping**: System does **not** auto-promote.
5. **Selection**: Admin reviews scores/proctoring stats and calls `/qualify-participants` to select who moves to Round 2.
6. **Promotion**: Selected users now see Round 2 (once Admin activates Round 2 globally).

## 6. API Endpoints Summary

### Auth
- `POST /api/auth/participant/login`
- `POST /api/auth/admin/login`

### Contest
- `GET /api/contest/questions`: Get questions for current level.
- `POST /api/contest/run`: Test code.
- `POST /api/contest/submit-question`: Final submission.
- `POST /api/contest/start-level`: User starts their timer.
- `POST /api/contest/participant-state`: Syncs UI with DB state.

### Proctoring
- `POST /api/proctoring/violation`: Report violation.
- `GET /api/proctoring/status/<contest_id>`: Admin view of all users.
- `POST /api/proctoring/action/disqualify`: Admin bans a user.

### Admin
- `POST /api/contest/<id>/control/start`: Start Contest.
- `POST /api/contest/<id>/qualify-participants`: Promote users to next level.
