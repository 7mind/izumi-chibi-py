"""
AsyncLocator - Asynchronous version of Locator with automatic resource cleanup.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, TypeVar

from .locator_base import Locator
from .logger_injection import AutoLoggerManager
from .model import DIKey, InstanceKey, Plan

T = TypeVar("T")


class AsyncLocator(Locator):
    """
    Asynchronous version of Locator that supports async dependency execution and
    automatic lifecycle resource cleanup.

    Use this locator as an async context manager to ensure proper cleanup:
        async with injector.produce_async(plan) as locator:
            result = await locator.run(my_async_function)

    Resources are released in reverse order when exiting the context.
    """

    def __init__(
        self,
        plan: Plan,
        instances: dict[DIKey, object],
        parent: Locator,
        lifecycle_resources: list[
            tuple[InstanceKey, Any, Any]
        ],  # [(key, instance, lifecycle), ...]
    ):
        """
        Create a new AsyncLocator from a Plan and instances.

        Args:
            plan: The validated Plan to execute
            instances: Dict mapping DIKey to instances
            parent: Parent locator for dependency inheritance
            lifecycle_resources: List of (key, instance, lifecycle) tuples for cleanup
        """
        self._plan = plan
        self._instances: dict[DIKey, object] = instances or {}
        self._parent = parent
        self._lifecycle_resources = lifecycle_resources
        self._closed = False

    def has_key_locally(self, key: DIKey) -> bool:
        """Check if this locator has the key in its local instances."""
        return key in self._instances

    def has_key(self, key: DIKey) -> bool:
        """Check if this locator (or its parent chain) has the key."""
        return self.has_key_locally(key) or self._parent.has_key(key)

    def is_empty(self) -> bool:
        """Check if this is an empty locator."""
        return False  # AsyncLocator is never empty

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
        if self._closed:
            raise RuntimeError("Cannot access closed AsyncLocator")

        if key not in self._instances:
            # Try to resolve it from parent
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
        except (ValueError, RuntimeError):
            return None

    def has(self, key: DIKey) -> bool:
        """
        Check if an instance can be resolved for the given key.

        Args:
            key: The DIKey to check

        Returns:
            True if the key can be resolved, False otherwise
        """
        if self._closed:
            return False

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

    async def run(self, func: Callable[..., T]) -> T:  # type: ignore[override]
        """
        Execute a function (sync or async) with dependency injection.

        Uses the signature of the function to determine what dependencies to inject.

        Args:
            func: Function to execute with injected dependencies

        Returns:
            The result of the function call

        Example:
            async def my_app(service: MyService, config: Config) -> str:
                return await service.process(config.value)

            async with locator:
                result = await locator.run(my_app)
        """
        if self._closed:
            raise RuntimeError("Cannot run functions on closed AsyncLocator")

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

        # Execute the function (handle both sync and async)
        if inspect.iscoroutinefunction(func):
            return await func(*resolved_args)  # type: ignore[no-any-return]
        else:
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

    async def __aenter__(self) -> AsyncLocator:
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager and release all resources."""
        await self.close()

    async def close(self) -> None:
        """Release all lifecycle resources in reverse order."""
        if self._closed:
            return

        self._closed = True

        # Release resources in reverse order (LIFO)
        for key, instance, lifecycle in reversed(self._lifecycle_resources):
            try:
                # Check if release is async
                if lifecycle.is_release_async():
                    await lifecycle.release(instance)
                else:
                    lifecycle.release(instance)
            except Exception as e:
                # Log but don't fail the cleanup
                import logging

                logging.getLogger(__name__).error(
                    f"Error releasing resource {key}: {e}", exc_info=True
                )
