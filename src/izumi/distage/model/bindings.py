"""
Binding definitions and types for Chibi Izumi.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..activation import Activation
from .keys import InstanceKey, SetElementKey

if TYPE_CHECKING:
    from ..functoid import Functoid


@dataclass(frozen=True)
class Binding:
    """A dependency injection binding."""

    key: InstanceKey | SetElementKey
    functoid: Functoid[Any]
    activation_tags: set[Any] | None = None  # Use Any to avoid circular import issues
    is_factory: bool = False  # Flag to indicate if this is a Factory[T] binding
    is_weak: bool = False  # Flag to indicate if this is a weak reference binding

    def __post_init__(self) -> None:
        if self.activation_tags is None:
            object.__setattr__(self, "activation_tags", set())

    def matches_activation(self, activation: Activation) -> bool:
        """Check if this binding matches the given activation."""
        if not self.activation_tags:
            return True  # Untagged bindings match any activation

        return activation.is_compatible_with_tags(self.activation_tags)

    def __str__(self) -> str:
        # Extract name from the functoid for display
        if self.functoid.original_class is not None:
            impl_name = getattr(
                self.functoid.original_class, "__name__", str(self.functoid.original_class)
            )
        elif self.functoid.original_func is not None:
            impl_name = getattr(
                self.functoid.original_func, "__name__", str(self.functoid.original_func)
            )
        elif self.functoid.original_value is not None:
            impl_name = str(self.functoid.original_value)
        elif self.functoid.original_target_type is not None:
            impl_name = getattr(
                self.functoid.original_target_type,
                "__name__",
                str(self.functoid.original_target_type),
            )
        else:
            impl_name = str(self.functoid)

        tags_str = (
            f" {{{', '.join(str(tag) for tag in self.activation_tags)}}}"
            if self.activation_tags
            else ""
        )
        functoid_repr = repr(self.functoid)
        return f"{self.key} -> {impl_name}{tags_str} ({functoid_repr})"
