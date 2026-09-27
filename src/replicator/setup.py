from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .benchmarks.reclaim import ReclaimCase


@dataclass(frozen=True)
class SetupEvidence:
    repo_url: str
    commit: str
    commands: list[str]


def prepare_reclaim_workspace(case: ReclaimCase, tools, *, evidence_path: Path | None = None) -> SetupEvidence:
    """Deterministically prepare released artifacts before the blind agent starts.

    Setup is intentionally target-agnostic. It may use network access to fetch the
    explicitly declared repository/model/dataset. The blind phase uses a separate
    network-disabled tool surface over the resulting filesystem state.
    """
    commands = [
        f"git clone --depth 1 {case.repo_url} .",
        "python -m pip install -e . datasets scipy tqdm",
    ]
    for command in commands:
        result = tools.run_shell(command, timeout_seconds=900)
        if not result.ok:
            raise RuntimeError(f"setup command failed: {command}\n{result.output}")

    if case.paper_id == "2505.18513":
        preload = """python - <<'PY'
from datasets import load_dataset
from airrep import AirRep
AirRep.from_pretrained('sunweiwei/AirRep-Flan-Small')
for name in ('flan/train.jsonl', 'flan/test.jsonl', 'flan/lds.jsonl'):
    load_dataset('sunweiwei/airrep-test', data_files=name, split='train')
print('airrep artifacts cached')
PY"""
        result = tools.run_shell(preload, timeout_seconds=1800)
        if not result.ok:
            raise RuntimeError(f"AirRep artifact preload failed:\n{result.output}")
        commands.append(preload)

    commit_result = tools.run_shell("git rev-parse HEAD", timeout_seconds=30)
    if not commit_result.ok:
        raise RuntimeError(f"could not capture repository commit: {commit_result.output}")
    commit = commit_result.output.strip().splitlines()[-1]
    evidence = SetupEvidence(case.repo_url, commit, commands)
    if evidence_path is not None:
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(json.dumps(asdict(evidence), indent=2), encoding="utf-8")
    return evidence
