-- Add chart_data column to chat_messages table
-- Stores chart payloads as JSON array for persistence

ALTER TABLE chat_messages ADD COLUMN chart_data JSON NULL COMMENT 'Array of ChartPayload objects generated for this message';