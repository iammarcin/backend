-- Migration: Add proactive agent tables for Sherlock AI assistant
-- Author: BetterAI Team
-- Date: 2025-12-11

-- Up Migration

-- Sessions table for proactive agent conversations
CREATE TABLE IF NOT EXISTS proactive_agent_sessions (
    id VARCHAR(36) PRIMARY KEY COMMENT 'UUID session identifier',
    user_id INT NOT NULL COMMENT 'Owner user ID',
    claude_session_id VARCHAR(255) NULL COMMENT 'Claude Code session ID for continuity',
    character_name VARCHAR(50) NOT NULL DEFAULT 'sherlock' COMMENT 'Character persona name',
    is_active BOOLEAN DEFAULT TRUE COMMENT 'Session active status',
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Last interaction timestamp',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Session creation timestamp',

    -- Indexes for common queries
    INDEX idx_proactive_session_user (user_id, is_active),
    INDEX idx_proactive_session_activity (last_activity),

    -- Foreign key to users table
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Proactive agent conversation sessions (Sherlock)';


-- Messages table for proactive agent conversations
CREATE TABLE IF NOT EXISTS proactive_agent_messages (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'Auto-increment message ID',
    session_id VARCHAR(36) NOT NULL COMMENT 'Parent session ID',
    direction ENUM('user_to_agent', 'agent_to_user', 'heartbeat') NOT NULL COMMENT 'Message direction',
    content TEXT NOT NULL COMMENT 'Message text content',
    source VARCHAR(50) NULL COMMENT 'Message source: text, audio_transcription, heartbeat',
    is_heartbeat_ok BOOLEAN DEFAULT FALSE COMMENT 'Was this a suppressed HEARTBEAT_OK',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Message creation timestamp',

    -- Indexes for common queries
    INDEX idx_proactive_message_session_created (session_id, created_at),
    INDEX idx_proactive_message_direction (direction),

    -- Foreign key to sessions table
    FOREIGN KEY (session_id) REFERENCES proactive_agent_sessions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Proactive agent conversation messages';


-- Down Migration (for rollback)
-- DROP TABLE IF EXISTS proactive_agent_messages;
-- DROP TABLE IF EXISTS proactive_agent_sessions;
