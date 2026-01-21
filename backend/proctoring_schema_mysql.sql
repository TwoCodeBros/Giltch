-- Proctoring Module Schema Extension (MySQL Compatible)
-- Add this to your existing schema

-- 1. Proctoring Configuration Table
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
  
  -- Violation Penalties
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

-- 2. Participant Proctoring Status
CREATE TABLE IF NOT EXISTS `participant_proctoring` (
  `id` VARCHAR(36) NOT NULL,
  `participant_id` VARCHAR(100) DEFAULT NULL, -- Can be username or logic mapping
  `user_id` INT(11) DEFAULT NULL, -- Use proper foreign key
  `contest_id` INT(11) NOT NULL,
  
  `total_violations` INT(11) DEFAULT 0,
  `violation_score` INT(11) DEFAULT 0,
  `risk_level` ENUM('low', 'medium', 'high', 'critical') DEFAULT 'low',
  
  `is_disqualified` BOOLEAN DEFAULT FALSE,
  `disqualified_at` DATETIME DEFAULT NULL,
  `disqualification_reason` TEXT DEFAULT NULL,
  
  `is_suspended` BOOLEAN DEFAULT FALSE,
  `suspended_at` DATETIME DEFAULT NULL,
  `suspension_reason` TEXT DEFAULT NULL,
  
  `extra_violations` INT DEFAULT 0,
  
  -- Activity Tracking
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
  CONSTRAINT `fk_pp_contest` FOREIGN KEY (`contest_id`) REFERENCES `contests` (`contest_id`) ON DELETE CASCADE
  -- Note: We generally lack a rigid FK to users here because participant_id might be used loosely, but adding user_id link is safer
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Proctoring Logs (Audit Trail)
CREATE TABLE IF NOT EXISTS `proctoring_logs` (
  `id` VARCHAR(36) NOT NULL,
  `contest_id` INT(11) DEFAULT NULL,
  `participant_id` VARCHAR(100) DEFAULT NULL,
  `user_id` INT(11) DEFAULT NULL,
  
  `action_type` VARCHAR(50) NOT NULL,
  `action_by` VARCHAR(100) DEFAULT NULL,
  
  `details` JSON DEFAULT NULL,
  `timestamp` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Proctoring Alerts
CREATE TABLE IF NOT EXISTS `proctoring_alerts` (
  `id` VARCHAR(36) NOT NULL,
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
