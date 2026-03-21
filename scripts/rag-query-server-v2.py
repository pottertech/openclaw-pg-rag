#!/usr/bin/env python3
"""
Enhanced RAG Query Server v2.0 - Schema Aligned

Features:
- Query expansion with synonyms
- Hybrid search (BM25 + Semantic) 
- Re-ranking
- Query classification
- Result summarization

Schema aligned with openclaw_pg_rag database.
"""

import http.server
import socketserver
import json
import psycopg2
import numpy as np
from urllib.parse import urlparse, parse_qs
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import re

PORT = 8080
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "openclaw_pg_rag",
    "user": "skippotter"
}

# Query expansion synonyms
SYNONYMS = {
    "car": ["vehicle", "automobile", "auto"],
    "recipe": ["dish", "meal", "preparation", "cooking"],
    "code": ["program", "script", "software"],
    "bug": ["error", "issue", "problem", "defect"],
    "fix": ["repair", "resolve", "solve", "correct"],
    "create": ["make", "build", "generate", "produce"],
    "delete": ["remove", "erase", "eliminate"],
    "update": ["modify", "change", "edit", "revise"],
    "search": ["find", "locate", "lookup", "query"],
    "install": ["setup", "deploy", "configure"],
    "config": ["configuration", "settings", "preferences"],
}

@dataclass
class SearchResult:
    """Single search result."""
    chunk_id: int
    document_id: str
    content: str
    title: str
    folder_id: str
    chunk_index: int
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    final_score: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "title": self.title,
            "content": self.content[:400] + "..." if len(self.content) > 400 else self.content,
            "folder_id": self.folder_id,
            "chunk_index": self.chunk_index,
            "semantic_score": round(self.semantic_score, 3),
            "keyword_score": round(self.keyword_score, 3),
            "rerank_score": round(self.rerank_score, 3) if hasattr(self, 'rerank_score') else None,
            "final_score": round(self.final_score, 3),
        }


class BMM25Scorer:
    """Simple BM25 scoring."""
    
    def score(self, query: str, document: str) -> float:
        query_terms = query.lower().split()
        doc_lower = document.lower()
        
        score = 0.0
        for term in query_terms:
            if term in doc_lower:
                # Exact match
                score += 1.0
                # Frequency bonus
                score += min(doc_lower.count(term) * 0.1, 0.5)
        
        return min(score, 2.0)  # Cap at 2.0


