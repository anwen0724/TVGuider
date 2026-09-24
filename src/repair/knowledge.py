from rag.contracts import SearchResponse

CAUSE_DESCRIPTIONS = {
    "S1_combinational_path_too_long": "long combinational logic path",
    "S2_high_fanout": "high signal fanout and routing delay",
    "S3_complex_arithmetic_no_pipeline": "complex arithmetic without sufficient pipelining",
    "S4_cross_hierarchy_path": "critical path crossing module hierarchy",
    "UNKNOWN": "uncertain setup root cause requiring evidence-based diagnosis",
}


def build_retrieval_query(tvir: dict, root_cause: dict) -> str:
    labels = root_cause.get("final_root_cause") or {}
    selected = [labels.get("primary", "UNKNOWN"), *(labels.get("secondary") or [])]
    descriptions = [CAUSE_DESCRIPTIONS[label] for label in selected if label in CAUSE_DESCRIPTIONS]
    metrics = tvir.get("path_metrics") or {}
    context = tvir.get("context") or {}
    facts = []
    for name, value in {
        "clock period ns": context.get("period_ns"),
        "setup slack ns": context.get("slack_ns"),
        "logic levels": metrics.get("logic_levels"),
        "logic delay ns": metrics.get("combinational_delay_ns"),
        "routing delay ns": metrics.get("net_delay_ns"),
        "maximum fanout": (tvir.get("fanout_info") or {}).get("max_fanout_count"),
    }.items():
        if type(value) in (int, float):
            facts.append(f"{name}: {value}")
    return (
        "Setup timing violation repair. Root cause: "
        + "; ".join(descriptions or [CAUSE_DESCRIPTIONS["UNKNOWN"]])
        + ". "
        + "; ".join(facts)
        + ". RTL optimization, strategy preconditions, interface and latency constraints, functional equivalence."
    )


def retrieval_context(response: SearchResponse) -> dict:
    return {
        "build_id": response.build_id,
        "mode": response.mode,
        "top_k": response.top_k,
        "chunks": [
            {
                "chunk_id": hit.chunk.chunk_id,
                "document_id": hit.chunk.document_id,
                "title": hit.chunk.title,
                "heading_path": hit.chunk.heading_path,
                "text": hit.chunk.text,
                "topics": hit.chunk.topics,
                "sources": hit.chunk.sources,
                "source_path": hit.chunk.source_path,
                "body_spans": hit.chunk.body_spans,
                "rank": hit.rank,
                "score": hit.score,
            }
            for hit in response.results
        ],
    }
