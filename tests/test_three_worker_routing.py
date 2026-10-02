"""Tests demonstrating generic routing across three real worker configurations.

Proves:
1. Capabilities determine WHO CAN do the work.
2. Preferences determine WHO SHOULD do the work.
3. The router treats all workers generically without identity assumptions.
"""

import httpx
import pytest

from switchyard.agy_worker import AgyWorker
from switchyard.graph import Switchyard
from switchyard.models import Cost, Speed, Task
from switchyard.openai_worker import OpenAICompatibleWorker
from switchyard.qoder_worker import QoderWorker
from switchyard.registry import WorkerRegistry
from switchyard.router import NoEligibleWorkerError, Router


@pytest.fixture
def three_worker_registry():
    """Registry with three real worker configurations."""
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

    qoder = QoderWorker(
        name="qoder",
        capabilities={"coding", "debugging", "refactoring", "reasoning"},
        speed=Speed.MEDIUM,
        cost=Cost.LOW,
        bin_path="qoder",
        model="Qwen3.8-Flash",
    )

    registry.register(colibri)
    registry.register(agy)
    registry.register(qoder)
    return registry


def test_capability_filtering_across_three_workers(three_worker_registry):
    """Router filters eligible candidates based strictly on required capabilities."""
    router = Router(three_worker_registry)

    # devops: only Colibrì is capable
    devops_res = router.route(Task(prompt="Setup ingress", required_capabilities={"devops"}))
    assert devops_res.selected_worker_name == "qwen-colibri"
    assert devops_res.eligible_workers == ["qwen-colibri"]

    # repo-editing: only AGY is capable
    repo_res = router.route(Task(prompt="Multi-file repo patch", required_capabilities={"repo-editing"}))
    assert repo_res.selected_worker_name == "agy"
    assert repo_res.eligible_workers == ["agy"]

    # refactoring: only Qoder is capable
    refactor_res = router.route(Task(prompt="Extract method", required_capabilities={"refactoring"}))
    assert refactor_res.selected_worker_name == "qoder"
    assert refactor_res.eligible_workers == ["qoder"]

    # coding: both AGY and Qoder are capable, Colibrì is not
    coding_res = router.route(Task(prompt="Write function", required_capabilities={"coding"}))
    assert set(coding_res.eligible_workers) == {"agy", "qoder"}
    assert "qwen-colibri" not in coding_res.eligible_workers


def test_preference_arbitration_when_all_three_capable(three_worker_registry):
    """When all 3 workers share a capability (reasoning), preferences determine selection."""
    router = Router(three_worker_registry)

    # All three possess "reasoning"
    # Cost preference: Colibrì (FREE) > Qoder (LOW) > AGY (MEDIUM) -> Colibrì wins
    cost_res = router.route(Task(prompt="Explain concept", required_capabilities={"reasoning"}, prefer_cost=True))
    assert cost_res.selected_worker_name == "qwen-colibri"
    assert set(cost_res.eligible_workers) == {"qwen-colibri", "agy", "qoder"}
    assert cost_res.scores["qwen-colibri"] > cost_res.scores["qoder"] > cost_res.scores["agy"]

    # Speed preference: AGY (FAST) > Qoder (MEDIUM) == Colibrì (MEDIUM) -> AGY wins
    speed_res = router.route(Task(prompt="Explain concept fast", required_capabilities={"reasoning"}, prefer_speed=True))
    assert speed_res.selected_worker_name == "agy"
    assert set(speed_res.eligible_workers) == {"agy", "qoder", "qwen-colibri"}
    assert speed_res.scores["agy"] > speed_res.scores["qoder"]

    # Neutral (no preference): All score 0, alphabetical tie-break: agy < qoder < qwen-colibri
    neutral_res = router.route(Task(prompt="Explain concept", required_capabilities={"reasoning"}))
    assert neutral_res.selected_worker_name == "agy"
    assert set(neutral_res.eligible_workers) == {"agy", "qoder", "qwen-colibri"}


def test_two_candidate_coding_preference(three_worker_registry):
    """Between two capable coding workers (AGY and Qoder), preferences decide correctly."""
    router = Router(three_worker_registry)

    # Coding with prefer_cost: Qoder (LOW cost) beats AGY (MEDIUM cost)
    cost_coding = router.route(Task(prompt="Write helper", required_capabilities={"coding"}, prefer_cost=True))
    assert cost_coding.selected_worker_name == "qoder"
    assert cost_coding.scores["qoder"] > cost_coding.scores["agy"]

    # Coding with prefer_speed: AGY (FAST) beats Qoder (MEDIUM)
    speed_coding = router.route(Task(prompt="Write helper fast", required_capabilities={"coding"}, prefer_speed=True))
    assert speed_coding.selected_worker_name == "agy"
    assert speed_coding.scores["agy"] > speed_coding.scores["qoder"]


def test_multi_capability_strict_match(three_worker_registry):
    """Worker must satisfy every requested capability."""
    router = Router(three_worker_registry)

    # Qoder satisfies coding + debugging + refactoring
    task = Task(prompt="Refactor bug", required_capabilities={"coding", "debugging", "refactoring"})
    decision = router.route(task)
    assert decision.selected_worker_name == "qoder"
    assert decision.eligible_workers == ["qoder"]

    # Incompatible combination: devops + coding (no worker has both)
    impossible = Task(prompt="CI coding script", required_capabilities={"devops", "coding"})
    with pytest.raises(NoEligibleWorkerError):
        router.route(impossible)


@pytest.mark.asyncio
async def test_end_to_end_langgraph_with_three_workers(three_worker_registry, monkeypatch):
    """Verify that routing and dispatch execute end-to-end to all three workers."""
    # Mock Colibrì HTTP
    async def mock_http_handler(request):
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "Colibri devops answer"}}]},
        )
    transport = httpx.MockTransport(mock_http_handler)
    async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "switchyard.openai_worker.httpx.AsyncClient",
        lambda **kwargs: async_client(transport=transport, **kwargs),
    )

    # Mock Subprocess for AGY and Qoder
    class DummyProc:
        def __init__(self, stdout: bytes):
            self.stdout = stdout
            self.returncode = 0
        async def communicate(self):
            return self.stdout, b""

    async def mock_subproc(*cmd, **kwargs):
        if "agy" in cmd[0]:
            return DummyProc(b'{"status": "SUCCESS", "response": "AGY execution answer"}')
        elif "qoder" in cmd[0]:
            return DummyProc(b'{"type": "result", "subtype": "success", "result": "Qoder execution answer"}')
        return DummyProc(b"unknown")

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_subproc)

    app = Switchyard(registry=three_worker_registry)

    # 1. Dispatch to Qoder via coding + prefer_cost
    qoder_task = Task(prompt="Write unit test", required_capabilities={"coding"}, prefer_cost=True)
    qoder_state = await app.run(qoder_task)
    assert qoder_state["selected_worker"] == "qoder"
    assert qoder_state["result"].output == "Qoder execution answer"

    # 2. Dispatch to AGY via coding + prefer_speed
    agy_task = Task(prompt="Write unit test", required_capabilities={"coding"}, prefer_speed=True)
    agy_state = await app.run(agy_task)
    assert agy_state["selected_worker"] == "agy"
    assert agy_state["result"].output == "AGY execution answer"

    # 3. Dispatch to Colibrì via devops
    colibri_task = Task(prompt="Audit pod security", required_capabilities={"devops"})
    colibri_state = await app.run(colibri_task)
    assert colibri_state["selected_worker"] == "qwen-colibri"
    assert colibri_state["result"].output == "Colibri devops answer"
