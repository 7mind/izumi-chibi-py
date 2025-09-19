"""
Abstract Locator interface and implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, TypeVar

from .model import DIKey, Plan

T = TypeVar("T")


class Locator(ABC):
    """
    Abstract interface for dependency locators.

    A locator is responsible for providing instances of requested types
    based on a validated Plan.
    """

    @abstractmethod
    def has_key_locally(self, key: DIKey) -> bool:
        """Check if this locator has the key in its local instances."""

    @abstractmethod
    def has_key(self, key: DIKey) -> bool:
        """Check if this locator (or its parent chain) has the key."""

    @abstractmethod
    def is_empty(self) -> bool:
        """Check if this is an empty locator."""

    @abstractmethod
    def get(self, key: DIKey) -> Any:
        """
        Get an instance for the given key.

        Args:
            key: The DIKey to resolve

        Returns:
            An instance for the requested key

        Raises:
            ValueError: If no binding exists for the requested key
        """

    @abstractmethod
    def find(self, key: DIKey) -> Any | None:
        """
        Try to get an instance, returning None if not found.

        Args:
            key: The DIKey to resolve

        Returns:
            An instance of the requested type or None if not found
        """

    @abstractmethod
    def has(self, key: DIKey) -> bool:
        """
        Check if an instance can be resolved for the given key.

        Args:
            key: The DIKey to check

        Returns:
            True if the key can be resolved, False otherwise
        """

    @abstractmethod
    def get_instance_count(self) -> int:
        """Get the number of instances currently stored in this locator."""

    @abstractmethod
    def run(self, func: Callable[..., T]) -> T:
        """
        Execute a function with dependency injection.

        Args:
            func: Function to execute with injected dependencies

        Returns:
            The result of the function call
        """

    @abstractmethod
    def plan(self) -> Plan:
        """Get the Plan this Locator is executing."""

    @property
    @abstractmethod
    def parent(self) -> Locator | None:
        """Get the parent locator, if any."""

    @abstractmethod
    def has_parent(self) -> bool:
        """Check if this locator has a parent."""

    @staticmethod
    def empty() -> Locator:
        """
        Create an empty Locator that has no dependencies and can be used as a null object.

        Returns:
            An empty Locator instance
        """
        return LocatorEmpty.instance()


class LocatorEmpty(Locator):
    """
    Empty locator implementation that provides no dependencies.

    This is a singleton that serves as a null object for parent locators.
    """

    _instance: LocatorEmpty | None = None

    def __init__(self) -> None:
        """Private constructor - use instance() instead."""
        if LocatorEmpty._instance is not None:
            raise RuntimeError("LocatorEmpty is a singleton - use instance() method")

    @classmethod
    def instance(cls) -> LocatorEmpty:
        """Get the singleton empty locator instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def has_key_locally(self, key: DIKey) -> bool:  # noqa: ARG002
        """Empty locator has no keys locally."""
        return False

    def has_key(self, key: DIKey) -> bool:  # noqa: ARG002
        """Empty locator has no keys."""
        return False

    def is_empty(self) -> bool:
        """Empty locator is always empty."""
        return True

    def get(self, key: DIKey) -> Any:
        """Empty locator cannot provide any instances."""
        raise ValueError(f"Empty locator cannot provide {key}")

    def find(self, key: DIKey) -> Any | None:  # noqa: ARG002
        """Empty locator cannot find any instances."""
        return None

    def has(self, key: DIKey) -> bool:  # noqa: ARG002
        """Empty locator has no types."""
        return False

    def get_instance_count(self) -> int:
        """Empty locator has no instances."""
        return 0

    def run(self, func: Callable[..., T]) -> T:  # noqa: ARG002
        """Empty locator cannot inject dependencies."""
        raise ValueError("Empty locator cannot execute functions with dependency injection")

    def plan(self) -> Plan:
        """Empty locator has an empty plan."""
        return Plan.empty()

    @property
    def parent(self) -> Locator | None:
        """Empty locator has no parent."""
        return None

    def has_parent(self) -> bool:
        """Empty locator has no parent."""
        return False
