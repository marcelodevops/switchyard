"""Worker abstraction and mock implementations for Switchyard."""

from abc import ABC, abstractmethod
from typing import Optional, Set

from switchyard.models import Cost, Result, Speed, Task


class Worker(ABC):
    """Abstract base worker representing an external agent."""

    def __init__(
        self,
        name: str,
        capabilities: Set[str],
        speed: Speed = Speed.MEDIUM,
        cost: Cost = Cost.MEDIUM,
        available: bool = True,
    ) -> None:
        self.name = name
        self.capabilities = set(capabilities)
        self.speed = speed
        self.cost = cost
        self.available = available

    def is_available(self) -> bool:
        """Check if worker is currently available."""
        return self.available

    @abstractmethod
    async def execute(self, task: Task) -> Result:
        """Execute a task and return the result."""
        pass

    def __repr__(self) -> str:
        return (
            f"Worker(name={self.name!r}, capabilities={self.capabilities!r}, "
            f"speed={self.speed.value!r}, cost={self.cost.value!r}, available={self.available})"
        )


class MockWorker(Worker):
    """Mock worker configurable for testing and demonstration."""

    def __init__(
        self,
        name: str,
        capabilities: Set[str],
        speed: Speed = Speed.MEDIUM,
        cost: Cost = Cost.MEDIUM,
        available: bool = True,
        response_template: Optional[str] = None,
    ) -> None:
        super().__init__(name, capabilities, speed, cost, available)
        self.response_template = response_template or f"Executed by {name}: {{prompt}}"

    async def execute(self, task: Task) -> Result:
        output = self.response_template.format(prompt=task.prompt)
        return Result(
            output=output,
            worker_name=self.name,
            success=True,
            metadata={"speed": self.speed.value, "cost": self.cost.value},
        )


class MockCoder(MockWorker):
    """Fast, capable, high-cost coding worker."""

    def __init__(self, name: str = "mock-coder", available: bool = True) -> None:
        super().__init__(
            name=name,
            capabilities={"coding", "debugging", "repo-editing"},
            speed=Speed.FAST,
            cost=Cost.HIGH,
            available=available,
        )


class MockReasoner(MockWorker):
    """Medium-speed, low-cost reasoning worker."""

    def __init__(self, name: str = "mock-reasoner", available: bool = True) -> None:
        super().__init__(
            name=name,
            capabilities={"reasoning", "analysis", "summarization"},
            speed=Speed.MEDIUM,
            cost=Cost.LOW,
            available=available,
        )


class MockCheapWorker(MockWorker):
    """Slow, free coding worker for simple tasks."""

    def __init__(self, name: str = "mock-cheap-worker", available: bool = True) -> None:
        super().__init__(
            name=name,
            capabilities={"coding", "quick-edits"},
            speed=Speed.SLOW,
            cost=Cost.FREE,
            available=available,
        )
