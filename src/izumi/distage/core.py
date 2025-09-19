"""
Core components for the Chibi Izumi dependency injection framework.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from .bindings import Binding
from .functoid import (
    Functoid,
    class_functoid,
    function_functoid,
    set_element_functoid,
    value_functoid,
)
from .keys import DIKey, SetElementKey
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

    def make(self, target_type: type[T] | Any) -> BindingBuilder[T]:
        """Create a binding builder for the given type."""
        return BindingBuilder(target_type, self)

    def many(self, target_type: type[T]) -> SetBindingBuilder[T]:
        """Create a set binding builder for the given type."""
        return SetBindingBuilder(target_type, self)


class BindingBuilder[T]:
    """Builder for creating bindings."""

    def __init__(self, target_type: type[T] | Any, module: ModuleDef):
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

    def using(self) -> UsingBuilder[T]:
        """Create a UsingBuilder for fluent binding configuration."""

        def finalize_binding(functoid: Functoid[T]) -> None:
            key = DIKey(self._target_type, self._name)

            # Convert tag to activation_tags if it's an AxisChoiceDef
            activation_tags: set[Any] = set()
            if self._tag is not None:
                from .activation import AxisChoiceDef

                if isinstance(self._tag, AxisChoiceDef):
                    activation_tags.add(self._tag)

            # Check if this is a Factory[T] binding
            is_factory = False
            if hasattr(self._target_type, "__origin__"):
                from .factory import Factory

                try:
                    is_factory = self._target_type.__origin__ is Factory  # type: ignore[union-attr]
                except AttributeError:
                    is_factory = False

            # Create binding with the functoid
            binding = Binding(key, functoid, activation_tags, is_factory)
            self._module.add_binding(binding)

        return UsingBuilder(self._target_type, finalize_binding)


class SetBindingBuilder[T]:
    """Builder for creating set bindings."""

    def __init__(self, target_type: type[T], module: ModuleDef):
        self._target_type = target_type
        self._module = module
        self._element_counter = 0

    def _generate_element_name(self) -> str:
        """Generate a unique name for set element."""
        name = f"set-element-{self._element_counter}"
        self._element_counter += 1
        return name

    def add(self, instance: T) -> SetBindingBuilder[T]:
        """Add an instance to the set (backward compatibility)."""
        return self.add_value(instance)

    def add_value(self, instance: T) -> SetBindingBuilder[T]:
        """Add a value instance to the set."""
        set_key = DIKey(set[self._target_type], None)  # type: ignore[name-defined]
        element_key = DIKey(self._target_type, self._generate_element_name())
        key = SetElementKey(set_key, element_key)
        functoid = set_element_functoid(value_functoid(instance))
        binding = Binding(key, functoid)
        self._module.add_binding(binding)
        return self

    def add_type(self, cls: type[T]) -> SetBindingBuilder[T]:
        """Add a class type to the set (will be instantiated)."""
        set_key = DIKey(set[self._target_type], None)  # type: ignore[name-defined]
        element_key = DIKey(self._target_type, self._generate_element_name())
        key = SetElementKey(set_key, element_key)
        functoid = set_element_functoid(class_functoid(cls))
        binding = Binding(key, functoid)
        self._module.add_binding(binding)
        return self

    def add_func(self, factory: Callable[..., T]) -> SetBindingBuilder[T]:
        """Add a factory function to the set."""
        set_key = DIKey(set[self._target_type], None)  # type: ignore[name-defined]
        element_key = DIKey(self._target_type, self._generate_element_name())
        key = SetElementKey(set_key, element_key)
        functoid = set_element_functoid(function_functoid(factory))
        binding = Binding(key, functoid)
        self._module.add_binding(binding)
        return self


class UsingBuilder[T]:
    """Builder for creating functoid-based bindings with a fluent API."""

    def __init__(self, target_type: type[T], finalize_callback: Callable[[Functoid[T]], None]):
        self._target_type = target_type
        self._finalize_callback = finalize_callback

    def value(self, instance: T) -> None:
        """Bind to a specific instance value."""
        functoid = value_functoid(instance)
        self._finalize_callback(functoid)

    def type(self, cls: type[T]) -> None:
        """Bind to a class that will be instantiated."""
        functoid = class_functoid(cls)
        self._finalize_callback(functoid)

    def func(self, factory: Callable[..., T]) -> None:
        """Bind to a factory function."""
        functoid = function_functoid(factory)
        self._finalize_callback(functoid)

    def factory_type(self, target_class: type[T]) -> None:  # type: ignore[valid-type]
        """Bind to a Factory[T] that creates class instances on-demand."""
        functoid: Functoid[T] = class_functoid(target_class)
        self._finalize_callback(functoid)

    def factory_func(self, factory_function: Callable[..., T]) -> None:
        """Bind to a Factory[T] that creates instances using a factory function on-demand."""
        functoid: Functoid[T] = function_functoid(factory_function)
        self._finalize_callback(functoid)
