"""External encoders must produce finite vectors in the recorded vector space."""

import pytest

from rag import BuildConfig, build_knowledge_base, search_knowledge_base
from rag.contracts import InputError, ModelError


@pytest.mark.parametrize("bad", [[], [0.0] * 10, [float("nan")] * 1024, [0.0] * 1024])
def test_bad_embedding_rejects_build_before_publication(tmp_path, source, config, backend, bad):
    backend.encode_documents = lambda texts: [bad for _ in texts]
    with pytest.raises(ModelError):
        build_knowledge_base(source, tmp_path / "kb", config, backend=backend)
    assert not (tmp_path / "kb" / "current.json").exists()


def test_mismatched_encoder_revision_cannot_query_existing_vectors(
    tmp_path, source, config, backend
):
    kb = tmp_path / "kb"
    build_knowledge_base(source, kb, config, backend=backend)
    backend.describe = lambda: {"adapter": "test-double", "revision": "changed", "dimension": 1024}
    with pytest.raises(ModelError, match="configuration|revision"):
        search_knowledge_base(kb, "setup", mode="hybrid", backend=backend)


@pytest.mark.parametrize(
    "values",
    [
        {"max_tokens": 0},
        {"max_tokens": 32769},
        {"overlap_tokens": 1024},
        {"dimension": 512},
        {"batch_size": True},
        {"dtype": "int8"},
    ],
)
def test_invalid_build_config_is_rejected(values):
    with pytest.raises(InputError):
        BuildConfig(model_path="unused", revision="test", **values)


def test_missing_local_model_is_actionable_without_network_fallback(tmp_path, source, config):
    with pytest.raises(ModelError, match="local|model"):
        build_knowledge_base(source, tmp_path / "kb", config)


def test_query_model_failure_is_not_a_silent_bm25_fallback(tmp_path, source, config, backend):
    kb = tmp_path / "kb"
    build_knowledge_base(source, kb, config, backend=backend)

    def fail(text):
        raise RuntimeError("inference unavailable")

    backend.encode_query = fail
    with pytest.raises(ModelError, match="inference unavailable"):
        search_knowledge_base(kb, "setup", backend=backend)
