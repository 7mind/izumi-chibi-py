"""
Concrete implementation of Locator.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from .locator_base import Locator
from .logger_injection import AutoLoggerManager
from .model import DIKey, InstanceKey, Plan

T = TypeVar("T")


class LocatorImpl(Locator):
    """
    Concrete implementation of Locator that manages instances and resolves dependencies.

    Each LocatorImpl represents one execution of a Plan and contains the
    resolved instances for that execution.

    Supports locator inheritance: when a parent locator is provided,
    this locator will check parent locators for missing dependencies.
    """

    def __init__(
        self,
        plan: Plan,
        instances: dict[DIKey, object],
        parent: Locator,
    ):
        """
        Create a new LocatorImpl from a Plan and instances.

        Args:
            plan: The validated Plan to execute
            instances: Dict mapping DIKey to instances
            parent: Parent locator for dependency inheritance
        """
        self._plan = plan
        self._instances: dict[DIKey, object] = instances or {}
        self._parent = parent

    def has_key_locally(self, key: DIKey) -> bool:
        """Check if this locator has the key in its local instances."""
        return key in self._instances

    def has_key(self, key: DIKey) -> bool:
        """Check if this locator (or its parent chain) has the key."""
        return self.has_key_locally(key) or self._parent.has_key(key)

    def is_empty(self) -> bool:
        """Check if this is an empty locator."""
        return False  # LocatorImpl is never empty

    def get(self, key: DIKey) -> Any:
        """
        Get an instance for the given key, resolving it if not already resolved.

        Args:
            key: The DIKey to resolve

        Returns:
            An instance for the requested key

        Raises:
            ValueError: If no binding exists for the requested key
        """
        if key not in self._instances:
            # Try to resolve it on-demand
            if self._parent.has_key(key):
                return self._parent.get(key)
            elif isinstance(key, InstanceKey) and AutoLoggerManager.should_auto_inject_logger(key):
                # Create a generic logger using stack introspection
                import logging

                from .logger_injection import LoggerLocationIntrospector

                location_name = LoggerLocationIntrospector.get_logger_location_name()
                logger = logging.getLogger(location_name)
                self._instances[key] = logger
                return logger
            else:
                raise ValueError(f"No binding found for {key}")

        return self._instances[key]

    def find(self, key: DIKey) -> Any | None:
        """
        Try to get an instance, returning None if not found.

        Args:
            key: The DIKey to resolve

        Returns:
            An instance of the requested type or None if not found
        """
        try:
            return self.get(key)
        except ValueError:
            return None

    def has(self, key: DIKey) -> bool:
        """
        Check if an instance can be resolved for the given key.

        Args:
            key: The DIKey to check

        Returns:
            True if the key can be resolved, False otherwise
        """
        # Check if already resolved
        if key in self._instances:
            return True

        # Only InstanceKey can be resolved directly
        if not isinstance(key, InstanceKey):
            return False

        # Check if we have a binding for it in the plan
        if self._plan.has_binding(key):
            return True

        # Check if it's an auto-injectable logger
        from .logger_injection import AutoLoggerManager

        if AutoLoggerManager.should_auto_inject_logger(key):
            return True

        # Check parent locator if available
        if not self._parent.is_empty():
            return self._parent.has(key)

        return False

    def get_instance_count(self) -> int:
        """Get the number of instances currently stored in this locator."""
        return len(self._instances)

    def run(self, func: Callable[..., T]) -> T:
        """
        Execute a function with dependency injection.

        Uses the signature of the function to determine what dependencies to inject.

        Args:
            func: Function to execute with injected dependencies

        Returns:
            The result of the function call

        Example:
            def my_app(service: MyService, config: Config) -> str:
                return service.process(config.value)

            result = locator.run(my_app)
        """
        import inspect

        from .introspection import SignatureIntrospector

        # Extract dependency information from the function signature
        dependencies = SignatureIntrospector.extract_from_callable(func)

        # Resolve each dependency
        resolved_args: list[Any] = []
        for dep in dependencies:
            # Skip parameters without proper type hints
            if dep.type_hint == type(None) or dep.type_hint == inspect.Parameter.empty:  # noqa: E721
                continue

            # Skip if type_hint is not a type
            if not isinstance(dep.type_hint, type):
                continue

            dep_key = DIKey.of(dep.type_hint, dep.dependency_name)
            if dep.is_optional and not self.has(dep_key):
                continue  # Skip optional dependencies that can't be resolved

            resolved_args.append(self.get(dep_key))

        return func(*resolved_args)

    def plan(self) -> Plan:
        """Get the Plan this Locator is executing."""
        return self._plan

    @property
    def parent(self) -> Locator | None:
        """Get the parent locator, if any."""
        return self._parent if not self._parent.is_empty() else None

    def has_parent(self) -> bool:
        """Check if this locator has a parent."""
        return not self._parent.is_empty()
