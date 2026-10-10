-- ==============================================================================
-- AI Developer Assistant — MySQL 8.0 Relational Database Schema
-- Charset: utf8mb4, Collation: utf8mb4_unicode_ci, Engine: InnoDB
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS `ai_developer_assistant`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE `ai_developer_assistant`;

-- ------------------------------------------------------------------------------
-- Table: users
-- Purpose: User identity, credentials, and timestamps
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `email` VARCHAR(255) NOT NULL,
    `password_hash` VARCHAR(255) NOT NULL,
    `full_name` VARCHAR(255) NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `uq_users_email` UNIQUE (`email`),
    INDEX `ix_users_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Table: projects
-- Purpose: Codebase projects owned by users or public
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `projects` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NULL,
    `name` VARCHAR(255) NOT NULL,
    `description` TEXT NULL,
    `source_type` VARCHAR(50) NOT NULL DEFAULT 'zip',
    `storage_path` VARCHAR(500) NOT NULL,
    `status` VARCHAR(50) NOT NULL DEFAULT 'pending',
    `error_message` TEXT NULL,
    `file_count` INT NOT NULL DEFAULT 0,
    `chunk_count` INT NOT NULL DEFAULT 0,
    `github_repo_url` VARCHAR(500) NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_projects_user_id`
        FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
        ON DELETE CASCADE,
    INDEX `ix_projects_user_id` (`user_id`),
    INDEX `ix_projects_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Table: project_files
-- Purpose: Indexed file paths, checksums, and metadata (no duplicate file bodies)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `project_files` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `project_id` INT NOT NULL,
    `file_path` VARCHAR(500) NOT NULL,
    `file_type` VARCHAR(50) NULL,
    `content_hash` VARCHAR(64) NULL,
    `file_size` INT NOT NULL DEFAULT 0,
    `line_count` INT NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `indexed_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_project_files_project_id`
        FOREIGN KEY (`project_id`) REFERENCES `projects` (`id`)
        ON DELETE CASCADE,
    CONSTRAINT `uq_project_file_path` UNIQUE (`project_id`, `file_path`),
    INDEX `ix_project_files_project_id` (`project_id`),
    INDEX `ix_project_files_content_hash` (`content_hash`),
    INDEX `ix_project_file_lookup` (`project_id`, `file_path`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Table: indexing_jobs
-- Purpose: Records background / async indexing status, progress and errors
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `indexing_jobs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `project_id` INT NOT NULL,
    `status` VARCHAR(50) NOT NULL DEFAULT 'pending',
    `progress_percentage` INT NOT NULL DEFAULT 0,
    `total_files` INT NOT NULL DEFAULT 0,
    `processed_files` INT NOT NULL DEFAULT 0,
    `error_message` TEXT NULL,
    `started_at` DATETIME NULL,
    `completed_at` DATETIME NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_indexing_jobs_project_id`
        FOREIGN KEY (`project_id`) REFERENCES `projects` (`id`)
        ON DELETE CASCADE,
    INDEX `ix_indexing_jobs_project_id` (`project_id`),
    INDEX `ix_indexing_jobs_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Table: conversations
-- Purpose: Chat sessions scoped to a project and user
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `conversations` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `project_id` INT NOT NULL,
    `user_id` INT NULL,
    `title` VARCHAR(255) NOT NULL DEFAULT 'Codebase Discussion',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_conversations_project_id`
        FOREIGN KEY (`project_id`) REFERENCES `projects` (`id`)
        ON DELETE CASCADE,
    CONSTRAINT `fk_conversations_user_id`
        FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
        ON DELETE CASCADE,
    INDEX `ix_conversations_project_id` (`project_id`),
    INDEX `ix_conversations_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Table: messages
-- Purpose: Dialog turns within a conversation (user, assistant, system)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `messages` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `conversation_id` INT NOT NULL,
    `role` VARCHAR(50) NOT NULL,
    `content` LONGTEXT NOT NULL,
    `metadata_json` TEXT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_messages_conversation_id`
        FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`)
        ON DELETE CASCADE,
    INDEX `ix_messages_conversation_id` (`conversation_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Table: message_citations
-- Purpose: Grounded line range citations associated with assistant messages
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `message_citations` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `message_id` INT NOT NULL,
    `file_path` VARCHAR(500) NOT NULL,
    `start_line` INT NOT NULL,
    `end_line` INT NOT NULL,
    `snippet` TEXT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_message_citations_message_id`
        FOREIGN KEY (`message_id`) REFERENCES `messages` (`id`)
        ON DELETE CASCADE,
    INDEX `ix_message_citations_message_id` (`message_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Table: github_imports
-- Purpose: Tracks metadata, sync state, and indexing metrics for imported GitHub repositories
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `github_imports` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `project_id` INT NOT NULL,
    `repo_url` VARCHAR(500) NOT NULL,
    `owner` VARCHAR(255) NOT NULL,
    `repo_name` VARCHAR(255) NOT NULL,
    `full_name` VARCHAR(511) NOT NULL,
    `default_branch` VARCHAR(255) NULL,
    `commit_sha` VARCHAR(40) NULL,
    `import_status` VARCHAR(50) NOT NULL DEFAULT 'pending',
    `error_message` TEXT NULL,
    `error_code` VARCHAR(50) NULL,
    `extracted_files` INT NOT NULL DEFAULT 0,
    `indexed_chunks` INT NOT NULL DEFAULT 0,
    `description` TEXT NULL,
    `html_url` VARCHAR(500) NULL,
    `stars` INT NOT NULL DEFAULT 0,
    `is_private` TINYINT(1) NOT NULL DEFAULT 0,
    `language` VARCHAR(100) NULL,
    `started_at` DATETIME NULL,
    `completed_at` DATETIME NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_github_imports_project_id`
        FOREIGN KEY (`project_id`) REFERENCES `projects` (`id`)
        ON DELETE CASCADE,
    CONSTRAINT `uq_github_imports_project_id` UNIQUE (`project_id`),
    INDEX `ix_github_imports_project_id` (`project_id`),
    INDEX `ix_github_imports_import_status` (`import_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

