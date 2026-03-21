# RAG Architecture Diagram - Embeddings Flow

## Enhanced RAG v2.0 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          ENHANCED RAG v2.0                              │
└─────────────────────────────────────────────────────────────────────────┘

USER QUERY
    │
    ▼
┌─────────────────┐
│ Query Expansion │◄── SYNONYMS (bge-m3 embeddings)
│  (Optional)     │    • car → vehicle, automobile
└────────┬────────┘    • recipe → dish, meal
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STAGE 1: INITIAL RETRIEVAL                  │
│                                                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │   BM25       │     │  Semantic    │     │   Combine    │   │
│  │  (Keyword)   │  +  │  (bge-m3)    │  →  │   Scores     │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
│        │                      │                    │           │
│        │                      │                    │           │
│        ▼                      ▼                    ▼           │
│  PostgreSQL ◄──────────────────────────────────────┘           │
│  (pgvector)                                                    │
│    • rag_documents                                            │
│    • rag_document_chunks                                      │
└────────────────────────┬──────────────────────────────────────┘
                         │
                         ▼
              Top 100 Results
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  STAGE 2: CROSS-ENCODER RERANK                   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  BGE-RERANKER-v2-m3 (Ollama)                              │   │
│  │                                                           │   │
│  │   Query: "chicken recipes"                                │   │
│  │      +                                                    │   │
│  │   Passage: "A delicious chicken recipe with herbs..."     │   │
│  │      ↓                                                    │   │
│  │   Cross-Encoder Score: 0.87                             │   │
│  │                                                           │   │
│  │   (vs. embedding similarity which scores: 0.72)          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                         │
│                         ▼
│              Top 20 Re-ranked
│                         │
│                         ▼
│  Final Score = 0.7 × Rerank + 0.3 × Original
│                         │
└─────────────────────────┼────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      STAGE 3: POST-PROCESSING                  │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐         │
│  │   Intent     │   │   Summary    │   │   Return     │         │
│  │ Classification│ → │  Generation  │ → │   Results    │         │
│  └──────────────┘   └──────────────┘   └──────────────┘         │
│       │                    │                    │              │
│       ▼                    ▼                    ▼              │
│  "how_to"             "Found 5              JSON Response         │
│  intent               chicken recipes                           │
│                       from 2 folders"                           │
└─────────────────────────────────────────────────────────────────┘
```

## Embedding Model Comparison

| Model | Type | Use Case |
|-------|------|----------|
| **bge-m3** | Bi-encoder (embeddings) | Initial retrieval - Fast, large scale |
| **bge-reranker-v2-m3** | Cross-encoder (joint encoding) | Re-ranking - Slow, high precision |

### Why Both?

**Bi-encoder (bge-m3):**
- ✅ Fast - pre-computed embeddings
- ✅ Scales to millions of documents
- ❌ Less accurate for fine-grained ranking

**Cross-encoder (bge-reranker):**
- ✅ Very accurate - sees query+doc together
- ❌ Slow - must encode each pair at runtime
- ❌ Doesn't scale to large retrieval sets

**Solution: Two-stage approach**
- **Stage 1**: Bi-encoder → Fast retrieval of candidate documents
- **Stage 2**: Cross-encoder → Precise ranking of top-N results

## Data Flow

```
Documents ──► Docling ──► Chunks ──► bge-m3 ──► PostgreSQL
                                              (embeddings)
                                                    ▲
Query ──────────────────────────────────────────────┤
  │                                                 │
  └─► bge-m3 (query embedding) ──► Similarity Search─┘
                                                    │
  ┌─────────────────────────────────────────────────┘
  │
  └─► bge-reranker-v2-m3 (query + passage) ──► Final Score
```

## Component Details

### 1. Query Expansion
- Uses synonym dictionary based on bge-m3 embeddings
- Expands query terms to improve recall
- Example: "car" → ["car", "vehicle", "automobile"]

### 2. Initial Retrieval (BM25 + Semantic)
- **BM25**: Keyword matching with term frequency weighting
- **Semantic**: Cosine similarity between bge-m3 embeddings
- **Combined**: Weighted average (0.6 semantic + 0.4 keyword)

### 3. Cross-Encoder Re-ranking
- Model: `qllama/bge-reranker-v2-m3` (Ollama)
- Input: Query text + Passage text (concatenated)
- Output: Relevance score (0-1)
- Processed: Top 20 candidates from initial retrieval

### 4. Final Scoring
```
final_score = 0.7 × rerank_score + 0.3 × original_score
```

### 5. Post-Processing
- **Intent Classification**: Detects query type (factual, how-to, troubleshooting)
- **Summarization**: Auto-generates summary of top results
- **Response Formatting**: Returns structured JSON with scores and metadata

## PostgreSQL Schema

```sql
-- Documents table
CREATE TABLE rag_documents (
    document_id TEXT PRIMARY KEY,
    title TEXT,
    content TEXT,
    folder_id TEXT,
    folder_name TEXT,
    created_at TIMESTAMP
);

-- Chunks table with embeddings
CREATE TABLE rag_document_chunks (
    chunk_id SERIAL PRIMARY KEY,
    document_id TEXT REFERENCES rag_documents(document_id),
    chunk_text TEXT,
    chunk_index INTEGER,
    embedding VECTOR(1024),  -- bge-m3 produces 1024-dim embeddings
    created_at TIMESTAMP
);

-- Vector index for fast similarity search
CREATE INDEX ON rag_document_chunks USING ivfflat (embedding vector_cosine_ops);
```

## API Endpoints

### Basic Search
```
POST /query
{
  "question": "chicken recipes",
  "folder_id": "cookbooks-scaleway"
}
```

### Enhanced Search (with all features)
```
POST /query/enhanced
{
  "question": "chicken recipes",
  "folder_id": "cookbooks-scaleway",
  "expand_query": true,
  "hybrid_search": true
}
```

**Response includes:**
- `semantic_score` - From bge-m3 embedding similarity
- `keyword_score` - From BM25 scoring
- `rerank_score` - From bge-reranker-v2-m3 cross-encoder
- `final_score` - Weighted combination
- `classification` - Detected query intent
- `summary` - Auto-generated result summary

## Performance Characteristics

| Stage | Latency | Accuracy | Scale |
|-------|---------|----------|-------|
| BM25 | ~10ms | Medium | Millions of docs |
| Semantic (bge-m3) | ~50ms | High | Millions of docs |
| Re-rank (bge-reranker) | ~500ms | Very High | Top 20 docs only |

**Total latency**: ~600ms for enhanced search with re-ranking

## Technology Stack

- **PostgreSQL 18+**: Document storage with pgvector extension
- **pgvector**: Vector similarity search (cosine distance)
- **Ollama**: Local LLM inference for embeddings and reranking
- **bge-m3**: 1024-dim embeddings (1.2GB model)
- **bge-reranker-v2-m3**: Cross-encoder reranker (635MB model)
- **Python**: Server implementation with psycopg2, numpy, requests

## Why This Architecture?

1. **Scalability**: Bi-encoders handle large document sets efficiently
2. **Accuracy**: Cross-encoders provide fine-grained relevance scoring
3. **Cost-effective**: Local Ollama deployment, no API costs
4. **Privacy**: All processing on-premise, no data leaves the machine
5. **Extensibility**: Easy to add features like query expansion and classification

---

**Last Updated**: 2026-03-21
**Version**: 2.0.0
