"""Tests for the OpenAI-compatible HTTP worker."""

import httpx
import pytest

from switchyard.openai_worker import OpenAICompatibleWorker
from switchyard.models import Task


@pytest.mark.asyncio
async def test_openai_worker_posts_chat_completion(monkeypatch):
    requests = []

    async def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "A real answer"}}
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "switchyard.openai_worker.httpx.AsyncClient",
        lambda **kwargs: async_client(transport=transport, **kwargs),
    )
    worker = OpenAICompatibleWorker(
        name="qwen-local",
        capabilities={"reasoning"},
        endpoint="http://colibri.local/v1/",
        model="qwen3.8-flash-next-colibri",
        api_key="test-key",
    )

    result = await worker.execute(Task(prompt="Explain this"))

    assert result.success is True
    assert result.output == "A real answer"
    assert result.worker_name == "qwen-local"
    request = requests[0]
    assert str(request.url) == "http://colibri.local/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-key"
    assert request.read() == (
        b'{"model":"qwen3.8-flash-next-colibri","messages":[{"role":"user","content":"Explain this"}]}'
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="server error"),
        httpx.Response(200, json={"choices": []}),
    ],
)
async def test_openai_worker_returns_failure_result(monkeypatch, response):
    async def handler(_request):
        return response

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "switchyard.openai_worker.httpx.AsyncClient",
        lambda **kwargs: async_client(transport=transport, **kwargs),
    )
    worker = OpenAICompatibleWorker(
        name="qwen-local",
        capabilities={"reasoning"},
        endpoint="http://colibri.local/v1",
        model="qwen3.8-flash-next-colibri",
    )

    result = await worker.execute(Task(prompt="Explain this"))

    assert result.success is False
    assert result.worker_name == "qwen-local"
    assert result.metadata["error"]
