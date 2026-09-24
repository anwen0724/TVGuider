"""Persist complete index generations and atomically publish their pointer."""

import json
import math
import os
import re
import shutil
from contextlib import closing
from dataclasses import asdict
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

from qdrant_client import QdrantClient, models

from .contracts import BuildConfig, Chunk, ConsistencyError, StorageError
from .lexical import tokenize


def write_json(path, value):
    """Write human-readable UTF-8 data; publication is managed separately."""
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path):
    """Read one persisted JSON value."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def file_hash(path):
    """Fingerprint exact persisted bytes."""
    with Path(path).open("rb") as stream:
        from hashlib import file_digest

        return file_digest(stream, "sha256").hexdigest()


def vector_fingerprint(generation, expected_ids):
    """Validate vector IDs, dimensions and numeric values without model inference."""
    vector_dir = generation / "qdrant"
    if not (vector_dir / "meta.json").is_file():
        raise ConsistencyError("Missing Qdrant data")
    with closing(QdrantClient(path=str(vector_dir))) as client:
        info = client.get_collection("chunks")
        if (
            info.config.params.vectors.size != 1024
            or info.config.params.vectors.distance != models.Distance.COSINE
        ):
            raise ConsistencyError("Incompatible vector configuration")
        records = []
        offset = None
        while True:
            page, offset = client.scroll(
                "chunks", limit=256, offset=offset, with_vectors=True, with_payload=False
            )
            records.extend(page)
            if offset is None:
                break
    if {str(p.id) for p in records} != set(expected_ids) or len(records) != len(expected_ids):
        raise ConsistencyError("Vector/chunk IDs differ")
    digest = sha256()
    for point in sorted(records, key=lambda p: str(p.id)):
        if len(point.vector) != 1024 or any(not math.isfinite(v) for v in point.vector):
            raise ConsistencyError("Invalid stored vector")
        digest.update(json.dumps([str(point.id), point.vector]).encode())
    return digest.hexdigest()


def _save_generation(kb, build_id, documents, chunks, vectors, config, descriptor):
    """Save both indexes before switching the current-generation pointer."""
    generation = kb / "generations" / build_id
    with closing(QdrantClient(path=str(generation / "qdrant"))) as client:
        client.create_collection(
            "chunks", vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE)
        )
        client.upsert(
            "chunks",
            points=[models.PointStruct(id=c.chunk_id, vector=v) for c, v in zip(chunks, vectors)],
        )
    (generation / "chunks.jsonl").write_text(
        "".join(json.dumps(asdict(c)) + "\n" for c in chunks), encoding="utf-8"
    )
    write_json(
        generation / "bm25.json",
        {
            "ids": [c.chunk_id for c in chunks],
            "corpus": [tokenize(c.encoding_text) for c in chunks],
            "parameters": {"k1": 1.5, "b": 0.75, "epsilon": 0.25},
        },
    )
    manifest = {
        "format_version": 1,
        "pipeline_version": "rag-v1",
        "runtime": {
            name: version(name)
            for name in ("qdrant-client", "rank-bm25", "markdown-it-py", "pysbd", "PyYAML")
        },
        "build_id": build_id,
        "config": asdict(config),
        "embedding": descriptor,
        "chunk_count": len(chunks),
        "documents": [
            {"id": d.metadata["id"], "path": d.source_path, "sha256": d.sha256} for d in documents
        ],
        "hashes": {name: file_hash(generation / name) for name in ("chunks.jsonl", "bm25.json")},
        "vectors_sha256": vector_fingerprint(generation, [c.chunk_id for c in chunks]),
    }
    write_json(generation / "manifest.json", manifest)
    validate_generation(generation)
    pointer = kb / f".{build_id}.json"
    write_json(pointer, {"build_id": build_id})
    os.replace(pointer, kb / "current.json")
    return manifest


def _remove_pending(kb, generation):
    """Confine deletion to one marked, unpublished child generation."""
    parent = (kb / "generations").resolve()
    target = generation.resolve()
    if (
        target.parent != parent
        or not re.fullmatch(r"[0-9a-f]{32}", generation.name)
        or generation.is_symlink()
    ):
        raise StorageError(f"Refusing cleanup outside generation directory: {generation}")
    current = (
        read_json(kb / "current.json").get("build_id") if (kb / "current.json").exists() else None
    )
    if generation.name != current and (generation / ".pending").is_file():
        shutil.rmtree(target)
        (kb / f".{generation.name}.json").unlink(missing_ok=True)


def save_generation(kb_dir, documents, chunks, vectors, config, descriptor):
    """Clean interrupted writes and publish only a validated full generation."""
    kb = Path(kb_dir)
    build_id = uuid4().hex
    generation = kb / "generations" / build_id
    try:
        for pending in (kb / "generations").glob("*/.pending"):
            _remove_pending(kb, pending.parent)
        generation.mkdir(parents=True)
        (generation / ".pending").write_text(build_id, encoding="utf-8")
        manifest = _save_generation(kb, build_id, documents, chunks, vectors, config, descriptor)
    except Exception as exc:
        if generation.exists():
            _remove_pending(kb, generation)
        raise StorageError(f"Knowledge base publication failed: {exc}") from exc
    # Publication is the commit point. A leftover marker cannot invalidate it.
    try:
        (generation / ".pending").unlink(missing_ok=True)
    except OSError:
        pass
    return manifest


def validate_generation(generation):
    """Verify a complete self-consistent generation before publication or retrieval."""
    manifest = read_json(generation / "manifest.json")
    if manifest["format_version"] != 1 or manifest["build_id"] != generation.name:
        raise ConsistencyError("Incompatible format or generation identity")
    BuildConfig(**manifest["config"])
    for name in ("qdrant-client", "rank-bm25"):
        if manifest["runtime"][name] != version(name):
            raise ConsistencyError(f"{name} version changed; rebuild the knowledge base")
    for name in ("chunks.jsonl", "bm25.json"):
        if file_hash(generation / name) != manifest["hashes"][name]:
            raise ConsistencyError(f"{name}: fingerprint mismatch")
    chunks = [
        Chunk(**json.loads(line))
        for line in (generation / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    ids = [c.chunk_id for c in chunks]
    if not chunks or len(set(ids)) != len(ids) or len(ids) != manifest["chunk_count"]:
        raise ConsistencyError("Invalid chunk count or duplicate IDs")
    doc_ids = {d["id"] for d in manifest["documents"]}
    if any(c.document_id not in doc_ids for c in chunks):
        raise ConsistencyError("Unknown source document")
    lexical = read_json(generation / "bm25.json")
    if lexical["ids"] != ids or lexical["corpus"] != [tokenize(c.encoding_text) for c in chunks]:
        raise ConsistencyError("BM25/chunk content differs")
    if lexical["parameters"] != {"k1": 1.5, "b": 0.75, "epsilon": 0.25}:
        raise ConsistencyError("Incompatible BM25 parameters")
    if vector_fingerprint(generation, ids) != manifest["vectors_sha256"]:
        raise ConsistencyError("Vector fingerprint mismatch")
    return generation, manifest, chunks, lexical


def load_generation(kb_dir):
    """Load persisted data without consulting or reparsing original Markdown."""
    kb = Path(kb_dir)
    try:
        build_id = read_json(kb / "current.json")["build_id"]
        if not isinstance(build_id, str) or not re.fullmatch(r"[0-9a-f]{32}", build_id):
            raise ConsistencyError("Invalid generation pointer")
        generation = kb / "generations" / build_id
        if generation.resolve().parent != (kb / "generations").resolve():
            raise ConsistencyError("Generation escapes knowledge base")
        return validate_generation(generation)
    except ConsistencyError:
        raise
    except Exception as exc:
        raise ConsistencyError(f"{kb}: unavailable or inconsistent knowledge base: {exc}") from exc
