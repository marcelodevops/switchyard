"""Tests proving that Switchyard meaningfully chooses between Colibrì and AGY.

Rule:
Capabilities determine WHO CAN do the work.
Preferences determine WHO SHOULD do the work.
"""

import pytest
import httpx

from switchyard.agy_worker import AgyWorker
from switchyard.graph import Switchyard
from switchyard.models import Cost, Speed, Task
from switchyard.openai_worker import OpenAICompatibleWorker
from switchyard.registry import WorkerRegistry
from switchyard.router import NoEligibleWorkerError, Router


@pytest.fixture
def dual_worker_registry():
    """Registry containing real worker definitions for Colibrì and AGY."""
    registry = WorkerRegistry()

    colibri = OpenAICompatibleWorker(
        name="qwen-colibri",
        capabilities={"reasoning", "analysis", "summarization", "devops"},
        speed=Speed.MEDIUM,
        cost=Cost.FREE,
        endpoint="http://macops.local:8000/v1",
        model="qwen3.8-flash-next-colibri",
        api_key="test-colibri-key",
    )

    agy = AgyWorker(
        name="agy",
        capabilities={"coding", "debugging", "repo-editing", "reasoning"},
        speed=Speed.FAST,
        cost=Cost.MEDIUM,
        bin_path="agy",
        effort="low",
    )

    registry.register(colibri)
    registry.register(agy)
    return registry


def test_capabilities_determine_who_can_do_the_work(dual_worker_registry):
    """Capabilities filter eligible candidates before preferences are considered."""
    router = Router(dual_worker_registry)

    # Coding: only AGY has it; Colibrì cannot do it
    coding_task = Task(prompt="Refactor parser", required_capabilities={"coding"})
    decision = router.route(coding_task)
    assert decision.selected_worker_name == "agy"
    assert decision.eligible_workers == ["agy"]

    # DevOps: only Colibrì has it; AGY cannot do it
    devops_task = Task(prompt="Audit Kube config", required_capabilities={"devops"})
    decision = router.route(devops_task)
    assert decision.selected_worker_name == "qwen-colibri"
    assert decision.eligible_workers == ["qwen-colibri"]

    # Debugging + Repo-editing: only AGY has both
    multi_task = Task(prompt="Fix bug across repo", required_capabilities={"debugging", "repo-editing"})
    decision = router.route(multi_task)
    assert decision.selected_worker_name == "agy"
    assert decision.eligible_workers == ["agy"]

    # Unsupported capability: neither can do it
    impossible_task = Task(prompt="Quantum simulation", required_capabilities={"quantum-computing"})
    with pytest.raises(NoEligibleWorkerError):
        router.route(impossible_task)


def test_preferences_determine_who_should_do_the_work(dual_worker_registry):
    """When both workers have capability (reasoning), preferences decide the winner."""
    router = Router(dual_worker_registry)

    # Both Colibrì and AGY can do "reasoning"
    # Cost preference: Colibrì is FREE, AGY is MEDIUM -> Colibrì wins
    cost_task = Task(
        prompt="Analyze architectural trade-off",
        required_capabilities={"reasoning"},
        prefer_cost=True,
    )
    decision = router.route(cost_task)
    assert decision.selected_worker_name == "qwen-colibri"
    assert set(decision.eligible_workers) == {"qwen-colibri", "agy"}
    assert decision.scores["qwen-colibri"] > decision.scores["agy"]

    # Speed preference: AGY is FAST, Colibrì is MEDIUM -> AGY wins
    speed_task = Task(
        prompt="Time-sensitive decision analysis",
        required_capabilities={"reasoning"},
        prefer_speed=True,
    )
    decision = router.route(speed_task)
    assert decision.selected_worker_name == "agy"
    assert set(decision.eligible_workers) == {"agy", "qwen-colibri"}
    assert decision.scores["agy"] > decision.scores["qwen-colibri"]


def test_explainability_exposes_tradeoff(dual_worker_registry):
    """Explanation clearly demonstrates why one worker won over the other."""
    router = Router(dual_worker_registry)

    task = Task(
        prompt="Synthesize findings",
        required_capabilities={"reasoning"},
        prefer_cost=True,
    )
    decision = router.route(task)

    assert decision.selected_worker_name == "qwen-colibri"
    assert "preference: cost" in decision.reason
    assert "selected cheapest eligible worker" in decision.reason
    assert "agy" in decision.reason


@pytest.mark.asyncio
async def test_end_to_end_langgraph_dispatch(dual_worker_registry, monkeypatch):
    """Verify that routing and dispatch execute end-to-end for both workers."""
    # Mock HTTP transport for Colibrì
    async def mock_http_handler(request):
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "Colibri reasoning"}}]},
        )

    transport = httpx.MockTransport(mock_http_handler)
    async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "switchyard.openai_worker.httpx.AsyncClient",
        lambda **kwargs: async_client(transport=transport, **kwargs),
    )

    # Mock Subprocess for AGY
    class DummyProc:
        def __init__(self):
            self.returncode = 0
        async def communicate(self):
            return b'{"status": "SUCCESS", "response": "AGY code result"}', b''

    async def mock_subproc(*cmd, **kwargs):
        return DummyProc()

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_subproc)

    app = Switchyard(registry=dual_worker_registry)

    # Run coding task -> routed to AGY
    coding_res = await app.run(Task(prompt="Write sort", required_capabilities={"coding"}))
    assert coding_res["selected_worker"] == "agy"
    assert coding_res["result"].output == "AGY code result"

    # Run devops task -> routed to Colibrì
    devops_res = await app.run(Task(prompt="Check ingress", required_capabilities={"devops"}))
    assert devops_res["selected_worker"] == "qwen-colibri"
    assert devops_res["result"].output == "Colibri reasoning"
