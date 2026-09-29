"""Command Line Interface for Switchyard."""

import argparse
import asyncio
import sys
from typing import List, Optional

from switchyard.graph import Switchyard
from switchyard.models import Cost, Speed, Task
from switchyard.registry import WorkerRegistry
from switchyard.router import NoEligibleWorkerError, Router
from switchyard.worker import MockWorker


def build_default_registry() -> WorkerRegistry:
    """Create a default registry populated with standard mock workers."""
    registry = WorkerRegistry()
    registry.register(
        MockWorker(
            name="codex",
            capabilities={"coding", "debugging", "repo-editing"},
            speed=Speed.FAST,
            cost=Cost.HIGH,
        )
    )
    registry.register(
        MockWorker(
            name="copilot",
            capabilities={"coding", "quick-edits"},
            speed=Speed.FAST,
            cost=Cost.MEDIUM,
        )
    )
    registry.register(
        MockWorker(
            name="agy",
            capabilities={"coding", "reasoning", "orchestration"},
            speed=Speed.MEDIUM,
            cost=Cost.MEDIUM,
        )
    )
    registry.register(
        MockWorker(
            name="qwen-local",
            capabilities={"reasoning", "analysis", "summarization", "devops"},
            speed=Speed.MEDIUM,
            cost=Cost.FREE,
        )
    )
    return registry


def cmd_workers(registry: WorkerRegistry, args: argparse.Namespace) -> int:
    """List registered workers and their attributes."""
    print("Registered Workers:")
    for worker in registry.list_workers():
        status = "available" if worker.is_available() else "unavailable"
        caps = ", ".join(sorted(worker.capabilities))
        print(f"  • {worker.name} ({status})")
        print(f"      capabilities : {caps}")
        print(f"      speed        : {worker.speed.value}")
        print(f"      cost         : {worker.cost.value}")
    return 0


def cmd_route(registry: WorkerRegistry, args: argparse.Namespace) -> int:
    """Route a task deterministically and print the decision explanation."""
    task = Task(
        prompt=args.prompt,
        required_capabilities=set(args.capability or []),
        prefer_speed=args.prefer_speed,
        prefer_cost=args.prefer_cost,
    )
    router = Router(registry)
    try:
        decision = router.route(task)
        print(decision.reason)
        return 0
    except NoEligibleWorkerError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


async def _run_task(registry: WorkerRegistry, task: Task) -> int:
    app = Switchyard(registry=registry)
    try:
        state = await app.run(task)
        print(state["routing_reason"])
        print("\n--- Worker Result ---")
        res = state["result"]
        if res:
            print(f"Worker : {res.worker_name}")
            print(f"Output : {res.output}")
        return 0
    except NoEligibleWorkerError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_run(registry: WorkerRegistry, args: argparse.Namespace) -> int:
    """Route and dispatch a task through the LangGraph pipeline."""
    task = Task(
        prompt=args.prompt,
        required_capabilities=set(args.capability or []),
        prefer_speed=args.prefer_speed,
        prefer_cost=args.prefer_cost,
    )
    return asyncio.run(_run_task(registry, task))


def create_parser() -> argparse.ArgumentParser:
    """Build the argument parser for switchyard CLI."""
    parser = argparse.ArgumentParser(
        prog="switchyard",
        description="Switchyard: Deterministic AI agent routing and dispatch",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: workers
    subparsers.add_parser("workers", help="List registered workers")

    # Subcommand: route
    p_route = subparsers.add_parser("route", help="Route task without executing")
    p_route.add_argument("prompt", help="Task prompt description")
    p_route.add_argument(
        "-c",
        "--capability",
        action="append",
        dest="capability",
        help="Required capability (can be specified multiple times)",
    )
    p_route.add_argument(
        "--prefer-speed",
        action="store_true",
        help="Prioritize worker execution speed",
    )
    p_route.add_argument(
        "--prefer-cost",
        action="store_true",
        help="Prioritize worker cost savings",
    )

    # Subcommand: run
    p_run = subparsers.add_parser("run", help="Route and execute task via LangGraph")
    p_run.add_argument("prompt", help="Task prompt description")
    p_run.add_argument(
        "-c",
        "--capability",
        action="append",
        dest="capability",
        help="Required capability (can be specified multiple times)",
    )
    p_run.add_argument(
        "--prefer-speed",
        action="store_true",
        help="Prioritize worker execution speed",
    )
    p_run.add_argument(
        "--prefer-cost",
        action="store_true",
        help="Prioritize worker cost savings",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint."""
    parser = create_parser()
    args = parser.parse_args(argv)
    registry = build_default_registry()

    if args.command == "workers":
        return cmd_workers(registry, args)
    elif args.command == "route":
        return cmd_route(registry, args)
    elif args.command == "run":
        return cmd_run(registry, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
