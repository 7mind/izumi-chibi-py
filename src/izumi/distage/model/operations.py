"""
Executable operations for dependency injection.

This module implements the separation between bindings (what to create) and operations (how to create them),
following the original distage architecture.
"""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .keys import InstanceKey, SetElementKey

if TYPE_CHECKING:
    from .bindings import Binding


class ExecutableOp(ABC):
    """Base class for executable operations in the dependency injection system."""

    @abstractmethod
    def key(self) -> InstanceKey:
        """Get the DIKey this operation produces."""

    @abstractmethod
    def dependencies(self) -> list[InstanceKey]:
        """Get the dependencies this operation requires."""

    @abstractmethod
    def execute(self, resolved_deps: dict[InstanceKey, Any]) -> Any:  # noqa: ARG002
        """Execute the operation with resolved dependencies."""


@dataclass
class Provide(ExecutableOp):
    """Operation that provides a single instance using a binding."""

    binding: Binding

    def key(self) -> InstanceKey:
        """Get the DIKey this operation produces."""
        if isinstance(self.binding.key, SetElementKey):
            return self.binding.key.element_key
        return self.binding.key

    def dependencies(self) -> list[InstanceKey]:
        """Get the dependencies this operation requires."""
        return self.binding.functoid.keys()

    def execute(self, resolved_deps: dict[InstanceKey, Any]) -> Any:  # noqa: ARG002
        """Execute the binding with resolved dependencies."""
        dependencies = self.binding.functoid.sig()
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
                dep_key = InstanceKey(dep.type_hint, dep.dependency_name)
                resolved_args.append(resolved_deps[dep_key])
            # For optional dependencies with defaults, let the functoid handle them

        return self.binding.functoid.call(*resolved_args)


@dataclass
class CreateFactory(ExecutableOp):
    """Operation that creates a Factory instance for assisted injection."""

    factory_key: InstanceKey
    target_type: type
    binding: Binding
    resolve_fn: Any = None  # Will be set during execution

    def key(self) -> InstanceKey:
        """Get the DIKey this operation produces."""
        return self.factory_key

    def dependencies(self) -> list[InstanceKey]:
        """Get the dependencies this operation requires."""
        # For factory operations, we only require dependencies that can be resolved from the container
        # Dependencies for assisted injection are handled at factory.create() time
        return []  # Factory operations should not require any upfront dependencies

    def execute(self, resolved_deps: dict[InstanceKey, Any]) -> Any:  # noqa: ARG002
        """Execute by creating a Factory instance."""
        from ..factory import Factory

        # Create a locator-like object that uses a resolve function
        class ResolverLocator:
            def __init__(self, resolve_fn: Any):
                self._resolve_fn = resolve_fn

            def get(self, key: Any) -> Any:  # noqa: A002
                return self._resolve_fn(key)

        # Use the resolve function provided during execution
        locator = ResolverLocator(self.resolve_fn) if self.resolve_fn else None
        return Factory(self.target_type, locator, self.binding.functoid)  # pyright: ignore[reportUnknownVariableType]


@dataclass
class Lookup(ExecutableOp):
    """Operation that looks up an existing binding and exposes it with a new key."""

    lookup_key: InstanceKey
    source_key: InstanceKey
    set_key: InstanceKey | None = None
    is_weak: bool = False

    def key(self) -> InstanceKey:
        """Get the DIKey this operation produces."""
        return self.lookup_key

    def dependencies(self) -> list[InstanceKey]:
        """Get the dependencies this operation requires."""
        return [self.source_key]

    def execute(self, resolved_deps: dict[InstanceKey, Any]) -> Any:
        """Execute by passing through the resolved dependency."""
        return resolved_deps[self.source_key]


@dataclass
class CreateSet(ExecutableOp):
    """Operation that creates a set by collecting all set element bindings."""

    set_key: InstanceKey
    element_keys: list[InstanceKey]

    def key(self) -> InstanceKey:
        """Get the DIKey this operation produces."""
        return self.set_key

    def dependencies(self) -> list[InstanceKey]:
        """Get the dependencies this operation requires."""
        return self.element_keys

    def execute(self, resolved_deps: dict[InstanceKey, Any]) -> Any:  # noqa: ARG002
        """Execute by collecting all resolved set elements."""
        elements: set[Any] = set()
        for element_key in self.element_keys:
            if element_key in resolved_deps:
                elements.add(resolved_deps[element_key])
        return elements
