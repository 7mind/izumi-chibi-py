"""
Factory bindings and assisted injection support for the distage dependency injection system.

This module provides Factory[T] for creating instances on-demand with assisted injection,
allowing users to explicitly opt into non-singleton semantics when necessary.
"""

from __future__ import annotations

import inspect
from typing import Any, TypeVar

from .introspection import DependencyInfo, SignatureIntrospector

T = TypeVar("T")


class Factory[T]:
    """
    Factory for creating instances of type T with assisted injection.

    The Factory[T] allows creating new instances on-demand, resolving dependencies
    from the DI system while allowing missing dependencies to be provided as arguments.

    Usage:
        factory = injector.get(planner_input, Factory[SomeClass])
        instance = factory.create(missing_param="value")
    """

    def __init__(self, target_type: type[T], locator: Any) -> None:
        """
        Initialize the factory.

        Args:
            target_type: The type of objects this factory creates
            locator: The locator for resolving dependencies
        """
        self._target_type = target_type
        self._locator = locator
        self._dependencies = SignatureIntrospector.extract_dependencies(target_type)

    def create(self, *args: Any, **kwargs: Any) -> T:
        """
        Create a new instance of T with assisted injection.

        Dependencies are resolved from the DI system first. If any dependencies
        are missing, they must be provided as arguments:
        - Unnamed dependencies are provided through positional args
        - Named dependencies are provided through keyword args

        Args:
            *args: Values for unnamed dependencies that couldn't be resolved
            **kwargs: Values for named dependencies that couldn't be resolved

        Returns:
            A new instance of type T

        Raises:
            ValueError: If required dependencies are missing and not provided
            TypeError: If provided arguments don't match expected dependencies
        """
        resolved_kwargs: dict[str, Any] = {}
        missing_unnamed: list[DependencyInfo] = []
        missing_named: dict[str, DependencyInfo] = {}

        # Try to resolve each dependency from the DI system
        for dep in self._dependencies:
            # Skip dependencies with 'Any' type hint as they're usually introspection failures
            if dep.type_hint == Any:
                continue

            if (not dep.is_optional or dep.default_value == inspect.Parameter.empty) and isinstance(
                dep.type_hint, type
            ):
                try:
                    # Try to resolve from the DI system
                    resolved_kwargs[dep.name] = self._locator.get(
                        dep.type_hint, dep.dependency_name
                    )
                except ValueError:
                    # Dependency not available in DI system, needs to be provided
                    if dep.dependency_name is None:
                        # Unnamed dependency - will be provided via args
                        missing_unnamed.append(dep)
                    else:
                        # Named dependency - will be provided via kwargs
                        missing_named[dep.dependency_name] = dep
            elif dep.is_optional and dep.default_value != inspect.Parameter.empty:
                # Use default value for optional dependencies
                resolved_kwargs[dep.name] = dep.default_value

        # Handle missing unnamed dependencies through positional args
        if len(args) != len(missing_unnamed) and missing_unnamed:
            dep_names = [dep.name for dep in missing_unnamed]
            raise ValueError(
                f"Factory for {self._target_type.__name__} requires {len(missing_unnamed)} "
                f"positional arguments for dependencies {dep_names}, but {len(args)} were provided"
            )

        for i, dep in enumerate(missing_unnamed):
            resolved_kwargs[dep.name] = args[i]

        # Handle missing named dependencies through keyword args
        for dep_name, dep in missing_named.items():
            if dep_name not in kwargs:
                raise ValueError(
                    f"Factory for {self._target_type.__name__} requires keyword argument "
                    f"'{dep_name}' for dependency '{dep.name}'"
                )
            resolved_kwargs[dep.name] = kwargs[dep_name]

        # Check for unexpected keyword arguments
        unexpected_kwargs = set(kwargs.keys()) - set(missing_named.keys())
        if unexpected_kwargs:
            raise TypeError(
                f"Factory for {self._target_type.__name__} got unexpected keyword arguments: "
                f"{', '.join(unexpected_kwargs)}"
            )

        # Create and return the instance
        return self._target_type(**resolved_kwargs)

    def __repr__(self) -> str:
        return f"Factory[{self._target_type.__name__}]"


class FactoryImpl[T]:
    """Implementation for Factory[T] bindings in the DI system."""

    def __init__(self, target_type: type[T]) -> None:
        """
        Initialize the factory implementation.

        Args:
            target_type: The type that the factory should create
        """
        self.target_type = target_type

    def create_factory(self, locator: Any) -> Factory[T]:
        """
        Create a factory instance with the given locator.

        Args:
            locator: The locator for dependency resolution

        Returns:
            A Factory[T] instance
        """
        return Factory(self.target_type, locator)

    def __repr__(self) -> str:
        return f"FactoryImpl[{self.target_type.__name__}]"
