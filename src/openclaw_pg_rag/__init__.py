"""OpenClaw pg-rag: PostgreSQL RAG with strategy-based retrieval."""

from .client import PgRAGClient, QueryStrategy
from .config import PgRAGConfig, get_config
from .strategies import (
    FactualStrategy,
    AnalyticalStrategy,
    OpinionStrategy,
    ContextualStrategy,
    StrategyResult,
)
from .database import DatabaseClient

__version__ = "1.0.0"
__all__ = [
    "PgRAGClient",
    "QueryStrategy",
    "PgRAGConfig",
    "get_config",
    "DatabaseClient",
    "FactualStrategy",
    "AnalyticalStrategy",
    "OpinionStrategy",
    "ContextualStrategy",
    "StrategyResult",
]