"""Build and query a local, traceable timing knowledge base."""

from .contracts import BuildConfig, RagError
from .service import build_knowledge_base, search_knowledge_base

__all__ = ["BuildConfig", "RagError", "build_knowledge_base", "search_knowledge_base"]
