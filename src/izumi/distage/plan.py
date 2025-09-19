"""
Plan - Represents a validated dependency graph with metadata that can be executed multiple times.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from .activation import Activation
from .graph import DependencyGraph
from .keys import DIKey
from .roots import Roots

T = TypeVar("T")


@dataclass(frozen=True)
class Plan:
    """
    A validated dependency injection plan containing the graph and metadata.

    Plans are immutable and can be executed multiple times to create different
    sets of instances. They contain:
    - The validated dependency graph
    - The roots (which keys should be available)
    - The activation configuration
    - Additional metadata for execution
    """

    graph: DependencyGraph
    roots: Roots
    activation: Activation
    topology: list[DIKey]

    def __post_init__(self) -> None:
        """Ensure the plan is validated."""
        # Since we're frozen, we can't modify after creation
        # The validation should have been done before creating the Plan
        if not getattr(self.graph, "_validated", False):
            raise ValueError("Plan created with unvalidated graph")

    def keys(self) -> set[DIKey]:
        """Get all available keys in this plan."""
        return set(self.graph.get_all_bindings().keys())

    def has_binding(self, key: DIKey) -> bool:
        """Check if a binding exists for the given key."""
        return self.graph.get_binding(key) is not None

    def get_execution_order(self) -> list[DIKey]:
        """Get the topological order for execution."""
        copy = self.topology.copy()
        copy.reverse()
        return copy
