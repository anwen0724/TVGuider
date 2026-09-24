"""Published generations survive rebuild failures and reject corrupt indexes."""

import json
from pathlib import Path

import pytest

from rag import build_knowledge_base, search_knowledge_base
from rag.contracts import ConsistencyError, StorageError


@pytest.mark.parametrize("damage", ["bm25", "vectors", "chunks", "manifest"])
def test_any_inconsistent_index_rejects_even_bm25_query(tmp_path, source, config, backend, damage):
    kb = tmp_path / "kb"
    report = build_knowledge_base(source, kb, config, backend=backend)
    generation = kb / "generations" / report.build_id
    if damage == "bm25":
        path = generation / "bm25.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["ids"][0] = "missing-chunk"
        path.write_text(json.dumps(data), encoding="utf-8")
    elif damage == "vectors":
        from qdrant_client import QdrantClient

        client = QdrantClient(path=str(generation / "qdrant"))
        client.delete_collection("chunks")
        client.close()
    elif damage == "chunks":
        (generation / "chunks.jsonl").write_text("", encoding="utf-8")
    else:
        (generation / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ConsistencyError):
        search_knowledge_base(kb, "setup", mode="bm25")


def test_failed_pointer_publication_preserves_old_and_cleans_partial(
    tmp_path, source, config, backend, monkeypatch
):
    kb = tmp_path / "kb"
    old = build_knowledge_base(source, kb, config, backend=backend)
    import os

    real_replace = os.replace

    def fail_pointer(src, dst):
        if Path(dst).name == "current.json":
            raise OSError("injected publication failure")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", fail_pointer)
    with pytest.raises(StorageError, match="publication failure"):
        build_knowledge_base(source, kb, config, backend=backend)
    assert search_knowledge_base(kb, "setup", mode="bm25").build_id == old.build_id
    assert [p.name for p in (kb / "generations").iterdir()] == [old.build_id]
    assert list(kb.glob(".*.json")) == []


def test_rebuild_removes_deleted_docs_and_recovers_only_marked_partial(
    tmp_path, source, config, backend
):
    kb = tmp_path / "kb"
    path = source / "setup.md"
    copy = source / "other.md"
    copy.write_text(
        path.read_text(encoding="utf-8")
        .replace("id: setup", "id: other")
        .replace("combinational", "obsoleteword"),
        encoding="utf-8",
    )
    old = build_knowledge_base(source, kb, config, backend=backend)
    old_ids = {
        h.chunk.chunk_id for h in search_knowledge_base(kb, "combinational", mode="bm25").results
    }
    abandoned = kb / "generations" / ("f" * 32)
    abandoned.mkdir()
    (abandoned / ".pending").write_text("interrupted", encoding="utf-8")
    copy.unlink()
    new = build_knowledge_base(source, kb, config, backend=backend)
    assert new.build_id != old.build_id
    assert search_knowledge_base(kb, "obsoleteword", mode="bm25").results == []
    assert {
        h.chunk.chunk_id for h in search_knowledge_base(kb, "combinational", mode="bm25").results
    } == old_ids
    assert not abandoned.exists()
    assert (kb / "generations" / old.build_id).exists()
