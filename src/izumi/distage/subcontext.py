"""
Subcontext implementation for dynamically resolved dependencies.

Subcontexts allow creating isolated dependency scopes where some dependencies
are provided at runtime rather than during initial graph construction.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from .injector import Injector
from .model.bindings import Binding
from .model.keys import InstanceKey

T = TypeVar("T")


class Subcontext:
    """
    A Subcontext allows creating isolated dependency scopes where some dependencies
    are provided at runtime rather than during initial graph construction.

    This is useful for scenarios where certain contextual data (like RequestId)
    becomes available later in the application lifecycle.
    """

    def __init__(
        self,
        target_key: InstanceKey,
        submodule_bindings: list[Binding],
        local_dependency_keys: list[InstanceKey],
        parent_resolved_deps: dict[InstanceKey, Any],
    ):
        self.target_key = target_key
        self.submodule_bindings = submodule_bindings
        self.local_dependency_keys = local_dependency_keys
        self.parent_resolved_deps = parent_resolved_deps.copy()
        self._local_deps: dict[InstanceKey, Any] = {}

    def provide(self, key: InstanceKey, instance: Any) -> Subcontext:
        """
        Provide a local dependency instance for this subcontext.

        Args:
            key: The dependency key to provide
            instance: The instance to provide for this key

        Returns:
            A new Subcontext with the provided dependency
        """
        new_subcontext = Subcontext(
            target_key=self.target_key,
            submodule_bindings=self.submodule_bindings,
            local_dependency_keys=self.local_dependency_keys,
            parent_resolved_deps=self.parent_resolved_deps,
        )
        new_subcontext._local_deps = self._local_deps.copy()
        new_subcontext._local_deps[key] = instance
        return new_subcontext

    def provide_value(self, instance: Any) -> Subcontext:
        """
        Provide a local dependency instance by its type (for convenience).

        Args:
            instance: The instance to provide (key inferred from type)

        Returns:
            A new Subcontext with the provided dependency
        """
        key = InstanceKey(type(instance), None)  # pyright: ignore[reportUnknownArgumentType]
        return self.provide(key, instance)

    def produce_run(self, fn: Callable[[Any], T]) -> T:
        """
        Run a function within this subcontext, providing all dependencies.

        Args:
            fn: Function to run with the target component as argument

        Returns:
            The result of the function
        """
        # Check that all local dependencies are provided
        missing_deps: list[InstanceKey] = []
        for local_key in self.local_dependency_keys:
            if local_key not in self._local_deps:
                missing_deps.append(local_key)  # pyright: ignore[reportUnknownMemberType]

        if missing_deps:
            missing_str = ", ".join(str(key) for key in missing_deps)  # pyright: ignore[reportUnknownArgumentType,reportUnknownVariableType]
            raise ValueError(f"Missing local dependencies: {missing_str}")

        # Create a mini-injector for the submodule with combined dependencies
        from .dsl import ModuleDef

        submodule = ModuleDef()
        for binding in self.submodule_bindings:
            submodule.add_binding(binding)

        # Add local dependencies as value bindings to the submodule
        for local_key, local_instance in self._local_deps.items():
            if local_key.name is not None:
                submodule.make(local_key.target_type).named(local_key.name).using().value(  # pyright: ignore[reportUnknownMemberType]
                    local_instance
                )
            else:
                submodule.make(local_key.target_type).using().value(local_instance)  # pyright: ignore[reportUnknownMemberType]

        # Add parent dependencies as value bindings to the submodule
        for parent_key, parent_instance in self.parent_resolved_deps.items():
            if parent_key.name is not None:
                submodule.make(parent_key.target_type).named(parent_key.name).using().value(  # pyright: ignore[reportUnknownMemberType]
                    parent_instance
                )
            else:
                submodule.make(parent_key.target_type).using().value(parent_instance)  # pyright: ignore[reportUnknownMemberType]

        # Find the actual target key in the submodule
        actual_target_key = None
        for binding in self.submodule_bindings:
            if (
                isinstance(binding.key, InstanceKey)
                and binding.key.target_type == self.target_key.target_type
            ):
                actual_target_key = binding.key
                break

        if actual_target_key is None:
            binding_keys = [str(binding.key) for binding in self.submodule_bindings]
            raise ValueError(
                f"Target type {self.target_key.target_type} not found in submodule bindings. "
                f"Available bindings: {binding_keys}"
            )

        # Create a simple injector and plan since all dependencies are now in the submodule
        injector = Injector()
        plan = injector.plan([actual_target_key], submodule)
        locator = injector.produce(plan)

        # Get the target component and run the function
        target_instance = locator.get(actual_target_key)
        return fn(target_instance)

    def produce(self) -> Any:
        """
        Create the target component with all dependencies resolved.

        Returns:
            The target component instance
        """
        return self.produce_run(lambda x: x)

    def __str__(self) -> str:
        """String representation of the subcontext."""
        local_deps_str = ", ".join(str(key) for key in self.local_dependency_keys)
        provided_deps_str = ", ".join(str(key) for key in self._local_deps)
        return f"Subcontext[{self.target_key}](local_deps=[{local_deps_str}], provided=[{provided_deps_str}])"

    def __repr__(self) -> str:
        """Detailed representation of the subcontext."""
        return str(self)
