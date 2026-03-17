-- OpenClaw pg-RAG Schema
-- Creates the correct tables for the pg-rag CLI
-- Run: psql -d openclaw_pg_rag -f migrate.sql

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create rag_folders table first (referenced by rag_documents)
CREATE TABLE IF NOT EXISTS rag_folders (
    id BIGSERIAL PRIMARY KEY,
    folder_id TEXT UNIQUE NOT NULL,
    location TEXT NOT NULL,
    location_type TEXT DEFAULT 'google-drive',
    status TEXT DEFAULT 'active',
    auto_ingest BOOLEAN DEFAULT false,
    min_age_hours INTEGER DEFAULT 24,
    min_stable_hours INTEGER DEFAULT 4,
    last_scan TIMESTAMP WITH TIME ZONE,
    last_scan_count INTEGER,
    last_scan_files INTEGER,
    registered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    owner TEXT DEFAULT 'skip',
    shared_with TEXT[] DEFAULT ARRAY['brodie', 'arty'],
    metadata JSONB DEFAULT '{}',
    notes TEXT
);

-- Create rag_documents table
CREATE TABLE IF NOT EXISTS rag_documents (
    id BIGSERIAL PRIMARY KEY,
    document_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    source_uri TEXT,
    source_type TEXT DEFAULT 'google-drive',
    mime_type TEXT,
    checksum TEXT,
    raw_markdown TEXT,
    content TEXT,
    metadata_json JSONB DEFAULT '{}',
    folder_id TEXT REFERENCES rag_folders(folder_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    indexed_at TIMESTAMP WITH TIME ZONE
);

-- Create rag_document_chunks table
CREATE TABLE IF NOT EXISTS rag_document_chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES rag_documents(document_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    section_title TEXT,
    page_number INTEGER,
    embedding VECTOR(1024),
    metadata_json JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_documents_document_id ON rag_documents(document_id);
CREATE INDEX IF NOT EXISTS idx_documents_folder ON rag_documents(folder_id);
CREATE INDEX IF NOT EXISTS idx_documents_created ON rag_documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_source ON rag_documents(source_type);
CREATE INDEX IF NOT EXISTS idx_documents_fts ON rag_documents 
    USING gin(to_tsvector('english', COALESCE(raw_markdown, '') || ' ' || COALESCE(title, '')));

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON rag_document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON rag_document_chunks 
    USING ivfflat (embedding vector_cosine_ops);

-- Create trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_rag_documents_updated_at ON rag_documents;
CREATE TRIGGER update_rag_documents_updated_at
    BEFORE UPDATE ON rag_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create folder_summary view
CREATE OR REPLACE VIEW folder_summary AS
SELECT 
    f.folder_id,
    f.location,
    f.status,
    f.last_scan,
    COUNT(d.id) as document_count,
    COUNT(d.id) FILTER (WHERE d.indexed_at IS NOT NULL) as indexed_count
FROM rag_folders f
LEFT JOIN rag_documents d ON f.folder_id = d.folder_id
GROUP BY f.folder_id, f.location, f.status, f.last_scan;

-- Insert default folder if not exists
INSERT INTO rag_folders (folder_id, location, location_type, status, notes)
VALUES ('d6q2qtr24teau8j24teg', 'Google Drive /Files', 'google-drive', 'active', 'Default RAG folder')
ON CONFLICT (folder_id) DO NOTHING;

-- Verify setup
SELECT 'Schema created successfully!' as status;
SELECT COUNT(*) as folder_count FROM rag_folders;
SELECT COUNT(*) as document_count FROM rag_documents;
SELECT COUNT(*) as chunk_count FROM rag_document_chunks;
