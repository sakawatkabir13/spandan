"""Verify security/regression tests, compare all models and write a private release gate."""

import json
import os
import subprocess
import sys
from pathlib import Path

from app.services.chat_contract import TOOL_CATALOG
from app.services.chat_evaluation import BASELINE, CHEAPER, DEFAULT, select_model
from app.services.chat_security import digest
from app.services.chat_service import SYSTEM


def main():
    root = Path(__file__).resolve().parents[2]
    folder = root / ".runtime/chat-evaluations"
    reports = {
        model: json.loads((folder / (model.replace(":", "_") + ".json")).read_text())
        for model in (DEFAULT, CHEAPER, BASELINE)
    }
    for report in reports.values():
        if report["contract_sha256"] != digest(TOOL_CATALOG) or report.get(
            "prompt_sha256"
        ) != digest(SYSTEM):
            raise RuntimeError("Run all comparisons against the current tool contract and prompt")
    environment = {
        **os.environ,
        "RUN_CHAT_EVALUATION": "0",
        "PYTHONPATH": str(root.parent / "spandan-mcp-server/src"),
    }
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--ignore=tests/test_chat_evaluation.py"],
        cwd=root / "backend",
        env=environment,
    )
    gate = {
        **select_model(reports, security_passed=result.returncode == 0),
        "contract_sha256": digest(TOOL_CATALOG),
        "prompt_sha256": digest(SYSTEM),
    }
    target = root / ".runtime/chat-evaluation.json"
    target.write_text(json.dumps(gate, indent=2))
    target.chmod(0o600)
    print(json.dumps(gate, indent=2))
    return 0 if gate["qualified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
