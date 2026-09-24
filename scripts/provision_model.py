"""Explicitly provision the pinned model and record exact local file fingerprints."""

import argparse
import json
from hashlib import file_digest
from pathlib import Path

import yaml
from huggingface_hub import snapshot_download


def main():
    """Download only the configured revision; normal RAG operations stay offline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/rag.yaml")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    root = Path(config["model_path"])
    snapshot_download(
        config["model_id"],
        revision=config["revision"],
        local_dir=str(root),
        ignore_patterns=["onnx/*"],
    )
    files = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if (
            path.is_file()
            and not any(p.startswith(".") for p in relative.parts)
            and path.name not in {"rag-model.json", "README.md"}
        ):
            with path.open("rb") as stream:
                files[relative.as_posix()] = file_digest(stream, "sha256").hexdigest()
    receipt = {"model_id": config["model_id"], "revision": config["revision"], "files": files}
    (root / "rag-model.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(
        json.dumps({"model_path": str(root), "revision": config["revision"], "files": len(files)})
    )


if __name__ == "__main__":
    main()
