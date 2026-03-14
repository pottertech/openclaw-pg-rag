# OpenClaw pg-RAG

PostgreSQL-based RAG (Retrieval-Augmented Generation) system for OpenClaw.

## Purpose

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
