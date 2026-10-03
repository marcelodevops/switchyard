# Switchyard

## Local process inspection

The transport-independent, read-only capability is callable directly from Python:

```python
from switchyard.processes import inspect_process, list_processes

matches = list_processes(command_contains="qwen38")
records = [process.model_dump() for process in matches]
record = inspect_process(pid=123).model_dump()
```

`ProcessInfo` contains `pid`, `ppid`, `state`, `cpu_percent`, `memory_percent`,
`rss_kib` (KiB), `elapsed` (the OS elapsed-time text), and `command` (command line).
Filtering is a case-sensitive literal substring, not a regex or shell expression.
An empty match list is valid; a missing PID raises `ProcessNotFoundError`.
Command failures, timeouts, and malformed output raise `ProcessInspectionError`;
invalid arguments raise `ValueError`.

V1 uses the local macOS `/bin/ps` with fixed arguments and a five-second timeout.
It does not contact `macops.local`; deploy the capability there to inspect that host.
Metrics are transient OS snapshots, not live monitoring; processes can exit or PIDs
can be reused after inspection. Command lines can contain sensitive arguments, so
treat returned records accordingly. No signals, process mutation, arbitrary command
execution, remote execution, agent reasoning, or ChatGPT transport are implemented.

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

Pass `--config PATH` before the command to load workers from a TOML file. Switchyard supports four real worker kinds:
- **`openai-compatible`**: Connects via HTTP chat completions (e.g. local Colibrì/Qwen).
- **`agy`**: Dispatches via the local Antigravity (`agy`) CLI non-interactive print mode.
- **`qoder`**: Dispatches via the local Qoder (`qoder`) CLI non-interactive print mode.
- **`copilot`**: Dispatches via GitHub Copilot CLI non-interactive prompt mode.

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

[[workers]]
name = "copilot"
kind = "copilot"
capabilities = ["coding", "debugging", "repo-editing", "quick-edits"]
speed = "medium"
cost = "medium"
bin_path = "copilot"
timeout = 120
```

Keep API keys out of TOML files. Set the referenced environment variable before invoking
Switchyard; `.env` files are ignored by Git but are not loaded automatically.
Copilot must be installed and signed in. Its non-interactive mode uses `--allow-all-tools`:
tools may execute without confirmation inside the CLI's permitted workspace. Switchyard
does not enable unrestricted path or URL access. `model` is optional for Copilot; when
omitted, its own default applies. The declared medium speed and cost are conservative
estimates for a CLI session with metered AI usage, not measured guarantees.

### Running & Choosing Workers

Capabilities determine **who can** do the work; preferences determine **who should** do the work:

```bash
# Capabilities determine who CAN do the work
switchyard --config workers.toml route -c devops "Audit Helm ingress config"      # -> routes to qwen-colibri
switchyard --config workers.toml route -c repo-editing "Refactor module tree"     # -> routes to agy
switchyard --config workers.toml route -c refactoring "Extract helper function"   # -> routes to qoder

# Preferences determine who SHOULD do the work when multiple workers are capable
# Coding: AGY, Qoder, and Copilot can do it
switchyard --config workers.toml route -c coding --prefer-cost "Implement binary search"  # -> routes to qoder (low cost)
switchyard --config workers.toml route -c coding --prefer-speed "Implement binary search" # -> routes to agy (fast speed)

# Reasoning: AGY, Qoder, and Colibrì are capable
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
