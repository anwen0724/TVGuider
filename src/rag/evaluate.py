"""Evaluate frozen English retrieval queries against original body-span labels."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from .contracts import BuildConfig, ConsistencyError, InputError, RagError
from .embedding import QwenEmbedding
from .service import search_knowledge_base
from .storage import file_hash, load_generation, read_json, write_json


def _is_relevant(chunk, labels):
    """Require document, full heading path and overlap with actual source body."""
    return any(
        chunk.document_id == label["document_id"]
        and chunk.heading_path == label["heading_path"]
        and any(a <= label["line_end"] and b >= label["line_start"] for a, b in chunk.body_spans)
        for label in labels
    )


def _metrics(rows):
    """Keep misses in the denominator; an empty category has no rate."""
    return {
        "count": len(rows),
        "hits": sum(row["hit"] for row in rows),
        "hit_rate_at_5": sum(row["hit"] for row in rows) / len(rows) if rows else None,
    }


def _load_inputs(dataset_path, manifest_path, build, chunks):
    """Reject stale data, missing categories and labels without original body evidence."""
    try:
        manifest = read_json(manifest_path)
        if manifest["schema_version"] != 1:
            raise ValueError("unsupported evaluation schema")
        root = manifest_path.resolve().parents[2]
        info = next(
            v
            for v in manifest["datasets"].values()
            if (root / v["path"]).resolve() == dataset_path.resolve()
        )
        if file_hash(dataset_path) != info["sha256"]:
            raise ValueError("dataset fingerprint differs from frozen manifest")
        expected_docs = {d["document_id"]: d["sha256"] for d in manifest["corpus"]}
        if expected_docs != {d["id"]: d["sha256"] for d in build["documents"]}:
            raise ValueError("built corpus differs from frozen evaluation corpus")
        for document in manifest["corpus"]:
            if file_hash(root / document["path"]) != document["sha256"]:
                raise ValueError(f"corpus fingerprint mismatch: {document['path']}")
        rows = [
            json.loads(line)
            for line in dataset_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if not rows or len(rows) != info["count"] or len({r["id"] for r in rows}) != len(rows):
            raise ValueError("invalid dataset count or duplicate query IDs")
        if info["purpose"] not in {"development", "acceptance"}:
            raise ValueError("unknown dataset purpose")
        for row in rows:
            if (
                not isinstance(row["id"], str)
                or not row["id"].strip()
                or row["topic"] not in {"setup", "hold"}
                or not isinstance(row["query"], str)
                or not row["query"].strip()
                or not row["relevant"]
            ):
                raise ValueError("invalid query fields")
            for label in row["relevant"]:
                if (
                    type(label["line_start"]) is not int
                    or type(label["line_end"]) is not int
                    or not 0 < label["line_start"] <= label["line_end"]
                ):
                    raise ValueError("invalid label line range")
                if not any(_is_relevant(c, [label]) for c in chunks):
                    raise ValueError(f"label has no matching source body: {row['id']}")
        counts = {topic: sum(r["topic"] == topic for r in rows) for topic in ("setup", "hold")}
        if "topics" in info and counts != info["topics"]:
            raise ValueError("topic counts differ from frozen manifest")
        if info["purpose"] == "acceptance" and counts != {"setup": 10, "hold": 10}:
            raise ValueError("acceptance requires 10 setup and 10 hold queries")
        return rows, info
    except (KeyError, TypeError, ValueError, OSError, StopIteration, IndexError) as exc:
        raise InputError(f"Invalid evaluation inputs: {exc}") from exc


def evaluate(kb_dir, dataset_path, manifest_path, output_dir, *, backend=None):
    """Evaluate three retrieval modes without generating or changing relevance labels."""
    dataset_path, manifest_path = Path(dataset_path), Path(manifest_path)
    _, build, chunks, _ = load_generation(kb_dir)
    rows, dataset_info = _load_inputs(dataset_path, manifest_path, build, chunks)
    backend = backend or QwenEmbedding(BuildConfig(**build["config"]))
    modes = {}
    for mode in ("dense", "bm25", "hybrid"):
        details = []
        for row in rows:
            response = search_knowledge_base(kb_dir, row["query"], mode=mode, backend=backend)
            if response.build_id != build["build_id"]:
                raise ConsistencyError("Knowledge base changed during evaluation")
            matching = [
                hit.rank for hit in response.results if _is_relevant(hit.chunk, row["relevant"])
            ]
            details.append(
                {
                    "id": row["id"],
                    "topic": row["topic"],
                    "query": row["query"],
                    "hit": bool(matching),
                    "first_relevant_rank": min(matching) if matching else None,
                    "results": [
                        {
                            "chunk_id": hit.chunk.chunk_id,
                            "document_id": hit.chunk.document_id,
                            "heading_path": hit.chunk.heading_path,
                            "body_spans": hit.chunk.body_spans,
                            "score": hit.score,
                        }
                        for hit in response.results
                    ],
                }
            )
        modes[mode] = {
            "overall": _metrics(details),
            "setup": _metrics([r for r in details if r["topic"] == "setup"]),
            "hold": _metrics([r for r in details if r["topic"] == "hold"]),
            "queries": details,
        }
    acceptance = dataset_info["purpose"] == "acceptance"
    hybrid = modes["hybrid"]
    passed = (
        all(hybrid[group]["hit_rate_at_5"] >= 0.8 for group in ("overall", "setup", "hold"))
        if acceptance
        else None
    )
    report = {
        "build_id": build["build_id"],
        "created_at": datetime.now(UTC).isoformat(),
        "dataset": dataset_info,
        "manifest_sha256": file_hash(manifest_path),
        "build_config": build["config"],
        "embedding": build["embedding"],
        "runtime": build["runtime"],
        "retrieval": {"top_k": 5, "candidate_k": 20, "rrf_k": 60},
        "modes": modes,
        "acceptance_passed": passed,
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "report.json", report)
    lines = [
        "# Retrieval evaluation",
        "",
        f"Build: `{build['build_id']}`",
        "",
        "| Mode | Overall HitRate@5 | Setup | Hold |",
        "| --- | --- | --- | --- |",
    ]
    for mode, values in modes.items():
        rates = [f"{values[g]['hits']}/{values[g]['count']}" for g in ("overall", "setup", "hold")]
        lines.append(f"| {mode} | {' | '.join(rates)} |")
    lines.extend(
        [
            "",
            f"Acceptance passed: {passed}",
            "",
            "Functional correctness and retrieval quality do not establish RTL repair success.",
            "",
        ]
    )
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def main(argv=None):
    """Run evaluation and write full JSON plus a readable summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kb", "dataset", "manifest", "output"):
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args(argv)
    try:
        result = evaluate(args.kb, args.dataset, args.manifest, args.output)
        print(
            json.dumps(
                {
                    "build_id": result["build_id"],
                    "acceptance_passed": result["acceptance_passed"],
                    "modes": {
                        m: {g: v[g] for g in ("overall", "setup", "hold")}
                        for m, v in result["modes"].items()
                    },
                }
            )
        )
        return 2 if result["acceptance_passed"] is False else 0
    except RagError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
