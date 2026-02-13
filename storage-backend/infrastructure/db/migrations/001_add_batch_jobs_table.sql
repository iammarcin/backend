-- Migration: Add batch_jobs table for Batch API
-- Author: Storage Backend Team
-- Date: 2024-01-15

-- Up Migration
CREATE TABLE IF NOT EXISTS batch_jobs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    job_id VARCHAR(255) UNIQUE NOT NULL COMMENT 'Provider-specific batch job ID',
    customer_id INT NOT NULL COMMENT 'User who submitted the batch',
    provider VARCHAR(50) NOT NULL COMMENT 'AI provider (openai, anthropic, google)',
    model VARCHAR(100) NOT NULL COMMENT 'Model name used for batch',
    status ENUM(
        'queued',
        'processing',
        'completed',
        'failed',
        'cancelled',
        'expired'
    ) NOT NULL DEFAULT 'queued' COMMENT 'Current job status',

    -- Request counts
    request_count INT NOT NULL DEFAULT 0 COMMENT 'Total requests in batch',
    succeeded_count INT DEFAULT 0 COMMENT 'Successfully completed requests',
    failed_count INT DEFAULT 0 COMMENT 'Failed requests',
    cancelled_count INT DEFAULT 0 COMMENT 'Cancelled requests',
    expired_count INT DEFAULT 0 COMMENT 'Expired requests',

    -- Results and errors
    results_url VARCHAR(500) COMMENT 'URL to download results file',
    error_message TEXT COMMENT 'Error details if job failed',

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'When batch was submitted',
    started_at TIMESTAMP NULL COMMENT 'When processing started',
    completed_at TIMESTAMP NULL COMMENT 'When processing finished',
    expires_at TIMESTAMP NULL COMMENT 'When results expire',

    -- Additional metadata (JSON)
    metadata JSON COMMENT 'Provider-specific metadata and custom fields',

    -- Indexes for common queries
    INDEX idx_customer_id (customer_id),
    INDEX idx_provider (provider),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at),
    INDEX idx_job_id (job_id),
    INDEX idx_status_provider (status, provider),
    INDEX idx_customer_created (customer_id, created_at DESC),

    -- Foreign key to users table
    FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Tracks batch job submissions and status across AI providers';

-- Down Migration (for rollback)
-- DROP TABLE IF EXISTS batch_jobs;
