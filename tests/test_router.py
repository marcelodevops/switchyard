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


def test_cost_only_ignores_speed():
    registry = WorkerRegistry()
    registry.register(MockWorker("fast-expensive", {"coding"}, Speed.FAST, Cost.HIGH))
    registry.register(MockWorker("slow-free", {"coding"}, Speed.SLOW, Cost.FREE))

    decision = Router(registry).route(Task(prompt="Task", required_capabilities={"coding"}, prefer_cost=True))

    assert decision.selected_worker_name == "slow-free"
    assert decision.scores["slow-free"] > decision.scores["fast-expensive"]
    assert "preference: cost" in decision.reason
    assert "selected cheapest eligible worker" in decision.reason


def test_speed_only_ignores_cost():
    registry = WorkerRegistry()
    registry.register(MockWorker("slow-free", {"coding"}, Speed.SLOW, Cost.FREE))
    registry.register(MockWorker("fast-expensive", {"coding"}, Speed.FAST, Cost.HIGH))

    decision = Router(registry).route(Task(prompt="Task", required_capabilities={"coding"}, prefer_speed=True))

    assert decision.selected_worker_name == "fast-expensive"
    assert decision.scores["fast-expensive"] > decision.scores["slow-free"]
    assert "preference: speed" in decision.reason
    assert "selected fastest eligible worker" in decision.reason


@pytest.mark.parametrize(
    ("alpha_speed", "alpha_cost", "zebra_speed", "zebra_cost"),
    [
        (Speed.SLOW, Cost.HIGH, Speed.FAST, Cost.FREE),
        (Speed.SLOW, Cost.FREE, Speed.FAST, Cost.FREE),
        (Speed.MEDIUM, Cost.HIGH, Speed.MEDIUM, Cost.FREE),
    ],
)
def test_neutral_routing_ignores_speed_and_cost(alpha_speed, alpha_cost, zebra_speed, zebra_cost):
    registry = WorkerRegistry()
    registry.register(MockWorker("zebra", {"coding"}, zebra_speed, zebra_cost))
    registry.register(MockWorker("alpha", {"coding"}, alpha_speed, alpha_cost))

    decision = Router(registry).route(Task(prompt="Task", required_capabilities={"coding"}))

    assert decision.selected_worker_name == "alpha"
    assert decision.eligible_workers == ["alpha", "zebra"]
    assert decision.scores == {"alpha": 0, "zebra": 0}
    assert "preference: none" in decision.reason
    assert "deterministic tie-break: worker name" in decision.reason


@pytest.mark.parametrize(
    ("prefer_speed", "prefer_cost", "alpha_speed", "alpha_cost", "zebra_speed", "zebra_cost"),
    [
        (True, False, Speed.FAST, Cost.HIGH, Speed.FAST, Cost.FREE),
        (False, True, Speed.SLOW, Cost.FREE, Speed.FAST, Cost.FREE),
        (True, True, Speed.FAST, Cost.HIGH, Speed.SLOW, Cost.LOW),
    ],
)
def test_equal_preference_scores_use_name_tie_break(
    prefer_speed, prefer_cost, alpha_speed, alpha_cost, zebra_speed, zebra_cost
):
    registry = WorkerRegistry()
    registry.register(MockWorker("zebra", {"coding"}, zebra_speed, zebra_cost))
    registry.register(MockWorker("alpha", {"coding"}, alpha_speed, alpha_cost))

    decision = Router(registry).route(
        Task(prompt="Task", required_capabilities={"coding"}, prefer_speed=prefer_speed, prefer_cost=prefer_cost)
    )

    assert decision.scores["alpha"] == decision.scores["zebra"]
    assert decision.selected_worker_name == "alpha"
    assert decision.eligible_workers == ["alpha", "zebra"]


def test_both_preferences_use_equal_combined_ranking():
    registry = WorkerRegistry()
    registry.register(MockWorker("fast-high", {"coding"}, Speed.FAST, Cost.HIGH))
    registry.register(MockWorker("slow-free", {"coding"}, Speed.SLOW, Cost.FREE))
    registry.register(MockWorker("fast-low", {"coding"}, Speed.FAST, Cost.LOW))

    decision = Router(registry).route(
        Task(prompt="Task", required_capabilities={"coding"}, prefer_speed=True, prefer_cost=True)
    )

    assert decision.selected_worker_name == "fast-low"
    assert decision.scores == {"fast-high": 3, "slow-free": 4, "fast-low": 5}
    assert "preference: speed + cost" in decision.reason
    assert "selected using equal combined speed/cost ranking" in decision.reason
