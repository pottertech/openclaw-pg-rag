"""PostgreSQL database client for pg-rag."""

from typing import List, Dict, Any, Optional, Tuple
import json
import time

import psycopg2
from psycopg2.extras import RealDictCursor
import requests

from .config import PgRAGConfig


class DatabaseClient:
    """PostgreSQL client with pgvector support."""
    
    def __init__(self, config: Optional[PgRAGConfig] = None):
        self.config = config or PgRAGConfig()
        self._conn = None
    
    def connect(self) -> None:
        """Establish database connection."""
        self._conn = psycopg2.connect(
            host=self.config.pg_host,
            port=self.config.pg_port,
            database=self.config.pg_database,
            user=self.config.pg_user,
            password=self.config.pg_password
        )
    
    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def ensure_connection(self) -> None:
        """Ensure connection is active."""
        if self._conn is None or self._conn.closed:
            self.connect()
    
    def __enter__(self):
        self.ensure_connection()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding via Ollama."""
        url = f"{self.config.ollama_url}/api/embeddings"
        response = requests.post(url, json={
            "model": self.config.embed_model,
            "prompt": text
        })
        response.raise_for_status()
        return response.json()["embedding"]
    
    def search_chunks(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search chunks using vector similarity."""
        self.ensure_connection()
        
        # Generate embedding for query
        embedding = self.generate_embedding(query)
        
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    r.id,
                    r.document_id,
                    r.chunk_index,
                    r.content,
                    r.metadata,
                    r.created_at,
                    d.filename,
                    d.file_path,
                    1 - (r.embedding <=> %s::vector) as similarity
                FROM rag_documents r
                JOIN documents d ON r.document_id = d.id
                WHERE 1 - (r.embedding <=> %s::vector) >= %s
                ORDER BY r.embedding <=> %s::vector
                LIMIT %s
            """, (embedding, embedding, threshold, embedding, top_k))
            
            results = []
            for row in cur.fetchall():
                result = dict(row)
                result['embedding'] = None  # Don't return embedding
                results.append(result)
            
            return results
    
    def get_document_chunks(
        self,
        document_id: int,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get all chunks for a document."""
        self.ensure_connection()
        
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    id,
                    document_id,
                    chunk_index,
                    content,
                    metadata,
                    created_at
                FROM rag_documents
                WHERE document_id = %s
                ORDER BY chunk_index
                LIMIT %s
            """, (document_id, limit))
            
            return [dict(row) for row in cur.fetchall()]
    
    def insert_document(
        self,
        filename: str,
        file_path: str,
        file_type: str,
        file_size: int,
        content: str,
        metadata: Optional[Dict] = None
    ) -> int:
        """Insert document and return ID."""
        self.ensure_connection()
        
        with self._conn.cursor() as cur:
            cur.execute("""
                INSERT INTO documents 
                (filename, file_path, file_type, file_size, content, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (filename, file_path, file_type, file_size, content, json.dumps(metadata or {})))
            
            return cur.fetchone()[0]
    
    def insert_chunk(
        self,
        document_id: int,
        chunk_index: int,
        content: str,
        embedding: List[float],
        metadata: Optional[Dict] = None
    ) -> int:
        """Insert chunk into rag_documents and return ID."""
        self.ensure_connection()
        
        with self._conn.cursor() as cur:
            cur.execute("""
                INSERT INTO rag_documents 
                (document_id, chunk_index, content, embedding, metadata)
                VALUES (%s, %s, %s, %s::vector, %s)
                RETURNING id
            """, (document_id, chunk_index, content, embedding, json.dumps(metadata or {})))
            
            return cur.fetchone()[0]
    
    def get_user_context(
        self,
        user_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get recent user context for contextual strategy."""
        self.ensure_connection()
        
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT query, strategy, results, created_at
                FROM user_context
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (user_id, limit))
            
            return [dict(row) for row in cur.fetchall()]
    
    def store_user_context(
        self,
        user_id: str,
        session_id: Optional[str],
        query: str,
        strategy: str,
        results: Dict[str, Any]
    ) -> None:
        """Store user context for future retrieval."""
        self.ensure_connection()
        
        with self._conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_context 
                (user_id, session_id, query, strategy, results)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, session_id, query, strategy, json.dumps(results)))
        
        self._conn.commit()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        self.ensure_connection()
        
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM documents")
            doc_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM rag_documents")
            chunk_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM user_context")
            context_count = cur.fetchone()[0]
            
            return {
                "documents": doc_count,
                "chunks": chunk_count,
                "user_context_entries": context_count,
            }
    
    def delete_document(self, document_id: int) -> bool:
        """Delete document and its chunks."""
        self.ensure_connection()
        
        with self._conn.cursor() as cur:
            # Delete chunks first (foreign key)
            cur.execute("DELETE FROM rag_documents WHERE document_id = %s", (document_id,))
            # Delete document
            cur.execute("DELETE FROM documents WHERE id = %s", (document_id,))
        
        self._conn.commit()
        return True
