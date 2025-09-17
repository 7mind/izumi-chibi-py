"""
Core components for the Chibi Izumi dependency injection framework.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from .bindings import Binding, BindingType
from .keys import DIKey
from .tag import Tag

T = TypeVar("T")


@dataclass(frozen=True)
class ModuleDef:
    """
    A module definition containing bindings for dependency injection.

    Modules are immutable collections of bindings that can be combined
    to form a complete dependency injection configuration.
    """

    bindings: list[Binding]

    def __init__(self) -> None:
        # Use object.__setattr__ since we're frozen
        object.__setattr__(self, "bindings", [])

    def add_binding(self, binding: Binding) -> None:
        """Add a binding to this module."""
        # Since we're frozen, we need to create a new list
        new_bindings = self.bindings + [binding]
        object.__setattr__(self, "bindings", new_bindings)

    def make(self, target_type: type[T]) -> BindingBuilder[T]:
        """Create a binding builder for the given type."""
        return BindingBuilder(target_type, self)

    def many(self, target_type: type[T]) -> SetBindingBuilder[T]:
        """Create a set binding builder for the given type."""
        return SetBindingBuilder(target_type, self)


class BindingBuilder[T]:
    """Builder for creating bindings."""

    def __init__(self, target_type: type[T], module: ModuleDef):
        self._target_type = target_type
        self._module = module
        self._name: str | None = None
        self._tag: Tag | None = None  # Keep for activation system

    def named(self, name: str) -> BindingBuilder[T]:
        """Add a name to this binding."""
        self._name = name
        return self

    def tagged(self, tag: Tag) -> BindingBuilder[T]:
        """Add a tag to this binding (for activation system)."""
        self._tag = tag
        return self

    def using(self, implementation: T | type[T] | Callable[[], T]) -> None:
        """Bind to a specific implementation, instance, or factory."""
        key = DIKey(self._target_type, self._name)

        # Convert tag to activation_tags if it's an AxisChoiceDef
        activation_tags: set[Any] = set()
        if self._tag is not None:
            from .activation import AxisChoiceDef

            if isinstance(self._tag, AxisChoiceDef):
                activation_tags.add(self._tag)

        if isinstance(implementation, type):
            # Class binding
            binding = Binding(key, BindingType.CLASS, implementation, activation_tags)
        elif callable(implementation) and not isinstance(implementation, type):
            # Factory binding
            binding = Binding(key, BindingType.FACTORY, implementation, activation_tags)
        else:
            # Instance binding
            binding = Binding(key, BindingType.INSTANCE, implementation, activation_tags)

        self._module.add_binding(binding)


class SetBindingBuilder[T]:
    """Builder for creating set bindings."""

    def __init__(self, target_type: type[T], module: ModuleDef):
        self._target_type = target_type
        self._module = module

    def add(self, instance: T) -> SetBindingBuilder[T]:
        """Add an instance to the set."""
        # Create a set binding key
        key = DIKey(set[self._target_type], None)  # type: ignore[name-defined]
        binding = Binding(key, BindingType.SET_ELEMENT, instance)
        self._module.add_binding(binding)
        return self


class FactoryBindingBuilder[T]:
    """Builder for creating factory bindings."""

    def __init__(self, factory_type: type[T], module: ModuleDef):
        self._factory_type = factory_type
        self._module = module

    def from_factory(self, factory_impl: type[T]) -> None:
        """Bind the factory to a specific implementation."""
        key = DIKey(self._factory_type, None)
        binding = Binding(key, BindingType.FACTORY, factory_impl)
        self._module.add_binding(binding)
