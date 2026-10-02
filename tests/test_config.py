"""Tests for TOML worker registry configuration."""

import pytest

from switchyard.config import build_registry_from_config
from switchyard.openai_worker import OpenAICompatibleWorker
from switchyard.models import Cost, Speed
from switchyard.worker import MockWorker


def test_build_registry_from_toml(tmp_path, monkeypatch):
    monkeypatch.setenv("COLI_API_KEY", "test-key")
    config = tmp_path / "workers.toml"
    config.write_text(
        """
[[workers]]
name = "qwen-local"
kind = "openai-compatible"
capabilities = ["reasoning", "analysis"]
speed = "fast"
cost = "free"
endpoint = "http://colibri.local/v1"
model = "qwen3.8-flash-next-colibri"
api_key_env = "COLI_API_KEY"

[[workers]]
name = "mock-worker"
kind = "mock"
capabilities = ["coding"]
speed = "slow"
cost = "low"
"""
    )

    registry = build_registry_from_config(config)

    openai_worker = registry.get("qwen-local")
    assert isinstance(openai_worker, OpenAICompatibleWorker)
    assert openai_worker.capabilities == {"reasoning", "analysis"}
    assert openai_worker.speed is Speed.FAST
    assert openai_worker.cost is Cost.FREE
    assert openai_worker.api_key == "test-key"
    mock_worker = registry.get("mock-worker")
    assert isinstance(mock_worker, MockWorker)
    assert mock_worker.capabilities == {"coding"}
    assert len(registry) == 2


def test_invalid_worker_config_names_worker(tmp_path):
    config = tmp_path / "workers.toml"
    config.write_text(
        """
[[workers]]
name = "broken-qwen"
kind = "openai-compatible"
capabilities = ["reasoning"]
speed = "warp"
cost = "free"
endpoint = "http://colibri.local/v1"
model = "qwen3.8-flash-next-colibri"
"""
    )

    with pytest.raises(ValueError, match="broken-qwen"):
        build_registry_from_config(config)


def test_missing_api_key_environment_variable_is_reported(tmp_path, monkeypatch):
    monkeypatch.delenv("COLI_API_KEY", raising=False)
    config = tmp_path / "workers.toml"
    config.write_text(
        """
[[workers]]
name = "qwen-local"
capabilities = ["reasoning"]
endpoint = "http://colibri.local/v1"
model = "qwen3.8-flash-next-colibri"
api_key_env = "COLI_API_KEY"
"""
    )

    with pytest.raises(ValueError, match="COLI_API_KEY"):
        build_registry_from_config(config)


def test_build_registry_from_toml_with_agy_worker(tmp_path):
    config = tmp_path / "workers.toml"
    config.write_text(
        """
[[workers]]
name = "agy"
kind = "agy"
capabilities = ["coding", "debugging"]
speed = "fast"
cost = "medium"
bin_path = "agy"
effort = "low"
timeout = 45
"""
    )

    registry = build_registry_from_config(config)
    worker = registry.get("agy")
    assert worker is not None
    assert worker.name == "agy"
    assert worker.capabilities == {"coding", "debugging"}
    assert worker.speed is Speed.FAST
    assert worker.cost is Cost.MEDIUM
    assert worker.effort == "low"
    assert worker.timeout == 45


def test_build_registry_from_toml_with_qoder_worker(tmp_path):
    config = tmp_path / "workers.toml"
    config.write_text(
        """
[[workers]]
name = "qoder"
kind = "qoder"
capabilities = ["coding", "debugging", "refactoring"]
speed = "medium"
cost = "low"
bin_path = "qoder"
model = "Qwen3.8-Flash"
timeout = 50
"""
    )

    registry = build_registry_from_config(config)
    worker = registry.get("qoder")
    assert worker is not None
    assert worker.name == "qoder"
    assert worker.capabilities == {"coding", "debugging", "refactoring"}
    assert worker.speed is Speed.MEDIUM
    assert worker.cost is Cost.LOW
    assert worker.model == "Qwen3.8-Flash"
    assert worker.timeout == 50


def test_qoder_worker_model_is_optional_and_unset_when_omitted(tmp_path):
    config = tmp_path / "workers.toml"
    config.write_text(
        """
[[workers]]
name = "qoder"
kind = "qoder"
capabilities = ["coding"]
"""
    )

    registry = build_registry_from_config(config)
    worker = registry.get("qoder")
    assert worker is not None
    assert worker.model is None


