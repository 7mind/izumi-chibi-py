"""
Factory bindings and assisted injection support for the distage dependency injection system.

This module provides Factory[T] for creating instances on-demand with assisted injection,
allowing users to explicitly opt into non-singleton semantics when necessary.
"""

from __future__ import annotations

from typing import Any, TypeVar

T = TypeVar("T")


class Factory[T]:
    """
    Factory for creating instances of type T with assisted injection.

    The Factory[T] allows creating new instances on-demand, resolving dependencies
    from the DI system while allowing missing dependencies to be provided as arguments.

    Usage:
        factory = injector.produce(injector.plan(planner_input)).get(Factory[SomeClass])
        instance = factory.create(missing_param="value")
    """

    def __init__(self, target_type: type[T], locator: Any, functoid: Any) -> None:
        """
        Initialize the factory.

        Args:
            target_type: The type of objects this factory creates
            locator: The locator for resolving dependencies
            functoid: The functoid to use for creating instances
        """
        self._target_type = target_type
        self._locator = locator
        self._functoid = functoid
        # Get dependencies directly from the functoid
        self._dependency_keys = functoid.keys()
        self._dependencies = functoid.sig()

        # Create mapping from DIKey to parameter name for better error messages
        self._key_to_param_name: dict[Any, str] = {}
        for i, dep in enumerate(self._dependencies):
            if i < len(self._dependency_keys):
                self._key_to_param_name[self._dependency_keys[i]] = dep.name

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
        resolved_args: list[Any] = []
        missing_unnamed_names: list[str] = []
        missing_named: set[str] = set()

        # Try to resolve each dependency from the DI system
        for di_key in self._dependency_keys:
            try:
                # Try to resolve from the DI system
                resolved_value = self._locator.get(di_key)
                resolved_args.append(resolved_value)
            except ValueError:
                # Dependency not available in DI system, needs to be provided
                if di_key.name is None:
                    # Unnamed dependency - will be provided via args
                    # Use parameter name from mapping for better error reporting
                    param_name = self._key_to_param_name.get(
                        di_key, str(di_key.target_type.__name__)
                    )
                    missing_unnamed_names.append(param_name)
                    resolved_args.append(None)  # Placeholder
                else:
                    # Named dependency - will be provided via kwargs
                    missing_named.add(di_key.name)
                    resolved_args.append(None)  # Placeholder

        # Check that we have values for all missing dependencies
        missing_unnamed = len(missing_unnamed_names)
        if len(args) != missing_unnamed:
            if missing_unnamed_names:
                param_names = ", ".join(f"'{name}'" for name in missing_unnamed_names)
                raise ValueError(
                    f"Factory for {self._target_type.__name__} requires {missing_unnamed} "
                    f"positional arguments ({param_names}) but got {len(args)}"
                )
            else:
                raise ValueError(
                    f"Factory for {self._target_type.__name__} requires {missing_unnamed} "
                    f"positional arguments but got {len(args)}"
                )

        # Check for missing named dependencies
        provided_named = set(kwargs.keys())
        missing_required = missing_named - provided_named

        if missing_required:
            missing_names = ", ".join(f"'{name}'" for name in sorted(missing_required))
            raise ValueError(
                f"Factory for {self._target_type.__name__} requires keyword argument {missing_names}"
            )

        # Check for unexpected keyword arguments
        unexpected_kwargs = provided_named - missing_named
        if unexpected_kwargs:
            unexpected_names = ", ".join(sorted(unexpected_kwargs))
            raise TypeError(
                f"Factory for {self._target_type.__name__} got unexpected keyword arguments: "
                f"{unexpected_names}"
            )

        # Fill in the missing dependencies with provided arguments
        arg_index = 0
        for i, di_key in enumerate(self._dependency_keys):
            if resolved_args[i] is None:  # This was a missing dependency
                if di_key.name is None:
                    # Unnamed dependency - use positional arg
                    resolved_args[i] = args[arg_index]
                    arg_index += 1
                else:
                    # Named dependency - use keyword arg
                    resolved_args[i] = kwargs[di_key.name]

        # Create and return the instance using the functoid
        result = self._functoid.call(*resolved_args)
        return result  # type: ignore[no-any-return]

    def __repr__(self) -> str:
        return f"Factory[{self._target_type.__name__}]"
