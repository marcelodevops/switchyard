"""Core data models for Switchyard."""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class Speed(str, Enum):
    """Declared worker execution speed."""
    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"

    @property
    def rank(self) -> int:
        """Higher is faster."""
        return {"slow": 1, "medium": 2, "fast": 3}[self.value]


class Cost(str, Enum):
    """Declared worker cost tier."""
    FREE = "free"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def rank(self) -> int:
        """Lower is cheaper."""
        return {"free": 0, "low": 1, "medium": 2, "high": 3}[self.value]


class Task(BaseModel):
    """Description of work to perform and routing preferences."""
    prompt: str
    required_capabilities: set[str] = Field(default_factory=set)
    prefer_speed: bool = False
    prefer_cost: bool = False


class Result(BaseModel):
    """Outcome returned from worker execution."""
    output: str
    worker_name: str
    success: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class RoutingDecision(BaseModel):
    """Deterministic routing outcome explaining worker selection."""
    selected_worker_name: str
    reason: str
    eligible_workers: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
