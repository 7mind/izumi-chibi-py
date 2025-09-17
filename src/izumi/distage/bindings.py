"""
Binding definitions and types for Chibi Izumi.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .activation import Activation
from .keys import DIKey


class BindingType(Enum):
    """Types of bindings supported."""

    CLASS = "class"
    INSTANCE = "instance"
    FACTORY = "factory"
    SET_ELEMENT = "set_element"


@dataclass(frozen=True)
class Binding:
    """A dependency injection binding."""

    key: DIKey
    binding_type: BindingType
    implementation: type | Any | Callable[..., Any]
    activation_tags: set[Any] | None = None  # Use Any to avoid circular import issues

    def __post_init__(self) -> None:
        if self.activation_tags is None:
            object.__setattr__(self, "activation_tags", set())

    def matches_activation(self, activation: Activation) -> bool:
        """Check if this binding matches the given activation."""
        if not self.activation_tags:
            return True  # Untagged bindings match any activation

        return activation.is_compatible_with_tags(self.activation_tags)

    def __str__(self) -> str:
        impl_name = getattr(self.implementation, "__name__", str(self.implementation))
        tags_str = (
            f" {{{', '.join(str(tag) for tag in self.activation_tags)}}}"
            if self.activation_tags
            else ""
        )
        return f"{self.key} -> {impl_name}{tags_str} ({self.binding_type.value})"