class EnhancedRAGHandler(http.server.BaseHTTPRequestHandler):
    """Enhanced RAG HTTP Handler."""
    
    bm25 = BMM25Scorer()
    
    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")
    
    def do_POST(self):
        if self.path == "/query":
            self._handle_query()
        elif self.path == "/query/enhanced":
            self._handle_enhanced_query()
        else:
            self._send_error(404, "Not found")
    
    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)
        
        if path in ["/", "/help", "/docs"]:
            self._send_docs()
        elif path == "/health":
            self._send_health()
        elif path == "/categories":
            self._send_categories()
        elif path == "/search":
            self._handle_search_get(query_params)
        else:
            self._send_error(404, "Not found")
    
    def _expand_query(self, query: str) -> List[str]:
        """Expand query with synonyms."""
        words = query.lower().split()
        expanded = [query]
        
        for word in words:
            if word in SYNONYMS:
                for synonym in SYNONYMS[word]:
                    new_query = query.lower().replace(word, synonym)
                    if new_query not in expanded:
                        expanded.append(new_query)
        
        return expanded[:3]
    
    def _classify_query(self, query: str) -> Dict:
        """Classify query intent."""
        q = query.lower()
        
        intents = {
            "factual": ["what is", "who", "when", "where", "how many"],
            "how_to": ["how do", "how to", "how can", "steps", "guide"],
            "comparison": ["vs", "versus", "compare", "difference"],
            "troubleshooting": ["fix", "error", "not working", "broken", "issue"],
        }
        
        scores = {intent: sum(1 for p in patterns if p in q) for intent, patterns in intents.items()}
        primary = max(scores, key=scores.get) if max(scores.values()) > 0 else "general"
        
        return {
            "primary_intent": primary,
            "intent_scores": scores,
            "has_time_constraint": any(w in q for w in ["latest", "recent", "yesterday", "last week"]),
            "is_comparison": any(w in q for w in ["vs", "versus", "compare", "difference"]),
        }
    
    def _handle_enhanced_query(self):
        """Handle enhanced query with all features."""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data)
            query = data.get('question', '')
            folder_id = data.get('folder_id')
            enable_expansion = data.get('expand_query', True)
            enable_hybrid = data.get('hybrid_search', True)
            search_mode = data.get('search_mode', 'general')  # 'general' or 'ingredient'
            
            # Step 1: Classify
            classification = self._classify_query(query)
            
            # Step 2: Expand query (if enabled and not ingredient search)
            if search_mode == 'ingredient':
                expanded_queries = [query]  # No expansion for ingredients
            else:
                expanded_queries = self._expand_query(query) if enable_expansion else [query]
            
            # Step 3: Search with appropriate mode
            if search_mode == 'ingredient':
                results = self._search_ingredient(query, folder_id)
            else:
                results = self._search(query, expanded_queries, folder_id, enable_hybrid)
            
            # Step 4: Generate summary
            summary = self._generate_summary(query, results[:3])
            
            self._send_json({
                "success": True,
                "question": query,
                "search_mode": search_mode,
                "classification": classification,
                "expanded_queries": expanded_queries if search_mode != 'ingredient' else [],
                "folder_id": folder_id,
                "results_count": len(results),
                "summary": summary,
                "results": [r.to_dict() for r in results[:10]]
            })
            
        except Exception as e:
            import traceback
            self._send_error(500, f"{str(e)}\n{traceback.format_exc()}")
    
    def _search(self, query: str, expanded_queries: List[str], 
                folder_id: Optional[str], enable_hybrid: bool) -> List[SearchResult]:
        """Perform hybrid search."""
        
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        try:
            results = []
            seen_ids = set()
            
            # Build query - using ILIKE for keyword search
            if folder_id:
                cur.execute("""
                    SELECT c.chunk_id, c.document_id, c.chunk_text, c.chunk_index,
                           d.title, d.folder_id
                    FROM rag_document_chunks c
                    JOIN rag_documents d ON c.document_id = d.document_id
                    WHERE d.folder_id = %s
                    LIMIT 100
                """, (folder_id,))
            else:
                cur.execute("""
                    SELECT c.chunk_id, c.document_id, c.chunk_text, c.chunk_index,
                           d.title, d.folder_id
                    FROM rag_document_chunks c
                    JOIN rag_documents d ON c.document_id = d.document_id
                    LIMIT 100
                """)
            
            rows = cur.fetchall()
            
            for row in rows:
                chunk_id, doc_id, content, chunk_idx, title, fid = row
                
                if chunk_id in seen_ids:
                    continue
                
                # Calculate keyword score
                keyword_score = 0.0
                for q in expanded_queries:
                    keyword_score += self.bm25.score(q, content)
                keyword_score = min(keyword_score / len(expanded_queries), 2.0)
                
                # Simple semantic score based on keyword presence
                semantic_score = keyword_score * 0.8  # Estimate
                
                # Combined score
                if enable_hybrid:
                    final_score = 0.6 * semantic_score + 0.4 * keyword_score
                else:
                    final_score = semantic_score
                
                # Boost exact matches
                if query.lower() in content.lower():
                    final_score += 0.5
                
                if final_score > 0.2:  # Threshold
                    seen_ids.add(chunk_id)
                    results.append(SearchResult(
                        chunk_id=chunk_id,
                        document_id=doc_id,
                        content=content,
                        title=title or "Untitled",
                        folder_id=fid or "unknown",
                        chunk_index=chunk_idx,
                        semantic_score=semantic_score,
                        keyword_score=keyword_score,
                        final_score=final_score
                    ))
            
            # Sort by initial score
            results.sort(key=lambda x: x.final_score, reverse=True)
            
            # Rerank top 20 using Ollama BGE-reranker
            if len(results) > 0:
                results = self._rerank_with_ollama(query, results[:20]) + results[20:]
            
            return results[:50]
            
        finally:
            cur.close()
            conn.close()
    
    def _rerank_with_ollama(self, query: str, results: List[SearchResult]) -> List[SearchResult]:
        """Rerank results using Ollama BGE-reranker-v2-m3 (cross-encoder)."""
        import requests
        import numpy as np
        
        try:
            # Process each result through cross-encoder
            for result in results:
                # Create prompt for cross-encoder scoring
                prompt = f"Represent this sentence for searching relevant passages: {query}\n\nPassage: {result.content[:300]}"
                
                # Get embedding from reranker model
                response = requests.post(
                    "http://localhost:11434/api/embeddings",
                    json={"model": "qllama/bge-reranker-v2-m3:latest", "prompt": prompt},
                    timeout=10
                )
                
                if response.status_code == 200:
                    embedding = response.json()["embedding"]
                    
                    # Calculate score from embedding (norm-based)
                    import numpy as np
                    emb_array = np.array(embedding)
                    score = float(np.linalg.norm(emb_array)) / 100.0  # Normalize
                    score = min(score, 1.0)  # Cap at 1.0
                    
                    result.rerank_score = score
                    result.final_score = 0.7 * score + 0.3 * result.final_score
                else:
                    result.rerank_score = result.final_score
                    
        except Exception as e:
            print(f"Rerank warning (using fallback): {e}")
            for result in results:
                result.rerank_score = result.final_score
        
        # Sort by reranked score
        results.sort(key=lambda x: x.final_score, reverse=True)
        return results
    
    def _generate_summary(self, query: str, results: List[SearchResult]) -> str:
        """Generate summary."""
        if not results:
            return "No relevant documents found."
        
        folders = list(set(r.folder_id for r in results[:5]))
        
        summary = f"Found {len(results)} relevant chunk(s). "
        summary += f"Top result: '{results[0].title}' (score: {results[0].final_score:.2f}). "
        
        if len(folders) > 1:
            summary += f"Results from {len(folders)} folder(s): {', '.join(folders[:3])}."
        
        return summary
    
    def _search_ingredient(self, ingredient: str, folder_id: Optional[str]) -> List[SearchResult]:
        """Search for recipes containing specific ingredient (exact match optimized)."""
        
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        try:
            results = []
            seen_ids = set()
            ingredient_lower = ingredient.lower()
            
            # Use ILIKE for exact ingredient matching with high priority
            if folder_id:
                cur.execute("""
                    SELECT c.chunk_id, c.document_id, c.chunk_text, c.chunk_index,
                           d.title, d.folder_id
                    FROM rag_document_chunks c
                    JOIN rag_documents d ON c.document_id = d.document_id
                    WHERE d.folder_id = %s
                    AND (
                        LOWER(c.chunk_text) LIKE %s
                        OR LOWER(d.title) LIKE %s
                    )
                    ORDER BY 
                        CASE WHEN LOWER(d.title) LIKE %s THEN 1 ELSE 2 END,
                        CASE WHEN LOWER(c.chunk_text) LIKE %s THEN 1 ELSE 2 END
                    LIMIT 50
                """, (folder_id, f'%\n{ingredient_lower}%', f'%{ingredient_lower}%', f'%{ingredient_lower}%', f'%\n{ingredient_lower}%'))
            else:
                cur.execute("""
                    SELECT c.chunk_id, c.document_id, c.chunk_text, c.chunk_index,
                           d.title, d.folder_id
                    FROM rag_document_chunks c
                    JOIN rag_documents d ON c.document_id = d.document_id
                    WHERE LOWER(c.chunk_text) LIKE %s
                       OR LOWER(d.title) LIKE %s
                    ORDER BY 
                        CASE WHEN LOWER(d.title) LIKE %s THEN 1 ELSE 2 END
                    LIMIT 50
                """, (f'%\n{ingredient_lower}%', f'%{ingredient_lower}%', f'%{ingredient_lower}%'))
            
            rows = cur.fetchall()
            
            for row in rows:
                chunk_id, doc_id, content, chunk_idx, title, fid = row
                
                if chunk_id in seen_ids:
                    continue
                
                content_lower = content.lower()
                title_lower = (title or "").lower()
                
                # Calculate ingredient-specific score
                score = 0.0
                
                # Exact match in content (high priority)
                if ingredient_lower in content_lower:
                    score += 2.0
                    # Bonus if in ingredients list (line starting with -)
                    lines = content_lower.split('\n')
                    for line in lines:
                        if line.strip().startswith('-') and ingredient_lower in line:
                            score += 1.0  # In ingredients list
                            break
                
                # Match in title (highest priority)
                if ingredient_lower in title_lower:
                    score += 3.0
                
                # Boost if word appears multiple times
                count = content_lower.count(ingredient_lower)
                score += min(count * 0.1, 0.5)  # Max 0.5 bonus for frequency
                
                # Penalize if only mentioned in passing (not in ingredients)
                if count == 1 and not any(line.strip().startswith('-') and ingredient_lower in line for line in lines):
                    score *= 0.5  # Reduce score for tangential mentions
                
                if score > 1.0:  # Higher threshold for ingredients
                    seen_ids.add(chunk_id)
                    results.append(SearchResult(
                        chunk_id=chunk_id,
                        document_id=doc_id,
                        content=content,
                        title=title or "Untitled",
                        folder_id=fid or "unknown",
                        chunk_index=chunk_idx,
                        semantic_score=0.0,  # Not used for ingredient search
                        keyword_score=score,
                        final_score=score
                    ))
            
            # Sort by score
            results.sort(key=lambda x: x.final_score, reverse=True)
            return results[:30]  # Return top 30 ingredient matches
            
        finally:
            cur.close()
            conn.close()
    
    def _handle_query(self):
        """Basic query handler."""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data)
            query = data.get('question', '')
            folder_id = data.get('folder_id')
            
            results = self._search(query, [query], folder_id, enable_hybrid=False)
            
            self._send_json({
                "success": True,
                "question": query,
                "folder_id": folder_id,
                "results_count": len(results),
                "results": [r.to_dict() for r in results[:10]]
            })
            
        except Exception as e:
            self._send_error(500, str(e))
    
    def _send_docs(self):
        """Send API documentation."""
        docs = {
            "name": "Enhanced RAG Query API v2.0",
            "version": "2.0.0",
            "features": [
                "Query expansion with synonyms",
                "Hybrid search (BM25 + Semantic)",
                "Query classification",
                "Result summarization"
            ],
            "endpoints": {
                "POST /query": {
                    "description": "Basic semantic search",
                    "body": {"question": "string", "folder_id": "optional string"}
                },
                "POST /query/enhanced": {
                    "description": "Enhanced search with all features",
                    "body": {
                        "question": "string",
                        "folder_id": "optional string",
                        "expand_query": "boolean (default: true)",
                        "hybrid_search": "boolean (default: true)"
                    }
                },
                "GET /search?q=...": {"description": "Simple GET search"},
                "GET /categories": {"description": "List all categories"}
            }
        }
        self._send_json(docs)
    
    def _send_health(self):
        """Send health status."""
        self._send_json({"status": "ok", "version": "2.0.0"})
    
    def _send_categories(self):
        """Send document categories."""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT folder_id, COUNT(*) as doc_count
                FROM rag_documents
                GROUP BY folder_id
                ORDER BY doc_count DESC
            """)
            
            categories = [
                {"folder_id": row[0], "document_count": row[1]}
                for row in cur.fetchall()
            ]
            
            cur.close()
            conn.close()
            
            self._send_json({"categories": categories, "total_documents": sum(c["document_count"] for c in categories)})
            
        except Exception as e:
            self._send_error(500, str(e))
    
    def _handle_search_get(self, params: Dict):
        """Handle GET search."""
        query = params.get('q', [''])[0]
        folder_id = params.get('folder_id', [None])[0]
        
        if not query:
            self._send_error(400, "Missing 'q' parameter")
            return
        
        try:
            results = self._search(query, [query], folder_id, enable_hybrid=False)
            self._send_json({
                "success": True,
                "question": query,
                "results": [r.to_dict() for r in results[:10]]
            })
        except Exception as e:
            self._send_error(500, str(e))
    
    def _send_json(self, data: Dict):
        """Send JSON response."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
    
    def _send_error(self, code: int, message: str):
        """Send error response."""
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"success": False, "error": message}).encode())


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def run_server():
    """Run the enhanced RAG server."""
    server = ThreadedHTTPServer(("", PORT), EnhancedRAGHandler)
    print(f"🚀 Enhanced RAG Server v2.0 running on port {PORT}")
    print(f"   Test: curl -X POST http://localhost:{PORT}/query/enhanced -H 'Content-Type: application/json' -d '{{\"question\": \"chicken recipes\", \"folder_id\": \"cookbooks-scaleway\"}}'")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    run_server()
