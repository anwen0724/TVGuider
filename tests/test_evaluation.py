"""Evaluation validates frozen inputs and scores body evidence, not synthetic headings."""

import json

import pytest

from rag import build_knowledge_base
from rag.contracts import InputError
from rag.evaluate import evaluate
from rag.storage import file_hash, write_json


@pytest.fixture
def evaluation_inputs(tmp_path, source, config, backend):
    kb = tmp_path / "kb"
    report = build_knowledge_base(source, kb, config, backend=backend)
    folder = tmp_path / "evaluation" / "rag"
    folder.mkdir(parents=True)
    dataset = folder / "dev.jsonl"
    rows = [
        {
            "id": "hit",
            "topic": "setup",
            "query": "combinational",
            "relevant": [
                {
                    "document_id": "setup",
                    "heading_path": ["Diagnosis"],
                    "line_start": 9,
                    "line_end": 9,
                }
            ],
        }
    ]
    dataset.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    manifest = folder / "manifest.json"
    write_json(
        manifest,
        {
            "schema_version": 1,
            "corpus": [
                {
                    "path": "source/setup.md",
                    "document_id": "setup",
                    "sha256": file_hash(source / "setup.md"),
                }
            ],
            "datasets": {
                "dev": {
                    "path": "evaluation/rag/dev.jsonl",
                    "purpose": "development",
                    "sha256": file_hash(dataset),
                    "count": 1,
                }
            },
        },
    )
    return kb, dataset, manifest, report


def test_evaluation_reports_all_modes_with_prespecified_body_labels(
    tmp_path, evaluation_inputs, backend
):
    kb, dataset, manifest, report = evaluation_inputs
    result = evaluate(kb, dataset, manifest, tmp_path / "reports", backend=backend)
    assert result["build_id"] == report.build_id
    assert set(result["modes"]) == {"dense", "bm25", "hybrid"}
    assert all(mode["overall"]["hit_rate_at_5"] == 1.0 for mode in result["modes"].values())
    assert result["acceptance_passed"] is None
    assert (tmp_path / "reports" / "report.json").is_file()
    assert (tmp_path / "reports" / "report.md").is_file()


@pytest.mark.parametrize(
    "change", ["dataset_hash", "corpus_hash", "heading_only_label", "acceptance_count"]
)
def test_evaluation_rejects_changed_or_invalid_frozen_inputs(
    tmp_path, evaluation_inputs, backend, change
):
    kb, dataset, manifest_path, _ = evaluation_inputs
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if change == "dataset_hash":
        with dataset.open("a", encoding="utf-8") as stream:
            stream.write("\n")
    elif change == "corpus_hash":
        (tmp_path / "source" / "setup.md").write_text("changed", encoding="utf-8")
    elif change == "heading_only_label":
        row = json.loads(dataset.read_text(encoding="utf-8"))
        row["relevant"][0].update(line_start=7, line_end=7)
        dataset.write_text(json.dumps(row), encoding="utf-8")
        manifest["datasets"]["dev"]["sha256"] = file_hash(dataset)
    else:
        manifest["datasets"]["dev"]["purpose"] = "acceptance"
    write_json(manifest_path, manifest)
    with pytest.raises(InputError):
        evaluate(kb, dataset, manifest_path, tmp_path / "reports", backend=backend)
    assert not (tmp_path / "reports" / "report.json").exists()
