import json
from pathlib import Path
from types import SimpleNamespace

from replicator.agent.nemotron import NemotronWorkspaceAgent


class FakeNemotronClient:
    def __init__(self):
        self.calls = 0

    def chat(self, *, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            tool_call = SimpleNamespace(
                id="call-1",
                function=SimpleNamespace(
                    name="write_file",
                    arguments=json.dumps({"path": "result.json", "content": '{"metric": 0.84}'}),
                ),
            )
            message = SimpleNamespace(content="", tool_calls=[tool_call])
        else:
            message = SimpleNamespace(content="Experiment artifact written.", tool_calls=[])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_agent_executes_tool_loop_and_writes_transcript(tmp_path: Path):
    transcript = tmp_path / "transcript.jsonl"
    agent = NemotronWorkspaceAgent(FakeNemotronClient(), max_steps=4)

    result = agent.run(
        prompt="Produce result.json",
        cwd=tmp_path,
        timeout_seconds=10,
        transcript_path=transcript,
    )

    assert result.success
    assert json.loads((tmp_path / "result.json").read_text()) == {"metric": 0.84}
    text = transcript.read_text()
    assert '"event": "tool"' in text
    assert '"name": "write_file"' in text
