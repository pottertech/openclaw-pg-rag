---
name: openclaw-pg-rag
description: PostgreSQL RAG system for document storage and search
version: 1.0.0
---

# OpenClaw pg-RAG

PostgreSQL-based RAG (Retrieval-Augmented Generation) for OpenClaw agents.

## Installation

```bash
pip install -e .
```

## Commands

### Ingest Documents

```bash
# Ingest all PDFs from default folder
pg-rag ingest --folder

# Ingest specific file
pg-rag ingest --file "document.pdf" --file-id "GOOGLE_DRIVE_ID"
```

### Query Documents

```bash
# Search content
pg-rag query --search "AI hallucinations"

# Search by title
pg-rag query --title "OAuth guide"

# Raw SQL
pg-rag query --sql "SELECT * FROM rag_documents WHERE title ILIKE '%security%'"

# JSON output
pg-rag query --search "RAG" --json
```

### Get Document

```bash
# View document
pg-rag get DOCUMENT_ID

# Save to file
pg-rag get DOCUMENT_ID --output document.md
```

### Check Status

```bash
pg-rag status
```

## Database

**Default:** `pg_vault_rag` on localhost

**Tables:**
- `rag_documents` - Document storage
- `rag_document_chunks` - Chunked content
- `rag_folders` - Folder registry

## Examples

### Python API

```python
from scripts.ingest import process_single_pdf

process_single_pdf(
    file_id="google_drive_id",
    filename="paper.pdf",
    folder_id="d6q2qtr24teau8j24teg"
)
```

### Direct SQL

```python
import psycopg2

conn = psycopg2.connect(
    dbname='pg_vault_rag',
    user='skippotter',
    host='localhost'
)

cur = conn.cursor()
cur.execute(
    "SELECT title, raw_markdown FROM rag_documents WHERE raw_markdown ILIKE %s",
    ("%AI%",)
)
results = cur.fetchall()
```

## Repository

https://github.com/pottertech/openclaw-pg-rag
