# Upgrading to Enhanced RAG v2.0

This guide covers upgrading from the basic RAG server to the enhanced v2.0 with reranking and advanced features.

## Overview

**What's New:**
- Query expansion with synonyms
- Hybrid search (BM25 + semantic)
- BGE-reranker-v2-m3 cross-encoder reranking
- Query intent classification
- Auto-summarization
- Faceted search (folder filtering)

## Prerequisites

Before upgrading, ensure you have:

1. **PostgreSQL 18+** with pgvector extension
2. **Ollama** installed and running
3. **Required models:**
   ```bash
   ollama pull bge-m3:latest
   ollama pull qllama/bge-reranker-v2-m3:latest
   ```

## Step-by-Step Upgrade

### Step 1: Backup Current Setup

```bash
# Backup your current server script
cp ~/.openclaw/workspace/scripts/rag-query-server.py ~/backups/rag-server-v1-backup.py

# Note your current database config
grep "DB_CONFIG" ~/.openclaw/workspace/scripts/rag-query-server.py
```

### Step 2: Stop Old Server

```bash
# Find and kill old server
pkill -f "rag-query-server"

# Verify it's stopped
curl http://localhost:8080/health
# Should return error or no response
```

### Step 3: Install Dependencies

```bash
# Install Python dependencies
pip install psycopg2-binary numpy requests

# Or if using requirements.txt
pip install -r requirements.txt
```

### Step 4: Configure New Server

```bash
# Copy the new server
cp ~/.openclaw/workspace/repos/openclaw-pg-rag/scripts/rag-query-server-v2.py \
   ~/.openclaw/workspace/scripts/

# Edit database configuration
nano ~/.openclaw/workspace/scripts/rag-query-server-v2.py
```

Update the `DB_CONFIG` section:

```python
DB_CONFIG = {
    "host": "localhost",      # Your PostgreSQL host
    "port": 5432,             # Your PostgreSQL port
    "database": "openclaw_pg_rag",  # Your database name
    "user": "your_username"   # Your PostgreSQL username
}
```

### Step 5: Start New Server

```bash
# Start the enhanced server
python3 ~/.openclaw/workspace/scripts/rag-query-server-v2.py

# Or run in background
nohup python3 ~/.openclaw/workspace/scripts/rag-query-server-v2.py \
  > /tmp/rag-v2.log 2>&1 &
```

### Step 6: Verify Installation

```bash
# Test health endpoint
curl http://localhost:8080/health

# Expected output:
# {"status": "ok", "version": "2.0.0"}

# Test enhanced search
curl -X POST http://localhost:8080/query/enhanced \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "chicken recipes",
    "folder_id": "cookbooks-scaleway",
    "expand_query": true,
    "hybrid_search": true
  }'
```

## Understanding the Changes

### Search Flow (v2.0)

```
User Query
    ↓
[Query Expansion] - Add synonyms
    ↓
[Initial Retrieval] - BM25 + bge-m3 embeddings
    ↓
[Top 20 Results] - Selected for reranking
    ↓
[BGE-Reranker-v2-m3] - Cross-encoder scoring
    ↓
[Final Ranking] - Weighted combination
    ↓
[Results + Summary] - Return to user
```

### Key Differences

| Feature | v1.0 | v2.0 |
|---------|------|------|
| Scoring | Semantic only | BM25 + Semantic + Reranker |
| Query Processing | Direct | Expanded with synonyms |
| Top Results | Embedding similarity | Cross-encoder relevance |
| Intent Detection | ❌ | ✅ |
| Auto-summarization | ❌ | ✅ |
| Latency | ~50ms | ~500ms-1s |

### Performance Considerations

**v2.0 is slower but more accurate:**
- Basic search: ~50-100ms
- With reranking: ~500ms-1s (depends on result count)

**Why the extra time?**
- Each of top 20 results requires an Ollama API call
- Cross-encoders are more compute-intensive but produce better rankings

**To disable reranking for faster queries:**
```json
{
  "question": "your query",
  "expand_query": true,
  "hybrid_search": true
}
# Note: No rerank parameter = uses default (enabled)
# To disable: modify the code to skip _rerank_with_ollama
```

## API Changes

### Backward Compatibility

The `/query` endpoint remains unchanged:

```bash
POST /query
{
  "question": "string",
  "folder_id": "optional"
}
```

### New Endpoint: /query/enhanced

```bash
POST /query/enhanced
{
  "question": "string",              # Required
  "folder_id": "optional",         # Optional category filter
  "expand_query": true,              # Enable synonym expansion
  "hybrid_search": true             # Enable BM25 + semantic
}
```

**Response includes new fields:**
- `classification` - Detected intent
- `expanded_queries` - Synonym variants
- `rerank_score` - Cross-encoder score
- `summary` - Auto-generated summary

## Troubleshooting

### Issue: "Model not found"

**Error:** `ollama pull qllama/bge-reranker-v2-m3:latest` not working

**Solution:**
```bash
# Check Ollama is running
ollama list

# Pull the model manually
ollama pull qllama/bge-reranker-v2-m3:latest
ollama pull bge-m3:latest

# Verify
ollama list | grep -E "bge|reranker"
```

### Issue: "Connection refused" on port 8080

**Error:** Port already in use

**Solution:**
```bash
# Kill existing processes
pkill -f "rag-query-server"

# Or change port in the script
PORT = 8081  # Edit in rag-query-server-v2.py
```

### Issue: "Database connection failed"

**Error:** Cannot connect to PostgreSQL

**Solution:**
```bash
# Check PostgreSQL is running
brew services list | grep postgresql

# Test connection
psql -d openclaw_pg_rag -c "SELECT 1"

# Update DB_CONFIG if needed
```

### Issue: Reranker returning low scores

**This is normal!** Cross-encoders have different output scales than embeddings.

The score is normalized and combined with original scores. Relative ranking is what matters.

### Issue: Slow performance

**Options to speed up:**

1. Reduce results to rerank (modify `results[:20]` to `results[:10]`)
2. Use basic search endpoint (`/query` instead of `/query/enhanced`)
3. Run Ollama on GPU if available

## Rollback to v1.0

If you need to rollback:

```bash
# Stop v2.0
pkill -f "rag-query-server-v2"

# Start v1.0
python3 ~/backups/rag-server-v1-backup.py
```

## Support

For issues or questions:
- Check logs: `/tmp/rag-v2.log`
- Review this guide
- Open an issue on GitHub: https://github.com/pottertech/openclaw-pg-rag

---

**Last Updated:** 2026-03-21
**Version:** 2.0.0
