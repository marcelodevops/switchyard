"""Deterministic, explainable routing by capability and explicit preference."""

from typing import Dict, List
from switchyard.models import RoutingDecision, Task
from switchyard.registry import WorkerRegistry
from switchyard.worker import Worker


class NoEligibleWorkerError(Exception):
    """Raised when no available worker satisfies the task requirements."""
    pass


class Router:
    """Select eligible workers using only requested speed and cost preferences."""

    def __init__(self, registry: WorkerRegistry) -> None:
        self.registry = registry

    def route(self, task: Task) -> RoutingDecision:
        """Evaluate available workers and deterministically select the best candidate.

        Raises:
            NoEligibleWorkerError: If no available worker meets required capabilities.
        """
        # Step 1: Filter available workers that satisfy all required capabilities
        eligible_workers: List[Worker] = []
        for worker in self.registry.get_available_workers():
            if task.required_capabilities.issubset(worker.capabilities):
                eligible_workers.append(worker)

        if not eligible_workers:
            reqs = sorted(task.required_capabilities)
            raise NoEligibleWorkerError(
                f"No available workers found satisfying required capabilities: {reqs}"
            )

        # Explicit preferences contribute equally; neutral tasks score every worker zero.
        scores: Dict[str, float] = {}
        for worker in eligible_workers:
            scores[worker.name] = (
                (worker.speed.rank if task.prefer_speed else 0)
                + (3 - worker.cost.rank if task.prefer_cost else 0)
            )

        # Step 3: Deterministic ranking (score descending, name ascending for stable tie-breaking)
        ranked = sorted(
            eligible_workers,
            key=lambda w: (-scores[w.name], w.name)
        )
        selected = ranked[0]

        # Step 4: Build explainable reason matching spec
        matched_caps = sorted(task.required_capabilities) if task.required_capabilities else sorted(selected.capabilities)
        other_workers = [w.name for w in ranked if w.name != selected.name]

        reason_lines = [
            f"selected: {selected.name}",
            "",
            "reason:",
            f"  required capabilities matched: {', '.join(matched_caps) if matched_caps else 'general'}",
            f"  speed: {selected.speed.value}",
            f"  cost: {selected.cost.value}",
        ]
        if task.prefer_speed and task.prefer_cost:
            reason_lines.extend([
                "  preference: speed + cost",
                "  selected using equal combined speed/cost ranking",
            ])
        elif task.prefer_speed:
            reason_lines.extend([
                "  preference: speed",
                "  selected fastest eligible worker",
            ])
        elif task.prefer_cost:
            reason_lines.extend([
                "  preference: cost",
                "  selected cheapest eligible worker",
            ])
        else:
            reason_lines.extend([
                "  preference: none",
                "  deterministic tie-break: worker name",
            ])

        reason_lines.append("")
        reason_lines.append("other eligible workers:")
        if other_workers:
            for other in other_workers:
                reason_lines.append(f"  {other}")
        else:
            reason_lines.append("  none")

        reason = "\n".join(reason_lines)

        return RoutingDecision(
            selected_worker_name=selected.name,
            reason=reason,
            eligible_workers=[w.name for w in ranked],
            scores=scores,
        )
