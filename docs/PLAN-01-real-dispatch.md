# Switchyard — Plan 01: Real Dispatch (HTTP worker + config-driven registry)

**Scope chosen:** dispatch only — make Switchyard route to a *real* worker and let workers
be declared in config instead of hardcoded. First real target: **local Qwen/Colibrì over an
OpenAI-compatible HTTP endpoint.**

**Explicitly deferred** (see *Out of scope*): router scoring model (`prefer_speed` +
`prefer_cost` interplay), typing/hygiene cleanup.

---

## Why this is P0

The README's sacred core is "remove the manual switching between agents." Every worker is
currently a `MockWorker` and the CLI hardcodes the pool in
`cli.build_default_registry()` (`src/switchyard/cli.py:15`). Until at least one real worker
can be dispatched, and until workers can be declared without editing code, the tool cannot
do its one job. Everything else in the codebase (router, registry, graph) is already sound
and just needs a real thing plugged into it.

The design deliberately keeps the `Worker` ABC (`worker.py:9`, async `execute(task) -> Result`)
as the seam: an HTTP adapter is one subclass, and config loading is one factory. No changes to
`router.py`, `registry.py`, or `graph.py` are required for this plan.

---

## Stage 0 — Confirm the endpoint contract (blocking, ~small)

Before writing any HTTP code, verify the real interface so the adapter is built against
observed behavior, not a guessed schema.

- Record the exact base URL + path for the local Qwen/Colibrì endpoint (e.g. is it
  `<host>/v1/chat/completions`, or a bare `/chat/completions`, or a Colibrì-specific route?).
- Confirm whether it is OpenAI-compatible (request body `{model, messages, temperature, ...}`
  and response `choices[0].message.content`), or whether the response shape differs.
- Confirm auth: local endpoints usually need no key; note the header/env var if any.
- Confirm a reachable model name (e.g. the loaded Qwen tag).

**Acceptance:** a curl (or one-shot request) to the endpoint returns model text, and the
request/response shape is documented here. If no endpoint is reachable, note it and build
Stage 1 against a fake server (respx / monkeypatched transport) plus a config `kind: mock`
path so tests never need a live model.

---

## Stage 1 — `HttpWorker` adapter (the real worker)

New file `src/switchyard/http_worker.py`.

- `class HttpWorker(Worker)` reusing the base constructor fields (`name`, `capabilities`,
  `speed`, `cost`, `available`) and adding: `endpoint` (base URL), `model`, `timeout`,
  optional `api_key` (resolved from env, see Stage 3), optional request extras (temperature).
- Implement `async execute(self, task: Task) -> Result`:
  - Build an OpenAI-compatible chat payload from `task.prompt`.
  - POST via **`httpx.AsyncClient`** (new dependency — async, clean, and already common
    alongside the langgraph/langchain stack). *Decision to confirm:* httpx vs stdlib
    `urllib` in a thread; recommend httpx for async correctness.
  - Parse text into `Result(output=..., worker_name=self.name, success=True, metadata={...})`.
- **Error policy:** catch network/HTTP/parse errors and return `Result(success=False,
  output=<message>, metadata={"error": ...})` rather than raising — so `dispatch_node`
  (`graph.py:31`) still returns a coherent state and the CLI reports failure cleanly. Routing
  errors (`NoEligibleWorkerError`) continue to raise from `route_node` as today.
- Keep `available` a static flag for now; an optional `async healthcheck()` that pings the
  endpoint is a nice-to-have, not in this stage's acceptance.

**Acceptance:** unit test with a mocked transport asserts (a) correct request built,
(b) `Result.success=True` with parsed output on 200, (c) `Result.success=False` on a 500/timeout.

---

## Stage 2 — Config-driven registry

New file `src/switchyard/config.py`.

- **Format: TOML** — readable like `pyproject.toml`, and **`tomllib` is stdlib (read-only is
  enough here)**, so no new dependency. *Decision to confirm:* TOML vs YAML(needs pyyaml)/JSON.
