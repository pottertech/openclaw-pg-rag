# Database Schema

## Tables

### rag_documents

Main document storage table.

```sql
CREATE TABLE rag_documents (
    id BIGSERIAL PRIMARY KEY,
    document_id TEXT UNIQUE NOT NULL,
    title TEXT,
    source_uri TEXT,
    source_type TEXT DEFAULT 'google-drive',
    mime_type TEXT DEFAULT 'application/pdf',
    checksum TEXT,
    notion_page_id TEXT,  -- Deprecated: Notion removed
    raw_markdown TEXT,    -- Full Markdown content with YAML front matter
    content TEXT,         -- Same as raw_markdown (for queries)
    metadata_json JSONB,  -- {tags: [...], category: "..."}
    folder_id TEXT REFERENCES rag_folders(folder_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    indexed_at TIMESTAMP WITH TIME ZONE,
    source_url TEXT,
    file_id TEXT,
    processed_at TIMESTAMP WITH TIME ZONE
);

-- Indexes
CREATE INDEX idx_rag_docs_document_id ON rag_documents(document_id);
CREATE INDEX idx_rag_docs_folder_id ON rag_documents(folder_id);
CREATE INDEX idx_rag_docs_checksum ON rag_documents(checksum);
```

### rag_document_chunks

Chunked content for semantic search with embeddings.

```sql
CREATE TABLE rag_document_chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES rag_documents(document_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    section_title TEXT,
    page_number INTEGER,
    embedding VECTOR(1024),  -- bge-m3: 1024 dimensions
    metadata_json JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_rag_chunks_document_id ON rag_document_chunks(document_id);
CREATE INDEX idx_rag_chunks_embedding ON rag_document_chunks USING ivfflat (embedding vector_cosine_ops);
```

### rag_folders

Folder registry for tracking document sources.

```sql
CREATE TABLE rag_folders (
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

-- Indexes
CREATE INDEX idx_rag_folders_folder_id ON rag_folders(folder_id);
CREATE INDEX idx_rag_folders_location ON rag_folders(location);
CREATE INDEX idx_rag_folders_status ON rag_folders(status);
```

## Setup SQL

```sql
-- Create database
CREATE DATABASE pg_vault_rag;

-- Connect to database
\c pg_vault_rag

-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Create tables (run above CREATE TABLE statements)

-- Create views
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
```

## Embedding Model

### Recommended: bge-m3

| Property | Value |
|----------|-------|
| **Model** | BAAI/bge-m3 |
| **Dimensions** | 1024 |
| **Provider** | Ollama (local) |
| **Ollama URL** | http://localhost:11434 |
| **Context Length** | 8192 tokens |

### Alternative: text-embedding-3-large

| Property | Value |
|----------|-------|
| **Model** | OpenAI text-embedding-3-large |
| **Dimensions** | 3072 (or 256 with truncation) |
| **Provider** | OpenAI API |
| **Cost** | ~$0.13 per 1M tokens |

### Chunking Strategy

```python
# Recommended settings
CHUNK_SIZE = 500       # Characters per chunk
CHUNK_OVERLAP = 100     # Overlap between chunks
MAX_CHUNKS = 50        # Per document

# For different content types:
# - Papers: 500 chars, semantic boundaries
# - Code: 300 chars, function boundaries  
# - Docs: 800 chars, section boundaries
```

### Vector Similarity Search

```sql
-- Cosine similarity search
SELECT 
    d.document_id,
    d.title,
    c.chunk_text,
    1 - (c.embedding <=> query_embedding) as similarity
FROM rag_document_chunks c
JOIN rag_documents d ON c.document_id = d.document_id
WHERE c.embedding <-> query_embedding < 0.3
ORDER BY similarity DESC
LIMIT 10;
```

## Column Purposes

### rag_documents

| Column | Purpose |
|--------|---------|
| document_id | Unique xid identifier |
| raw_markdown | Full Markdown with YAML front matter (canonical) |
| content | Alias for raw_markdown |
| metadata_json | {tags, category, ...} |
| folder_id | Source folder reference |
| indexed_at | When indexed to PostgreSQL |

### rag_document_chunks

| Column | Purpose |
|--------|---------|
| chunk_index | Position in document (0, 1, 2...) |
| chunk_text | Text content of chunk |
| embedding | 1024-dim vector (bge-m3) |
| section_title | Heading/context for chunk |

## Example Queries

```sql
-- Get full document
SELECT raw_markdown FROM rag_documents WHERE document_id = 'xid123';

-- Search content
SELECT title, source_uri 
FROM rag_documents 
WHERE raw_markdown ILIKE '%hallucination%';

-- Semantic search (with embeddings)
SELECT d.title, c.chunk_text,
       1 - (c.embedding <=> '[vec1,vec2,...]'::vector) as score
FROM rag_document_chunks c
JOIN rag_documents d ON c.document_id = d.document_id
ORDER BY c.embedding <-> '[vec1,vec2,...]'::vector
LIMIT 5;

-- By folder
SELECT * FROM rag_documents WHERE folder_id = 'd6q2qtr24teau8j24teg';

-- Recent documents
SELECT title, created_at FROM rag_documents 
ORDER BY created_at DESC LIMIT 10;
```
