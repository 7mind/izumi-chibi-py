"""
DIKey implementation for dependency injection.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
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
class DIKey(ABC):
    """Abstract base class for dependency injection keys."""

    @abstractmethod
    def __str__(self) -> str:
        """Return string representation of the key."""

    @abstractmethod
    def __hash__(self) -> int:
        """Return hash of the key."""

    @classmethod
    def of(cls, target_type: type[T], name: str | None = None) -> InstanceKey:
        return InstanceKey.of(target_type, name)

@dataclass(frozen=True)
class InstanceKey(DIKey):
    """A key that identifies a specific dependency in the object graph."""

    target_type: type
    name: str | None = None

    @classmethod
    def of(cls, target_type: type[T], name: str | None = None) -> InstanceKey:
        """Create a DIKey for the given type and optional name."""
        return cls(target_type, name)

    def __str__(self) -> str:
        name_str = f" {self.name}" if self.name else ""
        type_name = getattr(self.target_type, "__name__", str(self.target_type))
        return f"{type_name}{name_str}"

    def __hash__(self) -> int:
        return hash((self.target_type, self.name))


@dataclass(frozen=True)
class SetElementKey(DIKey):
    """A key that identifies a specific element within a set binding."""

    set_key: InstanceKey
    element_key: InstanceKey

    def __str__(self) -> str:
        return f"{self.set_key}[{self.element_key}]"

    def __hash__(self) -> int:
        return hash((self.set_key, self.element_key))
