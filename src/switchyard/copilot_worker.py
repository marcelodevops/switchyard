"""GitHub Copilot CLI worker implementation."""

import asyncio
import shutil

from switchyard.models import Cost, Result, Speed, Task
from switchyard.worker import Worker


class CopilotWorker(Worker):
    """Execute tasks through Copilot's non-interactive CLI."""

    def __init__(
        self,
        name: str,
        capabilities: set[str],
        speed: Speed = Speed.MEDIUM,
        cost: Cost = Cost.MEDIUM,
        available: bool = True,
        timeout: float = 120.0,
        bin_path: str = "copilot",
        model: str | None = None,
    ) -> None:
        super().__init__(name, capabilities, speed, cost, available)
        self.timeout = timeout
        self.bin_path = bin_path
        self.model = model

    async def execute(self, task: Task) -> Result:
        resolved_bin = shutil.which(self.bin_path) or self.bin_path
        cmd = [resolved_bin, "-p", task.prompt, "--silent", "--allow-all-tools"]
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
            if not stdout:
                raise RuntimeError(f"{resolved_bin} returned an empty response")
        except (RuntimeError, ValueError, OSError) as exc:
            return Result(
                output=f"Worker request failed: {exc}",
                worker_name=self.name,
                success=False,
                metadata={"error": str(exc)},
            )

        metadata = {"model": self.model} if self.model else {}
        return Result(output=stdout, worker_name=self.name, metadata=metadata)
