"""Main client for OpenClaw pg-rag."""

from typing import List, Dict, Any, Optional
import time

from .config import PgRAGConfig, get_config
from .database import DatabaseClient
from .strategies import (
    QueryStrategy,
    StrategyDetector,
    FactualStrategy,
    AnalyticalStrategy,
    OpinionStrategy,
    ContextualStrategy,
    StrategyResult,
)


class PgRAGClient:
    """Main client for PostgreSQL RAG with strategy-based retrieval."""
    
    def __init__(self, config: Optional[PgRAGConfig] = None):
        self.config = config or get_config()
        self.db = DatabaseClient(self.config)
        
        # Initialize strategies
        self.strategies = {
            QueryStrategy.FACTUAL: FactualStrategy(self.config),
            QueryStrategy.ANALYTICAL: AnalyticalStrategy(self.config),
            QueryStrategy.OPINION: OpinionStrategy(self.config),
            QueryStrategy.CONTEXTUAL: ContextualStrategy(self.config),
        }
    
    def search(
        self,
        query: str,
        strategy: Optional[QueryStrategy] = None,
        user_id: Optional[str] = None,
        context_summary: Optional[str] = None,
        auto_detect: bool = True
    ) -> StrategyResult:
        """
        Search with strategy-based retrieval.
        
        Args:
            query: User query
            strategy: Explicit strategy (or auto-detect if None)
            user_id: User ID for contextual strategy
            context_summary: Context summary for contextual strategy
            auto_detect: Whether to auto-detect strategy if not specified
            
        Returns:
            StrategyResult with retrieved chunks
        """
        # Auto-detect strategy if not specified
        if strategy is None or strategy == QueryStrategy.AUTO:
            if auto_detect:
                strategy = StrategyDetector.detect(query)
            else:
                strategy = QueryStrategy.ANALYTICAL  # Default
        
        # Get strategy handler
        strategy_handler = self.strategies.get(strategy)
        if not strategy_handler:
            raise ValueError(f"Unknown strategy: {strategy}")
        
        # Execute strategy
        result = strategy_handler.execute(
            query=query,
            db_client=self.db,
            context=context_summary,
            user_id=user_id
        )
        
        # Store user context if user_id provided
        if user_id:
            try:
                self.db.store_user_context(
                    user_id=user_id,
                    session_id=None,
                    query=query,
                    strategy=strategy.value,
                    results={
                        "transformed_queries": result.transformed_queries,
                        "total_results": result.total_results,
                        "top_chunks": [c.get('content', '')[:200] for c in result.chunks[:3]]
                    }
                )
            except Exception:
                pass  # Don't fail on context storage
        
        return result
    
    def get_document(self, document_id: int) -> Optional[Dict[str, Any]]:
        """Get full document content and metadata."""
        return self.db.get_document(document_id)
    
    def get_document_by_filename(self, filename: str) -> Optional[Dict[str, Any]]:
        """Get full document by filename."""
        return self.db.get_document_by_filename(filename)
    
    def get_document_chunks(self, document_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all chunks for a document."""
        return self.db.get_document_chunks(document_id, limit)
    
    def classify_query(self, query: str) -> QueryStrategy:
        """Classify a query into a strategy."""
        return StrategyDetector.detect(query)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        return self.db.get_stats()
    
    def close(self) -> None:
        """Close database connection."""
        self.db.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
