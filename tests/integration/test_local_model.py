"""Real pinned Qwen model tests; explicit runs fail if provisioning is incomplete."""

import math

import pytest

from rag.contracts import ModelError, load_config
from rag.embedding import QwenEmbedding

pytestmark = pytest.mark.model


@pytest.fixture(scope="module")
def real_backend():
    return QwenEmbedding(load_config("configs/rag.yaml"))


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
