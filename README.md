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

Pass `--config PATH` before the command to load workers from a TOML file. Switchyard supports three real worker kinds:
- **`openai-compatible`**: Connects via HTTP chat completions (e.g. local Colibrì/Qwen).
- **`agy`**: Dispatches via the local Antigravity (`agy`) CLI non-interactive print mode.
- **`qoder`**: Dispatches via the local Qoder (`qoder`) CLI non-interactive print mode.

```toml
[[workers]]
name = "qwen-colibri"
kind = "openai-compatible"
capabilities = ["reasoning", "analysis", "summarization", "devops"]
speed = "medium"
cost = "free"
endpoint = "http://macops.local:8000/v1"
model = "qwen3.8-flash-next-colibri"
api_key_env = "COLI_API_KEY"
timeout = 90

[[workers]]
name = "agy"
kind = "agy"
capabilities = ["coding", "debugging", "repo-editing", "reasoning"]
speed = "fast"
cost = "medium"
bin_path = "agy"
effort = "low"
timeout = 60

[[workers]]
name = "qoder"
kind = "qoder"
capabilities = ["coding", "debugging", "refactoring", "reasoning"]
speed = "medium"
cost = "low"
bin_path = "qoder"
model = "Qwen3.8-Flash"
timeout = 60
```

Keep API keys out of TOML files. Set the referenced environment variable before invoking
Switchyard; `.env` files are ignored by Git but are not loaded automatically.

### Running & Choosing Workers

Capabilities determine **who can** do the work; preferences determine **who should** do the work:

```bash
# Capabilities determine who CAN do the work
switchyard --config workers.toml route -c devops "Audit Helm ingress config"      # -> routes to qwen-colibri
switchyard --config workers.toml route -c repo-editing "Refactor module tree"     # -> routes to agy
switchyard --config workers.toml route -c refactoring "Extract helper function"   # -> routes to qoder

# Preferences determine who SHOULD do the work when multiple workers are capable
# Coding: both AGY and Qoder can do it
switchyard --config workers.toml route -c coding --prefer-cost "Implement binary search"  # -> routes to qoder (low cost)
switchyard --config workers.toml route -c coding --prefer-speed "Implement binary search" # -> routes to agy (fast speed)

# Reasoning: all three are capable
switchyard --config workers.toml route -c reasoning --prefer-cost "Compare architectures"  # -> routes to qwen-colibri (free)
switchyard --config workers.toml route -c reasoning --prefer-speed "Compare architectures" # -> routes to agy (fast)
switchyard --config workers.toml route -c reasoning "Compare architectures"                # -> routes to agy (alphabetical)

# Dispatch execution through LangGraph
switchyard --config workers.toml run -c coding --prefer-cost "Write a Python palindrome check function"
switchyard --config workers.toml run -c coding --prefer-speed "Write a Python lambda to square x"
switchyard --config workers.toml run -c reasoning --prefer-cost "What is the capital of France?"
```

Without `--config`, the CLI continues to use its built-in mock-worker registry.
Failed worker executions return an unsuccessful result and cause `run` to exit non-zero.
