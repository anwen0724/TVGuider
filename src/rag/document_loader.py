"""Read source Markdown with original positions, without rewriting documents."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse

import yaml
from markdown_it import MarkdownIt

from .contracts import InputError


def validate_metadata(metadata, path):
    """Reject malformed required fields before deriving any index data."""
    if not isinstance(metadata, dict):
        raise InputError(f"{path}: YAML front matter must be a mapping")
    for name in ("id", "title"):
        if not isinstance(metadata.get(name), str) or not metadata[name].strip():
            raise InputError(f"{path}: {name} must be a nonempty string")
    for name in ("topics", "sources"):
        values = metadata.get(name)
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(v, str) or not v.strip() for v in values)
        ):
            raise InputError(f"{path}: {name} must be a nonempty string list")
    if not set(metadata["topics"]) <= {"setup", "hold"}:
        raise InputError(f"{path}: topics must contain setup/hold only")
    if any(
        urlparse(v).scheme not in {"http", "https"} or not urlparse(v).netloc
        for v in metadata["sources"]
    ):
        raise InputError(f"{path}: sources must contain HTTP(S) links")


@dataclass
class Block:
    """A source structure unit with its enclosing heading path."""

    kind: str
    text: str
    heading_path: list[str]
    line_start: int
    line_end: int
    language: str | None = None
    section: int = 0


@dataclass
class Document:
    """Validated metadata and blocks, plus the original bytes' fingerprint."""

    metadata: dict
    source_path: str
    sha256: str
    blocks: list[Block]


def load_documents(source_dir):
    """Load Markdown recursively, retaining one-based inclusive source lines."""
    root = Path(source_dir)
    documents = []
    seen = set()
    paths = sorted(root.rglob("*.md")) if root.is_dir() else []
    if not paths:
        raise InputError(f"{root}: no Markdown documents")
    for path in paths:
        try:
            raw = path.read_bytes()
            lines = raw.decode("utf-8").splitlines(keepends=True)
            if not lines or lines[0].strip() != "---":
                raise ValueError("missing YAML front matter")
            closing = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
            metadata = yaml.safe_load("".join(lines[1:closing]))
        except (OSError, UnicodeError, ValueError, StopIteration, yaml.YAMLError) as exc:
            raise InputError(f"{path}: invalid Markdown/front matter: {exc}") from exc
        validate_metadata(metadata, path)
        if metadata["id"] in seen:
            raise InputError(f"{path}: duplicate document id {metadata['id']}")
        seen.add(metadata["id"])
        offset = closing + 1
        body = lines[offset:]
        tokens = MarkdownIt("commonmark").enable("table").parse("".join(body))
        headings = []
        blocks = []
        section = 0
        for i, token in enumerate(tokens):
            if token.type == "heading_open":
                section += 1
                level = int(token.tag[1:])
                headings = [(n, text) for n, text in headings if n < level]
                headings.append((level, tokens[i + 1].content))
            elif token.map and token.level == 0 and token.type != "heading_close":
                start, end = token.map
                kind = {"fence": "code", "code_block": "code", "table_open": "table"}.get(
                    token.type, "prose"
                )
                blocks.append(
                    Block(
                        kind,
                        "".join(body[start:end]).strip(),
                        [text for _, text in headings],
                        offset + start + 1,
                        offset + end,
                        token.info.strip() or None,
                        section,
                    )
                )
        if not blocks or not any(b.text.strip() for b in blocks):
            raise InputError(f"{path}: no body content")
        documents.append(
            Document(metadata, path.relative_to(root).as_posix(), sha256(raw).hexdigest(), blocks)
        )
    return documents
