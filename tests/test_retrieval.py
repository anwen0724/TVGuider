"""Lexical conventions and deterministic public retrieval behavior."""

import pytest

from rag import build_knowledge_base, search_knowledge_base
from rag.contracts import InputError


def test_bm25_identifier_matching_no_stemming_and_stable_ties(tmp_path, source, config, backend):
    path = source / "setup.md"
    original = path.read_text(encoding="utf-8")
    path.write_text(
        original + "\n## Signals\n\ndata_valid gates registered outputs.\n", encoding="utf-8"
    )
    sub = source / "nested"
    sub.mkdir()
    (sub / "other.md").write_text(original.replace("id: setup", "id: other"), encoding="utf-8")
    kb = tmp_path / "kb"
    build_knowledge_base(source, kb, config, backend=backend)
    search = lambda q: search_knowledge_base(kb, q, mode="bm25").results
    assert len(search("DATA_VALID")) == 1
    assert search("valid") == []
    assert search("register") == []
    assert search("unmatchedxyz") == []
    hits = search("COMBINATIONAL")
    assert len(hits) == 2
    assert [h.chunk.chunk_id for h in hits] == sorted(h.chunk.chunk_id for h in hits)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"query": " "},
        {"mode": "unknown"},
        {"top_k": 0},
        {"top_k": True},
        {"candidate_k": 2},
        {"rrf_k": 0},
        {"rrf_k": float("nan")},
    ],
)
def test_invalid_search_parameters_fail_before_accessing_storage(tmp_path, kwargs):
    params = {"query": "setup", **kwargs}
    with pytest.raises(InputError):
        search_knowledge_base(tmp_path / "absent", **params)


def test_dense_and_hybrid_use_vectors_rrf_and_missing_lexical_route(
    tmp_path, source, config, backend
):
    path = source / "setup.md"
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n# Hold\n\nShort paths cause hold failures.\n")
    kb = tmp_path / "kb"
    build_knowledge_base(source, kb, config, backend=backend)
    dense = search_knowledge_base(kb, "unmatchedxyz", mode="dense", backend=backend)
    assert len(dense.results) == 2
    assert [h.chunk.chunk_id for h in dense.results] == sorted(
        h.chunk.chunk_id for h in dense.results
    )
    assert all(h.score == pytest.approx(1.0) for h in dense.results)
    hybrid = search_knowledge_base(kb, "unmatchedxyz", backend=backend)
    assert [h.chunk.chunk_id for h in hybrid.results] == [h.chunk.chunk_id for h in dense.results]
    assert [h.score for h in hybrid.results] == pytest.approx([1 / 61, 1 / 62])
    assert all(h.bm25_rank is None for h in hybrid.results)
    fused = search_knowledge_base(kb, "hold", backend=backend)
    assert fused.results[0].chunk.heading_path == ["Hold"]
    first = fused.results[0]
    assert first.score == pytest.approx(1 / (60 + first.dense_rank) + 1 / 61)
