"""Tests for Router covering deterministic selection, preferences, and explainability."""

import pytest
from switchyard.models import Cost, Speed, Task
from switchyard.registry import WorkerRegistry
from switchyard.router import NoEligibleWorkerError, Router
from switchyard.worker import MockWorker


def test_capability_filtering():
    """Task requiring 'coding' routes to coder, not reasoner."""
    registry = WorkerRegistry()
    coder = MockWorker(name="coder", capabilities={"coding"})
    reasoner = MockWorker(name="reasoner", capabilities={"reasoning"})
    registry.register(coder)
    registry.register(reasoner)

    router = Router(registry)
    task = Task(prompt="Write a function", required_capabilities={"coding"})
    decision = router.route(task)

    assert decision.selected_worker_name == "coder"
    assert decision.eligible_workers == ["coder"]


def test_multiple_capabilities_requires_all():
    """Task requiring 'coding' and 'repo-editing' rejects worker with only 'coding'."""
    registry = WorkerRegistry()
    partial = MockWorker(name="partial", capabilities={"coding"})
    full = MockWorker(name="full", capabilities={"coding", "repo-editing"})
    registry.register(partial)
    registry.register(full)

    router = Router(registry)
    task = Task(
        prompt="Refactor repository",
        required_capabilities={"coding", "repo-editing"}
    )
    decision = router.route(task)

    assert decision.selected_worker_name == "full"
    assert "partial" not in decision.eligible_workers


def test_cost_preference():
    """When cost is preferred, cheaper worker wins between equally capable workers."""
    registry = WorkerRegistry()
    expensive = MockWorker(
        name="expensive",
        capabilities={"coding"},
        cost=Cost.HIGH,
        speed=Speed.MEDIUM,
    )
    cheap = MockWorker(
        name="cheap",
        capabilities={"coding"},
        cost=Cost.FREE,
        speed=Speed.MEDIUM,
    )
    registry.register(expensive)
    registry.register(cheap)

    router = Router(registry)
    task = Task(
        prompt="Fix typo",
        required_capabilities={"coding"},
        prefer_cost=True,
    )
    decision = router.route(task)

    assert decision.selected_worker_name == "cheap"
    assert decision.scores["cheap"] > decision.scores["expensive"]


def test_speed_preference():
    """When speed is preferred, faster worker wins between equally capable workers."""
    registry = WorkerRegistry()
    slow = MockWorker(
        name="slow",
        capabilities={"coding"},
        speed=Speed.SLOW,
        cost=Cost.LOW,
    )
    fast = MockWorker(
        name="fast",
        capabilities={"coding"},
        speed=Speed.FAST,
        cost=Cost.LOW,
    )
    registry.register(slow)
    registry.register(fast)

    router = Router(registry)
    task = Task(
        prompt="Urgent hotfix",
        required_capabilities={"coding"},
        prefer_speed=True,
    )
    decision = router.route(task)

    assert decision.selected_worker_name == "fast"
    assert decision.scores["fast"] > decision.scores["slow"]


def test_unavailable_worker_not_selected():
    """An unavailable worker must never be selected even if it is the best match."""
    registry = WorkerRegistry()
    best_but_offline = MockWorker(
        name="offline-pro",
        capabilities={"coding"},
        speed=Speed.FAST,
        cost=Cost.FREE,
        available=False,
    )
    backup = MockWorker(
        name="backup",
        capabilities={"coding"},
        speed=Speed.SLOW,
        cost=Cost.HIGH,
        available=True,
    )
    registry.register(best_but_offline)
    registry.register(backup)

    router = Router(registry)
    task = Task(prompt="Task", required_capabilities={"coding"})
    decision = router.route(task)

    assert decision.selected_worker_name == "backup"
    assert "offline-pro" not in decision.eligible_workers


def test_no_eligible_worker_raises():
    """When no available worker satisfies requirements, raise NoEligibleWorkerError."""
    registry = WorkerRegistry()
    coder = MockWorker(name="coder", capabilities={"coding"})
    registry.register(coder)

    router = Router(registry)
    task = Task(prompt="Design query", required_capabilities={"quantum-computing"})

    with pytest.raises(NoEligibleWorkerError) as exc_info:
        router.route(task)
    assert "quantum-computing" in str(exc_info.value)


def test_explainability():
    """Routing decision provides human-understandable explanation and scores."""
    registry = WorkerRegistry()
    w1 = MockWorker(
        name="codex",
        capabilities={"coding", "repo-editing"},
        speed=Speed.FAST,
        cost=Cost.MEDIUM,
    )
    w2 = MockWorker(
        name="copilot",
        capabilities={"coding"},
        speed=Speed.FAST,
        cost=Cost.LOW,
    )
    registry.register(w1)
    registry.register(w2)

    router = Router(registry)
    task = Task(
        prompt="Refactor code",
        required_capabilities={"coding", "repo-editing"},
    )
    decision = router.route(task)

    assert decision.selected_worker_name == "codex"
    assert "required capabilities matched: coding, repo-editing" in decision.reason
    assert "speed: fast" in decision.reason
    assert "cost: medium" in decision.reason
    assert decision.eligible_workers == ["codex"]
