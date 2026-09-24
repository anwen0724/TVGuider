from dataclasses import asdict
from hashlib import sha256

from llm_clients.responses import ResponseRecorder
from rag import search_knowledge_base
from root_cause import RootCauseClassifier
from root_cause.explanation import RootCauseExplainer
from root_cause.validation import validate_tvir

from .contracts import RepairConstraints
from .generator import RepairSuggestionGenerator
from .knowledge import build_retrieval_query, retrieval_context
from .planner import RepairPlanner


def repair_from_tvir(
    tvir,
    original_rtl,
    *,
    kb_dir,
    llm_client,
    constraints=None,
    mode="hybrid",
    top_k=5,
    embedding_backend=None,
    on_response=None,
):
    validate_tvir(tvir)
    if not isinstance(original_rtl, str) or not original_rtl.strip():
        raise ValueError("Original RTL must be nonempty")
    if mode not in {"hybrid", "dense", "bm25"} or type(top_k) is not int or top_k <= 0:
        raise ValueError("Invalid retrieval mode or top_k")
    constraints = constraints or RepairConstraints()
    rule = RootCauseClassifier().analyze(tvir)
    responses = {}
    diagnosis_client = ResponseRecorder(llm_client, "root_cause", responses, on_response)
    diagnosis = RootCauseExplainer(diagnosis_client).explain_and_adjust(tvir, rule).to_dict()
    query = build_retrieval_query(tvir, diagnosis)
    retrieval = search_knowledge_base(
        kb_dir, query, mode=mode, top_k=top_k, backend=embedding_backend
    )
    if not retrieval.results:
        raise ValueError("No knowledge chunks retrieved for setup repair")
    plan = RepairPlanner().plan(
        diagnosis,
        rule_result=rule,
        tvir=tvir,
    )
    repair_client = ResponseRecorder(llm_client, "repair", responses, on_response)
    repair = RepairSuggestionGenerator(repair_client).generate(
        tvir=tvir,
        module2_output=diagnosis,
        repair_plan=plan,
        original_rtl=original_rtl,
        retrieval=retrieval,
        constraints=constraints,
    )
    return {
        "responses": responses,
        "input_rtl_sha256": sha256(original_rtl.encode("utf-8")).hexdigest(),
        "rule_based_result": rule.to_dict(),
        "root_cause": diagnosis,
        "retrieval": {"query": query, **retrieval_context(retrieval)},
        "constraints": asdict(constraints),
        "repair": asdict(repair),
        "validation_status": "not_run",
    }
