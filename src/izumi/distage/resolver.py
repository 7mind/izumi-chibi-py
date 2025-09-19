"""
Dependency resolution and execution engine.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from .activation import Activation
from .bindings import Binding
from .functoid import Functoid
from .graph import DependencyGraph
from .introspection import SignatureIntrospector
from .keys import DIKey
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
        # Handle set bindings
        origin = getattr(key.target_type, "__origin__", None)
        if origin is set:
            return self._resolve_set_binding(key)

        binding = self._graph.get_binding(key)
        if not binding:
            # Check if we have set bindings for this type
            set_key = DIKey(key.target_type, key.name)  # Create set key
            set_bindings = self._graph.get_set_bindings(set_key)
            if set_bindings:
                return self._resolve_set_binding_direct(set_bindings)
            # Check parent locator if available
            if self._parent_locator is not None:
                try:
                    return self._parent_locator.get(key.target_type, key.name)
                except ValueError:
                    pass  # Parent doesn't have it either

            raise ValueError(f"No binding found for {key}")

        return self._create_from_binding(binding)

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

        # For dependencies, we need to resolve them and call with proper parameter mapping
        # Use existing helper methods that handle parameter name mapping correctly
        if functoid.original_class is not None:
            return self._instantiate_class(functoid.original_class)
        elif functoid.original_func is not None:
            return self._call_factory(functoid.original_func)
        else:
            # For other cases (like composed functoids), try calling with no args
            return functoid.call()

    def _instantiate_class(self, cls: type | Any | Callable[..., Any]) -> Any:
        """Instantiate a class by resolving its dependencies."""
        if inspect.isclass(cls):
            dependencies = SignatureIntrospector.extract_from_class(cls)
        else:
            dependencies = SignatureIntrospector.extract_from_callable(cls)
        kwargs = {}

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
                dep_key = DIKey(dep.type_hint, dep.dependency_name)
                kwargs[dep.name] = self.resolve(dep_key)
            # For optional dependencies with defaults, let the class handle them

        return cls(**kwargs)

    def _call_factory(self, factory: Callable[..., Any]) -> Any:
        """Call a factory function by resolving its dependencies."""
        dependencies = SignatureIntrospector.extract_from_callable(factory)
        kwargs = {}

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
                dep_key = DIKey(dep.type_hint, dep.dependency_name)
                kwargs[dep.name] = self.resolve(dep_key)
            # For optional dependencies with defaults, let the factory handle them

        return factory(**kwargs)

    def clear_instances(self) -> None:
        """Clear all resolved instances (useful for testing)."""
        self._instances.clear()

    def get_instance_count(self) -> int:
        """Get the number of resolved instances."""
        return len(self._instances)

    def is_resolved(self, key: DIKey) -> bool:
        """Check if a key has been resolved."""
        return key in self._instances
