from pathlib import Path

import pytest

from replicator.agent.workspace import WorkspaceTools


def test_workspace_tools_reject_path_escape(tmp_path: Path):
    tools = WorkspaceTools(tmp_path)
    with pytest.raises(ValueError):
        tools.read_file("../secret.txt")


def test_workspace_tools_can_execute_and_capture_output(tmp_path: Path):
    tools = WorkspaceTools(tmp_path)
    result = tools.run_shell("python -c \"print('replication-ok')\"")
    assert result.ok is True
    assert result.exit_code == 0
    assert "replication-ok" in result.output


def test_workspace_write_then_read(tmp_path: Path):
    tools = WorkspaceTools(tmp_path)
    assert tools.write_file("artifacts/result.txt", "42").ok
    read = tools.read_file("artifacts/result.txt")
    assert read.ok
    assert read.output == "42"
