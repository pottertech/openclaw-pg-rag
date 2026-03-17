# OpenClaw pg-RAG

PostgreSQL-based RAG (Retrieval-Augmented Generation) system for OpenClaw.

## ⚠️ Requirements

**CRITICAL: PostgreSQL 18+ REQUIRED**

This package requires PostgreSQL version 18 or higher. Earlier versions (14, 15, 16, 17) are NOT supported.

- **PostgreSQL 18+** (REQUIRED - no exceptions)
- **pgvector** extension
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
psql -d openclaw_pg_rag -c "CREATE EXTENSION IF NOT EXISTS vector;"
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
PostgreSQL 18 (openclaw_pg_rag database)
    ↓
Query via SQL / Semantic Search (pgvector)
```

## Query Types

pg-RAG supports **4 query strategies** for different information needs:

| Strategy | Best For | Example Queries |
|----------|----------|-----------------|
| **Factual** | Specific facts, definitions, exact data | "What is OAuth 2.0?", "How many calories in chicken?" |
| **Analytical** | Analysis, comparison, comprehensive review | "Compare Python vs JavaScript", "Analyze CMMC requirements" |
| **Opinion** | Pros/cons, recommendations, best practices | "What are the best practices for API security?" |
| **Contextual** | Follow-up questions, personal context | "What did we decide about the database schema?" |

### How It Works

The system automatically classifies your query and applies the appropriate retrieval strategy:

- **Factual** → Precision-focused search with exact matching
- **Analytical** → Comprehensive coverage with sub-question decomposition
- **Opinion** → Diverse perspectives retrieval from multiple sources
- **Contextual** → User context integration with conversation history

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
- Database: `openclaw_pg_rag`

See `docs/requirements.md` for detailed setup.

## License

MIT
