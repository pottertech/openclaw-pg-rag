-- Migration: pg-vault-rag (old) → openclaw-pg-rag (new)
-- Run this in psql or n8n PostgreSQL node

-- Step 1: Create new tables if not exists
CREATE TABLE IF NOT EXISTS raw_documents (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    file_path TEXT,
    file_type TEXT,
    file_size INTEGER,
    content TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES raw_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER,
    content TEXT NOT NULL,
    embedding VECTOR(1024),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING ivfflat (embedding vector_cosine_ops);

-- Step 2: Migrate data from old rag_documents table
-- This creates one document entry per unique source file
-- and links all chunks to it

DO $$
DECLARE
    old_record RECORD;
    new_doc_id INTEGER;
    extracted_filename TEXT;
    extracted_path TEXT;
BEGIN
    -- Check if old table exists
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'rag_documents') THEN
        
        -- Migrate each unique document
        FOR old_record IN 
            SELECT DISTINCT ON (COALESCE(metadata->>'filename', 'unknown')) 
                id,
                content,
                embedding,
                metadata,
                created_at
            FROM rag_documents
            ORDER BY COALESCE(metadata->>'filename', 'unknown'), id
        LOOP
            -- Extract filename from metadata or use default
            extracted_filename := COALESCE(old_record.metadata->>'filename', 'migrated_' || old_record.id || '.txt');
            extracted_path := COALESCE(old_record.metadata->>'file_path', '/migrated');
            
            -- Insert into raw_documents table
            INSERT INTO raw_documents (
                filename,
                file_path,
                file_type,
                file_size,
                content,
                metadata,
                created_at
            ) VALUES (
                extracted_filename,
                extracted_path,
                COALESCE(old_record.metadata->>'file_type', 'text/plain'),
                COALESCE((old_record.metadata->>'file_size')::INTEGER, LENGTH(old_record.content)),
                old_record.content,  -- Store full content
                old_record.metadata,
                COALESCE(old_record.created_at, NOW())
            )
            RETURNING id INTO new_doc_id;
            
            -- Now insert all chunks for this document
            INSERT INTO chunks (
                document_id,
                chunk_index,
                content,
                embedding,
                metadata,
                created_at
            )
            SELECT 
                new_doc_id,
                ROW_NUMBER() OVER (ORDER BY id) - 1 as chunk_index,
                content,
                embedding,
                metadata,
                created_at
            FROM rag_documents
            WHERE COALESCE(metadata->>'filename', 'unknown') = extracted_filename
            ORDER BY id;
            
        END LOOP;
        
        RAISE NOTICE 'Migration complete. Check raw_documents and chunks tables.';
    ELSE
        RAISE NOTICE 'Old table rag_documents not found. New tables created.';
    END IF;
END $$;

-- Step 3: Verify migration
SELECT 
    'raw_documents' as table_name, 
    COUNT(*) as count 
FROM raw_documents
UNION ALL
SELECT 
    'chunks' as table_name, 
    COUNT(*) as count 
FROM chunks
UNION ALL
SELECT 
    'Old rag_documents' as table_name, 
    COUNT(*) as count 
FROM rag_documents;

-- Step 4: Rename old table to backup (preserves data)
ALTER TABLE IF EXISTS rag_documents RENAME TO rag_documents_backup;

-- Step 5: Rename chunks to rag_documents (replaces old table with new structure)
ALTER TABLE chunks RENAME TO rag_documents;

-- Step 6: Update foreign key reference (now references raw_documents)
-- Note: The document_id column now references raw_documents(id)
-- This maintains the link between chunks and their parent raw_documents