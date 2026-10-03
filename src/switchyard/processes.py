"""Read-only process snapshots on the local macOS host."""

import os
import subprocess

from pydantic import BaseModel, Field


class ProcessInfo(BaseModel):
    """Process metrics reported by ps; RSS is in KiB and elapsed is OS text."""

    pid: int = Field(gt=0)
    ppid: int = Field(ge=0)
    state: str = Field(min_length=1)
    cpu_percent: float = Field(ge=0, allow_inf_nan=False)
    memory_percent: float = Field(ge=0, allow_inf_nan=False)
    rss_kib: int = Field(ge=0)
    elapsed: str = Field(min_length=1)
    command: str = Field(min_length=1)


class ProcessInspectionError(RuntimeError):
    """The OS command failed or returned an invalid snapshot."""


class ProcessNotFoundError(LookupError):
    """A requested PID was absent from the snapshot."""


def list_processes(command_contains: str | None = None) -> list[ProcessInfo]:
    """Read local processes, optionally matching a case-sensitive literal substring."""
    if command_contains is not None and not isinstance(command_contains, str):
        raise ValueError("command_contains must be a string or None")

    try:
        result = subprocess.run(
            [
                "/bin/ps", "-axww", "-o",
                "pid=,ppid=,state=,pcpu=,pmem=,rss=,etime=,command=",
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "LC_ALL": "C"},
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
        raise ProcessInspectionError(f"Unable to read process snapshot: {exc}") from exc

    if result.returncode != 0:
        raise ProcessInspectionError(
            f"ps failed with exit code {result.returncode}: {result.stderr.strip()}"
        )
    if not result.stdout.strip():
        raise ProcessInspectionError("ps returned empty output")

    processes = []
    for line_number, line in enumerate(result.stdout.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            pid, ppid, state, cpu, memory, rss, elapsed, command = line.split(maxsplit=7)
            process = ProcessInfo(
                pid=int(pid), ppid=int(ppid), state=state,
                cpu_percent=float(cpu), memory_percent=float(memory),
                rss_kib=int(rss), elapsed=elapsed, command=command,
            )
        except ValueError as exc:
            raise ProcessInspectionError(
                f"Malformed ps output at line {line_number}"
            ) from exc
        if command_contains is None or command_contains in process.command:
            processes.append(process)
    return processes


def inspect_process(pid: int) -> ProcessInfo:
    """Read one PID from a local snapshot, raising if it no longer exists."""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        raise ValueError("pid must be a positive integer")
    for process in list_processes():
        if process.pid == pid:
            return process
    raise ProcessNotFoundError(f"PID {pid} not found in the local process snapshot")
