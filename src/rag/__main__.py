"""JSON command-line entry point for the same public RAG service."""

import argparse
import json
import sys
from dataclasses import asdict

from .contracts import RagError, load_config
from .service import build_knowledge_base, search_knowledge_base


def main(argv=None):
    """Execute one build or search command."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Build and publish a full knowledge-base generation")
    build.add_argument("--source", required=True)
    build.add_argument("--kb", required=True)
    build.add_argument("--config", required=True)
    search = commands.add_parser(
        "search", help="Retrieve source chunks, without generating an answer"
    )
    search.add_argument("--kb", required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--mode", choices=["dense", "bm25", "hybrid"], default="hybrid")
    search.add_argument("--top-k", type=int, default=5)
    search.add_argument("--candidate-k", type=int)
    search.add_argument("--rrf-k", type=float, default=60)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            result = build_knowledge_base(args.source, args.kb, load_config(args.config))
        else:
            result = search_knowledge_base(
                args.kb, args.query, args.mode, args.top_k, args.candidate_k, args.rrf_k
            )
        print(json.dumps(asdict(result), ensure_ascii=False, allow_nan=False))
        return 0
    except RagError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
