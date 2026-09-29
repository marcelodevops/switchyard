"""Deterministic, explainable scoring router for Switchyard."""

from typing import Dict, List, Optional, Tuple
from switchyard.models import RoutingDecision, Task
from switchyard.registry import WorkerRegistry
from switchyard.worker import Worker


class NoEligibleWorkerError(Exception):
    """Raised when no available worker satisfies the task requirements."""
    pass


class Router:
    """Deterministic scoring router for selecting workers based on capability, speed, and cost."""

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

        # Step 2: Deterministic scoring
        # Weights adapt to explicit task preferences
        speed_weight = 3.0 if task.prefer_speed else 1.0
        cost_weight = 3.0 if task.prefer_cost else 1.0

        scores: Dict[str, float] = {}
        for worker in eligible_workers:
            speed_val = worker.speed.rank  # 1 (slow) to 3 (fast)
            cost_savings = 3 - worker.cost.rank  # 3 (free) to 0 (high)
            score = (speed_weight * speed_val) + (cost_weight * cost_savings)
            scores[worker.name] = round(score, 2)

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
        if task.prefer_cost:
            reason_lines.append("  preference: cost prioritized")
        if task.prefer_speed:
            reason_lines.append("  preference: speed prioritized")

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
