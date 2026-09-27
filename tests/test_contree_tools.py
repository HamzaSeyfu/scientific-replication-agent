import pytest

from replicator.sandbox.contree import ContreeWorkspaceTools


class FakeProc:
    def __init__(self, command: str):
        self.command = command
        self.stdout = "ok\n"
        self.stderr = ""
        self._returncode = 0

    def communicate(self, timeout=None):
        return self.stdout, self.stderr

    def wait(self):
        return self._returncode

    def kill(self):
        self._returncode = -9


class FakeSession:
    def __init__(self):
        self.commands = []

    def popen(self, command, **kwargs):
        self.commands.append(command)
        return FakeProc(command)


def test_contree_shell_is_rooted_in_remote_workspace():
    session = FakeSession()
    tools = ContreeWorkspaceTools(session)
    result = tools.run_shell("python experiment.py")
    assert result.ok
    assert any("cd /workspace" in command for command in session.commands)
    assert any("python experiment.py" in command for command in session.commands)


def test_contree_file_paths_reject_escape():
    tools = ContreeWorkspaceTools(FakeSession())
    with pytest.raises(ValueError):
        tools.read_file("../sealed-target.json")


def test_contree_write_transfers_content_without_interpolating_plaintext():
    session = FakeSession()
    tools = ContreeWorkspaceTools(session)
    result = tools.write_file("evidence/raw.txt", "scientific evidence")
    assert result.ok
    command = session.commands[-1]
    assert "scientific evidence" not in command
    assert "base64 -d" in command
