-- Migration: Add task metadata columns to ChatSessionsNG
-- Phase 2, Step 4a: Sessions can be "promoted" to tasks with status, priority, description
-- Author: BetterAI Team
-- Date: 2026-02-10

-- Idempotent: Check if columns exist before adding

-- Add task_status column
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'ChatSessionsNG'
    AND COLUMN_NAME = 'task_status'
    AND TABLE_SCHEMA = DATABASE()
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE ChatSessionsNG ADD COLUMN task_status ENUM(''active'', ''waiting'', ''done'') DEFAULT NULL',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add task_priority column
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'ChatSessionsNG'
    AND COLUMN_NAME = 'task_priority'
    AND TABLE_SCHEMA = DATABASE()
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE ChatSessionsNG ADD COLUMN task_priority ENUM(''high'', ''medium'', ''low'') DEFAULT NULL',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add task_description column
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'ChatSessionsNG'
    AND COLUMN_NAME = 'task_description'
    AND TABLE_SCHEMA = DATABASE()
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE ChatSessionsNG ADD COLUMN task_description VARCHAR(500) DEFAULT NULL',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add index on task_status
SET @idx_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_NAME = 'ChatSessionsNG'
    AND INDEX_NAME = 'idx_task_status'
    AND TABLE_SCHEMA = DATABASE()
);
SET @sql = IF(@idx_exists = 0,
    'ALTER TABLE ChatSessionsNG ADD INDEX idx_task_status (task_status)',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add composite index on (ai_character_name, task_status)
SET @idx_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_NAME = 'ChatSessionsNG'
    AND INDEX_NAME = 'idx_agent_task'
    AND TABLE_SCHEMA = DATABASE()
);
SET @sql = IF(@idx_exists = 0,
    'ALTER TABLE ChatSessionsNG ADD INDEX idx_agent_task (ai_character_name, task_status)',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Down Migration (for rollback)
-- ALTER TABLE ChatSessionsNG DROP INDEX idx_agent_task;
-- ALTER TABLE ChatSessionsNG DROP INDEX idx_task_status;
-- ALTER TABLE ChatSessionsNG DROP COLUMN task_description;
-- ALTER TABLE ChatSessionsNG DROP COLUMN task_priority;
-- ALTER TABLE ChatSessionsNG DROP COLUMN task_status;
