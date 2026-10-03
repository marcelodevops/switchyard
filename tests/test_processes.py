"""Tests for read-only local process inspection."""

import subprocess

import pytest

from switchyard.processes import (
    ProcessInspectionError,
    ProcessNotFoundError,
    inspect_process,
    list_processes,
)


SNAPSHOT = (
    "  42 1 S 12.5 2.1 8192 01:02:03 /usr/bin/python qwen38 --port 8000\n"
    "  77 42 R+ 0.0 0.1 1024 00:05 /bin/helper --label two words\n"
)


@pytest.fixture
def ps_output(monkeypatch):
    def set_output(stdout=SNAPSHOT, returncode=0, stderr=""):
        calls = []

        def run(args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(args, returncode, stdout, stderr)

        monkeypatch.setattr("switchyard.processes.subprocess.run", run)
        return calls

    return set_output


def test_listing_parses_structured_process_fields(ps_output):
    calls = ps_output()

    processes = list_processes()

    assert len(processes) == 2
    assert processes[0].model_dump() == {
        "pid": 42, "ppid": 1, "state": "S",
        "cpu_percent": 12.5, "memory_percent": 2.1,
        "rss_kib": 8192, "elapsed": "01:02:03",
        "command": "/usr/bin/python qwen38 --port 8000",
    }
    assert processes[1].command == "/bin/helper --label two words"
    args, kwargs = calls[0]
    assert args == [
        "/bin/ps", "-axww", "-o",
        "pid=,ppid=,state=,pcpu=,pmem=,rss=,etime=,command=",
    ]
    assert not kwargs.get("shell", False)
    assert kwargs["env"]["LC_ALL"] == "C"
    assert kwargs["timeout"] == 5


def test_filtering_is_literal_and_not_passed_to_ps(ps_output):
    calls = ps_output()

    assert [p.pid for p in list_processes("qwen38")] == [42]
    assert list_processes("qwen38; kill 42") == []
    assert len(calls) == 2
    assert calls[0][0] == calls[1][0]


def test_invalid_filter_never_runs_command(ps_output):
    calls = ps_output()
    with pytest.raises(ValueError, match="command_contains"):
        list_processes(42)
    assert calls == []


def test_inspect_returns_matching_pid(ps_output):
    ps_output()
    assert inspect_process(77).pid == 77


def test_missing_pid_is_explicit(ps_output):
    ps_output()
    with pytest.raises(ProcessNotFoundError, match="PID 99"):
        inspect_process(99)


@pytest.mark.parametrize("pid", [0, -1, True, "42"])
def test_invalid_pid_never_runs_command(ps_output, pid):
    calls = ps_output()
    with pytest.raises(ValueError, match="positive integer"):
        inspect_process(pid)
    assert calls == []


def test_command_failure_is_not_an_empty_listing(ps_output):
    ps_output(returncode=1, stderr="permission denied")
    with pytest.raises(ProcessInspectionError, match="exit code 1"):
        list_processes()


@pytest.mark.parametrize(
    "output",
    [
        "",
        "unexpected output\n",
        SNAPSHOT + "42 1 S invalid 1.0 100 00:05 command\n",
        "42 1 S nan 1.0 100 00:05 command\n",
        "42 1 S 1.0 1.0 -100 00:05 command\n",
    ],
)
def test_malformed_output_rejects_entire_snapshot(ps_output, output):
    ps_output(stdout=output)
    with pytest.raises(ProcessInspectionError, match="output"):
        list_processes()


@pytest.mark.parametrize(
    "error",
    [
        OSError("ps unavailable"),
        subprocess.TimeoutExpired("/bin/ps", 5),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid byte"),
    ],
)
def test_command_launch_or_timeout_failure(monkeypatch, error):
    def run(*args, **kwargs):
        raise error

    monkeypatch.setattr("switchyard.processes.subprocess.run", run)
    with pytest.raises(ProcessInspectionError):
        list_processes()
