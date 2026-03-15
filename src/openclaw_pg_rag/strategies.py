"""Strategy-based retrieval for pg-rag."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
import re


class QueryStrategy(Enum):
    """Available retrieval strategies."""
    FACTUAL = "factual"
    ANALYTICAL = "analytical"
    OPINION = "opinion"
    CONTEXTUAL = "contextual"
    AUTO = "auto"


@dataclass
class StrategyResult:
    """Result from a strategy execution."""
    strategy: QueryStrategy
    original_query: str
    transformed_queries: List[str]
    chunks: List[Dict[str, Any]]
    total_results: int
    execution_time_ms: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseStrategy(ABC):
    """Base class for retrieval strategies."""
    
    def __init__(self, config: Any):
        self.config = config
    
    @abstractmethod
    def transform_query(self, query: str, context: Optional[str] = None) -> List[str]:
        """Transform query for retrieval."""
        pass
    
    @abstractmethod
    def rank_results(self, chunks: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """Rank and filter retrieved chunks."""
        pass
    
    def execute(
        self,
        query: str,
        db_client: Any,
        context: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> StrategyResult:
        """Execute the strategy."""
        import time
        start = time.time()
        
        transformed = self.transform_query(query, context)
        
        all_chunks = []
        for tq in transformed:
            chunks = db_client.search_chunks(tq, self.get_top_k())
            all_chunks.extend(chunks)
        
        seen = set()
        unique_chunks = []
        for c in all_chunks:
            if c['id'] not in seen:
                seen.add(c['id'])
                unique_chunks.append(c)
        
        ranked = self.rank_results(unique_chunks, query)
        
        execution_time = int((time.time() - start) * 1000)
        
        return StrategyResult(
            strategy=self.get_strategy_type(),
            original_query=query,
            transformed_queries=transformed,
            chunks=ranked[:self.config.top_k],
            total_results=len(ranked),
            execution_time_ms=execution_time,
            metadata=self.get_metadata()
        )
    
    @abstractmethod
    def get_strategy_type(self) -> QueryStrategy:
        pass
    
    @abstractmethod
    def get_top_k(self) -> int:
        pass
    
    def get_metadata(self) -> Dict[str, Any]:
        return {}


class FactualStrategy(BaseStrategy):
    """High-precision retrieval for factual queries."""
    
    def get_strategy_type(self) -> QueryStrategy:
        return QueryStrategy.FACTUAL
    
    def get_top_k(self) -> int:
        return self.config.top_k
    
    def transform_query(self, query: str, context: Optional[str] = None) -> List[str]:
        transformed = [query]
        entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b|\b\d{4}\b|\b\d+\.?\d*\s*(?:GB|MB|KB|TB|ms|s|minutes?|hours?|days?)\b', query)
        if entities:
            entity_query = " ".join(entities)
            transformed.append(entity_query)
        key_terms = re.findall(r'\b\w{4,}\b', query.lower())
        if len(key_terms) >= 3:
            transformed.append(" ".join(key_terms[:5]))
        return transformed
    
    def rank_results(self, chunks: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        threshold = self.config.factual_threshold
        filtered = [c for c in chunks if c.get('similarity', 0) >= threshold]
        filtered.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        query_lower = query.lower()
        for c in filtered:
            content_lower = c.get('content', '').lower()
            if query_lower in content_lower:
                c['similarity'] = min(1.0, c.get('similarity', 0) + 0.1)
            key_terms = set(re.findall(r'\b\w{4,}\b', query_lower))
            content_terms = set(re.findall(r'\b\w{4,}\b', content_lower))
            overlap = len(key_terms & content_terms) / len(key_terms) if key_terms else 0
            c['similarity'] = min(1.0, c.get('similarity', 0) + (overlap * 0.05))
        filtered.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        return filtered
    
    def get_metadata(self) -> Dict[str, Any]:
        return {"threshold": self.config.factual_threshold, "focus": "precision"}


class AnalyticalStrategy(BaseStrategy):
    """Broad coverage retrieval for analytical queries."""
    
    def get_strategy_type(self) -> QueryStrategy:
        return QueryStrategy.ANALYTICAL
    
    def get_top_k(self) -> int:
        return self.config.top_k * 2
    
    def transform_query(self, query: str, context: Optional[str] = None) -> List[str]:
        transformed = [query]
        words = query.lower().split()
        stop_words = {'what', 'are', 'the', 'is', 'how', 'why', 'when', 'where', 'who', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or', 'but'}
        key_words = [w for w in words if w not in stop_words and len(w) > 3]
        if key_words:
            topic = key_words[0]
            aspects = [
                f"{topic} features",
                f"{topic} benefits",
                f"{topic} implementation",
                f"{topic} examples",
                f"{topic} comparison",
            ]
            transformed.extend(aspects[:3])
        return transformed
    
    def rank_results(self, chunks: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        threshold = self.config.analytical_threshold
        filtered = [c for c in chunks if c.get('similarity', 0) >= threshold]
        by_doc: Dict[int, List[Dict]] = {}
        for c in filtered:
            doc_id = c.get('document_id', 0)
            if doc_id not in by_doc:
                by_doc[doc_id] = []
            by_doc[doc_id].append(c)
        interleaved = []
        doc_ids = list(by_doc.keys())
        idx = 0
        while len(interleaved) < self.config.top_k:
            added = False
            for doc_id in doc_ids:
                if idx < len(by_doc[doc_id]):
                    interleaved.append(by_doc[doc_id][idx])
                    added = True
            idx += 1
            if not added:
                break
        return interleaved
    
    def get_metadata(self) -> Dict[str, Any]:
        return {"threshold": self.config.analytical_threshold, "focus": "coverage"}


class OpinionStrategy(BaseStrategy):
    """Diverse perspective retrieval for opinion queries."""
    
    def get_strategy_type(self) -> QueryStrategy:
        return QueryStrategy.OPINION
    
    def get_top_k(self) -> int:
        return self.config.top_k * 2
    
    def transform_query(self, query: str, context: Optional[str] = None) -> List[str]:
        transformed = [query]
        words = query.lower().split()
        stop_words = {'what', 'are', 'the', 'is', 'how', 'why', 'when', 'where', 'who', 'do', 'you', 'think', 'about', 'opinion', 'view', 'perspective'}
        key_words = [w for w in words if w not in stop_words and len(w) > 3]
        if key_words:
            topic = key_words[0]
            perspectives = [
                f"{topic} advantages",
                f"{topic} disadvantages",
                f"{topic} criticism",
                f"{topic} support",
            ]
            transformed.extend(perspectives)
        return transformed
    
    def rank_results(self, chunks: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        threshold = self.config.opinion_threshold
        filtered = [c for c in chunks if c.get('similarity', 0) >= threshold]
        positive_words = {'good', 'great', 'excellent', 'benefit', 'advantage', 'pro', 'positive', 'recommend', 'best', 'better', 'improve', 'success'}
        negative_words = {'bad', 'poor', 'disadvantage', 'con', 'negative', 'problem', 'issue', 'concern', 'criticism', 'limitation', 'drawback', 'risk'}
        positive_chunks = []
        negative_chunks = []
        neutral_chunks = []
        for c in filtered:
            content_lower = c.get('content', '').lower()
            pos_count = sum(1 for w in positive_words if w in content_lower)
            neg_count = sum(1 for w in negative_words if w in content_lower)
            if pos_count > neg_count:
                c['sentiment'] = 'positive'
                positive_chunks.append(c)
            elif neg_count > pos_count:
                c['sentiment'] = 'negative'
                negative_chunks.append(c)
            else:
                c['sentiment'] = 'neutral'
                neutral_chunks.append(c)
        balanced = []
        idx = 0
        while len(balanced) < self.config.top_k:
            if idx < len(positive_chunks):
                balanced.append(positive_chunks[idx])
            if idx < len(negative_chunks):
                balanced.append(negative_chunks[idx])
            if idx < len(neutral_chunks):
                balanced.append(neutral_chunks[idx])
            idx += 1
            if idx > max(len(positive_chunks), len(negative_chunks), len(neutral_chunks)):
                break
        return balanced
    
    def get_metadata(self) -> Dict[str, Any]:
        return {"threshold": self.config.opinion_threshold, "focus": "diversity"}


class ContextualStrategy(BaseStrategy):
    """User-context-aware retrieval for personalized queries."""
    
    def get_strategy_type(self) -> QueryStrategy:
        return QueryStrategy.CONTEXTUAL
    
    def get_top_k(self) -> int:
        return self.config.top_k
    
    def transform_query(self, query: str, context: Optional[str] = None) -> List[str]:
        transformed = [query]
        if context:
            combined = f"{query} {context}"
            transformed.append(combined)
            context_terms = re.findall(r'\b\w{4,}\b', context.lower())
            if context_terms:
                transformed.append(f"{' '.join(context_terms[:5])} {query}")
        return transformed
    
    def rank_results(self, chunks: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        threshold = self.config.contextual_threshold
        filtered = [c for c in chunks if c.get('similarity', 0) >= threshold]
        from datetime import datetime
        now = datetime.now()
        for c in filtered:
            boost = 0.0
            created_at = c.get('created_at')
            if created_at:
                try:
                    if isinstance(created_at, str):
                        created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    else:
                        created = created_at
                    days_old = (now - created).days
                    if days_old < 7:
                        boost += 0.1
                    elif days_old < 30:
                        boost += 0.05
                except:
                    pass
            if c.get('user_relevance'):
                boost += c.get('user_relevance', 0) * 0.1
            c['similarity'] = min(1.0, c.get('similarity', 0) + boost)
        filtered.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        return filtered
    
    def get_metadata(self) -> Dict[str, Any]:
        return {"threshold": self.config.contextual_threshold, "focus": "personalization"}


class StrategyDetector:
    """Auto-detect appropriate strategy for a query."""
    
    FACTUAL_KEYWORDS = [
        'what is', 'what are', 'define', 'explain', 'how many', 'how much',
        'when did', 'where is', 'who is', 'list', 'name', 'specify',
        'price', 'cost', 'version', 'date', 'time', 'location'
    ]
    
    ANALYTICAL_KEYWORDS = [
        'analyze', 'analysis', 'compare', 'contrast', 'evaluate', 'assess',
        'examine', 'investigate', 'review', 'study', 'research',
        'how does', 'why does', 'what causes', 'what factors',
        'review this', 'review the', 'review my', 'code review', 'pr review'
    ]
    
    OPINION_KEYWORDS = [
        'opinion', 'think', 'believe', 'view', 'perspective', 'stance',
        'recommend', 'suggest', 'advise', 'best', 'worst', 'better', 'worse',
        'should', 'would', 'could', 'pros', 'cons', 'advantages', 'disadvantages'
    ]
    
    CONTEXTUAL_KEYWORDS = [
        'my', 'mine', 'our', 'we', 'us', 'previous', 'before', 'earlier',
        'last time', 'again', 'also', 'too', 'as well', 'in addition',
        'referring to', 'about that', 'regarding', 'concerning'
    ]
    
    @classmethod
    def detect(cls, query: str) -> QueryStrategy:
        query_lower = query.lower()
        scores = {
            QueryStrategy.FACTUAL: 0,
            QueryStrategy.ANALYTICAL: 0,
            QueryStrategy.OPINION: 0,
            QueryStrategy.CONTEXTUAL: 0,
        }
        for kw in cls.FACTUAL_KEYWORDS:
            if kw in query_lower:
                scores[QueryStrategy.FACTUAL] += 1
        for kw in cls.ANALYTICAL_KEYWORDS:
            if kw in query_lower:
                scores[QueryStrategy.ANALYTICAL] += 1
        for kw in cls.OPINION_KEYWORDS:
            if kw in query_lower:
                scores[QueryStrategy.OPINION] += 1
        for kw in cls.CONTEXTUAL_KEYWORDS:
            if kw in query_lower:
                scores[QueryStrategy.CONTEXTUAL] += 1
        best = max(scores, key=scores.get)
        if scores[best] == 0:
            return QueryStrategy.ANALYTICAL
        return best
