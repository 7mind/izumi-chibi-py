from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Lifecycle[T]:
    """
    A Lifecycle represents a resource that needs to be acquired and released.

    Both acquire and release can be async functions. The Lifecycle tracks
    whether each function is async for proper handling during execution.
    """

    acquire: Callable[..., T]
    release: Callable[[T], None]

    def is_acquire_async(self) -> bool:
        """Check if acquire is an async function."""
        return inspect.iscoroutinefunction(self.acquire)

    def is_release_async(self) -> bool:
        """Check if release is an async function."""
        return inspect.iscoroutinefunction(self.release)

    @staticmethod
    def make(acquire: Callable[..., T], release: Callable[[T], None]) -> Lifecycle[T]:
        return Lifecycle(acquire=acquire, release=release)

    @staticmethod
    def pure(value: T) -> Lifecycle[T]:
        return Lifecycle(acquire=lambda: value, release=lambda _: None)

    @staticmethod
    def fromFactory(factory: Callable[..., T]) -> Lifecycle[T]:
        return Lifecycle(acquire=factory, release=lambda _: None)
