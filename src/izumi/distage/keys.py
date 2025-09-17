"""
DIKey implementation for dependency injection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class DIKey:
    """A key that identifies a specific dependency in the object graph."""

    target_type: type
    tag: Any = None

    @classmethod
    def get(cls, target_type: type[T], tag: Any = None) -> DIKey:
        """Create a DIKey for the given type and optional tag."""
        return cls(target_type, tag)

    def __str__(self) -> str:
        tag_str = f" {self.tag}" if self.tag else ""
        type_name = getattr(self.target_type, "__name__", str(self.target_type))
        return f"{type_name}{tag_str}"

    def __hash__(self) -> int:
        return hash((self.target_type, self.tag))
