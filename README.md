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

---

## 🚀 Enhanced RAG v2.0 Features

### What's New in v2.0

The Enhanced RAG Server adds powerful features for better document retrieval:

1. **Query Expansion** - Automatically expands queries with synonyms
2. **Hybrid Search** - Combines BM25 keyword matching with semantic search
3. **Cross-Encoder Reranking** - Uses BGE-reranker-v2-m3 for precise relevance scoring
4. **Query Classification** - Detects intent (factual, how-to, troubleshooting, etc.)
5. **Result Summarization** - Auto-generates summaries of top results
6. **Faceted Search** - Filter by folder/category

### Installation (Enhanced Server)

#### Prerequisites

- PostgreSQL 18+ with pgvector
- Ollama with models:
  ```bash
  ollama pull bge-m3:latest
  ollama pull qllama/bge-reranker-v2-m3:latest
  ```

#### 1. Install Dependencies

```bash
pip install psycopg2-binary numpy requests
```

#### 2. Configure Database

Update database connection in `scripts/rag-query-server-v2.py`:

```python
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "openclaw_pg_rag",
    "user": "your_username"
}
```

#### 3. Start the Enhanced Server

```bash
cd ~/.openclaw/workspace/repos/openclaw-pg-rag
python3 scripts/rag-query-server-v2.py
```

Server runs on port 8080 by default.

### API Endpoints

#### Basic Search (Backward Compatible)
```bash
POST http://localhost:8080/query
Content-Type: application/json

{
  "question": "chicken recipes",
  "folder_id": "cookbooks-scaleway"
}
```

#### Enhanced Search (All Features)
```bash
POST http://localhost:8080/query/enhanced
Content-Type: application/json

{
  "question": "chicken recipes",
  "folder_id": "cookbooks-scaleway",
  "expand_query": true,
  "hybrid_search": true
}
```

**Response includes:**
- `classification` - Query intent detection
- `expanded_queries` - Synonym-expanded versions
- `summary` - Auto-generated summary
- `rerank_score` - Cross-encoder relevance score
- `final_score` - Combined weighted score

#### Other Endpoints
```bash
GET /health                    # Health check
GET /categories               # List document categories
GET /search?q=query           # Simple GET search
GET /docs or /help            # API documentation
```

### How the Reranker Works

The BGE-reranker-v2-m3 is a cross-encoder that provides more accurate relevance scoring than embedding similarity alone:

1. **Initial Retrieval** - BM25 + bge-m3 embeddings retrieve top 100 documents
2. **Cross-Encoder Scoring** - Query + passage passed to bge-reranker-v2-m3
3. **Final Ranking** - Combined: `0.7 * rerank_score + 0.3 * original_score`

This two-stage approach significantly improves precision for the top results.

### Updating from v1.0

1. Backup your existing server (if customized)
2. Copy the new server: `cp scripts/rag-query-server-v2.py /your/location/`
3. Update database config in the new file
4. Stop old server: `pkill -f rag-query-server`
5. Start new server: `python3 rag-query-server-v2.py`

### Performance Notes

- **Latency**: ~50-100ms for basic search, ~500ms-1s with reranking
- **Memory**: ~500MB for Ollama models
- **Throughput**: Optimized for 10-20 concurrent queries

### Troubleshooting

**Issue**: Reranker not working
- Check Ollama is running: `ollama list`
- Verify models: `ollama pull qllama/bge-reranker-v2-m3:latest`
- Check logs: `/tmp/rag-v2.log`

**Issue**: Database connection failed
- Verify PostgreSQL is running: `brew services list | grep postgresql`
- Check credentials in DB_CONFIG
- Test connection: `psql -d openclaw_pg_rag -c "SELECT 1"`

**Issue**: Port already in use
- Kill existing: `pkill -f rag-query-server`
- Or change PORT in the script

---

## Service Manager (Auto-Restart)

For production deployments, use the service manager to auto-restart if crashes:

```bash
python3 scripts/service-manager.py &
```

This monitors:
- RAG API server
- PostgreSQL
- Redis
- ClawDispatch monitor

And automatically restarts any service that stops.

