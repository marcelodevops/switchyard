"""Qoder CLI worker implementation."""

import asyncio
import json
import shutil
from typing import Any

from switchyard.models import Cost, Result, Speed, Task
from switchyard.worker import Worker


class QoderWorker(Worker):
    """Worker that executes tasks using the Qoder CLI."""

    def __init__(
        self,
        name: str,
        capabilities: set[str],
        speed: Speed = Speed.MEDIUM,
        cost: Cost = Cost.LOW,
        available: bool = True,
        timeout: float = 60.0,
        bin_path: str = "qoder",
        model: str | None = "Qwen3.8-Flash",
    ) -> None:
        super().__init__(name, capabilities, speed, cost, available)
        self.timeout = timeout
        self.bin_path = bin_path
        self.model = model

    async def execute(self, task: Task) -> Result:
        resolved_bin = shutil.which(self.bin_path) or self.bin_path
        cmd = [
            resolved_bin,
            "-p",
            task.prompt,
            "--output-format",
            "json",
            "--no-session-persistence",
        ]
        if self.model:
            cmd.extend(["--model", self.model])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout
            )
            stdout = stdout_bytes.decode().strip()
            stderr = stderr_bytes.decode().strip()

            if process.returncode != 0:
                raise RuntimeError(
                    f"qoder exited with code {process.returncode}: {stderr or stdout}"
                )

            metadata: dict[str, Any] = {}
            if self.model:
                metadata["model"] = self.model

            try:
                payload = json.loads(stdout)
                if payload.get("is_error") is True:
                    errors = payload.get("errors") or [payload.get("subtype", "error")]
                    raise RuntimeError(f"qoder execution error: {'; '.join(errors)}")

                output = payload.get("result", stdout)
                if not isinstance(output, str):
                    raise ValueError("result field was not a string")

                for key in ("session_id", "duration_ms", "total_cost_usd", "usage"):
                    if key in payload:
                        metadata[key] = payload[key]
            except (json.JSONDecodeError, ValueError):
                output = stdout

        except (asyncio.TimeoutError, RuntimeError, ValueError, OSError) as exc:
            return Result(
                output=f"Worker request failed: {exc}",
                worker_name=self.name,
                success=False,
                metadata={"error": str(exc), "model": self.model},
            )

        return Result(
            output=output.strip(),
            worker_name=self.name,
            success=True,
            metadata=metadata,
        )
