"""
Algebraic data structure for binding implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


class Implementation(ABC):
    """Base class for all binding implementations."""

    @abstractmethod
    def get_value(self) -> Any:
        """Get the underlying implementation value."""
        pass


class ImplValue(Implementation):
    """Implementation using a concrete instance value."""

    def __init__(self, value: Any):
        self.value = value

    def get_value(self) -> Any:
        return self.value

    def __repr__(self) -> str:
        return f"ImplValue({self.value!r})"


class ImplClass(Implementation):
    """Implementation using a class that will be instantiated."""

    def __init__(self, cls: type):
        self.cls = cls

    def get_value(self) -> type:
        return self.cls

    def __repr__(self) -> str:
        return f"ImplClass({self.cls!r})"


class ImplFunc(Implementation):
    """Implementation using a factory function."""

    def __init__(self, func: Callable[..., Any]):
        self.func = func

    def get_value(self) -> Callable[..., Any]:
        return self.func

    def __repr__(self) -> str:
        return f"ImplFunc({self.func!r})"


class ImplSetElement(Implementation):
    """Implementation for set element bindings that wraps other implementations."""

    def __init__(self, impl: ImplClass | ImplValue | ImplFunc):
        self.impl = impl

    def get_value(self) -> Any:
        return self.impl.get_value()

    def __repr__(self) -> str:
        return f"ImplSetElement({self.impl!r})"


class ImplFactory(Implementation):
    """Implementation for Factory[T] bindings."""

    def __init__(self, target_type: type):
        self.target_type = target_type

    def get_value(self) -> type:
        """Return the target type for factory creation."""
        return self.target_type

    def __repr__(self) -> str:
        return f"ImplFactory({self.target_type.__name__})"


class UsingBuilder[T]:
    """Builder for creating implementations with a fluent API."""

    def __init__(self, target_type: type[T], finalize_callback: Callable[[Implementation], None]):
        self._target_type = target_type
        self._finalize_callback = finalize_callback

    def value(self, instance: T) -> None:
        """Bind to a specific instance value."""
        impl = ImplValue(instance)
        self._finalize_callback(impl)

    def type(self, cls: type[T]) -> None:
        """Bind to a class that will be instantiated."""
        impl = ImplClass(cls)
        self._finalize_callback(impl)

    def func(self, factory: Callable[..., T]) -> None:
        """Bind to a factory function."""
        impl = ImplFunc(factory)
        self._finalize_callback(impl)

    def factory(self, target_type: type[T]) -> None:  # type: ignore[valid-type]
        """Bind to a Factory[T] that creates instances on-demand."""
        impl = ImplFactory(target_type)
        self._finalize_callback(impl)