- Worker entry schema:
  ```toml
  [[workers]]
  name = "qwen-local"
  kind = "http"                 # "http" | "mock"
  capabilities = ["reasoning", "analysis", "summarization"]
  speed = "medium"              # maps to Speed enum value
  cost = "free"                 # maps to Cost enum value
  available = true
  endpoint = "http://localhost:11434/v1"
  model = "qwen2.5"
  timeout = 30
  api_key_env = "QWEN_API_KEY"  # optional; read at load, never a literal secret
  ```
- `build_registry_from_config(path: Path) -> WorkerRegistry`:
  - Validate each entry (name/capabilities/speed/cost/endpoint), coerce `speed`/`cost` strings
    to the `Speed`/`Cost` enums, raise a clear error naming the bad entry otherwise.
  - Dispatch on `kind` through a small factory map `{ "http": HttpWorker, "mock": MockWorker }`.
  - Call `registry.register(...)` for each (reuses existing API, `registry.py:13`).
- Secrets: only an **env var name** is stored in config; the loader reads the value from the
  environment. Add guidance to keep secrets out of the file (and note `.gitignore`).

**Acceptance:** loader test builds a registry from a fixture TOML with one `http` and one
`mock` worker, asserts count, types, capability sets, enum mapping, and that a malformed entry
raises with the offending worker name.

---

## Stage 3 — CLI wiring (backward compatible)

Edit `src/switchyard/cli.py`.

- Add a global `--config PATH` flag on the top-level parser.
- Registry resolution order:
  1. `--config` given → `build_registry_from_config(path)`
  2. no `--config` → fall back to existing `build_default_registry()` (keeps current tests green)
- Thread the resolved registry through `cmd_workers` / `cmd_route` / `cmd_run` (already take
  `registry`; just stop hardcoding it inside `main`).

**Acceptance:** `switchyard --config tests/fixtures/workers.toml workers` lists the config's
workers; `... run` dispatches. With no `--config`, existing CLI tests still pass.

---

## Stage 4 — Verify end-to-end

- Run the full suite: `pytest -q`.
- Smoke test the real path: `switchyard --config <your config> run -c reasoning "Summarize X"`
  against the reachable endpoint (Stage 0), and confirm a genuine model response flows back
  through `route -> dispatch` into the CLI output.
- Update `README.md` with a short "Configuration" section (config file + `--config` flag) and a
  "Real workers" note so the boundary doc stays truthful about current capabilities.

**Acceptance:** tests green; one documented example run against the live local endpoint.

---

## Suggested build order & rationale

1. Stage 0 first — it de-risks everything and dictates the adapter's request/response code.
2. Stage 1 (`HttpWorker`) next — the single highest-value artifact; unblocks the "real worker" gap on its own even before config.
3. Stage 2 (config) then Stage 3 (CLI) — together they remove the hardcoded pool; Stage 3 depends on Stage 2.
4. Stage 4 last — verification + docs.

Stages 1 and 2 are independent enough to build in either order, but adapter-before-config keeps
each step testable in isolation.

---

## New dependency / decisions to lock

- **`httpx`** (async HTTP client) — needed for Stage 1. Confirm acceptable.
- **TOML config** read via stdlib `tomllib` — no dep; confirm over YAML/JSON.
- **Error policy** — failed `Result` (recommended) vs raising.
- **Secret handling** — env-var reference in config, never a literal key.

---

## Out of scope (next plans)

- Router scoring model: define what `prefer_speed` **and** `prefer_cost` together mean, and
  normalize the `speed.rank` (1–3) vs `cost_savings` (0–3) asymmetry (`router.py:40-48`).
- Hygiene: standardize on builtin generics (`set[str]`, `dict`) and drop `typing.Optional/Set/…`
  now that `requires-python >= 3.12`.
- Additional worker kinds (e.g. generic command/subprocess, Codex CLI, Copilot).
- Optional endpoint `healthcheck()` feeding `is_available()`.
