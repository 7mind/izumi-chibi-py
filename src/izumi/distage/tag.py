"""
Tag implementation for distinguishing between different bindings of the same type.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tag:
    """A tag for distinguishing between different bindings of the same type."""

    name: str

    def __str__(self) -> str:
        return f"@{self.name}"
