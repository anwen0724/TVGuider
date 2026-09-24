"""CLI JSON, exit status and parity with the Python application boundary."""

import json
import subprocess
import sys
from dataclasses import asdict

from rag import build_knowledge_base, search_knowledge_base


def test_bm25_cli_reloads_in_another_process_with_api_parity(tmp_path, source, config, backend):
    kb = tmp_path / "kb"
    build_knowledge_base(source, kb, config, backend=backend)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "rag",
            "search",
            "--kb",
            str(kb),
            "--query",
            "setup",
            "--mode",
            "bm25",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == asdict(search_knowledge_base(kb, "setup", mode="bm25"))
    assert result.stderr == ""
