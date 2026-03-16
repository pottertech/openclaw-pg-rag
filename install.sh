#!/bin/bash
# OpenClaw pg-RAG Installation Script
# Requires: PostgreSQL 18+, Python 3.10+, pgvector

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_NAME="${PG_RAG_DB:-openclaw_pg_rag}"
DB_USER="${PG_RAG_USER:-$USER}"
DB_HOST="${PG_RAG_HOST:-localhost}"
DB_PORT="${PG_RAG_PORT:-5432}"

echo "=========================================="
echo "OpenClaw pg-RAG Installer"
echo "=========================================="
echo ""

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "ERROR: Python 3.10+ required, found $PYTHON_VERSION"
    exit 1
fi
echo "✓ Python $PYTHON_VERSION"

# Check PostgreSQL version
echo ""
echo "Checking PostgreSQL version..."
if ! command -v psql &> /dev/null; then
    echo "ERROR: PostgreSQL not found. Please install PostgreSQL 18+."
    echo ""
    echo "macOS: brew install postgresql@18"
    echo "Ubuntu: sudo apt-get install postgresql-18"
    exit 1
fi

PG_VERSION=$(psql --version | awk '{print $3}' | cut -d'.' -f1)
if [ "$PG_VERSION" -lt 18 ]; then
    echo "ERROR: PostgreSQL 18+ required, found version $PG_VERSION"
    echo ""
    echo "Please upgrade PostgreSQL:"
    echo "macOS: brew install postgresql@18"
    echo "Ubuntu: sudo apt-get install postgresql-18"
    exit 1
fi
echo "✓ PostgreSQL $PG_VERSION"

# Check pgvector
echo ""
echo "Checking pgvector extension..."
if ! psql -d postgres -c "SELECT 1" &> /dev/null; then
    echo "ERROR: Cannot connect to PostgreSQL. Is it running?"
    echo ""
    echo "Start PostgreSQL:"
    echo "macOS: brew services start postgresql@18"
    echo "Ubuntu: sudo service postgresql start"
    exit 1
fi

# Check if pgvector is installed
if ! psql -d postgres -c "SELECT * FROM pg_available_extensions WHERE name = 'vector';" | grep -q vector; then
    echo "ERROR: pgvector extension not found."
    echo ""
    echo "Install pgvector:"
    echo "macOS: brew install pgvector"
    echo "Ubuntu: sudo apt-get install postgresql-18-pgvector"
    exit 1
fi
echo "✓ pgvector available"

# Create database
echo ""
echo "Creating database '$DB_NAME'..."
if psql -d "$DB_NAME" -c "SELECT 1" &> /dev/null; then
    echo "⚠ Database '$DB_NAME' already exists"
    read -p "Drop and recreate? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        psql -d postgres -c "DROP DATABASE $DB_NAME;"
        psql -d postgres -c "CREATE DATABASE $DB_NAME;"
        echo "✓ Database recreated"
    else
        echo "Using existing database"
    fi
else
    psql -d postgres -c "CREATE DATABASE $DB_NAME;"
    echo "✓ Database created"
fi

# Enable pgvector
echo ""
echo "Enabling pgvector extension..."
psql -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;"
echo "✓ pgvector enabled"

# Run schema migration
echo ""
echo "Running schema migration..."
if [ -f "$SCRIPT_DIR/migrate.sql" ]; then
    psql -d "$DB_NAME" -f "$SCRIPT_DIR/migrate.sql"
    echo "✓ Schema created"
else
    echo "ERROR: migrate.sql not found in $SCRIPT_DIR"
    exit 1
fi

# Install Python package
echo ""
echo "Installing Python package..."
cd "$SCRIPT_DIR"
python3 -m pip install -e . --quiet
echo "✓ Package installed"

# Create config file
echo ""
echo "Creating configuration..."
CONFIG_DIR="${HOME}/.config/openclaw-pg-rag"
mkdir -p "$CONFIG_DIR"

cat > "$CONFIG_DIR/config.json" << EOF
{
  "database": {
    "host": "$DB_HOST",
    "port": $DB_PORT,
    "name": "$DB_NAME",
    "user": "$DB_USER"
  },
  "embedding": {
    "model": "bge-m3:latest",
    "dimensions": 1024,
    "provider": "ollama"
  },
  "chunking": {
    "size": 1000,
    "overlap": 200
  }
}
EOF
echo "✓ Config saved to $CONFIG_DIR/config.json"

# Test connection
echo ""
echo "Testing connection..."
if pg-rag status &> /dev/null; then
    echo "✓ Connection successful"
else
    echo "⚠ Connection test failed - check database credentials"
fi

# Summary
echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Database: $DB_NAME"
echo "User: $DB_USER"
echo "Host: $DB_HOST:$DB_PORT"
echo ""
echo "Commands:"
echo "  pg-rag status          # Check system status"
echo "  pg-rag query --search  # Search documents"
echo "  pg-rag ingest --folder # Ingest documents"
echo ""
echo "Configuration: $CONFIG_DIR/config.json"
echo ""
