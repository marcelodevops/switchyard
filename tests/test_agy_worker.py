"""Tests for the AGY CLI worker."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from switchyard.agy_worker import AgyWorker
from switchyard.models import Task


class DummyProcess:
    def __init__(self, stdout: bytes, stderr: bytes = b"", returncode: int = 0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self):
        return self._stdout, self._stderr


@pytest.mark.asyncio
async def test_agy_worker_executes_prompt(monkeypatch):
    recorded_cmd = []

    async def mock_subprocess_exec(*cmd, **kwargs):
        recorded_cmd.extend(cmd)
        return DummyProcess(
            stdout=b'{"status": "SUCCESS", "response": "def add(a, b): return a + b\\n", "duration_seconds": 1.2}',
            returncode=0,
        )

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_subprocess_exec)

    worker = AgyWorker(
        name="agy",
        capabilities={"coding"},
        bin_path="agy",
        effort="low",
    )

    result = await worker.execute(Task(prompt="Write an add function in Python"))

    assert result.success is True
    assert result.output == "def add(a, b): return a + b"
    assert result.worker_name == "agy"
    assert result.metadata.get("duration_seconds") == 1.2
    assert "-p" in recorded_cmd
    assert "Write an add function in Python" in recorded_cmd
    assert "--output-format" in recorded_cmd
    assert "json" in recorded_cmd
    assert "--effort" in recorded_cmd
    assert "low" in recorded_cmd


@pytest.mark.asyncio
async def test_agy_worker_handles_failure(monkeypatch):
    async def mock_subprocess_exec(*cmd, **kwargs):
        return DummyProcess(
            stdout=b"",
            stderr=b"Command failed due to network error",
            returncode=1,
        )

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_subprocess_exec)

    worker = AgyWorker(
        name="agy",
        capabilities={"coding"},
    )

    result = await worker.execute(Task(prompt="Do work"))

    assert result.success is False
    assert result.worker_name == "agy"
    assert "Worker request failed" in result.output
    assert result.metadata["error"]


@pytest.mark.asyncio
async def test_agy_worker_timeout_kills_process(monkeypatch):
    proc = AsyncMock()
    proc.kill = MagicMock()

    async def hang():
        await asyncio.Event().wait()

    proc.communicate.side_effect = hang
    proc.wait.return_value = -9

    async def mock_subprocess_exec(*cmd, **kwargs):
        return proc

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_subprocess_exec)

    worker = AgyWorker(
        name="agy",
        capabilities={"coding"},
        timeout=0.01,
    )

    result = await worker.execute(Task(prompt="Hang forever"))

    assert result.success is False
    assert result.worker_name == "agy"
    assert "timed out" in result.metadata["error"]
    assert proc.kill.called
    proc.wait.assert_awaited_once()


@pytest.mark.asyncio
async def test_agy_worker_handles_plain_text_fallback(monkeypatch):
    async def mock_subprocess_exec(*cmd, **kwargs):
        return DummyProcess(
            stdout=b"Plain text model answer\n",
            returncode=0,
        )

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_subprocess_exec)

    worker = AgyWorker(
        name="agy",
        capabilities={"coding"},
    )

    result = await worker.execute(Task(prompt="Simple question"))

    assert result.success is True
    assert result.output == "Plain text model answer"
