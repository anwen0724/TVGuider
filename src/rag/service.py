"""Application boundary for building and searching a local knowledge base."""

import math
from contextlib import contextmanager

from .chunking import chunk_documents
from .contracts import BuildConfig, BuildReport, InputError, ModelError, SearchHit, SearchResponse
from .document_loader import load_documents
from .embedding import QwenEmbedding, encode_checked
from .lexical import rank_bm25
from .retrieval import fuse, rank_dense
from .storage import load_generation, save_generation


@contextmanager
def _encoder(config, backend):
    """Own model lifetime only when the caller did not supply the adapter."""
    owned = backend is None
    adapter = QwenEmbedding(config) if owned else backend
    try:
        yield adapter
    finally:
        if owned:
            adapter.close()


def build_knowledge_base(source_dir, kb_dir, config, *, backend=None):
    """Build and publish a complete generation, preserving any previous one."""
    documents = load_documents(source_dir)
    with _encoder(config, backend) as adapter:
        chunks = chunk_documents(documents, config, adapter)
        vectors = encode_checked(adapter, [c.encoding_text for c in chunks])
        manifest = save_generation(kb_dir, documents, chunks, vectors, config, adapter.describe())
    return BuildReport(manifest["build_id"], len(documents), len(chunks), manifest["config"])


def search_knowledge_base(
    kb_dir, query, mode="hybrid", top_k=5, candidate_k=None, rrf_k=60, *, backend=None
):
    """Retrieve traceable chunks from the current complete generation."""
    if not isinstance(query, str) or not query.strip():
        raise InputError("query must be a nonempty string")
    if not isinstance(mode, str) or mode not in {"dense", "bm25", "hybrid"}:
        raise InputError("mode must be dense, bm25 or hybrid")
    if type(top_k) is not int or top_k <= 0:
        raise InputError("top_k must be a positive integer")
    candidate_k = max(20, top_k) if candidate_k is None else candidate_k
    if type(candidate_k) is not int or candidate_k < top_k:
        raise InputError("candidate_k must be an integer >= top_k")
    if type(rrf_k) not in {int, float} or not math.isfinite(rrf_k) or rrf_k <= 0:
        raise InputError("rrf_k must be a finite positive number")
    query = query.strip()
    generation, manifest, chunks, lexical = load_generation(kb_dir)
    by_id = {c.chunk_id: c for c in chunks}
    bm25 = rank_bm25(lexical, query) if mode != "dense" else []
    dense = []
    if mode != "bm25":
        with _encoder(BuildConfig(**manifest["config"]), backend) as adapter:
            if adapter.describe() != manifest["embedding"]:
                raise ModelError(
                    "Encoder configuration/revision differs from the built vector space"
                )
            dense = rank_dense(
                generation, encode_checked(adapter, [query], query=True)[0], len(chunks)
            )
    if mode == "hybrid":
        ranked = fuse(dense[:candidate_k], bm25[:candidate_k], rrf_k)
    else:
        ranked = [
            (cid, score, i if mode == "dense" else None, i if mode == "bm25" else None)
            for i, (cid, score) in enumerate(dense if mode == "dense" else bm25, 1)
        ]
    return SearchResponse(
        manifest["build_id"],
        mode,
        top_k,
        candidate_k or max(20, top_k),
        rrf_k,
        [
            SearchHit(by_id[cid], i, score, dr, br)
            for i, (cid, score, dr, br) in enumerate(ranked[:top_k], 1)
        ],
    )
