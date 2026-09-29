"""Tests for WorkerRegistry."""

import pytest
from switchyard.models import Cost, Speed
from switchyard.registry import WorkerRegistry
from switchyard.worker import MockWorker


def test_registry_register_and_get():
    registry = WorkerRegistry()
    worker = MockWorker(name="w1", capabilities={"coding"})
    registry.register(worker)

    assert len(registry) == 1
    assert "w1" in registry
    assert registry.get("w1") is worker
    assert registry.get("nonexistent") is None


def test_registry_unregister():
    registry = WorkerRegistry()
    worker = MockWorker(name="w1", capabilities={"coding"})
    registry.register(worker)

    removed = registry.unregister("w1")
    assert removed is worker
    assert len(registry) == 0
    assert "w1" not in registry


def test_registry_get_available_workers():
    registry = WorkerRegistry()
    w1 = MockWorker(name="w1", capabilities={"coding"}, available=True)
    w2 = MockWorker(name="w2", capabilities={"coding"}, available=False)
    registry.register(w1)
    registry.register(w2)

    available = registry.get_available_workers()
    assert len(available) == 1
    assert available[0].name == "w1"
