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


def test_english_abbreviation_and_decimal_stay_in_their_sentence(tmp_path, source, config, backend):
    path = source / "setup.md"
    front = path.read_text(encoding="utf-8").split("# Diagnosis")[0]
    first = "Dr. Smith measured 0.25 ns."
    path.write_text(
        front + "# Diagnosis\n\n" + first + " The path is slow. The clock is fast.\n",
        encoding="utf-8",
    )
    kb = tmp_path / "kb"
    build_knowledge_base(
        source, kb, replace(config, max_tokens=15, overlap_tokens=0), backend=backend
    )
    hits = search_knowledge_base(kb, "timing", mode="bm25", top_k=100).results
    assert sum(first in hit.chunk.text for hit in hits) == 1
    assert all(hit.chunk.token_count <= 15 for hit in hits)


def test_unbroken_text_uses_character_fallback_without_loss(tmp_path, source, config, backend):
    path = source / "setup.md"
    front = path.read_text(encoding="utf-8").split("# Diagnosis")[0]
    text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    path.write_text(front + "# Diagnosis\n\n" + text + "\n", encoding="utf-8")
    backend.count_tokens = len
    kb = tmp_path / "kb"
    build_knowledge_base(
        source, kb, replace(config, max_tokens=32, overlap_tokens=0), backend=backend
    )
    chunks = [
        hit.chunk for hit in search_knowledge_base(kb, "timing", mode="bm25", top_k=100).results
    ]
    assert len(chunks) > 1
    assert sorted("".join(c.text for c in chunks)) == sorted(text)
    assert all(c.token_count <= 32 for c in chunks)


def test_overlap_never_repeats_a_fragment_of_an_oversized_sentence(
    tmp_path, source, config, backend
):
    path = source / "setup.md"
    front = path.read_text(encoding="utf-8").split("# Diagnosis")[0]
    words = [f"word{i}" for i in range(25)]
    path.write_text(
        front + "# Diagnosis\n\nAlpha delay matters. " + " ".join(words) + ".\n", encoding="utf-8"
    )
    kb = tmp_path / "kb"
    build_knowledge_base(
        source, kb, replace(config, max_tokens=14, overlap_tokens=8), backend=backend
    )
    chunks = [h.chunk for h in search_knowledge_base(kb, "timing", mode="bm25", top_k=100).results]
    for word in words:
        assert sum(word in c.text.replace(".", "").split() for c in chunks) == 1
