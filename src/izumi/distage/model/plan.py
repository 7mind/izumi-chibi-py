"""
Plan - Represents a validated dependency graph with metadata that can be executed multiple times.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from ..activation import Activation
from ..roots import Roots
from .graph import DependencyGraph
from .keys import InstanceKey

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
    topology: list[InstanceKey]

    def __post_init__(self) -> None:
        """Ensure the plan is validated."""
        # Since we're frozen, we can't modify after creation
        # The validation should have been done before creating the Plan
        if not getattr(self.graph, "_validated", False):
            raise ValueError("Plan created with unvalidated graph")

    @staticmethod
    def empty() -> Plan:
        """
        Create an empty Plan that has no operations and can be used as a null object.

        Returns:
            An empty Plan instance
        """
        from ..activation import Activation
        from ..roots import Roots
        from .graph import DependencyGraph

        # Create an empty graph with no operations
        empty_graph = DependencyGraph()
        empty_graph.generate_operations()  # Creates empty operations dict
        empty_graph.validate()  # Mark as validated since it's empty

        return Plan(
            graph=empty_graph, roots=Roots.empty(), activation=Activation.empty(), topology=[]
        )

    def is_empty(self) -> bool:
        """
        Check if this is an empty plan.

        Returns:
            True if this plan has no operations
        """
        return len(self.graph.get_operations()) == 0

    def keys(self) -> set[InstanceKey]:
        """Get all available keys in this plan."""
        return set(self.graph.get_operations().keys())

    def has_operation(self, key: InstanceKey) -> bool:
        """Check if an operation exists for the given key."""
        return key in self.graph.get_operations()

    def has_binding(self, key: InstanceKey) -> bool:
        """Check if a binding exists for the given key."""
        return self.graph.get_binding(key) is not None

    def get_execution_order(self) -> list[InstanceKey]:
        """Get the topological order for execution."""
        copy = self.topology.copy()
        copy.reverse()
        return copy
