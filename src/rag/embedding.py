"""Local Qwen encoding boundary, with explicit version and length checks."""

import json
import math
from hashlib import file_digest
from importlib.metadata import version
from pathlib import Path

from .contracts import ModelError


class QwenEmbedding:
    """Lazy, offline-only Qwen adapter for tokenizer and document/query encoding."""

    def __init__(self, config):
        self.config = config
        self.model = None
        root = Path(config.model_path)
        try:
            self.receipt = json.loads((root / "rag-model.json").read_text(encoding="utf-8"))
            if (
                self.receipt["revision"] != config.revision
                or self.receipt["model_id"] != config.model_id
            ):
                raise ValueError("local model revision differs from configuration")
            for name, expected in self.receipt["files"].items():
                path = root / name
                if not path.resolve().is_relative_to(root.resolve()):
                    raise ValueError("invalid model receipt path")
                with path.open("rb") as stream:
                    if file_digest(stream, "sha256").hexdigest() != expected:
                        raise ValueError(f"local model file fingerprint mismatch: {name}")
            from transformers import AutoTokenizer

            self.tokenizer = AutoTokenizer.from_pretrained(
                str(root), local_files_only=True, padding_side="left"
            )
            self.prompt = json.loads(
                (root / "config_sentence_transformers.json").read_text(encoding="utf-8")
            )["prompts"]["query"]
        except Exception as exc:
            raise ModelError(f"Cannot load local model {root}: {exc}") from exc

    def count_tokens(self, text):
        """Count the exact document encoding, including tokenizer-added tokens."""
        return len(self.tokenizer(text, add_special_tokens=True, truncation=False)["input_ids"])

    def describe(self):
        """Describe every setting that defines this embedding vector space."""
        return {
            "adapter": "qwen-sentence-transformers-v1",
            "model_id": self.config.model_id,
            "revision": self.config.revision,
            "dimension": 1024,
            "dtype": self.config.dtype,
            "device": self.config.device,
            "normalize": True,
            "distance": "cosine",
            "query_prompt": self.prompt,
            "document_prompt": "",
            "model_files": self.receipt["files"],
            "packages": {
                name: version(name)
                for name in ("torch", "transformers", "sentence-transformers", "tokenizers")
            },
        }

    def encode_documents(self, texts):
        """Encode documents without the retrieval query instruction."""
        return self._encode(texts, query=False)

    def encode_query(self, text):
        """Encode a query using the checkpoint's official retrieval instruction."""
        return self._encode([text], query=True)[0]

    def _encode(self, texts, *, query):
        """Check actual prompted lengths before the library's truncation boundary."""
        try:
            limit = 32768 if query else self.config.max_tokens
            for text in texts:
                count = self.count_tokens((self.prompt if query else "") + text)
                if count > limit:
                    raise ModelError(f"Encoding requires {count} tokens; limit={limit}")
            if self.model is None:
                import torch
                from sentence_transformers import SentenceTransformer

                self.model = SentenceTransformer(
                    self.config.model_path,
                    device=self.config.device,
                    local_files_only=True,
                    trust_remote_code=False,
                    model_kwargs={
                        "dtype": getattr(torch, self.config.dtype),
                        "attn_implementation": "sdpa",
                    },
                    tokenizer_kwargs={"padding_side": "left"},
                )
                self.model.max_seq_length = 32768
            encoded = self.model.encode(
                texts,
                prompt=self.prompt if query else "",
                batch_size=self.config.batch_size,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            return validate_vectors(encoded.tolist(), len(texts))
        except ModelError:
            raise
        except Exception as exc:
            raise ModelError(f"Local Qwen inference failed: {exc}") from exc

    def close(self):
        """Release this adapter's model; callers may reuse it until explicitly closed."""
        self.model = None


def validate_vectors(vectors, expected_count):
    """Reject missing, non-finite or degenerate vectors before persistence/search."""
    try:
        if len(vectors) != expected_count:
            raise ValueError("embedding count differs from input count")
        result = []
        for row in vectors:
            values = [float(v) for v in row]
            if len(values) != 1024 or any(not math.isfinite(v) for v in values):
                raise ValueError("embedding must contain 1024 finite values")
            norm = math.sqrt(sum(v * v for v in values))
            if not math.isfinite(norm) or norm == 0:
                raise ValueError("embedding has invalid norm")
            result.append([v / norm for v in values])
        return result
    except (ValueError, TypeError, OverflowError) as exc:
        raise ModelError(str(exc)) from exc


def encode_checked(backend, texts, *, query=False):
    """Translate external adapter failures and validate every returned vector."""
    try:
        vectors = [backend.encode_query(texts[0])] if query else backend.encode_documents(texts)
        return validate_vectors(vectors, len(texts))
    except ModelError:
        raise
    except Exception as exc:
        raise ModelError(f"Embedding inference failed: {exc}") from exc
