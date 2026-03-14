#!/usr/bin/env python3
"""Simplified RAG Pipeline - PostgreSQL Only (No Notion)"""

import subprocess
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime, timezone

# Config
FOLDER_ID = "17Xrej0G2XCg7aWFjjGfzeUlqeHUxH_fH"  # Files/Knowledge Base:Neon
FOLDER_XID = "d6q2qtr24teau8j24teg"

def log(msg):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")

def get_pdfs_from_drive():
    """List PDFs from Google Drive."""
    try:
        result = subprocess.run(
            ['gog', 'drive', 'ls', '--parent', FOLDER_ID, '--max', '100', '--json'],
            capture_output=True, text=True, timeout=30
        )
        data = json.loads(result.stdout)
        files = data.get('files', [])
        pdfs = [(f['id'], f['name']) for f in files if f.get('name', '').endswith('.pdf')]
        return pdfs
    except Exception as e:
        log(f"Error listing PDFs: {e}")
        return []

def download_pdf(file_id, output_path):
    """Download PDF from Google Drive."""
    try:
        result = subprocess.run(
            ['gog', 'drive', 'download', file_id, '--out', str(output_path)],
            capture_output=True, text=True, timeout=60
        )
        return result.returncode == 0
    except Exception as e:
        log(f"Error downloading: {e}")
        return False

def convert_pdf(pdf_path, md_path):
    """Convert PDF to Markdown with Docling."""
    try:
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        content = result.document.export_to_markdown()
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, content
    except Exception as e:
        log(f"Error converting: {e}")
        return False, None

def add_front_matter(content, filename, file_id):
    """Add YAML front matter."""
    import xid
    
    doc_id = str(xid.Xid())
    title = filename.replace('.pdf', '')
    source_url = f"https://drive.google.com/file/d/{file_id}"
    
    front_matter = f"""---
document_id: {doc_id}
title: {title}
source_url: {source_url}
source_type: google-drive
mime_type: application/pdf
folder_id: {FOLDER_XID}
ingested_at: {datetime.now(timezone.utc).isoformat()}
---

"""
    
    return doc_id, front_matter + content

def index_to_postgresql(doc_id, title, source_url, content, folder_id):
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
                updated_at = NOW(),
                indexed_at = NOW(),
                raw_markdown = EXCLUDED.raw_markdown,
                content = EXCLUDED.content
        """, (
            doc_id, title, source_url, 'google-drive', 'application/pdf',
            content, content, json.dumps({"tags": ["pdf"]}), folder_id
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        log(f"PostgreSQL error: {e}")
        return False

def process_single_pdf(file_id, filename):
    """Process one PDF end-to-end."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / f"{file_id}.pdf"
        md_path = Path(tmpdir) / f"{file_id}.md"
        
        log(f"Processing: {filename[:50]}...")
        
        # 1. Download
        log("  [1/5] Downloading...")
        if not download_pdf(file_id, pdf_path):
            return False
        
        # 2. Convert
        log("  [2/5] Converting to Markdown...")
        success, md_content = convert_pdf(pdf_path, md_path)
        if not success:
            return False
        
        # 3. Add front matter
        log("  [3/5] Adding front matter...")
        doc_id, final_content = add_front_matter(md_content, filename, file_id)
        
        # 4. Index to PostgreSQL
        log("  [4/5] Indexing to PostgreSQL...")
        source_url = f"https://drive.google.com/file/d/{file_id}"
        title = filename.replace('.pdf', '')
        if not index_to_postgresql(doc_id, title, source_url, final_content, FOLDER_XID):
            return False
        
        # 5. Auto-cleanup
        log("  [5/5] Cleanup...")
        # TempDirectory auto-cleans
        
        log(f"  ✅ Complete: {doc_id}")
        return True

def main():
    log("=== Simplified RAG Pipeline (PostgreSQL Only) ===")
    log("")
    
    # Get PDFs
    pdfs = get_pdfs_from_drive()
    log(f"Found {len(pdfs)} PDFs to process")
    log("")
    
    # Process each
    success = 0
    for i, (file_id, filename) in enumerate(pdfs, 1):
        log(f"[{i}/{len(pdfs)}] {filename[:50]}...")
        if process_single_pdf(file_id, filename):
            success += 1
        else:
            log(f"  ❌ Failed")
        log("")
    
    log(f"=== Complete: {success}/{len(pdfs)} processed ===")
    
    # Final count
    try:
        import psycopg2
        conn = psycopg2.connect(dbname='pg_vault_rag', user='skippotter', host='localhost')
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM rag_documents WHERE folder_id = %s", (FOLDER_XID,))
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        log(f"Total documents in PostgreSQL: {count}")
    except Exception as e:
        log(f"Could not get final count: {e}")

if __name__ == '__main__':
    main()
