"""Public data and failure contracts shared by build, retrieval and CLI."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


def load_config(path):
    """Read a YAML build configuration using the public validation contract."""
    try:
        values = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(values, dict):
            raise TypeError("configuration must be a YAML mapping")
        return BuildConfig(**values)
    except (OSError, UnicodeError, ValueError, TypeError, yaml.YAMLError) as exc:
        raise InputError(f"{path}: invalid configuration: {exc}") from exc


class RagError(Exception):
    """Base class for actionable RAG failures."""


class InputError(RagError):
    """Invalid caller input or source document."""


class ChunkingError(InputError):
    """A protected source unit cannot fit the configured token budget."""


class ModelError(RagError):
    """The configured local embedding model cannot fulfill its contract."""


class StorageError(RagError):
    """A filesystem or vector storage operation failed."""


class ConsistencyError(StorageError):
    """Persisted data are incomplete or incompatible."""


@dataclass(frozen=True)
class BuildConfig:
    """Reproducible build parameters; model files are provisioned separately."""

    model_path: str
    revision: str
    model_id: str = "Qwen/Qwen3-Embedding-0.6B"
    dimension: int = 1024
    max_tokens: int = 1024
    overlap_tokens: int = 128
    device: str = "cpu"
    dtype: str = "float32"
    batch_size: int = 8

    def __post_init__(self):
        """Keep impossible budgets and unsupported encoding modes out of builds."""
        if type(self.max_tokens) is not int or not 0 < self.max_tokens <= 32768:
            raise InputError("max_tokens must be an integer in 1..32768")
        if type(self.overlap_tokens) is not int or not 0 <= self.overlap_tokens < self.max_tokens:
            raise InputError("overlap_tokens must be an integer in 0..max_tokens-1")
        if type(self.dimension) is not int or self.dimension != 1024:
            raise InputError("dimension must be 1024")
        if type(self.batch_size) is not int or self.batch_size <= 0:
            raise InputError("batch_size must be a positive integer")
        if self.dtype not in {"float32", "float16", "bfloat16"}:
            raise InputError("dtype must be float32, float16 or bfloat16")
        if self.model_id != "Qwen/Qwen3-Embedding-0.6B":
            raise InputError("model_id must be Qwen/Qwen3-Embedding-0.6B")
        for name in ("model_path", "revision", "device"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise InputError(f"{name} must be a nonempty string")


@dataclass
class Chunk:
    """Text plus original body spans; synthetic context is kept separately."""

    chunk_id: str
    document_id: str
    title: str
    source_path: str
    heading_path: list[str]
    text: str
    topics: list[str]
    sources: list[str]
    body_spans: list[list[int]]
    encoding_text: str
    token_count: int
    structure_id: str | None = None
    language: str | None = None


@dataclass
class BuildReport:
    """Published build identity and counts."""

    build_id: str
    document_count: int
    chunk_count: int
    config: dict


@dataclass
class SearchHit:
    """One ranked chunk; scores are mode-specific, not probabilities."""

    chunk: Chunk
    rank: int
    score: float
    dense_rank: int | None = None
    bm25_rank: int | None = None


@dataclass
class SearchResponse:
    """A single generation's ordered retrieval results and effective settings."""

    build_id: str
    mode: str
    top_k: int
    candidate_k: int
    rrf_k: float
    results: list[SearchHit] = field(default_factory=list)
