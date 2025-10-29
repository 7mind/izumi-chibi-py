"""
Dependency graph formation and validation.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from ..activation import Activation
from ..activation_context import ActivationContext
from .bindings import Binding
from .keys import InstanceKey, SetElementKey
from .operations import CreateFactory, CreateSet, ExecutableOp, Lookup, Provide


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
        self._set_lookup_operations: dict[InstanceKey, list[Lookup]] = defaultdict(list)
        self._all_set_keys: set[InstanceKey] = set()  # Track all set keys ever registered
        self._validated = False

    def add_binding(self, binding: Binding) -> None:
        """Add a binding to the graph."""
        # Check if this is a set element binding using SetElementKey
        if isinstance(binding.key, SetElementKey):
            self._set_bindings[binding.key.set_key].append(binding)
            self._all_set_keys.add(binding.key.set_key)
        else:
            # Group alternatives by type only (ignore tag for activation purposes)
            type_key = InstanceKey(binding.key.target_type, None)
            self._alternative_bindings[type_key].append(binding)

            # If this is the first binding or an untagged binding, also store in main bindings
            if binding.key not in self._bindings or not binding.activation_tags:
                self._bindings[binding.key] = binding

        self._validated = False

    def add_lookup_operation(self, operation: ExecutableOp) -> None:
        """Add a lookup operation or other executable operation directly to the graph."""
        # Directly add the operation to the operations
        self._operations[operation.key()] = operation

        # If this is a Lookup operation for a set element, track it
        if isinstance(operation, Lookup) and operation.set_key is not None:
            self._set_lookup_operations[operation.set_key].append(operation)
            self._all_set_keys.add(operation.set_key)

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
        # Preserve any lookup operations and subcontext operations that were added directly
        from .operations import CreateSubcontext

        existing_operations = {
            key: op
            for key, op in self._operations.items()
            if isinstance(op, (Lookup, CreateSubcontext))
        }
        self._operations.clear()
        self._operations.update(existing_operations)

        # Filter weak references before generating operations
        self._filter_weak_references()

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
        # Use all set keys that were ever registered, even if all elements were filtered out
        for set_key in self._all_set_keys:
            element_keys: list[InstanceKey] = []

            # Add elements from bindings
            bindings = self._set_bindings.get(set_key, [])
            for binding in bindings:
                # Create Provide operation for each set element
                if isinstance(binding.key, SetElementKey):
                    element_key = binding.key.element_key
                    self._operations[element_key] = Provide(binding)
                    element_keys.append(element_key)

            # Add elements from lookup operations
            lookup_ops = self._set_lookup_operations.get(set_key, [])
            for lookup_op in lookup_ops:
                # Lookup operations are already added to _operations in add_lookup_operation
                element_keys.append(lookup_op.key())

            # Create CreateSet operation to collect all elements (even if empty)
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

    def _filter_weak_references(self) -> None:
        """Filter out weak references that don't have non-weak counterparts."""
        # Find all keys that have non-weak references pointing to them
        keys_with_non_weak_refs: set[InstanceKey] = set()

        # Check lookup operations to see which source keys have non-weak references
        for lookup_ops_list in self._set_lookup_operations.values():
            for lookup_op in lookup_ops_list:
                if not lookup_op.is_weak:
                    keys_with_non_weak_refs.add(lookup_op.source_key)

        # Check set bindings to see which element keys have non-weak references
        for bindings_list in self._set_bindings.values():
            for binding in bindings_list:
                if not binding.is_weak and isinstance(binding.key, SetElementKey):
                    # For set element bindings, we need to check the element key
                    keys_with_non_weak_refs.add(binding.key.element_key)

        # Regular bindings are always kept if they're not weak
        # (they don't need to be "referenced" to exist)

        # Filter out weak lookup operations that don't have non-weak counterparts
        filtered_lookup_operations: dict[InstanceKey, list[Lookup]] = {}
        for set_key, lookup_ops_list in self._set_lookup_operations.items():
            filtered_lookup_ops_list: list[Lookup] = []
            for lookup_op in lookup_ops_list:
                if not lookup_op.is_weak or lookup_op.source_key in keys_with_non_weak_refs:
                    filtered_lookup_ops_list.append(lookup_op)
            if filtered_lookup_ops_list:
                filtered_lookup_operations[set_key] = filtered_lookup_ops_list
        self._set_lookup_operations = filtered_lookup_operations

        # Also filter out weak lookup operations from the main operations dict
        filtered_operations: dict[InstanceKey, ExecutableOp] = {}
        for key, operation in self._operations.items():
            if isinstance(operation, Lookup):
                if not operation.is_weak or operation.source_key in keys_with_non_weak_refs:
                    filtered_operations[key] = operation
            else:
                filtered_operations[key] = operation
        self._operations = filtered_operations

        # Filter out weak set bindings that don't have non-weak counterparts
        filtered_set_bindings: dict[InstanceKey, list[Binding]] = {}
        for set_key, bindings_list in self._set_bindings.items():
            filtered_bindings_list: list[Binding] = []
            for binding in bindings_list:
                if isinstance(binding.key, SetElementKey) and (
                    not binding.is_weak or binding.key.element_key in keys_with_non_weak_refs
                ):
                    filtered_bindings_list.append(binding)
            if filtered_bindings_list:
                filtered_set_bindings[set_key] = filtered_bindings_list
        self._set_bindings = filtered_set_bindings

        # Filter out weak regular bindings that don't have non-weak counterparts
        filtered_bindings: dict[InstanceKey, Binding] = {}
        for key, binding in self._bindings.items():
            if not binding.is_weak or key in keys_with_non_weak_refs:
                filtered_bindings[key] = binding
        self._bindings = filtered_bindings

    def filter_bindings_by_activation(self, activation: Activation) -> None:
        """
        Filter bindings based on activation, selecting the best match for each key.

        DEPRECATED: This method uses simple filtering without path-aware tracing.
        Use filter_bindings_by_activation_traced for sound axis resolution.
        """
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

    def filter_bindings_by_activation_traced(
        self, activation: Activation, roots: set[InstanceKey]
    ) -> None:
        """
        Filter bindings using path-aware tracing from roots.

        This implements the sound activation resolution from the original distage:
        - Start from roots and traverse dependencies
        - Track activation context (user choices + implied choices from selected bindings)
        - Resolve conflicts at each step considering the current path's context
        - Only include bindings that are reachable with valid activation
        """
        context = ActivationContext.from_activation(activation)
        visited: set[InstanceKey] = set()
        selected_bindings: dict[InstanceKey, Binding] = {}

        def trace_dependencies(key: InstanceKey, current_context: ActivationContext) -> None:
            """Recursively trace dependencies from a key with the given context."""
            if key in visited:
                return
            visited.add(key)

            # Find the type key for this instance key
            type_key = InstanceKey(key.target_type, None)

            # Get alternative bindings for this type
            alternatives = self._alternative_bindings.get(type_key, [])

            if not alternatives:
                # No alternatives, check if we have a direct binding
                if key in self._bindings:
                    selected_bindings[key] = self._bindings[key]
                return

            # Resolve conflict using current context
            best_binding = self._select_best_binding_traced(alternatives, current_context)

            if best_binding:
                # Store the selected binding for the untagged type key
                selected_bindings[type_key] = best_binding
                # Also store for the binding's actual key if it's different from type_key
                # (e.g., if it has a name)
                if best_binding.key != type_key:
                    selected_bindings[best_binding.key] = best_binding

                # Extend context with tags from selected binding
                extended_context = current_context.with_binding_tags(best_binding)

                # Trace dependencies of this binding
                # Get dependencies from Functoid using keys() method
                for dep_key in best_binding.functoid.keys():
                    if isinstance(dep_key, InstanceKey):
                        trace_dependencies(dep_key, extended_context)

        # Trace from each root
        for root_key in roots:
            trace_dependencies(root_key, context)

        # Also trace set bindings and their elements
        for set_key, bindings in self._set_bindings.items():
            if set_key in roots or set_key in visited:
                for binding in bindings:
                    if context.is_binding_valid(binding):
                        if isinstance(binding.key, SetElementKey):
                            element_key = binding.key.element_key
                            trace_dependencies(element_key, context)

        # Update bindings to only include selected ones
        self._bindings = selected_bindings
        self._validated = False

    def _select_best_binding_traced(
        self, bindings: list[Binding], context: ActivationContext
    ) -> Binding | None:
        """Select the best binding from alternatives based on activation context."""
        if not bindings:
            return None

        if len(bindings) == 1:
            binding = bindings[0]
            return binding if context.is_binding_valid(binding) else None

        # Filter bindings that are valid in this context
        valid_bindings = [b for b in bindings if context.is_binding_valid(b)]

        if not valid_bindings:
            # If no bindings are valid, prefer untagged bindings as defaults
            untagged_bindings = [b for b in bindings if not b.activation_tags]
            return untagged_bindings[0] if untagged_bindings else None

        if len(valid_bindings) == 1:
            return valid_bindings[0]

        # If multiple bindings are valid, prefer more specific ones (more tags)
        # A binding is more specific if it has more axis choices configured
        valid_bindings.sort(key=lambda b: len(b.activation_tags or set()), reverse=True)  # pyright: ignore[reportUnknownArgumentType]
        return valid_bindings[0]

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
