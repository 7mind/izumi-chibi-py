"""
Functoid - generalized dependency injection provider with runtime introspection.

Functoid[T] is a generalization of function taking zero or more arguments and returning T.
These functions can be introspected at runtime to discover their dependencies.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from .introspection import SignatureIntrospector
from .model import InstanceKey

T = TypeVar("T")


class Functoid[T]:
    """
    A generalized dependency injection provider that can be introspected at runtime.

    A Functoid[T] is a generalization of a function that:
    - Takes zero or more arguments and returns T
    - Can be introspected to discover its dependencies via .keys()
    - Can be called with arbitrary arguments via .call()
    """

    def __init__(
        self,
        keys_fn: Callable[[], list[InstanceKey]],
        sig_fn: Callable[[], list[Any]],  # Returns list[DependencyInfo]
        call_fn: Callable[..., T],
        name: str | None = None,
        # Store original objects for special handling when needed
        original_value: Any = None,
        original_class: type | None = None,
        original_func: Callable[..., Any] | None = None,
        original_target_type: type | None = None,
    ):
        """
        Create a functoid with the given keys and call functions.

        Args:
            keys_fn: Function that returns the list of DIKey dependencies
            sig_fn: Function that returns the list of DependencyInfo with parameter names
            call_fn: Function that performs the actual work when called
            name: Optional name for debugging/display purposes
            original_*: Store original objects for special handling (e.g., dependency resolution)
        """
        self._keys_fn = keys_fn
        self._sig_fn = sig_fn
        self._call_fn = call_fn
        self._name = name
        self.original_value = original_value
        self.original_class = original_class
        self.original_func = original_func
        self.original_target_type = original_target_type

    def keys(self) -> list[InstanceKey]:
        """Return a list of DIKey dependencies that this functoid requires."""
        return self._keys_fn()

    def sig(self) -> list[Any]:  # Returns list[DependencyInfo]
        """Return a list of DependencyInfo with parameter names for this functoid."""
        return self._sig_fn()

    def call(self, *args: Any, **kwargs: Any) -> T:
        """Call the underlying function with the provided arguments."""
        return self._call_fn(*args, **kwargs)

    def __repr__(self) -> str:
        name = self._name or "Functoid"
        return f"{name}({self._call_fn!r})"


# Factory functions for creating functoids
def value_functoid[T](value: T) -> Functoid[T]:
    """Create a functoid that returns a concrete value."""
    return Functoid(
        keys_fn=lambda: [],  # No dependencies
        sig_fn=lambda: [],  # No dependencies
        call_fn=lambda *_args, **_kwargs: value,  # Always return the value
        name="ValueFunctoid",
        original_value=value,
    )


def class_functoid[T](cls: type[T]) -> Functoid[T]:
    """Create a functoid that instantiates a class."""
    dependencies = SignatureIntrospector.extract_from_class(cls)

    return Functoid(
        keys_fn=lambda: SignatureIntrospector.get_binding_keys(dependencies),
        sig_fn=lambda: dependencies,
        call_fn=lambda *args, **kwargs: cls(*args, **kwargs),
        name=f"ClassFunctoid({cls.__name__})",
        original_class=cls,
    )


def function_functoid[T](func: Callable[..., T]) -> Functoid[T]:
    """Create a functoid that calls a function."""
    dependencies = SignatureIntrospector.extract_from_callable(func)

    return Functoid(
        keys_fn=lambda: SignatureIntrospector.get_binding_keys(dependencies),
        sig_fn=lambda: dependencies,
        call_fn=func,
        name=f"FunctionFunctoid({func.__name__})",
        original_func=func,
    )


def set_element_functoid[T](inner_functoid: Functoid[T]) -> Functoid[T]:
    """Create a functoid for set element bindings that wraps other functoids."""
    return Functoid(
        keys_fn=inner_functoid.keys,  # Delegate to inner functoid
        sig_fn=inner_functoid.sig,  # Delegate to inner functoid
        call_fn=inner_functoid.call,  # Delegate to inner functoid
        name=f"SetElementFunctoid({inner_functoid})",
        # Copy original attributes from inner functoid
        original_value=inner_functoid.original_value,
        original_class=inner_functoid.original_class,
        original_func=inner_functoid.original_func,
        original_target_type=inner_functoid.original_target_type,
    )


def lifecycle_functoid(lifecycle: Any) -> Functoid[Any]:
    """Create a functoid from a Lifecycle resource."""
    from .lifecycle import Lifecycle

    assert isinstance(lifecycle, Lifecycle), f"Expected Lifecycle, got {type(lifecycle)}"

    dependencies = SignatureIntrospector.extract_from_callable(lifecycle.acquire)

    return Functoid(  # pyright: ignore[reportUnknownVariableType]
        keys_fn=lambda: SignatureIntrospector.get_binding_keys(dependencies),
        sig_fn=lambda: dependencies,
        call_fn=lifecycle.acquire,
        name=f"LifecycleFunctoid({lifecycle.acquire.__name__})",
        original_func=lifecycle.acquire,
    )
