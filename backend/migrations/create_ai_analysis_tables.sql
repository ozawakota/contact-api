-- Next-Generation Support System - AI Analysis Tables Migration
-- Contact AI Analysis and Vector Storage Tables with pgvector Integration
-- 
-- This migration creates the foundational database schema for AI-powered
-- customer support automation including vector similarity search capabilities.

-- Enable pgvector extension for high-performance vector operations
CREATE EXTENSION IF NOT EXISTS vector;

-- Ensure contacts table exists (should already exist from base setup)
-- This is a safety check for dependency validation
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'contacts') THEN
        RAISE EXCEPTION 'contacts table must exist before creating AI analysis tables';
    END IF;
END $$;

-- Create contact_ai_analyses table for storing AI analysis results
-- Features: Category classification, urgency levels, sentiment analysis, confidence scoring
CREATE TABLE IF NOT EXISTS contact_ai_analyses (
    id SERIAL PRIMARY KEY,
    
    -- Foreign key relationship with contacts (1:1)
    contact_id INTEGER NOT NULL UNIQUE,
    
    -- AI Analysis Results from Gemini Function Calling
    category VARCHAR(20) CHECK (category IN ('shipping', 'product', 'billing', 'other')),
    urgency INTEGER CHECK (urgency IN (1, 2, 3)),
    sentiment VARCHAR(20) CHECK (sentiment IN ('positive', 'neutral', 'negative')),
    confidence_score DECIMAL(3,2) CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    summary VARCHAR(30),  -- 30-character AI-generated summary
    reasoning TEXT,       -- AI decision rationale and explanation
    
    -- Processing metadata
    processed_at TIMESTAMP,
    
    -- Timestamp management
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraint with CASCADE delete
    CONSTRAINT fk_contact_ai_analyses_contact_id 
        FOREIGN KEY (contact_id) 
        REFERENCES contacts(id) 
        ON DELETE CASCADE,
    
    -- Unique constraint for 1:1 relationship
    CONSTRAINT uq_contact_ai_analyses_contact_id UNIQUE (contact_id),
    
    -- Additional validation constraints
    CONSTRAINT ck_summary_length CHECK (LENGTH(summary) <= 30)
);

-- Create contact_vectors table for RAG (Retrieval-Augmented Generation) search
-- Features: 768-dimension vector embeddings, HNSW indexing, metadata tracking
CREATE TABLE IF NOT EXISTS contact_vectors (
    id SERIAL PRIMARY KEY,
    
    -- Foreign key relationship with contacts (1:1)
    contact_id INTEGER NOT NULL UNIQUE,
    
    -- pgvector 768-dimension embedding field (standard for Gemini models)
    embedding vector(768) NOT NULL,
    
    -- Metadata fields for model tracking and quality control
    model_version VARCHAR(50) NOT NULL,  -- e.g., "gemini-pro-1.5"
    metadata JSONB,                      -- Additional processing metadata
    vectorized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Timestamp management
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraint with CASCADE delete
    CONSTRAINT fk_contact_vectors_contact_id 
        FOREIGN KEY (contact_id) 
        REFERENCES contacts(id) 
        ON DELETE CASCADE,
    
    -- Unique constraint for 1:1 relationship
    CONSTRAINT uq_contact_vectors_contact_id UNIQUE (contact_id)
);

-- Create HNSW index for high-performance cosine similarity search
-- Configuration optimized for production workloads based on pgvector 0.8.0 best practices
-- m=16: Maximum connections per layer (balance between accuracy and memory)
-- ef_construction=64: Search candidates during index construction (build quality)
CREATE INDEX IF NOT EXISTS idx_contact_vectors_embedding_hnsw 
ON contact_vectors 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Performance optimization indexes for frequent query patterns

-- contact_ai_analyses performance indexes
CREATE INDEX IF NOT EXISTS idx_contact_ai_analyses_category 
ON contact_ai_analyses (category);

