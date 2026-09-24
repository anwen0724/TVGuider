"""Create stable, traceable chunks using the actual encoding token budget."""

import json
import re
from dataclasses import replace
from itertools import pairwise
from uuid import NAMESPACE_URL, uuid5

import pysbd

from .contracts import Chunk, ChunkingError

_sentences = pysbd.Segmenter(language="en", clean=False, char_span=True)


def _pieces(text, start, fits, level=0):
    """Refine only oversized units: paragraphs, sentences, words, characters."""
    if fits(text):
        return [(start, start + len(text))]
    if level == 0:
        boundaries = [m.end() for m in re.finditer(r"\n\s*\n", text)]
    elif level == 1:
        boundaries = [span.end for span in _sentences.segment(text)]
    elif level == 2:
        boundaries = [m.end() for m in re.finditer(r"\S+\s*", text)]
    else:
        boundaries = list(range(1, len(text) + 1))
    boundaries = sorted({0, *boundaries, len(text)})
    if level >= 3 and len(text) == 1:
        raise ChunkingError("Necessary heading context leaves no room for one character")
    result = []
    for a, b in pairwise(boundaries):
        if a < b:
            result.extend(_pieces(text[a:b], start + a, fits, level + 1))
    return result


def _prose_parts(text, fits, backend, overlap_tokens):
    """Greedily pack recursive units, retaining exact source character offsets."""
    units = _pieces(text, 0, fits)
    sentences = _sentences.segment(text) if overlap_tokens else []
    start, end = units[0]
    parts = []
    for a, b in units[1:]:
        if fits(text[start:b]):
            end = b
        else:
            parts.append((start, end))
            overlap_start = a
            complete_end = any(
                start <= s.start < s.end <= end and not text[s.end : end].strip() for s in sentences
            )
            if overlap_tokens and complete_end:
                for sentence in sentences:
                    candidate = sentence.start
                    if candidate < start or sentence.end > end:
                        continue
                    suffix = text[candidate:end].strip()
                    if (
                        suffix
                        and backend.count_tokens(suffix) <= overlap_tokens
                        and fits(text[candidate:b])
                    ):
                        overlap_start = candidate
                        break
            start, end = overlap_start, b
    parts.append((start, end))
    return parts


def _merge_prose(blocks):
    """Merge adjacent prose only within the same original heading section."""
    result = []
    for block in blocks:
        if (
            result
            and result[-1].kind == block.kind == "prose"
            and result[-1].section == block.section
        ):
            previous = result[-1]
            result[-1] = replace(
                previous,
                text=previous.text + "\n" * (block.line_start - previous.line_end) + block.text,
                line_end=block.line_end,
            )
        else:
            result.append(block)
    return result


def _structured_parts(block, fits, token_count, source_path):
    """Split protected blocks by original rows, never within a row."""
    lines = block.text.splitlines()
    if block.kind == "table":
        prefix, suffix, rows, offset = lines[:2], [], lines[2:], 2
    else:
        fence = re.match(r"^\s*(`{3,}|~{3,})", lines[0])
        if fence:
            marker = fence.group(1)
            closed = (
                bool(
                    re.fullmatch(
                        r"\s*" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}\s*", lines[-1]
                    )
                )
                and len(lines) > 1
            )
            prefix, suffix = [lines[0]], [marker]
            rows, offset = lines[1:-1] if closed else lines[1:], 1
        else:
            prefix, suffix, rows, offset = ["```"], ["```"], lines, 0
    wrap = lambda selected: "\n".join([*prefix, *selected, *suffix])
    if not rows:
        if not fits(wrap([])):
            raise ChunkingError(
                f"{source_path}:{block.line_start}: wrapper tokens={token_count(wrap([]))}"
            )
        return [(wrap([]), [])]
    result = []
    start = 0
    for i, row in enumerate(rows):
        if not fits(wrap([row])):
            raise ChunkingError(
                f"{source_path}:{block.line_start + offset + i}: protected row requires {token_count(wrap([row]))} tokens"
            )
        if i > start and not fits(wrap(rows[start : i + 1])):
            result.append(
                (
                    wrap(rows[start:i]),
                    [[block.line_start + offset + start, block.line_start + offset + i - 1]],
                )
            )
            start = i
    result.append(
        (
            wrap(rows[start:]),
            [[block.line_start + offset + start, block.line_start + offset + len(rows) - 1]],
        )
    )
    return result


def chunk_documents(documents, config, backend):
    """Convert parsed document blocks to encoding-ready knowledge chunks."""
    chunks = []
    for doc in documents:
        meta = doc.metadata
        for block in _merge_prose(doc.blocks):
            context = "\n".join([meta["title"], *block.heading_path])
            fits = lambda text, context=context: (
                backend.count_tokens(context + "\n\n" + text.strip()) <= config.max_tokens
            )
            if block.kind in {"code", "table"}:
                structure_id = f"{meta['id']}:{block.kind}:{block.line_start}"
                for text, spans in _structured_parts(
                    block,
                    fits,
                    lambda text, context=context: backend.count_tokens(context + "\n\n" + text),
                    doc.source_path,
                ):
                    encoding = context + "\n\n" + text
                    identity = json.dumps(
                        [
                            meta["id"],
                            structure_id,
                            spans,
                            text,
                            config.max_tokens,
                            config.overlap_tokens,
                        ]
                    )
                    chunks.append(
                        Chunk(
                            str(uuid5(NAMESPACE_URL, identity)),
                            meta["id"],
                            meta["title"],
                            doc.source_path,
                            block.heading_path,
                            text,
                            meta["topics"],
                            meta["sources"],
                            spans,
                            encoding,
                            backend.count_tokens(encoding),
                            structure_id,
                            block.language if block.kind == "code" else None,
                        )
                    )
                continue
            try:
                parts = _prose_parts(block.text, fits, backend, config.overlap_tokens)
            except ChunkingError as exc:
                raise ChunkingError(
                    f"{doc.source_path}:{block.line_start}: {exc}; context tokens={backend.count_tokens(context)}"
                ) from exc
            for a, b in parts:
                text = block.text[a:b].strip()
                if not text:
                    continue
                encoding = context + "\n\n" + text
                start_line = block.line_start + block.text[:a].count("\n")
                end_line = block.line_start + block.text[:b].rstrip().count("\n")
                identity = json.dumps(
                    [
                        meta["id"],
                        start_line,
                        end_line,
                        a,
                        b,
                        text,
                        config.max_tokens,
                        config.overlap_tokens,
                    ]
                )
                chunks.append(
                    Chunk(
                        str(uuid5(NAMESPACE_URL, identity)),
                        meta["id"],
                        meta["title"],
                        doc.source_path,
                        block.heading_path,
                        text,
                        meta["topics"],
                        meta["sources"],
                        [[start_line, end_line]],
                        encoding,
                        backend.count_tokens(encoding),
                    )
                )
    return chunks
