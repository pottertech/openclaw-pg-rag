#!/usr/bin/env python3
"""Simplified RAG Pipeline - PostgreSQL Only (Multi-format via Docling)"""

import subprocess
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime, timezone

# Config
FOLDER_ID = "17Xrej0G2XCg7aWFjjGfzeUlqeHUxH_fH"  # Files/Knowledge Base:Neon
FOLDER_XID = "d6q2qtr24teau8j24teg"

# Docling supported formats
SUPPORTED_EXTENSIONS = ['.pdf', '.docx', '.pptx', '.xlsx', '.html', '.htm', '.md', '.txt']

def log(msg):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")

def get_files_from_drive(folder_id=FOLDER_ID, extensions=None):
    """List files from Google Drive matching extensions."""
    if extensions is None:
        extensions = SUPPORTED_EXTENSIONS
    
    try:
        result = subprocess.run(
            ['gog', 'drive', 'ls', '--parent', folder_id, '--max', '200', '--json'],
            capture_output=True, text=True, timeout=30
        )
        data = json.loads(result.stdout)
        files = data.get('files', [])
        
        matches = []
        for f in files:
            name = f.get('name', '').lower()
            if any(name.endswith(ext.lower()) for ext in extensions):
                matches.append((f['id'], f['name']))
        
        return matches
    except Exception as e:
        log(f"Error listing files: {e}")
        return []

def download_file(file_id, output_path):
    """Download file from Google Drive."""
    try:
        result = subprocess.run(
            ['gog', 'drive', 'download', file_id, '--out', str(output_path)],
            capture_output=True, text=True, timeout=60
        )
        return result.returncode == 0
    except Exception as e:
        log(f"Error downloading: {e}")
        return False

def convert_document(file_path, md_path):
    """Convert document to Markdown with Docling."""
    try:
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        result = converter.convert(str(file_path))
        content = result.document.export_to_markdown()
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, content
    except Exception as e:
        log(f"Error converting: {e}")
        return False, None

def get_mime_type(filename):
    """Get MIME type from extension."""
    ext = filename.split('.')[-1].lower()
    mime_types = {
        'pdf': 'application/pdf',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'html': 'text/html',
        'htm': 'text/html',
        'md': 'text/markdown',
        'txt': 'text/plain'
    }
    return mime_types.get(ext, 'application/octet-stream')

def add_front_matter(content, filename, file_id, folder_id=FOLDER_XID):
    """Add YAML front matter."""
    import xid
    
    doc_id = str(xid.Xid())
    title = Path(filename).stem
    source_url = f"https://drive.google.com/file/d/{file_id}"
    mime_type = get_mime_type(filename)
    
    front_matter = f"""---
document_id: {doc_id}
title: {title}
source_url: {source_url}
source_type: google-drive
mime_type: {mime_type}
folder_id: {folder_id}
ingested_at: {datetime.now(timezone.utc).isoformat()}
---

"""
    
    return doc_id, front_matter + content

def index_to_postgresql(doc_id, title, source_url, content, folder_id, mime_type):
    """Index document to PostgreSQL."""
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            dbname='pg_vault_rag',
            user='skippotter',
            host='localhost'
        )
        cur = conn.cursor()
        
        # Insert main document
        cur.execute("""
            INSERT INTO rag_documents 
            (document_id, title, source_uri, source_type, mime_type,
             raw_markdown, content, metadata_json, folder_id, created_at, updated_at, indexed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), NOW())
            ON CONFLICT (document_id) DO UPDATE SET
                raw_markdown = EXCLUDED.raw_markdown,
                content = EXCLUDED.content,
                updated_at = NOW(),
                indexed_at = NOW()
        """, (doc_id, title, source_url, 'google-drive', mime_type,
              content, content, '{}', folder_id))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        log(f"Error indexing: {e}")
        return False

def process_file(file_id, filename, folder_id=FOLDER_ID):
    """Process single file."""
    log(f"Processing: {filename}")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Download
        log("  [1/5] Downloading...")
        file_path = Path(tmpdir) / filename
        if not download_file(file_id, file_path):
            log(f"  ❌ Download failed: {filename}")
            return False
        
        # Convert
        log("  [2/5] Converting to Markdown...")
        md_path = Path(tmpdir) / "output.md"
        success, content = convert_document(file_path, md_path)
        if not success:
            log(f"  ❌ Conversion failed: {filename}")
            return False
        
        # Add front matter
        log("  [3/5] Adding front matter...")
        doc_id, full_content = add_front_matter(content, filename, file_id, FOLDER_XID)
        
        # Index
        log("  [4/5] Indexing to PostgreSQL...")
        mime_type = get_mime_type(filename)
        if not index_to_postgresql(doc_id, Path(filename).stem, 
                                    f"https://drive.google.com/file/d/{file_id}",
                                    full_content, FOLDER_XID, mime_type):
            log(f"  ❌ Index failed: {filename}")
            return False
        
        # Cleanup (auto)
        log("  [5/5] Cleanup...")
        log(f"  ✅ Complete: {doc_id}")
        return True

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Ingest documents to pg-RAG')
    parser.add_argument('--folder', action='store_true', help='Process entire folder')
    parser.add_argument('--file', help='Process single file')
    parser.add_argument('--file-id', help='Google Drive file ID')
    parser.add_argument('--folder-id', default=FOLDER_ID, help='Folder ID')
    parser.add_argument('--types', default='pdf,docx,pptx,xlsx,html,md,txt',
                        help='Comma-separated file types')
    
    args = parser.parse_args()
    
    # Parse extensions
    extensions = [f'.{t.strip()}' for t in args.types.split(',')]
    
    if args.folder:
        log(f"Scanning folder: {args.folder_id}")
        log(f"Supported types: {', '.join(extensions)}")
        files = get_files_from_drive(args.folder_id, extensions)
        log(f"Found {len(files)} files")
        
        for i, (file_id, filename) in enumerate(files, 1):
            log(f"[{i}/{len(files)}] {filename}...")
            process_file(file_id, filename, args.folder_id)
            
    elif args.file and args.file_id:
        process_file(args.file_id, args.file, args.folder_id)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
