-- debug_marathon_schema.sql
-- Production-ready MySQL Schema for Debug Marathon Proctoring Assessment System
-- Target: XAMPP MySQl (Localhost)

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";

-- Set Character Set
/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

-- Database: `debug_marathon`
-- Database Selection handled by connection/script

-- --------------------------------------------------------
-- 1. users Table
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `users` (
  `user_id` INT(11) NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(50) NOT NULL,
  `email` VARCHAR(100) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `full_name` VARCHAR(100) DEFAULT NULL,
  `role` ENUM('participant', 'admin') NOT NULL DEFAULT 'participant',
  `registration_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `last_login` DATETIME DEFAULT NULL,
  `is_active` BOOLEAN DEFAULT TRUE,
  `status` ENUM('active', 'disqualified', 'held', 'suspended') DEFAULT 'active',
  `admin_status` ENUM('PENDING', 'APPROVED', 'REJECTED') DEFAULT 'PENDING',
  `approved_by` INT DEFAULT NULL,
  `approval_at` DATETIME DEFAULT NULL,
  `profile_image` VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`),
  KEY `role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- 2. contests Table
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `contests` (
  `contest_id` INT(11) NOT NULL AUTO_INCREMENT,
  `contest_name` VARCHAR(255) NOT NULL,
  `description` TEXT DEFAULT NULL,
  `start_datetime` DATETIME NOT NULL,
  `end_datetime` DATETIME NOT NULL,
  `created_by` INT(11) DEFAULT NULL,
  `is_active` BOOLEAN DEFAULT TRUE,
  `status` ENUM('draft', 'live', 'paused', 'ended') DEFAULT 'draft',
  `max_violations_allowed` INT(11) DEFAULT 5,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`contest_id`),
  KEY `active_status` (`is_active`),
  CONSTRAINT `fk_contests_creator` FOREIGN KEY (`created_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- 3. rounds Table
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `rounds` (
  `round_id` INT(11) NOT NULL AUTO_INCREMENT,
  `contest_id` INT(11) NOT NULL,
  `round_name` VARCHAR(100) NOT NULL,
  `round_number` INT(11) NOT NULL,
  `time_limit_minutes` INT(11) NOT NULL,
  `total_questions` INT(11) NOT NULL,
  `passing_score` DECIMAL(5,2) DEFAULT NULL,
  `is_locked` BOOLEAN DEFAULT TRUE,
  `status` ENUM('pending', 'active', 'completed') DEFAULT 'pending',
  `unlock_condition` TEXT DEFAULT NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`round_id`),
  UNIQUE KEY `contest_round` (`contest_id`, `round_number`),
  KEY `lock_status` (`is_locked`),
  CONSTRAINT `fk_rounds_contest` FOREIGN KEY (`contest_id`) REFERENCES `contests` (`contest_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- 4. questions Table
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `questions` (
  `question_id` INT(11) NOT NULL AUTO_INCREMENT,
  `round_id` INT(11) NOT NULL,
  `question_number` INT(11) NOT NULL,
  `question_title` VARCHAR(500) NOT NULL,
  `question_description` TEXT NOT NULL,
  `buggy_code` TEXT NOT NULL,
  `expected_output` TEXT DEFAULT NULL,
  `test_cases` JSON DEFAULT NULL,
  `hints` TEXT DEFAULT NULL,
  `difficulty_level` ENUM('easy', 'medium', 'hard') NOT NULL,
  `points` INT(11) DEFAULT 10,
  `time_estimate_minutes` INT(11) DEFAULT NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`question_id`),
  UNIQUE KEY `round_question` (`round_id`, `question_number`),
  KEY `difficulty` (`difficulty_level`),
  CONSTRAINT `fk_questions_round` FOREIGN KEY (`round_id`) REFERENCES `rounds` (`round_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- 5. submissions Table
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `submissions` (
  `submission_id` INT(11) NOT NULL AUTO_INCREMENT,
  `user_id` INT(11) NOT NULL,
  `question_id` INT(11) NOT NULL,
  `round_id` INT(11) NOT NULL,
  `contest_id` INT(11) NOT NULL,
  `submitted_code` TEXT DEFAULT NULL,
  `submission_timestamp` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `time_taken_seconds` INT(11) DEFAULT NULL,
  `is_correct` BOOLEAN DEFAULT NULL,
  `score_awarded` DECIMAL(5,2) DEFAULT 0.00,
  `test_results` JSON DEFAULT NULL,
  `status` ENUM('pending', 'evaluated', 'failed') NOT NULL DEFAULT 'pending',
  PRIMARY KEY (`submission_id`),
  KEY `participant_contest` (`user_id`, `contest_id`),
  KEY `ts_index` (`submission_timestamp`),
  CONSTRAINT `fk_sub_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_sub_question` FOREIGN KEY (`question_id`) REFERENCES `questions` (`question_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_sub_round` FOREIGN KEY (`round_id`) REFERENCES `rounds` (`round_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_sub_contest` FOREIGN KEY (`contest_id`) REFERENCES `contests` (`contest_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- 6. violations Table
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `violations` (
  `violation_id` INT(11) NOT NULL AUTO_INCREMENT,
  `user_id` INT(11) NOT NULL,
  `contest_id` INT(11) NOT NULL,
  `round_id` INT(11) NOT NULL,
  `question_id` INT(11) DEFAULT NULL,
  `violation_type` ENUM('tab_switch', 'copy_attempt', 'esc_key', 'right_click', 'screenshot', 'focus_loss', 'minimize_window', 'paste_attempt') NOT NULL,
  `violation_description` TEXT DEFAULT NULL,
  `violation_timestamp` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `severity` ENUM('low', 'medium', 'high', 'critical') NOT NULL DEFAULT 'medium',
  `ip_address` VARCHAR(45) DEFAULT NULL,
  `level` INT(11) DEFAULT 1,
  PRIMARY KEY (`violation_id`),
  KEY `tracking_index` (`user_id`, `contest_id`),
  KEY `type_index` (`violation_type`),
  KEY `ts_index` (`violation_timestamp`),
  CONSTRAINT `fk_v_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_v_contest` FOREIGN KEY (`contest_id`) REFERENCES `contests` (`contest_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_v_round` FOREIGN KEY (`round_id`) REFERENCES `rounds` (`round_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_v_question` FOREIGN KEY (`question_id`) REFERENCES `questions` (`question_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `participant_level_stats` (
  `stat_id` INT(11) NOT NULL AUTO_INCREMENT,
  `user_id` INT(11) NOT NULL,
  `contest_id` INT(11) NOT NULL,
  `level` INT(11) NOT NULL,
  `violation_count` INT(11) DEFAULT 0,
  `level_score` DECIMAL(5,2) DEFAULT 0.00,
  `completed_at` DATETIME DEFAULT NULL,
  `status` ENUM('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED') DEFAULT 'NOT_STARTED',
  `start_time` DATETIME DEFAULT NULL,
  `questions_solved` INT DEFAULT 0,
  `run_count` INT DEFAULT 0,
  PRIMARY KEY (`stat_id`),
  UNIQUE KEY `user_contest_level` (`user_id`, `contest_id`, `level`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `shortlisted_participants` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `contest_id` INT NOT NULL,
    `user_id` INT NOT NULL,
    `level` INT NOT NULL,
    `is_allowed` BOOLEAN DEFAULT TRUE,
    UNIQUE KEY `sl_user` (`contest_id`, `level`, `user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `admin_state` (
    `key_name` VARCHAR(100) NOT NULL PRIMARY KEY,
    `value` TEXT,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------
-- 7. leaderboard Table
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `leaderboard` (
  `leaderboard_id` INT(11) NOT NULL AUTO_INCREMENT,
  `user_id` INT(11) NOT NULL,
  `contest_id` INT(11) NOT NULL,
  `total_score` DECIMAL(7,2) DEFAULT 0.00,
  `total_time_taken_seconds` INT(11) DEFAULT 0,
  `questions_attempted` INT(11) DEFAULT 0,
  `questions_correct` INT(11) DEFAULT 0,
  `violations_count` INT(11) DEFAULT 0,
  `current_round` INT(11) DEFAULT 1,
  `rank_position` INT(11) DEFAULT NULL,
  `last_updated` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`leaderboard_id`),
  UNIQUE KEY `user_contest_unique` (`user_id`, `contest_id`),
  KEY `rank_index` (`rank_position`),
  KEY `score_sort` (`total_score` DESC),
  CONSTRAINT `fk_lb_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_lb_contest` FOREIGN KEY (`contest_id`) REFERENCES `contests` (`contest_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
