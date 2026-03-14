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

def cmd_decode(args):
    """Decode xid to extract metadata."""
    import xid as xid_lib
    from datetime import datetime
    
    try:
        # Parse the xid from string
        x = xid_lib.Xid.from_string(args.xid_string)
        
        # Extract components
        timestamp = x.time()
        machine = x.machine()
        pid = x.pid()
        counter = x.counter()
        
        print(f"=== xid Decode: {args.xid_string} ===")
        print()
        print(f"Timestamp:      {datetime.fromtimestamp(timestamp)}")
        print(f"Unix Time:      {timestamp}")
        print(f"Machine ID:     {machine.hex() if hasattr(machine, 'hex') else machine.encode('latin-1').hex() if isinstance(machine, str) else machine.hex()}")
        print(f"Process ID:     {pid}")
        print(f"Counter:        {counter}")
        print()
        print(f"String:         {x.string()}")
        try:
            print(f"Bytes:          {x.bytes().encode('latin-1').hex()}")
        except:
            print(f"Bytes:          {repr(x.bytes())}")
        
        if args.json:
            import json
            output = {
                "xid": args.xid_string,
                "timestamp": timestamp,
                "datetime": datetime.fromtimestamp(timestamp).isoformat(),
                "machine": machine,
                "pid": pid,
                "counter": counter
            }
            print()
            print(json.dumps(output, indent=2))
            
    except Exception as e:
        print(f"Error: Invalid xid - {e}")
        return 1
    
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

def cmd_list(args):
    """List documents with metadata."""
    import psycopg2
    
    conn = psycopg2.connect(
        dbname=args.database or 'pg_vault_rag',
        user=args.user or 'skippotter',
        host=args.host or 'localhost'
    )
    cur = conn.cursor()
    
    # Build query
    if args.folder:
        cur.execute(
            "SELECT document_id, title, source_uri, created_at, metadata_json FROM rag_documents WHERE folder_id = %s ORDER BY created_at DESC LIMIT %s",
            (args.folder, args.limit)
        )
    elif args.recent:
        cur.execute(
            "SELECT document_id, title, source_uri, created_at, metadata_json FROM rag_documents ORDER BY created_at DESC LIMIT %s",
            (args.limit,)
        )
    else:
        cur.execute(
            "SELECT document_id, title, source_uri, created_at, metadata_json FROM rag_documents ORDER BY title LIMIT %s",
            (args.limit,)
        )
    
    results = cur.fetchall()
    
    if args.json:
        output = []
        for r in results:
            output.append({
                "document_id": r[0],
                "title": r[1],
                "source_uri": r[2],
                "created_at": str(r[3]),
                "metadata": r[4]
            })
        print(json.dumps(output, indent=2))
    else:
        print(f"Found {len(results)} documents:")
        print(f"{'ID':<25} {'Title':<40} {'Created':<20}")
        print("-" * 90)
        for r in results:
            title = r[1][:38] if r[1] else 'Untitled'
            created = str(r[3])[:19] if r[3] else 'N/A'
            print(f"{r[0]:<25} {title:<40} {created:<20}")
    
    cur.close()
    conn.close()
    return 0

def cmd_show(args):
    """Show metadata for a document."""
    import psycopg2
    
    conn = psycopg2.connect(
        dbname=args.database or 'pg_vault_rag',
        user=args.user or 'skippotter',
        host=args.host or 'localhost'
    )
    cur = conn.cursor()
    
    cur.execute(
        "SELECT document_id, title, source_uri, source_type, mime_type, folder_id, created_at, updated_at, indexed_at, metadata_json FROM rag_documents WHERE document_id = %s",
        (args.document_id,)
    )
    
    result = cur.fetchone()
    if not result:
        print(f"Document not found: {args.document_id}")
        return 1
    
    print(f"=== Document Metadata ===")
    print(f"ID:            {result[0]}")
    print(f"Title:         {result[1]}")
    print(f"Source:        {result[2]}")
    print(f"Source Type:   {result[3]}")
    print(f"MIME Type:     {result[4]}")
    print(f"Folder ID:     {result[5]}")
    print(f"Created:       {result[6]}")
    print(f"Updated:       {result[7]}")
    print(f"Indexed:       {result[8]}")
    print(f"Metadata:      {json.dumps(result[9], indent=2) if result[9] else '{}'}")
    
    cur.close()
    conn.close()
    return 0

