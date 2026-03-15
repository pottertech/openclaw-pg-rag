# System Requirements

## Database

**PostgreSQL Version:** 18+ (Recommended: 18.x)

**Required Extensions:**
- `pgvector` - For vector embeddings and semantic search

**Installation:**

### macOS (Homebrew)
```bash
# Install PostgreSQL 18
brew install postgresql@18

# Start PostgreSQL
brew services start postgresql@18

# Install pgvector
brew install pgvector

# Enable extension
psql -d your_database -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Ubuntu/Debian
```bash
# Install PostgreSQL 18
sudo apt-get update
sudo apt-get install postgresql-18 postgresql-contrib-18

# Install pgvector
sudo apt-get install postgresql-18-pgvector

# Enable extension
sudo -u postgres psql -d your_database -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Verify Installation
```bash
psql --version  # Should show 18.x

# Check pgvector
psql -d openclaw_pg_rag -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

## Database Configuration

**Required:**
- PostgreSQL 18+
- pgvector extension
- Database: `openclaw_pg_rag`
- User: `skippotter` (or your user)

**Vector Dimensions:** 1024 (for bge-m3 embeddings)

## Python

**Version:** 3.10+

**Dependencies:**
```bash
pip install psycopg2-binary docling xid requests
```

## Network

**Default Connection:**
- Host: `localhost`
- Port: `5432`
- Database: `openclaw_pg_rag`

**Tailscale (for distributed agents):**
- Host: `100.99.127.10`
- Port: `5432`
