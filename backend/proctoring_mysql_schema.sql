-- proctoring_mysql_schema.sql
USE `debug_marathon`;

CREATE TABLE IF NOT EXISTS `proctoring_config` (
  `config_id` INT(11) NOT NULL AUTO_INCREMENT,
  `contest_id` INT(11) NOT NULL,
  `enabled` BOOLEAN DEFAULT TRUE,
  `max_violations` INT(11) DEFAULT 10,
  `auto_disqualify` BOOLEAN DEFAULT TRUE,
  `warning_threshold` INT(11) DEFAULT 5,
  `grace_violations` INT(11) DEFAULT 2,
  `strict_mode` BOOLEAN DEFAULT FALSE,
  `track_tab_switches` BOOLEAN DEFAULT TRUE,
  `track_focus_loss` BOOLEAN DEFAULT TRUE,
  `block_copy` BOOLEAN DEFAULT TRUE,
  `block_paste` BOOLEAN DEFAULT TRUE,
  `block_cut` BOOLEAN DEFAULT TRUE,
  `block_selection` BOOLEAN DEFAULT FALSE,
  `block_right_click` BOOLEAN DEFAULT TRUE,
  `detect_screenshot` BOOLEAN DEFAULT TRUE,
  `tab_switch_penalty` INT(11) DEFAULT 1,
  `copy_paste_penalty` INT(11) DEFAULT 2,
  `screenshot_penalty` INT(11) DEFAULT 3,
  `focus_loss_penalty` INT(11) DEFAULT 1,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`config_id`),
  UNIQUE KEY `contest_id` (`contest_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `participant_proctoring` (
  `proctoring_id` INT(11) NOT NULL AUTO_INCREMENT,
  `user_id` INT(11) NOT NULL,
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
  `tab_switches` INT(11) DEFAULT 0,
  `focus_losses` INT(11) DEFAULT 0,
  `copy_attempts` INT(11) DEFAULT 0,
  `paste_attempts` INT(11) DEFAULT 0,
  `screenshot_attempts` INT(11) DEFAULT 0,
  `last_violation_at` DATETIME DEFAULT NULL,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`proctoring_id`),
  UNIQUE KEY `user_contest` (`user_id`, `contest_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `proctoring_alerts` (
  `alert_id` INT(11) NOT NULL AUTO_INCREMENT,
  `contest_id` INT(11) NOT NULL,
  `user_id` INT(11) NOT NULL,
  `alert_type` VARCHAR(100) NOT NULL,
  `severity` ENUM('info', 'warning', 'critical') DEFAULT 'warning',
  `message` TEXT NOT NULL,
  `is_read` BOOLEAN DEFAULT FALSE,
  `read_at` DATETIME DEFAULT NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`alert_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
