"""Antigravity (AGY) CLI worker implementation."""

import asyncio
import json
import shutil
from typing import Any

from switchyard.models import Cost, Result, Speed, Task
from switchyard.worker import Worker


class AgyWorker(Worker):
    """Worker that executes tasks using the Antigravity (AGY) CLI."""

    def __init__(
        self,
        name: str,
        capabilities: set[str],
        speed: Speed = Speed.FAST,
        cost: Cost = Cost.MEDIUM,
        available: bool = True,
        timeout: float = 60.0,
        bin_path: str = "agy",
        effort: str | None = None,
        model: str | None = None,
    ) -> None:
        super().__init__(name, capabilities, speed, cost, available)
        self.timeout = timeout
        self.bin_path = bin_path
        self.effort = effort
        self.model = model

    async def execute(self, task: Task) -> Result:
        resolved_bin = shutil.which(self.bin_path) or self.bin_path
        cmd = [resolved_bin, "-p", task.prompt, "--output-format", "json"]
        if self.effort:
            cmd.extend(["--effort", self.effort])
        if self.model:
            cmd.extend(["--model", self.model])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise RuntimeError(f"{resolved_bin} timed out after {self.timeout} seconds")
            stdout = stdout_bytes.decode().strip()
            stderr = stderr_bytes.decode().strip()

            if process.returncode != 0:
                raise RuntimeError(
                    f"{resolved_bin} exited with code {process.returncode}: {stderr or stdout}"
                )

            metadata: dict[str, Any] = {}
            if self.model:
                metadata["model"] = self.model
            if self.effort:
                metadata["effort"] = self.effort

            try:
                payload = json.loads(stdout)
                output = payload.get("response", stdout)
                if not isinstance(output, str):
                    raise ValueError("response field was not a string")
                for key in ("conversation_id", "duration_seconds", "usage"):
                    if key in payload:
                        metadata[key] = payload[key]
            except (json.JSONDecodeError, ValueError):
                output = stdout

        except (asyncio.TimeoutError, RuntimeError, ValueError, OSError) as exc:
            return Result(
                output=f"Worker request failed: {exc}",
                worker_name=self.name,
                success=False,
                metadata={"error": str(exc)},
            )

        return Result(
            output=output.strip(),
            worker_name=self.name,
            success=True,
            metadata=metadata,
        )
