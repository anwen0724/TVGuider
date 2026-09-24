"""Chunk budgets, recursive boundaries and source provenance at the service boundary."""

from dataclasses import replace

from rag import build_knowledge_base, search_knowledge_base


def test_recursive_prose_splitting_preserves_text_and_chapter_boundaries(
    tmp_path, source, config, backend
):
    path = source / "setup.md"
    front = path.read_text(encoding="utf-8").split("# Diagnosis")[0]
    sentences = [f"Stage {i} has long combinational delay." for i in range(12)]
    path.write_text(
        front + "# Diagnosis\n\n" + " ".join(sentences) + "\n\n# Hold\n\nShort paths matter.\n",
        encoding="utf-8",
    )
    cfg = replace(config, max_tokens=27, overlap_tokens=0)
    kb = tmp_path / "kb"
    build_knowledge_base(source, kb, cfg, backend=backend)
    hits = search_knowledge_base(kb, "timing", mode="bm25", top_k=100).results
    chunks = sorted(
        (h.chunk for h in hits if h.chunk.heading_path == ["Diagnosis"]), key=lambda c: c.text
    )
    assert len(chunks) > 1
    assert all(c.token_count <= 27 for c in chunks)
    for sentence in sentences:
        assert sum(sentence in c.text for c in chunks) == 1
    assert all("Short paths" not in c.text for c in chunks)


def test_short_paragraphs_pack_and_long_prose_overlaps_whole_sentences(
    tmp_path, source, config, backend
):
    path = source / "setup.md"
    front = path.read_text(encoding="utf-8").split("# Diagnosis")[0]
    path.write_text(
        front
        + "# Diagnosis\n\nAlpha delay matters.\n\nBeta delay matters.\n\nGamma delay matters.\n\nDelta delay matters.\n",
        encoding="utf-8",
    )
    cfg = replace(config, max_tokens=16, overlap_tokens=5)
    kb = tmp_path / "kb"
    report = build_knowledge_base(source, kb, cfg, backend=backend)
    chunks = [h.chunk for h in search_knowledge_base(kb, "timing", mode="bm25", top_k=100).results]
    assert report.chunk_count == 2
    assert any("Alpha" in c.text and "Gamma" in c.text for c in chunks)
    assert any(c.text.startswith("Gamma delay matters.") and "Delta" in c.text for c in chunks)
    assert all(c.token_count <= 16 for c in chunks)
