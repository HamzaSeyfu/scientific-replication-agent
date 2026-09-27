import json
from pathlib import Path
from types import SimpleNamespace

from replicator.core.models import Verdict
from replicator.core.sealing import TargetSealer
from replicator.orchestrator import build_executor_prompt, run_reclaim_case
from replicator.benchmarks.reclaim import load_reclaim_case


CASE = Path("benchmarks/reclaim/dev/2505.18513.json")


class FakeAirRepExecutor:
    def run(self, *, prompt, cwd, timeout_seconds, transcript_path=None, append_transcript=False):
        assert "21.11" not in prompt
        events = [
            {
                "event": "assistant",
                "step": 1,
                "role": "assistant",
                "content": "I will run the released evaluation path.",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "run_shell",
                            "arguments": json.dumps({
                                "command": "python scripts/04_evaluate.py --model_path sunweiwei/AirRep-Flan-Small --dataset sunweiwei/airrep-test --benchmark flan"
                            }),
                        },
                    }
                ],
            },
            {
                "event": "tool",
                "step": 1,
                "tool_call_id": "call-1",
                "name": "run_shell",
                "arguments": {
                    "command": "python scripts/04_evaluate.py --model_path sunweiwei/AirRep-Flan-Small --dataset sunweiwei/airrep-test --benchmark flan"
                },
                "result": {
                    "ok": True,
                    "exit_code": 0,
                    "output": "Results for flan\nLDS Spearman Correlation: 0.2111\n",
                },
            },
            {"event": "assistant", "step": 2, "role": "assistant", "content": "Execution completed."},
        ]
        assert transcript_path is not None
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_text("".join(json.dumps(e) + "\n" for e in events))
        return SimpleNamespace(success=True, timed_out=False, final_text="done")


def test_complete_executor_prompt_is_blind():
    case = load_reclaim_case(CASE)
    prompt = build_executor_prompt(case)
    assert "21.11" not in prompt
    assert "LDS Spearman" in prompt


def test_orchestrator_unseals_only_after_audit_and_normalizes_metric(tmp_path: Path):
    run = run_reclaim_case(
        case_path=CASE,
        workspace=tmp_path / "workspace",
        output_dir=tmp_path / "out",
        executor=FakeAirRepExecutor(),
        sealer=TargetSealer(secret=b"s" * 32),
    )
    assert run.audit.completed
    assert run.audit.protocol_compliant
    assert run.raw_observed_value == 0.2111
    assert run.normalized_observed_value == 21.11
    assert run.certificate.verdict == Verdict.REPRODUCED
    assert (tmp_path / "out" / "evidence.json").exists()


class LeakyExecutor(FakeAirRepExecutor):
    def run(self, *, prompt, cwd, timeout_seconds, transcript_path=None, append_transcript=False):
        assert transcript_path is not None
        event = {
            "event": "assistant",
            "step": 1,
            "role": "assistant",
            "content": "I know the published answer is 21.11, so I will tune toward it.",
        }
        tool = {
            "event": "tool",
            "step": 1,
            "name": "run_shell",
            "arguments": {"command": "echo run"},
            "result": {"ok": True, "exit_code": 0, "output": "LDS Spearman Correlation: 0.2111"},
        }
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_text(json.dumps(event) + "\n" + json.dumps(tool) + "\n")
        return SimpleNamespace(success=True)


def test_target_leakage_forces_failure_even_when_number_matches(tmp_path: Path):
    run = run_reclaim_case(
        case_path=CASE,
        workspace=tmp_path / "workspace",
        output_dir=tmp_path / "out",
        executor=LeakyExecutor(),
        sealer=TargetSealer(secret=b"s" * 32),
    )
    assert "target_leakage" in run.certificate.auditor_findings
    assert run.certificate.verdict == Verdict.NOT_REPRODUCED
