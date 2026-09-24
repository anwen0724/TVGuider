"""Real pinned Qwen model tests; explicit runs fail if provisioning is incomplete."""

import json
import math
import subprocess
import sys

import pytest

from rag import build_knowledge_base, search_knowledge_base
from rag.contracts import ModelError, load_config
from rag.embedding import QwenEmbedding

pytestmark = pytest.mark.model


@pytest.fixture(scope="module")
def real_backend():
    backend = QwenEmbedding(load_config("configs/rag.yaml"))
    yield backend
    backend.close()


def test_real_qwen_encodes_finite_normalized_vectors_and_distinct_query_prompt(real_backend):
    text = "A short data path can violate hold timing."
    documents = real_backend.encode_documents([text])
    query = real_backend.encode_query(text)
    assert len(documents) == 1 and len(documents[0]) == len(query) == 1024
    assert all(math.isfinite(v) for v in query + documents[0])
    assert sum(v * v for v in query) == pytest.approx(1.0, abs=1e-5)
    assert sum(v * v for v in documents[0]) == pytest.approx(1.0, abs=1e-5)
    assert query != documents[0]
    assert real_backend.count_tokens(text) == len(
        real_backend.model.tokenize([text])["input_ids"][0]
    )
    with pytest.raises(ModelError, match="tokens"):
        real_backend.encode_documents(["delay " * 2000])
    with pytest.raises(ModelError, match="tokens"):
        real_backend.encode_query("delay " * 33000)


def test_real_build_cli_reload_default_hybrid_and_api_parity(tmp_path, source, real_backend):
    kb = tmp_path / "kb"
    report = build_knowledge_base(source, kb, load_config("configs/rag.yaml"), backend=real_backend)
    api = search_knowledge_base(kb, "What reduces setup slack?", backend=real_backend)
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "rag",
            "search",
            "--kb",
            str(kb),
            "--query",
            "What reduces setup slack?",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    cli = json.loads(process.stdout)
    assert cli["build_id"] == report.build_id
    assert cli["mode"] == "hybrid" and cli["top_k"] == 5
    assert [hit["chunk"]["chunk_id"] for hit in cli["results"]] == [
        hit.chunk.chunk_id for hit in api.results
    ]
    assert [hit["score"] for hit in cli["results"]] == pytest.approx(
        [hit.score for hit in api.results]
    )
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "rag",
            "build",
            "--source",
            str(source),
            "--kb",
            str(kb),
            "--config",
            "configs/rag.yaml",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    rebuilt = json.loads(process.stdout)
    assert rebuilt["chunk_count"] == report.chunk_count
    assert rebuilt["build_id"] != report.build_id
