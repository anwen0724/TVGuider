"""Public build/reload/retrieval behavior against real local storage."""

import pytest

from rag import build_knowledge_base, search_knowledge_base
from rag.contracts import InputError


def test_build_persist_reload_bm25_preserves_body_and_provenance(tmp_path, source, config, backend):
    original = (source / "setup.md").read_bytes()
    kb = tmp_path / "kb"
    report = build_knowledge_base(source, kb, config, backend=backend)
    response = search_knowledge_base(kb, "COMBINATIONAL", mode="bm25")
    assert response.build_id == report.build_id
    assert report.document_count == report.chunk_count == 1
    hit = response.results[0]
    assert hit.chunk.text == "Long combinational paths reduce setup slack."
    assert hit.chunk.heading_path == ["Diagnosis"]
    assert hit.chunk.body_spans == [[9, 9]]
    assert hit.chunk.sources == ["https://example.com/sta"]
    assert hit.rank == 1
    assert (source / "setup.md").read_bytes() == original


@pytest.mark.parametrize(
    "change", ["missing_title", "bad_topics", "bad_sources", "title_only", "duplicate", "empty"]
)
def test_invalid_corpus_fails_as_input_error(tmp_path, source, config, backend, change):
    path = source / "setup.md"
    text = path.read_text(encoding="utf-8")
    if change == "missing_title":
        path.write_text(text.replace("title: Setup timing\n", ""), encoding="utf-8")
    elif change == "bad_topics":
        path.write_text(text.replace("[setup]", "[cdc]"), encoding="utf-8")
    elif change == "bad_sources":
        path.write_text(text.replace("https://example.com/sta", "not-a-link"), encoding="utf-8")
    elif change == "title_only":
        path.write_text(text[: text.index("Long combinational")], encoding="utf-8")
    elif change == "duplicate":
        (source / "copy.md").write_text(text, encoding="utf-8")
    else:
        path.unlink()
    with pytest.raises(InputError):
        build_knowledge_base(source, tmp_path / "kb", config, backend=backend)
