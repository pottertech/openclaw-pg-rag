# OpenClaw pg-RAG

PostgreSQL-based RAG (Retrieval-Augmented Generation) system for OpenClaw.

## Requirements

- **PostgreSQL 18+** with **pgvector** extension
- Python 3.10+
- Docling for document conversion

## Purpose

Provides document storage, indexing, and semantic search for OpenClaw agents.

## Installation

### 1. Install PostgreSQL 18 + pgvector

**macOS:**
```bash
brew install postgresql@18 pgvector
brew services start postgresql@18
```

**Ubuntu:**
```bash
sudo apt-get install postgresql-18 postgresql-18-pgvector
```

### 2. Enable pgvector

```bash
psql -d pg_vault_rag -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 3. Install pg-RAG

```bash
pip install -e .
```

## Architecture

```
Source Documents (PDF, DOCX, etc.)
    ↓
Docling Converter
    ↓
Markdown + YAML Front Matter
    ↓
PostgreSQL 18 (pg_vault_rag database)
    ↓
Query via SQL / Semantic Search (pgvector)
```

## Database Schema

### rag_documents
- document_id (text, PK)
- title, source_uri, source_type
- raw_markdown (full content)
- metadata_json (YAML front matter)
- folder_id, created_at, updated_at

### rag_document_chunks
- chunk_index, chunk_text
- embedding (pgvector - 1024 dimensions)
- For semantic search

### rag_folders
- folder registry for tracking

## CLI Commands

```bash
# Ingest documents
pg-rag ingest --folder                    # Process folder
pg-rag ingest --file document.pdf         # Single file

# Query
pg-rag query --search "AI"                # Content search
pg-rag query --title "OAuth"              # Title search
pg-rag status                             # System status

# Get document
pg-rag get d6qb9cr24te02or24ttg           # View content
pg-rag get DOC_ID --output file.md       # Save to file
```

## Configuration

**Database connection:**
- Host: `100.99.127.10` (Tailscale) or `localhost`
- Port: `5432`
- Database: `pg_vault_rag`

See `docs/requirements.md` for detailed setup.

## License

MIT

Provides document storage, indexing, and semantic search for OpenClaw agents.

## Architecture

```
Source Documents (PDF, DOCX, etc.)
    ↓
Docling Converter
    ↓
Markdown + YAML Front Matter
    ↓
PostgreSQL (pg_vault_rag database)
    ↓
Query via SQL / Semantic Search
```

## Database Schema

### rag_documents
- document_id (text, PK)
- title, source_uri, source_type
- raw_markdown (full content)
- metadata_json (YAML front matter)
- folder_id, created_at, updated_at

### rag_document_chunks
- chunk_index, chunk_text
- embedding (pgvector)
- For semantic search

### rag_folders
- folder registry for tracking

## Usage

```python
from scripts.ingest import process_pdf

process_pdf(file_id, filename, folder_id)
```

## Installation

```bash
pip install -e .
# Requires: PostgreSQL + pgvector, Docling, psycopg2
```

## License

MIT
