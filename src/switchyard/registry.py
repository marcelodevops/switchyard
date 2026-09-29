"""In-memory registry of available workers."""

from typing import Dict, Iterator, List, Optional
from switchyard.worker import Worker


class WorkerRegistry:
    """Registry maintaining available workers for Switchyard."""

    def __init__(self) -> None:
        self._workers: Dict[str, Worker] = {}

    def register(self, worker: Worker) -> None:
        """Register a worker in the pool."""
        self._workers[worker.name] = worker

    def unregister(self, name: str) -> Optional[Worker]:
        """Remove a worker from the pool."""
        return self._workers.pop(name, None)

    def get(self, name: str) -> Optional[Worker]:
        """Retrieve a worker by name."""
        return self._workers.get(name)

    def list_workers(self) -> List[Worker]:
        """Return all registered workers."""
        return list(self._workers.values())

    def get_available_workers(self) -> List[Worker]:
        """Return only workers that are currently available."""
        return [w for w in self._workers.values() if w.is_available()]

    def __len__(self) -> int:
        return len(self._workers)

    def __contains__(self, name: str) -> bool:
        return name in self._workers

    def __iter__(self) -> Iterator[Worker]:
        return iter(self._workers.values())
