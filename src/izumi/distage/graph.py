"""
Dependency graph formation and validation.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from .activation import Activation
from .bindings import Binding, BindingKey, BindingType
from .introspection import SignatureIntrospector


class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected."""

    def __init__(self, cycle: list[BindingKey]):
        self.cycle = cycle
        cycle_str = " -> ".join(str(key) for key in cycle)
        super().__init__(f"Circular dependency detected: {cycle_str}")


class MissingBindingError(Exception):
    """Raised when a required binding is not found."""

    def __init__(self, key: BindingKey, dependent: BindingKey | None = None):
        self.key = key
        self.dependent = dependent
        msg = f"No binding found for {key}"
        if dependent:
            msg += f" (required by {dependent})"
        super().__init__(msg)


@dataclass
class GraphNode:
    """A node in the dependency graph."""

    key: BindingKey
    binding: Binding
    dependencies: list[BindingKey]
    dependents: set[BindingKey]

    def __post_init__(self) -> None:
        self.dependents = set()


class DependencyGraph:
    """Manages the dependency graph for the entire application."""

    def __init__(self) -> None:
        super().__init__()
        self._bindings: dict[BindingKey, Binding] = {}
        self._alternative_bindings: dict[BindingKey, list[Binding]] = defaultdict(list)
        self._nodes: dict[BindingKey, GraphNode] = {}
        self._set_bindings: dict[BindingKey, list[Binding]] = defaultdict(list)
        self._validated = False

    def add_binding(self, binding: Binding) -> None:
        """Add a binding to the graph."""
        if binding.binding_type == BindingType.SET_ELEMENT:
            self._set_bindings[binding.key].append(binding)
        else:
            # Store all bindings as alternatives initially
            self._alternative_bindings[binding.key].append(binding)

            # If this is the first binding or an untagged binding, also store in main bindings
            if binding.key not in self._bindings or not binding.activation_tags:
                self._bindings[binding.key] = binding

        self._validated = False

    def get_binding(self, key: BindingKey) -> Binding | None:
        """Get a binding by key."""
        return self._bindings.get(key)

    def get_set_bindings(self, key: BindingKey) -> list[Binding]:
        """Get all set bindings for a key."""
        return self._set_bindings.get(key, [])

    def get_all_bindings(self) -> dict[BindingKey, Binding]:
        """Get all regular bindings."""
        return self._bindings.copy()

    def get_node(self, key: BindingKey) -> GraphNode | None:
        """Get a graph node by key."""
        return self._nodes.get(key)

    def validate(self) -> None:
        """Validate the dependency graph."""
        if self._validated:
            return

        self._build_graph()
        self._check_missing_dependencies()
        self._check_circular_dependencies()
        self._validated = True

    def _build_graph(self) -> None:
        """Build the dependency graph nodes."""
        self._nodes.clear()

        # Create nodes for all bindings
        for key, binding in self._bindings.items():
            dependencies = self._extract_dependencies(binding)
            node = GraphNode(key, binding, dependencies, set())
            self._nodes[key] = node

        # Build dependent relationships
        for node in self._nodes.values():
            for dep_key in node.dependencies:
                dep_node = self._nodes.get(dep_key)
                if dep_node:
                    dep_node.dependents.add(node.key)

    def _extract_dependencies(self, binding: Binding) -> list[BindingKey]:
        """Extract dependency keys from a binding."""
        if binding.binding_type == BindingType.INSTANCE:
            return []

        try:
            dependencies = SignatureIntrospector.extract_dependencies(binding.implementation)
            return SignatureIntrospector.get_binding_keys(dependencies)
        except Exception:
            # If introspection fails, assume no dependencies
            return []

    def _check_missing_dependencies(self) -> None:
        """Check for missing dependencies."""
        for node in self._nodes.values():
            for dep_key in node.dependencies:
                if dep_key not in self._bindings and dep_key not in self._set_bindings:
                    raise MissingBindingError(dep_key, node.key)

    def _check_circular_dependencies(self) -> None:
        """Check for circular dependencies using DFS."""
        WHITE = 0  # Not visited
        GRAY = 1  # Currently being processed
        BLACK = 2  # Completely processed

        colors: dict[BindingKey, int] = defaultdict(lambda: WHITE)
        parent: dict[BindingKey, BindingKey | None] = {}

        def dfs(key: BindingKey, path: list[BindingKey]) -> None:
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

    def get_topological_order(self) -> list[BindingKey]:
        """Get a topological ordering of the dependency graph."""
        if not self._validated:
            self.validate()

        in_degree: dict[BindingKey, int] = defaultdict(int)

        # Calculate in-degrees
        for node in self._nodes.values():
            for dep_key in node.dependencies:
                if dep_key in self._nodes:
                    in_degree[dep_key] += 1

        # Initialize queue with nodes that have no dependencies
        queue: deque[BindingKey] = deque()
        for key in self._nodes:
            if in_degree[key] == 0:
                queue.append(key)

        result: list[BindingKey] = []

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
        # Import here to avoid circular import

        filtered_bindings = {}
        for key, alternatives in self._alternative_bindings.items():
            # Find the best matching binding for this key
            best_binding = self._select_best_binding(alternatives, activation)
            if best_binding:
                filtered_bindings[key] = best_binding

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

    def garbage_collect(self, reachable_keys: set[BindingKey]) -> None:
        """Remove unreachable bindings from the graph."""
        # Filter main bindings
        filtered_bindings = {
            key: binding for key, binding in self._bindings.items() if key in reachable_keys
        }

        # Filter set bindings
        filtered_set_bindings = {}
        for key, bindings in self._set_bindings.items():
            if key in reachable_keys:
                filtered_set_bindings[key] = bindings

        self._bindings = filtered_bindings
        self._set_bindings = filtered_set_bindings
        self._validated = False
