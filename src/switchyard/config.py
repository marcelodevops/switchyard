"""TOML configuration loading for worker registries."""

import os
import tomllib
from pathlib import Path
from typing import Any

from switchyard.agy_worker import AgyWorker
from switchyard.models import Cost, Speed
from switchyard.openai_worker import OpenAICompatibleWorker
from switchyard.qoder_worker import QoderWorker
from switchyard.registry import WorkerRegistry
from switchyard.worker import MockWorker


def build_registry_from_config(path: Path) -> WorkerRegistry:
    """Load workers from a TOML file and return a populated registry."""
    with path.open("rb") as config_file:
        config = tomllib.load(config_file)

    workers = config.get("workers")
    if not isinstance(workers, list):
        raise ValueError("configuration must contain a [[workers]] list")

    registry = WorkerRegistry()
    for index, entry in enumerate(workers, start=1):
        name = entry.get("name", f"entry #{index}") if isinstance(entry, dict) else f"entry #{index}"
        try:
            worker = _build_worker(entry)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid worker '{name}': {exc}") from exc
        registry.register(worker)
    return registry


def _build_worker(entry: Any) -> OpenAICompatibleWorker | AgyWorker | QoderWorker | MockWorker:
    if not isinstance(entry, dict):
        raise ValueError("entry must be a table")

    name = entry["name"]
    kind = entry.get("kind", "openai-compatible")
    capabilities = entry["capabilities"]
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string")
    if not isinstance(capabilities, list) or not all(
        isinstance(capability, str) and capability for capability in capabilities
    ):
        raise ValueError("capabilities must be a list of non-empty strings")

    common = {
        "name": name,
        "capabilities": set(capabilities),
        "speed": Speed(entry.get("speed", Speed.MEDIUM.value)),
        "cost": Cost(entry.get("cost", Cost.MEDIUM.value)),
        "available": entry.get("available", True),
    }

    if kind == "mock":
        return MockWorker(**common, response_template=entry.get("response_template"))

    if kind == "agy":
        bin_path = entry.get("bin_path", "agy")
        if not isinstance(bin_path, str) or not bin_path.strip():
            raise ValueError("bin_path must be a non-empty string")
        effort = entry.get("effort")
        if effort is not None and (not isinstance(effort, str) or not effort.strip()):
            raise ValueError("effort must be a non-empty string")
        model = entry.get("model")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise ValueError("model must be a non-empty string")
        timeout = entry.get("timeout", 60)
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
            raise ValueError("timeout must be a positive number")
        return AgyWorker(
            **common,
            bin_path=bin_path,
            effort=effort,
            model=model,
            timeout=timeout,
        )

    if kind == "qoder":
        bin_path = entry.get("bin_path", "qoder")
        if not isinstance(bin_path, str) or not bin_path.strip():
            raise ValueError("bin_path must be a non-empty string")
        model = entry.get("model", "Qwen3.8-Flash")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise ValueError("model must be a non-empty string")
        timeout = entry.get("timeout", 60)
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
            raise ValueError("timeout must be a positive number")
        return QoderWorker(
            **common,
            bin_path=bin_path,
            model=model,
            timeout=timeout,
        )

    if kind != "openai-compatible":
        raise ValueError(
            f"unsupported kind '{kind}' (expected 'openai-compatible', 'agy', 'qoder', or 'mock')"
        )

    endpoint = entry["endpoint"]
    model = entry["model"]
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ValueError("endpoint must be a non-empty string")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must be a non-empty string")

    api_key_env = entry.get("api_key_env")
    api_key = None
    if api_key_env is not None:
        if not isinstance(api_key_env, str) or not api_key_env:
            raise ValueError("api_key_env must be a non-empty environment variable name")
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise ValueError(f"environment variable '{api_key_env}' is not set")

    timeout = entry.get("timeout", 30)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("timeout must be a positive number")

    return OpenAICompatibleWorker(
        **common,
        endpoint=endpoint,
        model=model,
        timeout=timeout,
        api_key=api_key,
    )
