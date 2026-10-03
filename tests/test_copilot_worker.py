"""Tests for the GitHub Copilot CLI worker."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from switchyard.copilot_worker import CopilotWorker
from switchyard.models import Task


class DummyProcess:
    def __init__(self, stdout: bytes, stderr: bytes = b"", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

    async def communicate(self):
        return self.stdout, self.stderr


@pytest.mark.asyncio
async def test_copilot_worker_runs_headless_with_scoped_permissions(monkeypatch):
    commands = []

    async def mock_subprocess_exec(*cmd, **kwargs):
        commands.append((cmd, kwargs))
        return DummyProcess(b"COPILOT_WORKER_OK\n")

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_subprocess_exec)
    monkeypatch.setattr("switchyard.copilot_worker.shutil.which", lambda path: None)
    worker = CopilotWorker(name="copilot", capabilities={"coding"}, bin_path="copilot")

    result = await worker.execute(Task(prompt="Reply exactly COPILOT_WORKER_OK"))

    assert result.success is True
    assert result.output == "COPILOT_WORKER_OK"
    assert result.worker_name == "copilot"
    assert result.metadata == {}
    cmd, kwargs = commands[0]
    assert cmd == (
        "copilot", "-p", "Reply exactly COPILOT_WORKER_OK",
        "--silent", "--allow-all-tools",
    )
    assert kwargs == {
        "stdout": asyncio.subprocess.PIPE,
        "stderr": asyncio.subprocess.PIPE,
    }


@pytest.mark.asyncio
async def test_copilot_worker_passes_optional_model(monkeypatch):
    commands = []

    async def mock_subprocess_exec(*cmd, **kwargs):
        commands.append(cmd)
        return DummyProcess(b"Answer\n")

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_subprocess_exec)
    worker = CopilotWorker(name="copilot", capabilities={"coding"}, model="gpt-5.4")

    result = await worker.execute(Task(prompt="Task"))

    assert result.success is True
    assert result.metadata == {"model": "gpt-5.4"}
    assert commands[0][-2:] == ("--model", "gpt-5.4")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stdout", "stderr", "returncode", "message"),
    [
        (b"", b"Authentication required", 1, "Authentication required"),
        (b"", b"", 0, "empty response"),
    ],
)
async def test_copilot_worker_returns_failure_for_bad_output(
    monkeypatch, stdout, stderr, returncode, message
):
    async def mock_subprocess_exec(*cmd, **kwargs):
        return DummyProcess(stdout, stderr, returncode)

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_subprocess_exec)
    worker = CopilotWorker(name="copilot", capabilities={"coding"})

    result = await worker.execute(Task(prompt="Task"))

    assert result.success is False
    assert result.worker_name == "copilot"
    assert message in result.metadata["error"]


@pytest.mark.asyncio
async def test_copilot_worker_timeout_kills_and_reaps(monkeypatch):
    process = AsyncMock()
    process.kill = MagicMock()

    async def hang():
        await asyncio.Event().wait()

    process.communicate.side_effect = hang
    process.wait.return_value = -9

    async def mock_subprocess_exec(*cmd, **kwargs):
        return process

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_subprocess_exec)
    worker = CopilotWorker(name="copilot", capabilities={"coding"}, timeout=0.01)

    result = await worker.execute(Task(prompt="Task"))

    assert result.success is False
    assert "timed out" in result.metadata["error"]
    process.kill.assert_called_once()
    process.wait.assert_awaited_once()
