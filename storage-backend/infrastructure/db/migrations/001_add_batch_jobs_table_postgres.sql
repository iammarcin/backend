-- Migration: Add batch_jobs table for Batch API (PostgreSQL/Supabase)
-- Author: Storage Backend Team
-- Date: 2024-01-15
-- Updated: 2026-01-10 (PostgreSQL version)

-- Up Migration
CREATE TABLE IF NOT EXISTS batch_jobs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(255) UNIQUE NOT NULL,
    customer_id INT NOT NULL,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'processing', 'completed', 'failed', 'cancelled', 'expired')),

    -- Request counts
    request_count INT NOT NULL DEFAULT 0,
    succeeded_count INT DEFAULT 0,
    failed_count INT DEFAULT 0,
    cancelled_count INT DEFAULT 0,
    expired_count INT DEFAULT 0,

    -- Results and errors
    results_url VARCHAR(500),
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,

    -- Additional metadata (JSONB for better PostgreSQL performance)
    metadata JSONB,

    -- Foreign key to Users table
    CONSTRAINT fk_batch_jobs_customer
        FOREIGN KEY (customer_id) REFERENCES "Users"(customer_id) ON DELETE CASCADE
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_batch_jobs_job_id ON batch_jobs(job_id);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_customer_id ON batch_jobs(customer_id);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_provider ON batch_jobs(provider);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_status ON batch_jobs(status);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_created_at ON batch_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_status_provider ON batch_jobs(status, provider);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_customer_created ON batch_jobs(customer_id, created_at DESC);

-- Add comment to table
COMMENT ON TABLE batch_jobs IS 'Tracks batch job submissions and status across AI providers';

-- Down Migration (for rollback)
-- DROP TABLE IF EXISTS batch_jobs;
