"""Code/table structural integrity under strict encoding budgets."""

from dataclasses import replace

import pytest

from rag import build_knowledge_base, search_knowledge_base
from rag.contracts import ChunkingError


@pytest.mark.parametrize("kind", ["code", "table"])
def test_long_structures_split_only_whole_rows_with_repeated_wrappers(
    tmp_path, source, config, backend, kind
):
    path = source / "setup.md"
    front = path.read_text(encoding="utf-8").split("# Diagnosis")[0]
    if kind == "code":
        rows = [f"assign out_{i} = data_{i};" for i in range(8)]
        body = "```verilog\n" + "\n".join(rows) + "\n```"
    else:
        rows = [f"| stage_{i} | delay_{i} |" for i in range(8)]
        body = "| Stage | Delay |\n| --- | --- |\n" + "\n".join(rows)
    path.write_text(front + "# Diagnosis\n\n" + body + "\n", encoding="utf-8")
    kb = tmp_path / "kb"
    build_knowledge_base(
        source, kb, replace(config, max_tokens=37, overlap_tokens=0), backend=backend
    )
    chunks = [h.chunk for h in search_knowledge_base(kb, "timing", mode="bm25", top_k=100).results]
    assert len(chunks) > 1
    assert all(c.token_count <= 37 and c.structure_id for c in chunks)
    assert len({c.structure_id for c in chunks}) == 1
    for row in rows:
        assert sum(row in c.text for c in chunks) == 1
    if kind == "code":
        assert all(c.text.startswith("```verilog\n") and c.text.endswith("\n```") for c in chunks)
        assert all(c.language == "verilog" for c in chunks)
    else:
        assert all(c.text.startswith("| Stage | Delay |\n| --- | --- |\n") for c in chunks)
    original_lines = path.read_text(encoding="utf-8").splitlines()
    recovered = [
        original_lines[n - 1] for c in chunks for a, b in c.body_spans for n in range(a, b + 1)
    ]
    assert sorted(recovered) == sorted(rows)


def test_oversized_protected_row_fails_and_keeps_old_generation(tmp_path, source, config, backend):
    kb = tmp_path / "kb"
    report = build_knowledge_base(source, kb, config, backend=backend)
    path = source / "setup.md"
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n```verilog\nassign wide = " + " + ".join(["data"] * 100) + ";\n```\n")
    with pytest.raises(ChunkingError, match=r"setup.md:\d+:.*tokens"):
        build_knowledge_base(
            source, kb, replace(config, max_tokens=40, overlap_tokens=0), backend=backend
        )
    assert search_knowledge_base(kb, "setup", mode="bm25").build_id == report.build_id


def test_indented_code_keeps_original_indentation(tmp_path, source, config, backend):
    path = source / "setup.md"
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n    assign out = data;\n        // retained indentation\n")
    kb = tmp_path / "kb"
    build_knowledge_base(source, kb, config, backend=backend)
    hit = search_knowledge_base(kb, "retained", mode="bm25").results[0]
    assert "\n    assign out = data;\n        // retained indentation\n" in hit.chunk.text


def test_code_nested_in_list_is_protected_from_prose_splitting(tmp_path, source, config, backend):
    path = source / "setup.md"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(
            "\n- A nested RTL example:\n\n  ```verilog\n  "
            + "\n  ".join(f"assign out_{i} = data_{i};" for i in range(12))
            + "\n  ```\n"
        )
    kb = tmp_path / "kb"
    build_knowledge_base(
        source, kb, replace(config, max_tokens=37, overlap_tokens=0), backend=backend
    )
    hits = search_knowledge_base(kb, "assign", mode="bm25", top_k=100).results
    assert len(hits) > 1
    assert all(h.chunk.structure_id and h.chunk.language == "verilog" for h in hits)
    for i in range(12):
        assert sum(f"assign out_{i} = data_{i};" in h.chunk.text for h in hits) == 1
