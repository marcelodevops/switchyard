# Switchyard

## Sacred Core

Switchyard exists to do exactly this:

> Receive a task, identify which available worker is appropriate based on required capability, speed, and cost, dispatch the task to that worker, and return the result.

A **worker** is an existing AI agent such as Codex, AGY, Copilot, or a local agent backed by Colibrì/Qwen.

Workers may use completely different providers and execution mechanisms. Switchyard hides those differences behind a tiny common worker interface.

The user currently performs this routing manually. Switchyard exists to remove that manual switching and, eventually, manual passing of results between agents.

## Architectural Boundary

Switchyard is NOT:
- ALFRED
- an AI operating system
- a replacement for existing agents
- a new general-purpose agent
- a RAG system
- a memory platform
- a dashboard
- an observability platform
- a plugin ecosystem
- a model-hosting system
- a vector database
- a workflow product

## Core Concepts

- **Task**: Specification of work to perform, required capabilities, and preferences (cost/speed).
- **Worker**: Abstraction over an external AI agent with declared capabilities, speed, cost, and availability.
- **WorkerRegistry**: In-memory registry of available workers.
- **Router**: Deterministic, explainable scoring engine selecting the appropriate worker.
- **Result**: Output returned from worker execution.
- **Graph**: Minimal LangGraph coordinating execution (`route -> dispatch`).

## Configuration

Pass `--config PATH` before the command to load workers from a TOML file. HTTP workers
use an OpenAI-compatible chat completion endpoint; the endpoint should be its API base
URL, such as `http://macops.local:8000/v1`.

```toml
[[workers]]
name = "qwen-local"
kind = "http"
capabilities = ["reasoning", "analysis", "summarization", "devops"]
speed = "medium"
cost = "free"
endpoint = "http://macops.local:8000/v1"
model = "qwen3.8-flash-next-colibri"
api_key_env = "COLI_API_KEY"
timeout = 30
```

Keep API keys out of TOML files. Set the referenced environment variable before invoking
Switchyard; `.env` files are ignored by Git but are not loaded automatically.

Run the worker or list configured workers with:

```bash
switchyard --config workers.toml workers
switchyard --config workers.toml run -c reasoning "Summarize this report"
```

Without `--config`, the CLI continues to use its built-in mock-worker registry.
Failed HTTP requests return an unsuccessful worker result and cause `run` to exit non-zero.