def cmd_update(args):
    """Update document metadata."""
    import psycopg2
    
    conn = psycopg2.connect(
        dbname=args.database or 'pg_vault_rag',
        user=args.user or 'skippotter',
        host=args.host or 'localhost'
    )
    cur = conn.cursor()
    
    # Build update
    updates = []
    params = []
    
    if args.title:
        updates.append("title = %s")
        params.append(args.title)
    if args.metadata:
        updates.append("metadata_json = %s")
        params.append(json.dumps(json.loads(args.metadata)))
    if args.folder:
        updates.append("folder_id = %s")
        params.append(args.folder)
    
    if not updates:
        print("Error: No fields to update. Use --title, --metadata, or --folder")
        return 1
    
    params.append(args.document_id)
    
    sql = f"UPDATE rag_documents SET {', '.join(updates)}, updated_at = NOW() WHERE document_id = %s"
    cur.execute(sql, params)
    
    conn.commit()
    
    if cur.rowcount > 0:
        print(f"✅ Updated: {args.document_id}")
    else:
        print(f"❌ Document not found: {args.document_id}")
    
    cur.close()
    conn.close()
    return 0

def cmd_delete(args):
    """Delete document from RAG."""
    import psycopg2
    
    conn = psycopg2.connect(
        dbname=args.database or 'pg_vault_rag',
        user=args.user or 'skippotter',
        host=args.host or 'localhost'
    )
    cur = conn.cursor()
    
    if not args.force:
        # Confirm
        cur.execute("SELECT title FROM rag_documents WHERE document_id = %s", (args.document_id,))
        result = cur.fetchone()
        if not result:
            print(f"Document not found: {args.document_id}")
            return 1
        print(f"Delete: {result[0]}")
        print(f"ID: {args.document_id}")
        confirm = input("Confirm delete? [y/N]: ")
        if confirm.lower() != 'y':
            print("Cancelled")
            return 0
    
    # Delete (cascades to chunks via FK)
    cur.execute("DELETE FROM rag_documents WHERE document_id = %s", (args.document_id,))
    conn.commit()
    
    if cur.rowcount > 0:
        print(f"✅ Deleted: {args.document_id}")
    else:
        print(f"❌ Document not found: {args.document_id}")
    
    cur.close()
    conn.close()
    return 0
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
    ingest_parser.add_argument('--file', help='Process single file (PDF, DOCX, PPTX, XLSX, HTML, MD, TXT)')
    ingest_parser.add_argument('--types', default='pdf,docx,pptx,xlsx,html,md,txt', help='Comma-separated file types to process')
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
    
    # Decode command
    decode_parser = subparsers.add_parser('decode', help='Decode xid to extract metadata')
    decode_parser.add_argument('xid_string', help='xid to decode (e.g., d6qb9cr24te02or24ttg)')
    decode_parser.add_argument('--json', action='store_true', help='JSON output')
    
    # Get command
    get_parser = subparsers.add_parser('get', help='Get document content')
    get_parser.add_argument('document_id', help='Document ID')
    get_parser.add_argument('--output', '-o', help='Output file')
    get_parser.add_argument('--database', default='pg_vault_rag')
    get_parser.add_argument('--user', default='skippotter')
    get_parser.add_argument('--host', default='localhost')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List documents')
    list_parser.add_argument('--folder', '-f', help='Filter by folder ID')
    list_parser.add_argument('--recent', '-r', action='store_true', help='Sort by recent')
    list_parser.add_argument('--limit', '-l', type=int, default=20, help='Limit results')
    list_parser.add_argument('--json', action='store_true', help='JSON output')
    list_parser.add_argument('--database', default='pg_vault_rag')
    list_parser.add_argument('--user', default='skippotter')
    list_parser.add_argument('--host', default='localhost')
    
    # Show command
    show_parser = subparsers.add_parser('show', help='Show document metadata')
    show_parser.add_argument('document_id', help='Document ID')
    show_parser.add_argument('--database', default='pg_vault_rag')
    show_parser.add_argument('--user', default='skippotter')
    show_parser.add_argument('--host', default='localhost')
    
    # Update command
    update_parser = subparsers.add_parser('update', help='Update document metadata')
    update_parser.add_argument('document_id', help='Document ID')
    update_parser.add_argument('--title', help='New title')
    update_parser.add_argument('--metadata', help='JSON metadata string')
    update_parser.add_argument('--folder', help='New folder ID')
    update_parser.add_argument('--database', default='pg_vault_rag')
    update_parser.add_argument('--user', default='skippotter')
    update_parser.add_argument('--host', default='localhost')
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete document')
    delete_parser.add_argument('document_id', help='Document ID')
    delete_parser.add_argument('--force', '-f', action='store_true', help='Skip confirmation')
    delete_parser.add_argument('--database', default='pg_vault_rag')
    delete_parser.add_argument('--user', default='skippotter')
    delete_parser.add_argument('--host', default='localhost')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    commands = {
        'ingest': cmd_ingest,
        'query': cmd_query,
        'status': cmd_status,
        'decode': cmd_decode,
        'get': cmd_get,
        'list': cmd_list,
        'show': cmd_show,
        'update': cmd_update,
        'delete': cmd_delete,
    }
    
    return commands[args.command](args)

if __name__ == '__main__':
    sys.exit(main())
