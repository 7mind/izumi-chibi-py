"""
Dependency resolution and execution engine.
"""

from __future__ import annotations

import inspect
from typing import Any

from .activation import Activation
from .bindings import Binding
from .functoid import Functoid
from .graph import DependencyGraph
from .keys import DIKey
from .operations import ExecutableOp
from .roots import Roots


class DependencyResolver:
    """Resolves dependencies and creates instances."""

    def __init__(
        self,
        graph: DependencyGraph,
        activation: Activation | None = None,
        roots: Roots | None = None,
        parent_locator: Any = None,
    ):
        super().__init__()
        self._graph = graph
        self._activation = activation
        self._roots = roots
        self._parent_locator = parent_locator
        self._instances: dict[DIKey, Any] = {}
        self._resolving: set[DIKey] = set()

    def resolve(self, key: DIKey) -> Any:
        """Resolve a dependency and return an instance."""
        # Check if already resolved
        if key in self._instances:
            return self._instances[key]

        # Check for circular dependency during resolution
        if key in self._resolving:
            raise ValueError(f"Circular dependency detected during resolution: {key}")

        self._resolving.add(key)

        try:
            instance = self._create_instance(key)
            self._instances[key] = instance
            return instance
        finally:
            self._resolving.discard(key)

    def _create_instance(self, key: DIKey) -> Any:
        """Create an instance for the given key."""
        # Get operation for this key
        operations = self._graph.get_operations()
        operation = operations.get(key)

        if not operation:
            # Check parent locator if available
            if self._parent_locator is not None:
                try:
                    return self._parent_locator.get(key.target_type, key.name)
                except ValueError:
                    pass  # Parent doesn't have it either

            raise ValueError(f"No operation found for {key}")

        return self._execute_operation(operation)

    def _execute_operation(self, operation: ExecutableOp) -> Any:
        """Execute an operation with resolved dependencies."""
        import logging

        from .operations import CreateFactory

        # Special handling for CreateFactory operations
        if isinstance(operation, CreateFactory):
            # Set the resolve function for the factory operation
            operation.resolve_fn = self.resolve
            return operation.execute({})

        # Build resolved dependencies map for other operations
        resolved_deps: dict[DIKey, Any] = {}
        for dep_key in operation.dependencies():
            try:
                resolved_deps[dep_key] = self.resolve(dep_key)
            except ValueError:
                # Check if this is an auto-injectable logger
                from .logger_injection import AutoLoggerManager

                if AutoLoggerManager.should_auto_inject_logger(dep_key):
                    # Create an appropriate logger as fallback
                    from .logger_injection import LoggerLocationIntrospector

                    logger_name = LoggerLocationIntrospector.get_logger_location_name()
                    resolved_deps[dep_key] = logging.getLogger(logger_name)
                else:
                    # Re-raise the original error for non-logger dependencies
                    raise

        return operation.execute(resolved_deps)

    def _resolve_set_binding(self, key: DIKey) -> set[Any]:
        """Resolve a set binding."""
        set_bindings = self._graph.get_set_bindings(key)
        return self._resolve_set_binding_direct(set_bindings)

    def _resolve_set_binding_direct(self, set_bindings: list[Binding]) -> set[Any]:
        """Resolve set bindings directly from a list of bindings."""
        result_set: set[Any] = set()

        for binding in set_bindings:
            instance = self._create_from_binding(binding)
            result_set.add(instance)

        return result_set

    def _create_from_binding(self, binding: Binding) -> Any:
        """Create an instance from a specific binding."""
        functoid = binding.functoid
        return self._call_functoid(functoid)

    def _create_from_functoid_direct(self, functoid: Functoid[Any]) -> Any:
        """Create an instance directly from a functoid."""
        return self._call_functoid(functoid)

    def _call_functoid(self, functoid: Functoid[Any]) -> Any:
        """Call a functoid by resolving its dependencies."""
        # Get the functoid's dependencies
        dependency_keys = functoid.keys()

        # If no dependencies, just call it
        if not dependency_keys:
            return functoid.call()

        # Get dependencies from functoid and resolve them
        dependencies = functoid.sig()
        resolved_args: list[Any] = []

        for dep in dependencies:
            # Skip Any types which are usually introspection failures
            if dep.type_hint == Any:
                continue
            if (
                (not dep.is_optional or dep.default_value == inspect.Parameter.empty)
                and (isinstance(dep.type_hint, type) or hasattr(dep.type_hint, "__origin__"))
                and not isinstance(dep.type_hint, str)
            ):
                # Handle both regular types and generic types (like set[T]), but skip string forward references
                di_key = DIKey(dep.type_hint, dep.dependency_name)
                resolved_value = self.resolve(di_key)
                resolved_args.append(resolved_value)
            # For optional dependencies with defaults, let the functoid handle them

        return functoid.call(*resolved_args)

    def clear_instances(self) -> None:
        """Clear all resolved instances (useful for testing)."""
        self._instances.clear()

    def get_instance_count(self) -> int:
        """Get the number of resolved instances."""
        return len(self._instances)

    def is_resolved(self, key: DIKey) -> bool:
        """Check if a key has been resolved."""
        return key in self._instances
