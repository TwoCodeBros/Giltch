-- Database Setup for Debug Marathon
-- Compatible with XAMPP MySQL
-- Version: 3.1 (Refined for Code Compatibility)

CREATE DATABASE IF NOT EXISTS `debug_marathon_v3` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `debug_marathon_v3`;

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";

-- --------------------------------------------------------
-- 1. Users Table (Core)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `users` (
  `user_id` INT(11) NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(50) NOT NULL,
  `email` VARCHAR(100) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `full_name` VARCHAR(100) DEFAULT NULL,
  `role` ENUM('participant', 'admin', 'leader') NOT NULL DEFAULT 'participant',
  `department` VARCHAR(100) DEFAULT NULL,
  `college` VARCHAR(100) DEFAULT NULL,
  
  -- Account Status
  `status` ENUM('active', 'disqualified', 'held', 'suspended') DEFAULT 'active',
  `is_active` BOOLEAN DEFAULT TRUE,
  
  -- Admin/Leader Approval
  `admin_status` ENUM('PENDING', 'APPROVED', 'REJECTED') DEFAULT 'PENDING',
  `approved_by` INT DEFAULT NULL,
  `approval_at` DATETIME DEFAULT NULL,
  
  -- Meta
  `profile_image` VARCHAR(255) DEFAULT NULL,
  `registration_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `last_login` DATETIME DEFAULT NULL,
  
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`),
  KEY `role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- 2. Contests Table
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `contests` (
  `contest_id` INT(11) NOT NULL AUTO_INCREMENT,
  `contest_name` VARCHAR(255) NOT NULL,
  `description` TEXT DEFAULT NULL,
  
  `start_datetime` DATETIME NOT NULL,
  `end_datetime` DATETIME NOT NULL,
  
  `status` ENUM('draft', 'live', 'paused', 'ended') DEFAULT 'draft',
  `is_active` BOOLEAN DEFAULT TRUE,
  `max_violations_allowed` INT(11) DEFAULT 5,
  `current_round` INT(11) DEFAULT 1,
  
  `created_by` INT(11) DEFAULT NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  
  PRIMARY KEY (`contest_id`),
  KEY `active_status` (`is_active`),
  CONSTRAINT `fk_contests_creator` FOREIGN KEY (`created_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- 3. Rounds (Levels) Table
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `rounds` (
  `round_id` INT(11) NOT NULL AUTO_INCREMENT,
  `contest_id` INT(11) NOT NULL,
  `round_name` VARCHAR(100) NOT NULL,
  `round_number` INT(11) NOT NULL,
  
  `time_limit_minutes` INT(11) NOT NULL,
  `total_questions` INT(11) NOT NULL,
  `passing_score` DECIMAL(5,2) DEFAULT NULL,
  
  `status` ENUM('pending', 'active', 'completed') DEFAULT 'pending',
  `is_locked` BOOLEAN DEFAULT TRUE,
  `unlock_condition` TEXT DEFAULT NULL,
  
  `allowed_language` VARCHAR(50) DEFAULT 'python', -- Added for Language Restriction
  
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  
  PRIMARY KEY (`round_id`),
  UNIQUE KEY `contest_round` (`contest_id`, `round_number`),
  CONSTRAINT `fk_rounds_contest` FOREIGN KEY (`contest_id`) REFERENCES `contests` (`contest_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- 4. Questions Table
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `questions` (
  `question_id` INT(11) NOT NULL AUTO_INCREMENT,
  `round_id` INT(11) NOT NULL,
  `question_number` INT(11) NOT NULL,
  
  `question_title` VARCHAR(500) NOT NULL,
  `question_description` TEXT NOT NULL,
  `buggy_code` TEXT NOT NULL,
  
  `expected_output` TEXT DEFAULT NULL,
  `test_input` TEXT DEFAULT NULL,
  `test_cases` JSON DEFAULT NULL,
  `difficulty_level` ENUM('easy', 'medium', 'hard') NOT NULL,
  
  `points` INT(11) DEFAULT 10,
  `hints` TEXT DEFAULT NULL,
  `time_estimate_minutes` INT(11) DEFAULT NULL,
  
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  
  PRIMARY KEY (`question_id`),
  UNIQUE KEY `round_question` (`round_id`, `question_number`),
  CONSTRAINT `fk_questions_round` FOREIGN KEY (`round_id`) REFERENCES `rounds` (`round_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- 5. Submissions Table (Results)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `submissions` (
  `submission_id` INT(11) NOT NULL AUTO_INCREMENT,
  `user_id` INT(11) NOT NULL,
  `contest_id` INT(11) NOT NULL,
  `round_id` INT(11) NOT NULL,
  `question_id` INT(11) NOT NULL,
  
  `submitted_code` TEXT DEFAULT NULL,
  `is_correct` BOOLEAN DEFAULT NULL,
  `score_awarded` DECIMAL(5,2) DEFAULT 0.00,
  `test_results` JSON DEFAULT NULL,
  
  `status` ENUM('pending', 'evaluated', 'failed') NOT NULL DEFAULT 'pending',
  `time_taken_seconds` INT(11) DEFAULT NULL,
  `submission_timestamp` DATETIME DEFAULT CURRENT_TIMESTAMP,
  
  PRIMARY KEY (`submission_id`),
  KEY `participant_contest` (`user_id`, `contest_id`),
  CONSTRAINT `fk_sub_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_sub_question` FOREIGN KEY (`question_id`) REFERENCES `questions` (`question_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_sub_round` FOREIGN KEY (`round_id`) REFERENCES `rounds` (`round_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_sub_contest` FOREIGN KEY (`contest_id`) REFERENCES `contests` (`contest_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- 6. Participant Level Stats (Progress)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `participant_level_stats` (
  `stat_id` INT(11) NOT NULL AUTO_INCREMENT,
  `user_id` INT(11) NOT NULL,
  `contest_id` INT(11) NOT NULL,
  `level` INT(11) NOT NULL, -- matches rounds.round_number
  
  `status` ENUM('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED') DEFAULT 'NOT_STARTED',
  `questions_solved` INT DEFAULT 0,
  `level_score` DECIMAL(5,2) DEFAULT 0.00,
  `violation_count` INT(11) DEFAULT 0,
  
  `start_time` DATETIME DEFAULT NULL,
  `completed_at` DATETIME DEFAULT NULL,
  `run_count` INT DEFAULT 0,
  
  PRIMARY KEY (`stat_id`),
  UNIQUE KEY `user_contest_level` (`user_id`, `contest_id`, `level`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- 7. Proctoring Configuration
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `proctoring_config` (
  `id` VARCHAR(36) NOT NULL,
  `contest_id` INT(11) NOT NULL,
  
  `enabled` BOOLEAN DEFAULT TRUE,
  `max_violations` INT(11) DEFAULT 10,
  `auto_disqualify` BOOLEAN DEFAULT TRUE,
  `warning_threshold` INT(11) DEFAULT 5,
  `grace_violations` INT(11) DEFAULT 2,
  `strict_mode` BOOLEAN DEFAULT FALSE,
  
  -- Monitoring Settings
  `track_tab_switches` BOOLEAN DEFAULT TRUE,
  `track_focus_loss` BOOLEAN DEFAULT TRUE,
  `block_copy` BOOLEAN DEFAULT TRUE,
  `block_paste` BOOLEAN DEFAULT TRUE,
  `block_cut` BOOLEAN DEFAULT TRUE,
  `block_selection` BOOLEAN DEFAULT FALSE,
  `block_right_click` BOOLEAN DEFAULT TRUE,
  `detect_screenshot` BOOLEAN DEFAULT TRUE,
  
  -- Penalties
  `tab_switch_penalty` INT(11) DEFAULT 1,
  `copy_paste_penalty` INT(11) DEFAULT 2,
  `screenshot_penalty` INT(11) DEFAULT 3,
  `focus_loss_penalty` INT(11) DEFAULT 1,
  
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  
  PRIMARY KEY (`id`),
  UNIQUE KEY `contest_config` (`contest_id`),
  CONSTRAINT `fk_pc_contest` FOREIGN KEY (`contest_id`) REFERENCES `contests` (`contest_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- 8. Participant Proctoring Status (Global Risk State)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `participant_proctoring` (
  `id` VARCHAR(36) NOT NULL,
  `participant_id` VARCHAR(100) DEFAULT NULL, -- Keeps sync with legacy usage (Username)
  `user_id` INT(11) DEFAULT NULL, -- Linked FK
  `contest_id` INT(11) NOT NULL,
  
  `risk_level` ENUM('low', 'medium', 'high', 'critical') DEFAULT 'low',
  `total_violations` INT(11) DEFAULT 0,
  `violation_score` INT(11) DEFAULT 0,
  `extra_violations` INT DEFAULT 0,
  
  -- Status Flags
  `is_disqualified` BOOLEAN DEFAULT FALSE,
  `disqualified_at` DATETIME DEFAULT NULL,
  `disqualification_reason` TEXT DEFAULT NULL,
  
  `is_suspended` BOOLEAN DEFAULT FALSE,
  `suspended_at` DATETIME DEFAULT NULL,
  `suspension_reason` TEXT DEFAULT NULL,

  -- Live Monitoring
  `last_heartbeat` DATETIME DEFAULT NULL,
  `client_ip` VARCHAR(45) DEFAULT NULL,
  
  -- Violation Counts Breakdown
  `tab_switches` INT(11) DEFAULT 0,
  `focus_losses` INT(11) DEFAULT 0,
  `copy_attempts` INT(11) DEFAULT 0,
  `paste_attempts` INT(11) DEFAULT 0,
  `screenshot_attempts` INT(11) DEFAULT 0,
  
  `last_violation_at` DATETIME DEFAULT NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  
  PRIMARY KEY (`id`),
  UNIQUE KEY `participant_contest` (`participant_id`, `contest_id`),
  CONSTRAINT `fk_pp_contest` FOREIGN KEY (`contest_id`) REFERENCES `contests` (`contest_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_pp_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- 9. Violations Log (Detailed)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `violations` (
  `violation_id` INT(11) NOT NULL AUTO_INCREMENT,
  `user_id` INT(11) NOT NULL,
  `contest_id` INT(11) NOT NULL,
  `round_id` INT(11) DEFAULT NULL,
  `question_id` INT(11) DEFAULT NULL,
  
  `violation_type` VARCHAR(50) NOT NULL,
  `description` TEXT DEFAULT NULL, -- Matching code expectation
  `severity` ENUM('low', 'medium', 'high', 'critical') NOT NULL DEFAULT 'medium',
  `penalty_points` INT DEFAULT 1,
  
  `level` INT(11) DEFAULT 1,
  `ip_address` VARCHAR(45) DEFAULT NULL,
  `timestamp` DATETIME DEFAULT CURRENT_TIMESTAMP, -- Matching code expectation
  
  PRIMARY KEY (`violation_id`),
  KEY `tracking_index` (`user_id`, `contest_id`),
  CONSTRAINT `fk_v_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_v_contest` FOREIGN KEY (`contest_id`) REFERENCES `contests` (`contest_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- 10. Proctoring Logs (Audit Trail - Unused by code but kept)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `proctoring_logs` (
  `id` VARCHAR(36) NOT NULL,
  `contest_id` INT(11) DEFAULT NULL,
  `user_id` INT(11) DEFAULT NULL,
  `participant_id` VARCHAR(100) DEFAULT NULL,
  
  `action_type` VARCHAR(50) NOT NULL,
  `action_by` VARCHAR(100) DEFAULT NULL,
  `details` JSON DEFAULT NULL,
  `timestamp` DATETIME DEFAULT CURRENT_TIMESTAMP,
  
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- 11. Shortlisted Participants (Level Gatekeeping)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `shortlisted_participants` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `contest_id` INT NOT NULL,
    `user_id` INT NOT NULL,
    `level` INT NOT NULL,
    `is_allowed` BOOLEAN DEFAULT TRUE,
    UNIQUE KEY `sl_user` (`contest_id`, `level`, `user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------
-- 12. Leaderboard
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `leaderboard` (
  `leaderboard_id` INT(11) NOT NULL AUTO_INCREMENT,
  `user_id` INT(11) NOT NULL,
  `contest_id` INT(11) NOT NULL,
  
  `rank_position` INT(11) DEFAULT NULL,
  `total_score` DECIMAL(7,2) DEFAULT 0.00,
  `total_time_taken_seconds` INT(11) DEFAULT 0,
  
  `questions_attempted` INT(11) DEFAULT 0,
  `questions_correct` INT(11) DEFAULT 0,
  `violations_count` INT(11) DEFAULT 0,
  `current_round` INT(11) DEFAULT 1,
  
  `last_updated` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  
  PRIMARY KEY (`leaderboard_id`),
  UNIQUE KEY `user_contest_unique` (`user_id`, `contest_id`),
  CONSTRAINT `fk_lb_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_lb_contest` FOREIGN KEY (`contest_id`) REFERENCES `contests` (`contest_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- 13. Admin Key-Value State
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `admin_state` (
    `key_name` VARCHAR(100) NOT NULL PRIMARY KEY,
    `value` TEXT,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------
-- 14. Proctoring Alerts
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `proctoring_alerts` (
  `id` INT(11) NOT NULL AUTO_INCREMENT, -- Changed to AI because code doesn't generate UUID
  `contest_id` INT(11) NOT NULL,
  `participant_id` VARCHAR(100) DEFAULT NULL,
  
  `alert_type` VARCHAR(50) NOT NULL,
  `severity` ENUM('info', 'warning', 'critical') DEFAULT 'warning',
  `message` TEXT NOT NULL,
  
  `is_read` BOOLEAN DEFAULT FALSE,
  `read_at` DATETIME DEFAULT NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

