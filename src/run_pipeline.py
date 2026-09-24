"""Read RTL/report directories, call the analysis modules, and save their results."""

import json
import logging
from contextlib import chdir
from pathlib import Path
from tempfile import TemporaryDirectory

from llm_clients.deepseek_client import DeepSeekLLMClient
from rag import search_knowledge_base
from repair import RepairPlanner, RepairSuggestionGenerator
from repair.knowledge import build_retrieval_query, retrieval_context
from root_cause import RootCauseClassifier
from root_cause.explanation import RootCauseExplainer
from tvir.api import build_tvir_dicts_from_vivado_report_and_rtl

RTL_DIR = Path("inputs/rtl")
REPORT_DIR = Path("inputs/reports")
OUTPUT_DIR = Path("outputs")
KB_DIR = Path("artifacts/rag/kb")
RETRIEVAL_MODE = "hybrid"
TOP_K = 5

client = DeepSeekLLMClient()


def discover_cases(rtl_dir, report_dir):
    """Pair files recursively by relative path without extension; reject ambiguous inputs."""

    def scan(directory, suffixes):
        directory = Path(directory)
        if not directory.is_dir():
            raise FileNotFoundError(f"Input directory does not exist: {directory}")
        files = {}
        for path in sorted(directory.rglob("*")):
            if path.is_file() and path.suffix.lower() in suffixes:
                key = path.relative_to(directory).with_suffix("")
                if key in files:
                    raise ValueError(f"Multiple input files match {key}: {files[key]}, {path}")
                files[key] = path
        return files

    rtl_files = scan(rtl_dir, (".v",))
    reports = scan(report_dir, (".rpt", ".txt"))
    if not rtl_files or not reports:
        raise ValueError("No RTL files or timing reports found in the configured directories")
    unmatched = rtl_files.keys() ^ reports.keys()
    if unmatched:
        raise ValueError(
            "Unmatched RTL/report names: " + ", ".join(str(p) for p in sorted(unmatched))
        )
    return [(key, rtl_files[key], reports[key]) for key in sorted(reports)]


def main(*, llm_client=None, embedding_backend=None):
    """Run every case and save each stage; report case failures and continue the batch."""
    model = llm_client if llm_client is not None else client
    output_dir, kb_dir = resolve_path(OUTPUT_DIR), resolve_path(KB_DIR)
    try:
        cases = discover_cases(resolve_path(RTL_DIR), resolve_path(REPORT_DIR))
    except (OSError, ValueError) as exc:
        print(f"Input error: {exc}")
        return 1

    classifier = RootCauseClassifier()
    explainer = RootCauseExplainer(model)
    planner = RepairPlanner()
    generator = RepairSuggestionGenerator(model)
    failures = 0

    for case_id, rtl_path, report_path in cases:
        try:
            rtl = rtl_path.read_text(encoding="utf-8-sig")
            report = report_path.read_text(encoding="utf-8-sig")
            with TemporaryDirectory(prefix="tvguider-tvir-") as scratch, chdir(scratch):
                tvirs = build_tvir_dicts_from_vivado_report_and_rtl(report, rtl)
            if not tvirs:
                raise ValueError("No negative-slack timing path found")

            for index, tvir in enumerate(tvirs, 1):
                path_output = output_dir / case_id / f"path-{index:03d}"
                root_file = path_output / "root_cause.json"
                repair_file = path_output / "repair_result.json"
                if root_file.exists() or repair_file.exists():
                    raise FileExistsError(f"Results already exist: {path_output}")
                path_output.mkdir(parents=True, exist_ok=True)

                rule = classifier.analyze(tvir)
                analysis = explainer.explain_and_adjust(tvir, rule)
                diagnosis = analysis.to_dict()
                save_json(
                    root_file,
                    {
                        "rule_analysis": rule.to_dict(),
                        "model_raw_response": analysis.model_raw_response,
                        "model_analysis": diagnosis,
                    },
                )

                query = build_retrieval_query(tvir, diagnosis)
                retrieval = search_knowledge_base(
                    kb_dir, query, mode=RETRIEVAL_MODE, top_k=TOP_K, backend=embedding_backend
                )
                plan = planner.plan(diagnosis, rule_result=rule, tvir=tvir)
                repair = generator.generate(
                    tvir=tvir,
                    module2_output=diagnosis,
                    repair_plan=plan,
                    original_rtl=rtl,
                    retrieval=retrieval,
                )
                save_json(
                    repair_file,
                    {
                        "retrieval": {"query": query, **retrieval_context(retrieval)},
                        "model_raw_response": repair.model_raw_response,
                        "model_result": repair.to_dict(),
                    },
                )
                print(f"Saved: {path_output}")
        except Exception:
            failures += 1
            logging.getLogger(__name__).exception("Failed %s", case_id)
    print(f"Processed {len(cases)} cases; failed {failures}; output: {output_dir}")
    return 1 if failures else 0


def resolve_path(path):
    path = Path(path)
    return (
        path.resolve()
        if path.is_absolute()
        else (Path(__file__).resolve().parents[1] / path).resolve()
    )


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
