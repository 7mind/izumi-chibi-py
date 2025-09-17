"""
Dependency resolution and execution engine.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from .activation import Activation
from .bindings import Binding, BindingType
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
    ):
        super().__init__()
        self._graph = graph
        self._activation = activation
        self._roots = roots
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
            set_key = DIKey(key.target_type, key.tag)  # Create set key
            set_bindings = self._graph.get_set_bindings(set_key)
            if set_bindings:
                return self._resolve_set_binding_direct(set_bindings)
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
        if binding.binding_type == BindingType.INSTANCE:
            return binding.implementation

        elif binding.binding_type == BindingType.FACTORY:
            return self._call_factory(binding.implementation)

        elif binding.binding_type == BindingType.CLASS:
            return self._instantiate_class(binding.implementation)

        elif binding.binding_type == BindingType.SET_ELEMENT:
            # For set elements, treat them like regular bindings
            if inspect.isclass(binding.implementation):
                return self._instantiate_class(binding.implementation)
            elif callable(binding.implementation):
                return self._call_factory(binding.implementation)
            else:
                return binding.implementation

        else:
            raise ValueError(f"Unknown binding type: {binding.binding_type}")

    def _instantiate_class(self, cls: type | Any | Callable[..., Any]) -> Any:
        """Instantiate a class by resolving its dependencies."""
        dependencies = SignatureIntrospector.extract_dependencies(cls)
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
                dep_key = DIKey(dep.type_hint, None)
                kwargs[dep.name] = self.resolve(dep_key)
            # For optional dependencies with defaults, let the class handle them

        return cls(**kwargs)

    def _call_factory(self, factory: Callable[..., Any]) -> Any:
        """Call a factory function by resolving its dependencies."""
        dependencies = SignatureIntrospector.extract_dependencies(factory)
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
                dep_key = DIKey(dep.type_hint, None)
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
