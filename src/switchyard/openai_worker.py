"""OpenAI-compatible HTTP worker implementation."""

import httpx

from switchyard.models import Cost, Result, Speed, Task
from switchyard.worker import Worker


class OpenAICompatibleWorker(Worker):
    """Worker that executes tasks using an OpenAI-compatible chat endpoint."""

    def __init__(
        self,
        name: str,
        capabilities: set[str],
        endpoint: str,
        model: str,
        speed: Speed = Speed.MEDIUM,
        cost: Cost = Cost.MEDIUM,
        available: bool = True,
        timeout: float = 30,
        api_key: str | None = None,
    ) -> None:
        super().__init__(name, capabilities, speed, cost, available)
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.api_key = api_key

    async def execute(self, task: Task) -> Result:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.endpoint}/chat/completions",
                    headers=headers,
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": task.prompt}],
                    },
                )
                response.raise_for_status()
                payload = response.json()
                output = payload["choices"][0]["message"]["content"]
                if not isinstance(output, str):
                    raise ValueError("chat completion content was not a string")
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            return Result(
                output=f"Worker request failed: {exc}",
                worker_name=self.name,
                success=False,
                metadata={"error": str(exc), "model": self.model},
            )

        return Result(
            output=output,
            worker_name=self.name,
            success=True,
            metadata={"model": self.model},
        )
