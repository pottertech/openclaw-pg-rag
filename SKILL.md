---
name: openclaw-pg-rag
description: PostgreSQL RAG system for document storage and search
version: 1.0.0
---

# OpenClaw pg-RAG

PostgreSQL-based RAG (Retrieval-Augmented Generation) for OpenClaw agents.

## Installation

```bash
pip install -e .
```

## Commands

### Ingest Documents

```bash
# Ingest all PDFs from default folder
pg-rag ingest --folder

# Ingest specific file
pg-rag ingest --file "document.pdf" --file-id "GOOGLE_DRIVE_ID"
```

### Query Documents

```bash
# Search content
pg-rag query --search "AI hallucinations"

# Search by title
pg-rag query --title "OAuth guide"

# Raw SQL
pg-rag query --sql "SELECT * FROM rag_documents WHERE title ILIKE '%security%'"

# JSON output
pg-rag query --search "RAG" --json
```

### Get Document

```bash
# View document
pg-rag get DOCUMENT_ID

# Save to file
pg-rag get DOCUMENT_ID --output document.md
```

### Check Status

```bash
pg-rag status
```

## Database

**Default:** `pg_vault_rag` on localhost

**Tables:**
- `rag_documents` - Document storage
- `rag_document_chunks` - Chunked content
- `rag_folders` - Folder registry

## Email Documents (Markdown → HTML)

When retrieving documents for email, always convert Markdown to HTML first:

```python
import psycopg2
import markdown
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 1. Retrieve document from pg-rag
conn = psycopg2.connect('host=/tmp dbname=pg_vault_rag user=skippotter')
cur = conn.cursor()
cur.execute("SELECT title, raw_markdown FROM rag_documents WHERE title ILIKE %s", ("%chef cho%",))
title, md_content = cur.fetchone()
conn.close()

# 2. Convert Markdown to HTML
html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])

# 3. Create styled HTML email
html_body = f"""
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #333; border-bottom: 2px solid #e74c3c; }}
        h2 {{ color: #e74c3c; margin-top: 30px; }}
        h3 {{ color: #555; }}
        ul {{ padding-left: 20px; }}
        li {{ margin: 5px 0; }}
        code {{ background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }}
        pre {{ background: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>
"""

# 4. Send email
msg = MIMEMultipart('alternative')
msg['From'] = 'brodie.foxworth@pottersquill.com'
msg['To'] = 'skip.potter.va@gmail.com'
msg['Subject'] = title

msg.attach(MIMEText(md_content[:2000] + "\n\n[Full content in HTML version]", 'plain'))
msg.attach(MIMEText(html_body, 'html'))

context = ssl.create_default_context()
with smtplib.SMTP_SSL('mail.pottersquill.com', 465, context=context) as server:
    server.login('brodie.foxworth@pottersquill.com', 'SMTP_PASSWORD')
    server.send_message(msg)
```

**Rule:** Always convert Markdown → HTML before emailing documents from pg-rag.

## Examples

### Python API

```python
from scripts.ingest import process_single_pdf

process_single_pdf(
    file_id="google_drive_id",
    filename="paper.pdf",
    folder_id="d6q2qtr24teau8j24teg"
)
```

### Direct SQL

```python
import psycopg2

conn = psycopg2.connect(
    dbname='pg_vault_rag',
    user='skippotter',
    host='localhost'
)

cur = conn.cursor()
cur.execute(
    "SELECT title, raw_markdown FROM rag_documents WHERE raw_markdown ILIKE %s",
    ("%AI%",)
)
results = cur.fetchall()
```

## Repository

https://github.com/pottertech/openclaw-pg-rag