CREATE INDEX IF NOT EXISTS idx_contact_ai_analyses_urgency 
ON contact_ai_analyses (urgency);

CREATE INDEX IF NOT EXISTS idx_contact_ai_analyses_sentiment 
ON contact_ai_analyses (sentiment);

CREATE INDEX IF NOT EXISTS idx_contact_ai_analyses_created_at 
ON contact_ai_analyses (created_at);

CREATE INDEX IF NOT EXISTS idx_contact_ai_analyses_processed_at 
ON contact_ai_analyses (processed_at);

-- Composite index for common filtering patterns (category + urgency)
CREATE INDEX IF NOT EXISTS idx_contact_ai_analyses_category_urgency 
ON contact_ai_analyses (category, urgency);

-- Index for unprocessed items (NULL processed_at)
CREATE INDEX IF NOT EXISTS idx_contact_ai_analyses_unprocessed 
ON contact_ai_analyses (processed_at) 
WHERE processed_at IS NULL;

-- contact_vectors performance indexes
CREATE INDEX IF NOT EXISTS idx_contact_vectors_model_version 
ON contact_vectors (model_version);

CREATE INDEX IF NOT EXISTS idx_contact_vectors_vectorized_at 
ON contact_vectors (vectorized_at);

CREATE INDEX IF NOT EXISTS idx_contact_vectors_created_at 
ON contact_vectors (created_at);

-- JSONB metadata index for metadata queries (GIN index for JSONB operations)
CREATE INDEX IF NOT EXISTS idx_contact_vectors_metadata 
ON contact_vectors USING GIN (metadata);

-- Update triggers for automatic timestamp management
-- contact_ai_analyses update trigger
CREATE OR REPLACE FUNCTION update_contact_ai_analyses_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER contact_ai_analyses_updated_at_trigger
    BEFORE UPDATE ON contact_ai_analyses
    FOR EACH ROW EXECUTE FUNCTION update_contact_ai_analyses_updated_at();

-- contact_vectors update trigger  
CREATE OR REPLACE FUNCTION update_contact_vectors_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER contact_vectors_updated_at_trigger
    BEFORE UPDATE ON contact_vectors
    FOR EACH ROW EXECUTE FUNCTION update_contact_vectors_updated_at();

-- Verification queries and statistics
-- These can be used to validate the migration success

-- Table existence verification
DO $$
BEGIN
    -- Verify all tables exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'contact_ai_analyses') THEN
        RAISE EXCEPTION 'contact_ai_analyses table was not created successfully';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'contact_vectors') THEN
        RAISE EXCEPTION 'contact_vectors table was not created successfully';
    END IF;
    
    -- Verify pgvector extension
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE EXCEPTION 'pgvector extension was not enabled successfully';
    END IF;
    
    RAISE NOTICE 'Migration completed successfully: AI analysis tables and indexes created';
END $$;

-- Performance optimization settings for vector operations
-- These settings optimize PostgreSQL for vector similarity search workloads

-- Increase maintenance_work_mem for index building (temporarily)
-- This helps with HNSW index construction performance
SET maintenance_work_mem = '1GB';

-- Enable parallel index building if supported
SET max_parallel_maintenance_workers = 4;

-- Index statistics update for query planner optimization
ANALYZE contact_ai_analyses;
ANALYZE contact_vectors;

-- Reset memory settings to default after index creation
RESET maintenance_work_mem;
RESET max_parallel_maintenance_workers;

-- Migration completion summary
SELECT 
    'Migration Summary' as status,
    (SELECT count(*) FROM information_schema.tables 
     WHERE table_name IN ('contact_ai_analyses', 'contact_vectors')) as tables_created,
    (SELECT count(*) FROM pg_indexes 
     WHERE tablename IN ('contact_ai_analyses', 'contact_vectors')) as indexes_created,
    (SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')) as pgvector_enabled;