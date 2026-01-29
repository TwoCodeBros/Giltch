
-- SQLite Schema for Debug Marathon

CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  full_name TEXT,
  role TEXT NOT NULL DEFAULT 'participant', -- ENUM handled as TEXT
  department TEXT,
  college TEXT,
  status TEXT DEFAULT 'active',
  is_active BOOLEAN DEFAULT 1,
  admin_status TEXT DEFAULT 'PENDING',
  approved_by INTEGER,
  approval_at DATETIME,
  profile_image TEXT,
  registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
  last_login DATETIME
);

CREATE TABLE IF NOT EXISTS contests (
  contest_id INTEGER PRIMARY KEY AUTOINCREMENT,
  contest_name TEXT NOT NULL,
  description TEXT,
  start_datetime DATETIME NOT NULL,
  end_datetime DATETIME NOT NULL,
  status TEXT DEFAULT 'draft',
  is_active BOOLEAN DEFAULT 1,
  max_violations_allowed INTEGER DEFAULT 5,
  current_round INTEGER DEFAULT 1,
  created_by INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rounds (
  round_id INTEGER PRIMARY KEY AUTOINCREMENT,
  contest_id INTEGER NOT NULL,
  round_name TEXT NOT NULL,
  round_number INTEGER NOT NULL,
  time_limit_minutes INTEGER NOT NULL,
  total_questions INTEGER NOT NULL,
  passing_score REAL,
  status TEXT DEFAULT 'pending',
  is_locked BOOLEAN DEFAULT 1,
  unlock_condition TEXT,
  allowed_language TEXT DEFAULT 'python',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(contest_id, round_number)
);

CREATE TABLE IF NOT EXISTS questions (
  question_id INTEGER PRIMARY KEY AUTOINCREMENT,
  round_id INTEGER NOT NULL,
  question_number INTEGER NOT NULL,
  question_title TEXT NOT NULL,
  question_description TEXT NOT NULL,
  buggy_code TEXT NOT NULL,
  expected_output TEXT,
  test_input TEXT,
  test_cases JSON,
  difficulty_level TEXT NOT NULL,
  points INTEGER DEFAULT 10,
  hints TEXT,
  time_estimate_minutes INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(round_id, question_number)
);

CREATE TABLE IF NOT EXISTS submissions (
  submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  contest_id INTEGER NOT NULL,
  round_id INTEGER NOT NULL,
  question_id INTEGER NOT NULL,
  submitted_code TEXT,
  is_correct BOOLEAN,
  score_awarded REAL DEFAULT 0.00,
  test_results JSON,
  status TEXT DEFAULT 'pending',
  time_taken_seconds INTEGER,
  submission_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS participant_level_stats (
  stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  contest_id INTEGER NOT NULL,
  level INTEGER NOT NULL,
  status TEXT DEFAULT 'NOT_STARTED',
  questions_solved INTEGER DEFAULT 0,
  level_score REAL DEFAULT 0.00,
  violation_count INTEGER DEFAULT 0,
  start_time DATETIME,
  completed_at DATETIME,
  run_count INTEGER DEFAULT 0,
  UNIQUE(user_id, contest_id, level)
);

CREATE TABLE IF NOT EXISTS proctoring_config (
  id TEXT PRIMARY KEY,
  contest_id INTEGER NOT NULL UNIQUE,
  enabled BOOLEAN DEFAULT 1,
  max_violations INTEGER DEFAULT 10,
  auto_disqualify BOOLEAN DEFAULT 1,
  warning_threshold INTEGER DEFAULT 5,
  grace_violations INTEGER DEFAULT 2,
  strict_mode BOOLEAN DEFAULT 0,
  track_tab_switches BOOLEAN DEFAULT 1,
  track_focus_loss BOOLEAN DEFAULT 1,
  block_copy BOOLEAN DEFAULT 1,
  block_paste BOOLEAN DEFAULT 1,
  block_cut BOOLEAN DEFAULT 1,
  block_selection BOOLEAN DEFAULT 0,
  block_right_click BOOLEAN DEFAULT 1,
  detect_screenshot BOOLEAN DEFAULT 1,
  tab_switch_penalty INTEGER DEFAULT 1,
  copy_paste_penalty INTEGER DEFAULT 2,
  screenshot_penalty INTEGER DEFAULT 3,
  focus_loss_penalty INTEGER DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS participant_proctoring (
  id TEXT PRIMARY KEY,
  participant_id TEXT,
  user_id INTEGER,
  contest_id INTEGER NOT NULL,
  risk_level TEXT DEFAULT 'low',
  total_violations INTEGER DEFAULT 0,
  violation_score INTEGER DEFAULT 0,
  extra_violations INTEGER DEFAULT 0,
  is_disqualified BOOLEAN DEFAULT 0,
  disqualified_at DATETIME,
  disqualification_reason TEXT,
  is_suspended BOOLEAN DEFAULT 0,
  suspended_at DATETIME,
  suspension_reason TEXT,
  last_heartbeat DATETIME,
  client_ip TEXT,
  tab_switches INTEGER DEFAULT 0,
  focus_losses INTEGER DEFAULT 0,
  copy_attempts INTEGER DEFAULT 0,
  paste_attempts INTEGER DEFAULT 0,
  screenshot_attempts INTEGER DEFAULT 0,
  last_violation_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(participant_id, contest_id)
);

CREATE TABLE IF NOT EXISTS violations (
  violation_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  contest_id INTEGER NOT NULL,
  round_id INTEGER,
  question_id INTEGER,
  violation_type TEXT NOT NULL,
  description TEXT,
  severity TEXT DEFAULT 'medium',
  penalty_points INTEGER DEFAULT 1,
  level INTEGER DEFAULT 1,
  ip_address TEXT,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS shortlisted_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contest_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    level INTEGER NOT NULL,
    is_allowed BOOLEAN DEFAULT 1,
    UNIQUE(contest_id, level, user_id)
);

CREATE TABLE IF NOT EXISTS leaderboard (
  leaderboard_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  contest_id INTEGER NOT NULL,
  rank_position INTEGER,
  total_score REAL DEFAULT 0.00,
  total_time_taken_seconds INTEGER DEFAULT 0,
  questions_attempted INTEGER DEFAULT 0,
  questions_correct INTEGER DEFAULT 0,
  violations_count INTEGER DEFAULT 0,
  current_round INTEGER DEFAULT 1,
  last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, contest_id)
);

CREATE TABLE IF NOT EXISTS admin_state (
    key_name TEXT PRIMARY KEY,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proctoring_alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  contest_id INTEGER NOT NULL,
  participant_id TEXT,
  alert_type TEXT NOT NULL,
  severity TEXT DEFAULT 'warning',
  message TEXT NOT NULL,
  is_read BOOLEAN DEFAULT 0,
  read_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
