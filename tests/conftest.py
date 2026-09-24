"""External embedding test double; storage and domain logic remain real."""

import re

import pytest

from rag import BuildConfig


class FakeEmbedding:
    """Predictable 1024-D vectors without substituting application algorithms."""

    def count_tokens(self, text):
        return len(re.findall(r"\w+|[^\w\s]", text)) + 1

    def encode_documents(self, texts):
        return [[1.0] + [0.0] * 1023 for _ in texts]

    def encode_query(self, text):
        return [1.0] + [0.0] * 1023

    def describe(self):
        return {"adapter": "test-double", "revision": "test", "dimension": 1024}


@pytest.fixture
def backend():
    return FakeEmbedding()


@pytest.fixture
def config():
    return BuildConfig(model_path="unused", revision="test")


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "setup.md").write_text(
        "---\nid: setup\ntitle: Setup timing\ntopics: [setup]\n"
        "sources: [https://example.com/sta]\n---\n"
        "# Diagnosis\n\nLong combinational paths reduce setup slack.\n",
        encoding="utf-8",
    )
    return root
