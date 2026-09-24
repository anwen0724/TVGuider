"""Run RTL/report directories through TVIR, diagnosis, retrieval and repair."""

import json
import os
from contextlib import chdir
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from dotenv import load_dotenv
from openai import OpenAIError
from pyverilog.vparser.parser import ParseError

from llm_clients.deepseek_client import DeepSeekClientConfig, DeepSeekLLMClient
from rag import search_knowledge_base
from rag.contracts import RagError
from repair import RepairConstraints, RepairPlanner, RepairSuggestionGenerator
from repair.knowledge import build_retrieval_query, retrieval_context
from root_cause import RootCauseClassifier
from root_cause.explanation import RootCauseExplainer
from tvir.api import build_tvir_dicts_from_vivado_report_and_rtl

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RTL_DIR = Path("C:/all/work/paper-project/VioAdvisor/code_and_xdc/all_code/s3_code")
REPORT_DIR = Path("C:/all/work/paper-project/VioAdvisor/code_and_xdc/all_reports/s3_reports")
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "pipeline"
KB_DIR = PROJECT_ROOT / "artifacts" / "rag" / "kb"
ENV_FILE = PROJECT_ROOT / ".env"
LLM_CONFIG = DeepSeekClientConfig(model="deepseek-flash", max_tokens=32768, temperature=0.2)
DESIGN_CONTEXT = ""
RETRIEVAL_MODE = "hybrid"
TOP_K = 5
MAX_PATHS = 1
IVERILOG_DIR = Path("C:/all/software/iverilog/bin")
RTL_SUFFIXES = (".v",)
REPORT_SUFFIXES = (".rpt", ".txt")


def discover_cases(rtl_dir, report_dir):
    rtl_dir, report_dir = Path(rtl_dir), Path(report_dir)
    for directory in (rtl_dir, report_dir):
        if not directory.is_dir():
            raise FileNotFoundError(f"Input directory does not exist: {directory}")

    def scan(directory, suffixes):
        files = {}
        for path in sorted(directory.rglob("*")):
            if path.is_file() and path.suffix.lower() in suffixes:
                key = path.relative_to(directory).with_suffix("")
                if key in files:
                    raise ValueError(f"Multiple input files match {key}: {files[key]}, {path}")
                files[key] = path
        return files

    rtl_files = scan(rtl_dir, RTL_SUFFIXES)
    reports = scan(report_dir, REPORT_SUFFIXES)
    if not rtl_files or not reports:
        raise ValueError("No RTL files or timing reports found in the configured directories")
    unmatched = rtl_files.keys() ^ reports.keys()
    if unmatched:
        raise ValueError(
            "Unmatched RTL/report names: " + ", ".join(str(p) for p in sorted(unmatched))
        )
    return [(key, rtl_files[key], reports[key]) for key in sorted(reports)]


def main(*, llm_client=None, embedding_backend=None):
    load_dotenv(resolve_path(ENV_FILE))
    if IVERILOG_DIR:
        os.environ["PATH"] = (
            str(resolve_path(IVERILOG_DIR)) + os.pathsep + os.environ.get("PATH", "")
        )
    rtl_dir = resolve_path(RTL_DIR)
    report_dir = resolve_path(REPORT_DIR)
    output_dir = resolve_path(OUTPUT_DIR)
    kb_dir = resolve_path(KB_DIR)
    try:
        cases = discover_cases(rtl_dir, report_dir)
    except (OSError, ValueError) as exc:
        print(f"Input error: {exc}")
        return 1

    failures = 0
    for case_id, rtl_path, report_path in cases:
        try:
            rtl = rtl_path.read_text(encoding="utf-8-sig")
            report = report_path.read_text(encoding="utf-8-sig")
            with TemporaryDirectory(prefix="tvguider-tvir-") as scratch, chdir(scratch):
                tvirs = build_tvir_dicts_from_vivado_report_and_rtl(
                    report, rtl, max_paths=MAX_PATHS
                )
            if not tvirs:
                raise ValueError("No negative-slack timing path found")

            for index, tvir in enumerate(tvirs, 1):
                case_output = output_dir / case_id
                if len(tvirs) > 1:
                    case_output = case_output / f"path-{index:03d}"
                root_file = case_output / "root_cause.json"
                repair_file = case_output / "repair_result.json"
                if root_file.exists() or repair_file.exists():
                    raise FileExistsError(f"Results already exist: {case_output}")
                case_output.mkdir(parents=True, exist_ok=True)
                if llm_client is None:
                    llm_client = DeepSeekLLMClient(LLM_CONFIG)

                rule = RootCauseClassifier().analyze(tvir)
                explainer = RootCauseExplainer(llm_client)
                root_response = llm_client.generate_response(explainer.build_prompt(tvir, rule))
                root_result = {
                    "rule_analysis": rule.to_dict(),
                    "model_raw_response": root_response,
                    "model_analysis": None,
                }
                save_json(root_file, root_result)
                diagnosis = explainer.parse_response(root_response["content"] or "", rule).to_dict()
                root_result["model_analysis"] = diagnosis
                save_json(root_file, root_result)

                query = build_retrieval_query(tvir, diagnosis)
                retrieval = search_knowledge_base(
                    kb_dir, query, mode=RETRIEVAL_MODE, top_k=TOP_K, backend=embedding_backend
                )
                plan = RepairPlanner().plan(diagnosis, rule_result=rule, tvir=tvir)
                generator = RepairSuggestionGenerator(llm_client)
                repair_prompt = generator.build_prompt(
                    tvir=tvir,
                    module2_output=diagnosis,
                    repair_plan=plan,
                    original_rtl=rtl,
                    retrieval=retrieval,
                    constraints=RepairConstraints(design_context=DESIGN_CONTEXT),
                )
                repair_response = llm_client.generate_response(repair_prompt)
                repair_result = {
                    "retrieval": {"query": query, **retrieval_context(retrieval)},
                    "model_raw_response": repair_response,
                    "model_result": None,
                }
                save_json(repair_file, repair_result)
                repair_result["model_result"] = asdict(
                    generator.parse_response(repair_response["content"] or "")
                )
                save_json(repair_file, repair_result)
                print(f"Saved: {case_output}")
        except (
            OSError,
            ValueError,
            TypeError,
            RuntimeError,
            OpenAIError,
            RagError,
            ParseError,
        ) as exc:
            failures += 1
            print(f"Failed {case_id}: {type(exc).__name__}: {exc}")
    print(f"Processed {len(cases)} cases; failed {failures}; output: {output_dir}")
    return 1 if failures else 0


def resolve_path(path):
    path = Path(path)
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
