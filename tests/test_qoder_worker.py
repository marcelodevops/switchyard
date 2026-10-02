"""Tests for the Qoder CLI worker."""

import asyncio
from unittest.mock import AsyncMock
import pytest

from switchyard.models import Task
from switchyard.qoder_worker import QoderWorker


class DummyProcess:
    def __init__(self, stdout: bytes, stderr: bytes = b"", returncode: int = 0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self):
        return self._stdout, self._stderr


@pytest.mark.asyncio
async def test_qoder_worker_executes_prompt(monkeypatch):
    recorded_cmd = []

    async def mock_subprocess_exec(*cmd, **kwargs):
        recorded_cmd.extend(cmd)
        return DummyProcess(
            stdout=(
                b'{"type":"result","subtype":"success","result":"Qoder answer",'
                b'"duration_ms":3200,"session_id":"sess-123","total_cost_usd":0}'
            ),
            returncode=0,
        )

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_subprocess_exec)

    worker = QoderWorker(
        name="qoder",
        capabilities={"coding"},
        bin_path="qoder",
        model="Qwen3.8-Flash",
    )

    result = await worker.execute(Task(prompt="Write palindrome function"))

    assert result.success is True
    assert result.output == "Qoder answer"
    assert result.worker_name == "qoder"
    assert result.metadata["model"] == "Qwen3.8-Flash"
    assert result.metadata["duration_ms"] == 3200
    assert result.metadata["session_id"] == "sess-123"

    assert "-p" in recorded_cmd
    assert "Write palindrome function" in recorded_cmd
    assert "--output-format" in recorded_cmd
    assert "json" in recorded_cmd
    assert "--no-session-persistence" in recorded_cmd
    assert "--model" in recorded_cmd
    assert "Qwen3.8-Flash" in recorded_cmd


@pytest.mark.asyncio
async def test_qoder_worker_handles_process_failure(monkeypatch):
    async def mock_subprocess_exec(*cmd, **kwargs):
        return DummyProcess(
            stdout=b"",
            stderr=b"Command failed due to missing binary",
            returncode=1,
        )

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_subprocess_exec)

    worker = QoderWorker(name="qoder", capabilities={"coding"})
    result = await worker.execute(Task(prompt="Do work"))

    assert result.success is False
    assert result.worker_name == "qoder"
    assert "Worker request failed" in result.output
    assert result.metadata["error"]


@pytest.mark.asyncio
async def test_qoder_worker_handles_is_error_payload(monkeypatch):
    async def mock_subprocess_exec(*cmd, **kwargs):
        return DummyProcess(
            stdout=b'{"is_error":true,"errors":["Credit limit reached"],"subtype":"error"}',
            returncode=0,
        )

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_subprocess_exec)

    worker = QoderWorker(name="qoder", capabilities={"coding"})
    result = await worker.execute(Task(prompt="Do work"))

    assert result.success is False
    assert result.worker_name == "qoder"
    assert "Credit limit reached" in result.output


@pytest.mark.asyncio
async def test_qoder_worker_handles_timeout(monkeypatch):
    async def mock_subprocess_exec(*cmd, **kwargs):
        proc = AsyncMock()
        proc.communicate.side_effect = asyncio.TimeoutError()
        return proc

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_subprocess_exec)

    worker = QoderWorker(name="qoder", capabilities={"coding"}, timeout=0.01)
    result = await worker.execute(Task(prompt="Hang"))

    assert result.success is False
    assert result.worker_name == "qoder"
    assert "Worker request failed" in result.output


@pytest.mark.asyncio
async def test_qoder_worker_handles_plain_text_fallback(monkeypatch):
    async def mock_subprocess_exec(*cmd, **kwargs):
        return DummyProcess(
            stdout=b"Plain text qoder response\n",
            returncode=0,
        )

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_subprocess_exec)

    worker = QoderWorker(name="qoder", capabilities={"coding"})
    result = await worker.execute(Task(prompt="Question"))

    assert result.success is True
    assert result.output == "Plain text qoder response"
