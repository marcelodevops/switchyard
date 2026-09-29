"""Minimal LangGraph execution flow: route -> dispatch."""

from typing import Any, Dict, Optional, TypedDict
from langgraph.graph import END, START, StateGraph

from switchyard.models import Result, Task
from switchyard.registry import WorkerRegistry
from switchyard.router import Router


class SwitchyardState(TypedDict, total=False):
    """Execution state passed through the LangGraph pipeline."""
    task: Task
    selected_worker: Optional[str]
    routing_reason: Optional[str]
    result: Optional[Result]


def create_switchyard_graph(router: Router, registry: WorkerRegistry):
    """Compile the minimal route -> dispatch LangGraph."""
    builder = StateGraph(SwitchyardState)

    def route_node(state: SwitchyardState) -> Dict[str, Any]:
        task = state["task"]
        decision = router.route(task)
        return {
            "selected_worker": decision.selected_worker_name,
            "routing_reason": decision.reason,
        }

    async def dispatch_node(state: SwitchyardState) -> Dict[str, Any]:
        worker_name = state.get("selected_worker")
        if not worker_name:
            raise ValueError("No worker was selected by the router.")
        worker = registry.get(worker_name)
        if not worker:
            raise ValueError(f"Worker '{worker_name}' not found in registry during dispatch.")
        task = state["task"]
        result = await worker.execute(task)
        return {
            "result": result,
        }

    builder.add_node("route", route_node)
    builder.add_node("dispatch", dispatch_node)

    builder.add_edge(START, "route")
    builder.add_edge("route", "dispatch")
    builder.add_edge("dispatch", END)

    return builder.compile()


class Switchyard:
    """Entry point coordinating the registry, router, and LangGraph execution."""

    def __init__(
        self,
        registry: Optional[WorkerRegistry] = None,
        router: Optional[Router] = None,
    ) -> None:
        self.registry = registry or WorkerRegistry()
        self.router = router or Router(self.registry)
        self.graph = create_switchyard_graph(self.router, self.registry)

    async def run(self, task: Task) -> SwitchyardState:
        """Run task through route -> dispatch graph."""
        initial_state: SwitchyardState = {"task": task}
        return await self.graph.ainvoke(initial_state)
