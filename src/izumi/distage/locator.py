"""
Locator - Simple dict-based container mapping DIKey to instances.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, TypeVar

from .keys import DIKey
from .plan import Plan

T = TypeVar("T")


class Locator:
    """
    Simple dict-based container mapping DIKey to instances.

    Each Locator represents one execution of a Plan and contains the
    resolved instances for that execution.

    Supports locator inheritance: when a parent locator is provided,
    this locator will check parent locators for missing dependencies.
    """

    def __init__(
        self,
        plan: Plan,
        instances: dict[DIKey, object] | None = None,
        parent: Locator | None = None,
    ):
        """
        Create a new Locator from a Plan and instances.

        Args:
            plan: The validated Plan to execute
            instances: Dict mapping DIKey to instances
            parent: Optional parent locator for dependency inheritance
        """
        self._plan = plan
        self._instances: dict[DIKey, object] = instances or {}
        self._parent = parent

    def get(self, target_type: type[T] | Any, name: str | None = None) -> T:
        """
        Get an instance of the given type, resolving it if not already resolved.

        Args:
            target_type: The type to resolve
            name: Optional name to distinguish between different bindings

        Returns:
            An instance of the requested type

        Raises:
            ValueError: If no binding exists for the requested type
        """
        key = DIKey(target_type, name)
        if key not in self._instances:
            # Try to resolve it on-demand
            if not self._plan.has_binding(key):
                # Check if this is an auto-injectable logger
                from .logger_injection import AutoLoggerManager

                if AutoLoggerManager.should_auto_inject_logger(key):
                    # Create a generic logger using stack introspection
                    import logging

                    from .logger_injection import LoggerLocationIntrospector

                    location_name = LoggerLocationIntrospector.get_logger_location_name()
                    logger = logging.getLogger(location_name)
                    self._instances[key] = logger
                    return logger  # type: ignore[return-value]
                else:
                    # Check parent locator if available
                    if self._parent is not None:
                        try:
                            instance = self._parent.get(target_type, name)
                            # Cache the instance from parent in this locator
                            self._instances[key] = instance
                            return instance  # type: ignore[no-any-return]
                        except ValueError:
                            pass  # Parent doesn't have it either

                    raise ValueError(f"No binding found for {key}")

            # Import here to avoid circular import
            from .resolver import DependencyResolver

            # Create a resolver and resolve this key
            resolver = DependencyResolver(
                self._plan.graph, self._plan.activation, parent_locator=self._parent
            )
            # Pass existing instances to the resolver
            resolver._instances.update(self._instances)  # pyright: ignore[reportPrivateUsage]

            resolver.resolve(key)
            # Update our instances with anything new that was resolved
            self._instances.update(resolver._instances)  # pyright: ignore[reportPrivateUsage]

        return self._instances[key]  # type: ignore[return-value]

    def find(self, target_type: type[T], name: str | None = None) -> T | None:
        """
        Try to get an instance, returning None if not found.

        Args:
            target_type: The type to resolve
            name: Optional name to distinguish between different bindings

        Returns:
            An instance of the requested type, or None if not found
        """
        key = DIKey(target_type, name)
        instance = self._instances.get(key)
        return instance  # type: ignore[return-value]

    def has(self, target_type: type[T], name: str | None = None) -> bool:
        """
        Check if a binding exists for the given type.

        Args:
            target_type: The type to check
            name: Optional name to distinguish between different bindings

        Returns:
            True if a binding exists, False otherwise
        """
        key = DIKey(target_type, name)
        return self._plan.has_binding(key)

    def is_resolved(self, target_type: type[T], name: str | None = None) -> bool:
        """
        Check if an instance has already been resolved.

        Args:
            target_type: The type to check
            name: Optional name to distinguish between different bindings

        Returns:
            True if the instance has been resolved, False otherwise
        """
        key = DIKey(target_type, name)
        return key in self._instances

    def get_instance_count(self) -> int:
        """
        Get the number of instances that have been resolved.

        Returns:
            The number of resolved instances
        """
        return len(self._instances)

    def clear_instances(self) -> None:
        """
        Clear all resolved instances.

        This allows the Locator to be reused to create a fresh set of instances.
        """
        self._instances.clear()

    def run(self, func: Callable[..., T]) -> T:
        """
        Execute a function by automatically resolving its dependencies from this Locator.

        This method introspects the function's signature and automatically resolves
        all required dependencies from the locator, then calls the function with
        the resolved instances.

        Args:
            func: A function whose arguments will be resolved from the locator

        Returns:
            The result returned by the function

        Example:
            ```python
            def my_app(service: MyService, config: Config) -> str:
                return service.process(config.value)

            result = locator.run(my_app)
            ```
        """
        from .introspection import SignatureIntrospector

        # Extract dependencies from the function signature
        dependencies = SignatureIntrospector.extract_from_callable(func)
        kwargs = {}

        # Resolve each dependency from the locator
        for dep in dependencies:
            # Skip Any types which are usually introspection failures
            if (
                hasattr(dep, "type_hint")
                and dep.type_hint is not object
                and (
                    not dep.is_optional
                    or hasattr(dep, "default_value")
                    and dep.default_value == inspect.Parameter.empty
                )
                and (isinstance(dep.type_hint, type) or hasattr(dep.type_hint, "__origin__"))
                and not isinstance(dep.type_hint, str)
            ):
                # Resolve the dependency from this locator
                kwargs[dep.name] = self.get(dep.type_hint, dep.dependency_name)
            # For optional dependencies with defaults, let the function handle them

        return func(**kwargs)

    @property
    def plan(self) -> Plan:
        """Get the Plan this Locator is executing."""
        return self._plan

    @property
    def parent(self) -> Locator | None:
        """Get the parent locator, if any."""
        return self._parent

    def has_parent(self) -> bool:
        """Check if this locator has a parent."""
        return self._parent is not None

    def create_child(self, plan: Plan, instances: dict[DIKey, object] | None = None) -> Locator:
        """
        Create a child locator with this locator as parent.

        Args:
            plan: The Plan for the child locator
            instances: Optional initial instances for the child

        Returns:
            A new Locator with this locator as parent
        """
        return Locator(plan, instances, self)
