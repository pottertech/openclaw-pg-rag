#!/usr/bin/env python3
"""
OpenClaw pg-RAG CLI
Command-line interface for PostgreSQL RAG system
"""

import argparse
import sys
import json
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def cmd_ingest(args):
    """Ingest documents into RAG."""
    from scripts.ingest import process_single_pdf
    
    if args.folder:
        # Process entire folder
        from scripts.ingest import get_pdfs_from_drive, FOLDER_ID
        folder_id = args.folder or FOLDER_ID
        pdfs = get_pdfs_from_drive(folder_id)
        print(f"Found {len(pdfs)} PDFs to process")
        for file_id, filename in pdfs:
            process_single_pdf(file_id, filename, folder_id)
    elif args.file:
        # Process single file
        print(f"Processing: {args.file}")
        process_single_pdf(args.file_id or "unknown", args.file, args.folder_id or "d6q2qtr24teau8j24teg")
    else:
        print("Error: Use --folder or --file")
        return 1
    return 0

def cmd_query(args):
    """Query documents."""
    import psycopg2
    
    conn = psycopg2.connect(
        dbname=args.database or 'pg_vault_rag',
        user=args.user or 'skippotter',
        host=args.host or 'localhost'
    )
    cur = conn.cursor()
    
    if args.sql:
        # Raw SQL
        cur.execute(args.sql)
    elif args.search:
        # Full text search
        cur.execute(
            "SELECT document_id, title, source_uri FROM rag_documents WHERE raw_markdown ILIKE %s LIMIT %s",
            (f"%{args.search}%", args.limit)
        )
    elif args.title:
        # Title search
        cur.execute(
            "SELECT document_id, title, source_uri FROM rag_documents WHERE title ILIKE %s LIMIT %s",
            (f"%{args.title}%", args.limit)
        )
    else:
        # List recent
        cur.execute(
            "SELECT document_id, title, source_uri, created_at FROM rag_documents ORDER BY created_at DESC LIMIT %s",
            (args.limit,)
        )
    
    results = cur.fetchall()
    
    if args.json:
        print(json.dumps([{"document_id": r[0], "title": r[1], "source_uri": r[2]} for r in results], indent=2))
    else:
        print(f"Found {len(results)} results:")
        for r in results:
            print(f"  - {r[1][:60]}")
            print(f"    ID: {r[0]}")
            if len(r) > 2 and r[2]:
                print(f"    Source: {r[2][:60]}")
            print()
    
    cur.close()
    conn.close()
    return 0

def cmd_status(args):
    """Show RAG system status."""
    import psycopg2
    
    conn = psycopg2.connect(
        dbname=args.database or 'pg_vault_rag',
        user=args.user or 'skippotter',
        host=args.host or 'localhost'
    )
    cur = conn.cursor()
    
    # Get stats
    cur.execute("SELECT COUNT(*) FROM rag_documents")
    total = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(DISTINCT folder_id) FROM rag_documents")
    folders = cur.fetchone()[0]
    
    cur.execute("SELECT MAX(created_at) FROM rag_documents")
    last = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    print("=== OpenClaw pg-RAG Status ===")
    print(f"Database: {args.database or 'pg_vault_rag'}")
    print(f"Total documents: {total}")
    print(f"Folders: {folders}")
    print(f"Last ingest: {last}")
    
    return 0

def cmd_get(args):
    """Get full document content."""
    import psycopg2
    
    conn = psycopg2.connect(
        dbname=args.database or 'pg_vault_rag',
        user=args.user or 'skippotter',
        host=args.host or 'localhost'
    )
    cur = conn.cursor()
    
    cur.execute(
        "SELECT document_id, title, raw_markdown, source_uri, metadata_json FROM rag_documents WHERE document_id = %s",
        (args.document_id,)
    )
    
    result = cur.fetchone()
    if not result:
        print(f"Document not found: {args.document_id}")
        return 1
    
    if args.output:
        # Save to file
        with open(args.output, 'w') as f:
            f.write(result[2])
        print(f"Saved to: {args.output}")
    else:
        # Print to stdout
        print(f"=== {result[1]} ===")
        print(f"ID: {result[0]}")
        print(f"Source: {result[3]}")
        print(f"Metadata: {result[4]}")
        print()
        print(result[2][:5000])  # First 5000 chars
    
    cur.close()
    conn.close()
    return 0

def main():
    parser = argparse.ArgumentParser(
        prog='pg-rag',
        description='OpenClaw pg-RAG - PostgreSQL RAG system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pg-rag ingest --folder                    # Ingest all PDFs from default folder
  pg-rag query --search "AI"                # Search for "AI" in documents
  pg-rag query --title "hallucination"      # Search by title
  pg-rag get d6qb9cr24te02or24ttg           # Get document content
  pg-rag status                             # Show system status

Documentation: https://github.com/pottertech/openclaw-pg-rag
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # Ingest command
    ingest_parser = subparsers.add_parser('ingest', help='Ingest documents')
    ingest_parser.add_argument('--folder', help='Process entire folder')
    ingest_parser.add_argument('--file', help='Process single file')
    ingest_parser.add_argument('--file-id', help='Google Drive file ID')
    ingest_parser.add_argument('--folder-id', default='d6q2qtr24teau8j24teg', help='Folder ID')
    
    # Query command
    query_parser = subparsers.add_parser('query', help='Query documents')
    query_parser.add_argument('--search', '-s', help='Search content (ILIKE)')
    query_parser.add_argument('--title', '-t', help='Search title')
    query_parser.add_argument('--sql', help='Raw SQL query')
    query_parser.add_argument('--limit', '-l', type=int, default=20, help='Result limit')
    query_parser.add_argument('--json', action='store_true', help='JSON output')
    query_parser.add_argument('--database', default='pg_vault_rag', help='Database name')
    query_parser.add_argument('--user', default='skippotter', help='DB user')
    query_parser.add_argument('--host', default='localhost', help='DB host')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show system status')
    status_parser.add_argument('--database', default='pg_vault_rag')
    status_parser.add_argument('--user', default='skippotter')
    status_parser.add_argument('--host', default='localhost')
    
    # Get command
    get_parser = subparsers.add_parser('get', help='Get document content')
    get_parser.add_argument('document_id', help='Document ID')
    get_parser.add_argument('--output', '-o', help='Output file')
    get_parser.add_argument('--database', default='pg_vault_rag')
    get_parser.add_argument('--user', default='skippotter')
    get_parser.add_argument('--host', default='localhost')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    commands = {
        'ingest': cmd_ingest,
        'query': cmd_query,
        'status': cmd_status,
        'get': cmd_get,
    }
    
    return commands[args.command](args)

if __name__ == '__main__':
    sys.exit(main())
