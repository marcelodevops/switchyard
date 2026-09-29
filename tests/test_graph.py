"""Tests for LangGraph execution flow in Switchyard."""

import pytest
from switchyard.graph import Switchyard, create_switchyard_graph
from switchyard.models import Cost, Speed, Task
from switchyard.registry import WorkerRegistry
from switchyard.router import NoEligibleWorkerError, Router
from switchyard.worker import MockCheapWorker, MockCoder, MockReasoner


@pytest.mark.asyncio
async def test_switchyard_graph_execution():
    registry = WorkerRegistry()
    coder = MockCoder(name="mock-coder")
    reasoner = MockReasoner(name="mock-reasoner")
    cheap = MockCheapWorker(name="mock-cheap")
    registry.register(coder)
    registry.register(reasoner)
    registry.register(cheap)

    app = Switchyard(registry=registry)

    task = Task(
        prompt="Find the off-by-one bug in binary search",
        required_capabilities={"coding", "debugging"},
    )

    final_state = await app.run(task)

    assert final_state["selected_worker"] == "mock-coder"
    assert "mock-coder" in final_state["routing_reason"]
    assert final_state["result"] is not None
    assert final_state["result"].worker_name == "mock-coder"
    assert final_state["result"].success is True
    assert "Find the off-by-one bug" in final_state["result"].output


@pytest.mark.asyncio
async def test_switchyard_graph_cheap_preference():
    registry = WorkerRegistry()
    coder = MockCoder(name="mock-coder")
    cheap = MockCheapWorker(name="mock-cheap")
    registry.register(coder)
    registry.register(cheap)

    app = Switchyard(registry=registry)

    task = Task(
        prompt="Quick edit in README",
        required_capabilities={"coding"},
        prefer_cost=True,
    )

    final_state = await app.run(task)

    assert final_state["selected_worker"] == "mock-cheap"
    assert final_state["result"].worker_name == "mock-cheap"


@pytest.mark.asyncio
async def test_switchyard_graph_no_eligible_worker():
    registry = WorkerRegistry()
    coder = MockCoder(name="mock-coder")
    registry.register(coder)

    app = Switchyard(registry=registry)

    task = Task(
        prompt="Write a poem",
        required_capabilities={"creative-writing"},
    )

    with pytest.raises(NoEligibleWorkerError):
        await app.run(task)
