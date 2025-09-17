"""
DIKey implementation for dependency injection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


class Id:
    """Annotation for named dependencies using typing.Annotated."""

    def __init__(self, value: str):
        self.value = value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Id) and self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __repr__(self) -> str:
        return f"Id({self.value!r})"


@dataclass(frozen=True)
class DIKey:
    """A key that identifies a specific dependency in the object graph."""

    target_type: type
    name: str | None = None

    @classmethod
    def get(cls, target_type: type[T], name: str | None = None) -> DIKey:
        """Create a DIKey for the given type and optional name."""
        return cls(target_type, name)

    def __str__(self) -> str:
        name_str = f" {self.name}" if self.name else ""
        type_name = getattr(self.target_type, "__name__", str(self.target_type))
        return f"{type_name}{name_str}"

    def __hash__(self) -> int:
        return hash((self.target_type, self.name))
