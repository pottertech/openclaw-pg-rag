"""Configuration management for OpenClaw pg-rag."""

import os
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
import json


@dataclass
class PgRAGConfig:
    """Configuration for pg-rag."""
    
    pg_host: str = field(default_factory=lambda: os.getenv("PG_HOST", "100.99.127.10"))
    pg_port: int = field(default_factory=lambda: int(os.getenv("PG_PORT", "5432")))
    pg_database: str = field(default_factory=lambda: os.getenv("PG_DATABASE", "openclaw_pg_rag"))
    pg_user: str = field(default_factory=lambda: os.getenv("PG_USER", "openclaw"))
    pg_password: str = field(default_factory=lambda: os.getenv("PG_PASSWORD", ""))
    
    ollama_url: str = field(default_factory=lambda: os.getenv("OLLAMA_URL", "http://localhost:11434"))
    embed_model: str = field(default_factory=lambda: os.getenv("EMBED_MODEL", "bge-m3"))
    
    chunk_size: int = field(default_factory=lambda: int(os.getenv("CHUNK_SIZE", "500")))
    chunk_overlap: int = field(default_factory=lambda: int(os.getenv("CHUNK_OVERLAP", "100")))
    
    factual_threshold: float = field(default_factory=lambda: float(os.getenv("FACTUAL_THRESHOLD", "0.85")))
    analytical_threshold: float = field(default_factory=lambda: float(os.getenv("ANALYTICAL_THRESHOLD", "0.75")))
    opinion_threshold: float = field(default_factory=lambda: float(os.getenv("OPINION_THRESHOLD", "0.70")))
    contextual_threshold: float = field(default_factory=lambda: float(os.getenv("CONTEXTUAL_THRESHOLD", "0.75")))
    
    top_k: int = field(default_factory=lambda: int(os.getenv("TOP_K", "5")))
    max_chunks_per_doc: int = field(default_factory=lambda: int(os.getenv("MAX_CHUNKS_PER_DOC", "3")))
    
    @property
    def pg_connection_string(self) -> str:
        return f"postgresql://{self.pg_user}:{self.pg_password}@{self.pg_host}:{self.pg_port}/{self.pg_database}"
    
    @classmethod
    def from_file(cls, path: str) -> "PgRAGConfig":
        with open(path, 'r') as f:
            data = json.load(f)
        return cls(**data)


_config: Optional[PgRAGConfig] = None


def get_config() -> PgRAGConfig:
    global _config
    if _config is None:
        config_paths = [
            Path.home() / ".openclaw" / "config" / "pg-rag.json",
            Path("config.json"),
        ]
        for path in config_paths:
            if path.exists():
                _config = PgRAGConfig.from_file(str(path))
                break
        else:
            _config = PgRAGConfig()
    return _config


def set_config(config: PgRAGConfig) -> None:
    global _config
    _config = config
