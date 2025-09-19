"""
Dependency graph formation and validation.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from ..activation import Activation
from .bindings import Binding
from .keys import InstanceKey, SetElementKey
from .operations import CreateFactory, CreateSet, ExecutableOp, Provide


class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected."""

    def __init__(self, cycle: list[InstanceKey]):
        self.cycle = cycle
        cycle_str = " -> ".join(str(key) for key in cycle)
        super().__init__(f"Circular dependency detected: {cycle_str}")


class MissingBindingError(Exception):
    """Raised when a required binding is not found."""

    def __init__(self, key: InstanceKey, dependent: InstanceKey | None = None):
        self.key = key
        self.dependent = dependent
        msg = f"No binding found for {key}"
        if dependent:
            msg += f" (required by {dependent})"
        super().__init__(msg)


@dataclass
class GraphNode:
    """A node in the dependency graph."""

    key: InstanceKey
    operation: ExecutableOp
    dependencies: list[InstanceKey]
    dependents: set[InstanceKey]

    def __post_init__(self) -> None:
        self.dependents = set()


class DependencyGraph:
    """Manages the dependency graph for the entire application."""

    def __init__(self) -> None:
        super().__init__()
        self._bindings: dict[InstanceKey, Binding] = {}
        self._alternative_bindings: dict[InstanceKey, list[Binding]] = defaultdict(list)
        self._operations: dict[InstanceKey, ExecutableOp] = {}
        self._nodes: dict[InstanceKey, GraphNode] = {}
        self._set_bindings: dict[InstanceKey, list[Binding]] = defaultdict(list)
        self._validated = False

    def add_binding(self, binding: Binding) -> None:
        """Add a binding to the graph."""
        # Check if this is a set element binding using SetElementKey
        if isinstance(binding.key, SetElementKey):
            self._set_bindings[binding.key.set_key].append(binding)
        else:
            # Group alternatives by type only (ignore tag for activation purposes)
            type_key = InstanceKey(binding.key.target_type, None)
            self._alternative_bindings[type_key].append(binding)

            # If this is the first binding or an untagged binding, also store in main bindings
            if binding.key not in self._bindings or not binding.activation_tags:
                self._bindings[binding.key] = binding

        self._validated = False

    def get_binding(self, key: InstanceKey) -> Binding | None:
        """Get a binding by key."""
        # First check regular bindings
        binding = self._bindings.get(key)
        if binding:
            return binding

        # Then check set element bindings
        for set_bindings in self._set_bindings.values():
            for binding in set_bindings:
                if isinstance(binding.key, SetElementKey) and binding.key.element_key == key:
                    return binding

        return None

    def get_set_bindings(self, key: InstanceKey) -> list[Binding]:
        """Get all set bindings for a key."""
        return self._set_bindings.get(key, [])

    def get_all_bindings(self) -> dict[InstanceKey, Binding]:
        """Get all regular bindings."""
        return self._bindings.copy()

    def get_node(self, key: InstanceKey) -> GraphNode | None:
        """Get a graph node by key."""
        return self._nodes.get(key)

    def get_operations(self) -> dict[InstanceKey, ExecutableOp]:
        """Get all operations."""
        return self._operations.copy()

    def generate_operations(self) -> None:
        """Generate operations from bindings."""
        self._operations.clear()

        # Create operations for regular bindings
        for key, binding in self._bindings.items():
            if binding.is_factory:
                # Create CreateFactory operation for factory bindings
                # Extract the target type from Factory[T]
                # Factory bindings only work with InstanceKey, not SetElementKey
                # Since _bindings is typed as dict[InstanceKey, Binding], key is always InstanceKey
                if (
                    hasattr(key.target_type, "__args__") and key.target_type.__args__  # pyright: ignore[reportUnknownMemberType]
                ):  # pyright: ignore[reportUnknownMemberType]
                    target_type = key.target_type.__args__[0]  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
                    self._operations[key] = CreateFactory(key, target_type, binding)  # pyright: ignore[reportUnknownArgumentType]
                else:
                    raise ValueError(f"Invalid Factory binding: {key}")
            else:
                # Create Provide operation for regular bindings
                self._operations[key] = Provide(binding)

        # Create CreateSet operations for set bindings
        for set_key, bindings in self._set_bindings.items():
            element_keys: list[InstanceKey] = []
            for binding in bindings:
                # Create Provide operation for each set element
                if isinstance(binding.key, SetElementKey):
                    element_key = binding.key.element_key
                    self._operations[element_key] = Provide(binding)
                    element_keys.append(element_key)

            # Create CreateSet operation to collect all elements
            if element_keys:
                self._operations[set_key] = CreateSet(set_key, element_keys)

    def validate(self) -> None:
        """Validate the dependency graph."""
        if self._validated:
            return

        self.generate_operations()
        self._build_graph()
        self._check_missing_dependencies()
        self._check_circular_dependencies()
        self._validated = True

    def validate_with_parent_locator(self, parent_locator: Any) -> None:
        """Validate the dependency graph with a parent locator for missing dependencies."""
        if self._validated:
            return

        self.generate_operations()
        self._build_graph()
        self._check_missing_dependencies_with_parent(parent_locator)
        self._check_circular_dependencies()
        self._validated = True

    def _build_graph(self) -> None:
        """Build the dependency graph nodes."""
        self._nodes.clear()

        # Create nodes for all operations
        for key, operation in self._operations.items():
            dependencies = operation.dependencies()
            node = GraphNode(key, operation, dependencies, set())
            self._nodes[key] = node

        # Build dependent relationships
        for node in self._nodes.values():
            for dep_key in node.dependencies:
                dep_node = self._nodes.get(dep_key)
                if dep_node:
                    dep_node.dependents.add(node.key)

    def _check_missing_dependencies(self) -> None:
        """Check for missing dependencies."""
        for node in self._nodes.values():
            # Skip dependency validation for factory operations
            # Factory operations are expected to have missing dependencies (assisted injection)
            if isinstance(node.operation, CreateFactory):
                continue

            for dep_key in node.dependencies:
                if dep_key not in self._operations:
                    # Check if this is an auto-injectable logger
                    from ..logger_injection import AutoLoggerManager

                    if AutoLoggerManager.should_auto_inject_logger(dep_key):
                        # Skip validation for auto-injectable loggers
                        continue
                    raise MissingBindingError(dep_key, node.key)

    def _check_missing_dependencies_with_parent(self, parent_locator: Any) -> None:
        """Check for missing dependencies, allowing parent locator to provide them."""
        for node in self._nodes.values():
            # Skip dependency validation for factory operations
            # Factory operations are expected to have missing dependencies (assisted injection)
            if isinstance(node.operation, CreateFactory):
                continue

            for dep_key in node.dependencies:
                if dep_key not in self._operations:
                    # Check if this is an auto-injectable logger
                    from ..logger_injection import AutoLoggerManager

                    if AutoLoggerManager.should_auto_inject_logger(dep_key):
                        # Skip validation for auto-injectable loggers
                        continue

                    # Check if parent locator can provide this dependency
                    try:
                        parent_locator.get(dep_key)
                        # Parent has it, so it's OK
                        continue
                    except ValueError:
                        # Parent doesn't have it either
                        pass

                    raise MissingBindingError(dep_key, node.key)

    def _check_circular_dependencies(self) -> None:
        """Check for circular dependencies using DFS."""
        WHITE = 0  # Not visited
        GRAY = 1  # Currently being processed
        BLACK = 2  # Completely processed

        colors: dict[InstanceKey, int] = defaultdict(lambda: WHITE)
        parent: dict[InstanceKey, InstanceKey | None] = {}

        def dfs(key: InstanceKey, path: list[InstanceKey]) -> None:
            if colors[key] == GRAY:
                # Found a back edge - circular dependency
                cycle_start = path.index(key)
                cycle = path[cycle_start:] + [key]
                raise CircularDependencyError(cycle)

            if colors[key] == BLACK:
                return

            colors[key] = GRAY
            path.append(key)

            node = self._nodes.get(key)
            if node:
                for dep_key in node.dependencies:
                    if dep_key in self._nodes:  # Only check dependencies that exist
                        parent[dep_key] = key
                        dfs(dep_key, path)

            path.pop()
            colors[key] = BLACK

        # Start DFS from all unvisited nodes
        for key in self._nodes:
            if colors[key] == WHITE:
                dfs(key, [])

    def get_topological_order(self) -> list[InstanceKey]:
        """Get a topological ordering of the dependency graph."""
        if not self._validated:
            self.validate()

        in_degree: dict[InstanceKey, int] = defaultdict(int)

        # Calculate in-degrees
        for node in self._nodes.values():
            for dep_key in node.dependencies:
                if dep_key in self._nodes:
                    in_degree[dep_key] += 1

        # Initialize queue with nodes that have no dependencies
        queue: deque[InstanceKey] = deque()
        for key in self._nodes:
            if in_degree[key] == 0:
                queue.append(key)

        result: list[InstanceKey] = []

        while queue:
            key = queue.popleft()
            result.append(key)

            node = self._nodes[key]
            for dep_key in node.dependencies:
                if dep_key in self._nodes:
                    in_degree[dep_key] -= 1
                    if in_degree[dep_key] == 0:
                        queue.append(dep_key)

        if len(result) != len(self._nodes):
            # This shouldn't happen if circular dependency check passed
            raise CircularDependencyError([])

        return result

    def filter_bindings_by_activation(self, activation: Activation) -> None:
        """Filter bindings based on activation, selecting the best match for each key."""
        filtered_bindings = {}
        for type_key, alternatives in self._alternative_bindings.items():
            # Find the best matching binding for this type
            best_binding = self._select_best_binding(alternatives, activation)
            if best_binding:
                # Store the best binding for the untagged type key (what dependents will request)
                filtered_bindings[type_key] = best_binding
                # Also store it for any specific tagged keys that exist
                for binding in alternatives:
                    if isinstance(binding.key, InstanceKey) and binding.key in self._bindings:
                        filtered_bindings[binding.key] = best_binding

        self._bindings = filtered_bindings
        self._validated = False

    def _select_best_binding(
        self, bindings: list[Binding], activation: Activation
    ) -> Binding | None:
        """Select the best binding from alternatives based on activation."""
        if not bindings:
            return None

        if len(bindings) == 1:
            return bindings[0]

        # Find bindings that match the activation
        matching_bindings = [b for b in bindings if b.matches_activation(activation)]

        if not matching_bindings:
            # If no bindings match, prefer untagged bindings as defaults
            untagged_bindings = [b for b in bindings if not b.activation_tags]
            return untagged_bindings[0] if untagged_bindings else None

        if len(matching_bindings) == 1:
            return matching_bindings[0]

        # If multiple bindings match, prefer more specific ones (more tags)
        matching_bindings.sort(key=lambda b: len(b.activation_tags or set()), reverse=True)  # pyright: ignore[reportUnknownArgumentType]
        return matching_bindings[0]

    def garbage_collect(self, reachable_keys: set[InstanceKey]) -> None:
        """Remove unreachable operations and bindings from the graph."""
        # Filter operations
        filtered_operations = {
            key: operation for key, operation in self._operations.items() if key in reachable_keys
        }

        # Filter main bindings
        filtered_bindings = {
            key: binding for key, binding in self._bindings.items() if key in reachable_keys
        }

        # Filter set bindings
        filtered_set_bindings = {}
        for key, bindings in self._set_bindings.items():
            if key in reachable_keys:
                filtered_set_bindings[key] = bindings

        self._operations = filtered_operations
        self._bindings = filtered_bindings
        self._set_bindings = filtered_set_bindings
        self._validated = False
