import argparse
import json
import sys
from contextlib import chdir
from pathlib import Path
from tempfile import TemporaryDirectory

from rag.contracts import RagError

from .contracts import RepairConstraints
from .service import repair_from_tvir


def main(argv=None, *, llm_client=None):
    parser = argparse.ArgumentParser(
        description="Generate one setup repair candidate using TVIR and retrieved knowledge."
    )
    parser.add_argument("--rtl", required=True)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--report", help="Vivado STA report; process its first negative-slack path")
    inputs.add_argument("--tvir", help="A single pre-built TVIR JSON object")
    parser.add_argument("--kb", required=True)
    parser.add_argument(
        "--output",
        required=True,
        help="Directory for model responses, result.json and extracted repaired.v",
    )
    parser.add_argument("--mode", choices=["hybrid", "dense", "bm25"], default="hybrid")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--model", help="Override the model configured by DeepSeekClientConfig")
    parser.add_argument(
        "--max-tokens", type=int, help="Override the generation budget in DeepSeekClientConfig"
    )
    parser.add_argument("--design-context", help="Optional design constraints / XDC text file")
    args = parser.parse_args(argv)
    failures = (OSError, ValueError, TypeError, RuntimeError, ImportError, RagError)
    try:
        if args.max_tokens is not None and args.max_tokens <= 0:
            raise ValueError("--max-tokens must be a positive integer")
        output = Path(args.output).resolve()
        names = ("result.json", "repaired.v", "root_cause_response.json", "repair_response.json")
        if any((output / name).exists() for name in names):
            raise ValueError("Output files already exist; choose a new output directory")
        rtl = Path(args.rtl).read_text(encoding="utf-8-sig")
        if args.tvir:
            tvir = json.loads(Path(args.tvir).read_text(encoding="utf-8-sig"))
        else:
            from tvir.api import build_tvir_dicts_from_vivado_report_and_rtl

            report = Path(args.report).read_text(encoding="utf-8-sig")
            with TemporaryDirectory(prefix="tvguider-tvir-") as scratch, chdir(scratch):
                paths = build_tvir_dicts_from_vivado_report_and_rtl(report, rtl, max_paths=1)
            if not paths:
                raise ValueError("No negative-slack timing path found")
            tvir = paths[0]
        from root_cause.validation import validate_tvir

        validate_tvir(tvir)
        if llm_client is None:
            from openai import OpenAIError

            from llm_clients.deepseek_client import DeepSeekClientConfig, DeepSeekLLMClient

            failures = (*failures, OpenAIError)
            client_config = DeepSeekClientConfig()
            if args.model:
                client_config.model = args.model
            if args.max_tokens is not None:
                client_config.max_tokens = args.max_tokens
            llm_client = DeepSeekLLMClient(client_config)
        constraints = RepairConstraints(
            design_context=Path(args.design_context).read_text(encoding="utf-8-sig")
            if args.design_context
            else "",
        )
        output.mkdir(parents=True, exist_ok=True)

        def save_response(stage, response):
            with (output / f"{stage}_response.json").open("x", encoding="utf-8") as stream:
                json.dump(response, stream, ensure_ascii=False, indent=2)

        result = repair_from_tvir(
            tvir,
            rtl,
            kb_dir=args.kb,
            llm_client=llm_client,
            constraints=constraints,
            mode=args.mode,
            top_k=args.top_k,
            on_response=save_response,
        )
        with (output / "result.json").open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        repaired_rtl = result["repair"]["repaired_rtl"]
        if isinstance(repaired_rtl, str) and repaired_rtl.strip():
            with (output / "repaired.v").open("x", encoding="utf-8", newline="") as stream:
                stream.write(repaired_rtl)
        print(json.dumps({"output": str(output), "validation_status": "not_run"}))
        return 0
    except failures as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
