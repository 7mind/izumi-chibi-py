from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Lifecycle[T]:
    acquire: Callable[..., T]
    release: Callable[[T], None]

    @staticmethod
    def make(acquire: Callable[..., T], release: Callable[[T], None]) -> Lifecycle[T]:
        return Lifecycle(acquire=acquire, release=release)

    @staticmethod
    def pure(value: T) -> Lifecycle[T]:
        return Lifecycle(acquire=lambda: value, release=lambda _: None)

    @staticmethod
    def fromFactory(factory: Callable[..., T]) -> Lifecycle[T]:
        return Lifecycle(acquire=factory, release=lambda _: None)
