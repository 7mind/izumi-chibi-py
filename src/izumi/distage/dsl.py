"""
Core components for the Chibi Izumi dependency injection framework.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from .functoid import (
    Functoid,
    class_functoid,
    function_functoid,
    set_element_functoid,
    value_functoid,
)
from .model import Binding, InstanceKey, SetElementKey
from .tag import Tag

T = TypeVar("T")


@dataclass(frozen=True)
class ModuleDef:
    """
    A module definition containing bindings for dependency injection.

    Modules are immutable collections of bindings that can be combined
    to form a complete dependency injection configuration.
    """

    bindings: list[Binding]
    lookup_operations: list[Any]

    def __init__(self) -> None:
        # Use object.__setattr__ since we're frozen
        object.__setattr__(self, "bindings", [])
        object.__setattr__(self, "lookup_operations", [])

    def add_binding(self, binding: Binding) -> None:
        """Add a binding to this module."""
        # Since we're frozen, we need to create a new list
        new_bindings = self.bindings + [binding]
        object.__setattr__(self, "bindings", new_bindings)

    def add_lookup_operation(self, lookup_op: Any) -> None:
        """Add a lookup operation to this module."""
        # Since we're frozen, we need to create a new list
        new_lookup_operations = self.lookup_operations + [lookup_op]
        object.__setattr__(self, "lookup_operations", new_lookup_operations)

    def make(self, target_type: type[T] | Any) -> BindingBuilder[T]:
        """Create a binding builder for the given type."""
        return BindingBuilder(target_type, self)

    def many(self, target_type: type[T]) -> SetBindingBuilder[T]:
        """Create a set binding builder for the given type."""
        return SetBindingBuilder(target_type, self)

    def makeSubcontext(self, target_type: type[T]) -> SubcontextBuilder[T]:
        """Create a subcontext builder for the given type."""
        return SubcontextBuilder(target_type, self)


class BindingBuilder[T]:
    """Builder for creating bindings."""

    def __init__(self, target_type: type[T] | Any, module: ModuleDef):
        self._target_type = target_type
        self._module = module
        self._name: str | None = None
        self._tag: Tag | None = None  # Keep for activation system

    def named(self, name: str) -> BindingBuilder[T]:
        """Add a name to this binding."""
        self._name = name
        return self

    def tagged(self, tag: Tag) -> BindingBuilder[T]:
        """Add a tag to this binding (for activation system)."""
        self._tag = tag
        return self

    def aliased(self, alias_key: InstanceKey) -> BindingBuilder[T]:
        """Create an alias for this binding.

        The alias will resolve to the same instance as the original binding.

        Args:
            alias_key: The key that should alias this binding

        Returns:
            The same BindingBuilder for method chaining
        """

        def finalize_with_alias(functoid: Functoid[T]) -> None:
            # Create the original binding
            key = InstanceKey(self._target_type, self._name)

            # Convert tag to activation_tags if it's an AxisChoiceDef
            activation_tags: set[Any] = set()
            if self._tag is not None:
                from .activation import AxisChoiceDef

                if isinstance(self._tag, AxisChoiceDef):
                    activation_tags.add(self._tag)

            # Check if this is a Factory[T] binding
            is_factory = False
            if hasattr(self._target_type, "__origin__"):
                from .factory import Factory

                try:
                    is_factory = self._target_type.__origin__ is Factory  # type: ignore[union-attr]
                except AttributeError:
                    is_factory = False

            # Create the original binding
            binding = Binding(key, functoid, activation_tags, is_factory)
            self._module.add_binding(binding)

            # Create the alias lookup operation
            from .model.operations import Lookup

            alias_lookup = Lookup(alias_key, key, set_key=None, is_weak=False)
            self._module.add_lookup_operation(alias_lookup)

        # Store the modified finalize callback
        self._finalize_callback = finalize_with_alias
        return self

    def using(self) -> UsingBuilder[T]:
        """Create a UsingBuilder for fluent binding configuration."""

        def finalize_binding(functoid: Functoid[T]) -> None:
            if hasattr(self, "_finalize_callback"):
                # Use the modified callback if aliased() was called
                self._finalize_callback(functoid)
            else:
                # Original finalize logic
                key = InstanceKey(self._target_type, self._name)

                # Convert tag to activation_tags if it's an AxisChoiceDef
                activation_tags: set[Any] = set()
                if self._tag is not None:
                    from .activation import AxisChoiceDef

                    if isinstance(self._tag, AxisChoiceDef):
                        activation_tags.add(self._tag)

                # Check if this is a Factory[T] binding
                is_factory = False
                if hasattr(self._target_type, "__origin__"):
                    from .factory import Factory

                    try:
                        is_factory = self._target_type.__origin__ is Factory  # type: ignore[union-attr]
                    except AttributeError:
                        is_factory = False

                # Create binding with the functoid
                binding = Binding(key, functoid, activation_tags, is_factory)
                self._module.add_binding(binding)

        return UsingBuilder(self._target_type, finalize_binding)


class SetBindingBuilder[T]:
    """Builder for creating set bindings."""

    def __init__(self, target_type: type[T], module: ModuleDef):
        self._target_type = target_type
        self._module = module
        self._element_counter = 0

    def _generate_element_name(self) -> str:
        """Generate a unique name for set element."""
        name = f"set-element-{self._element_counter}"
        self._element_counter += 1
        return name

    def add(self, instance: T) -> SetBindingBuilder[T]:
        """Add an instance to the set (backward compatibility)."""
        return self.add_value(instance)

    def add_value(self, instance: T) -> SetBindingBuilder[T]:
        """Add a value instance to the set."""
        set_key = InstanceKey(set[self._target_type], None)  # type: ignore[name-defined]
        element_key = InstanceKey(self._target_type, self._generate_element_name())
        key = SetElementKey(set_key, element_key)
        functoid = set_element_functoid(value_functoid(instance))
        binding = Binding(key, functoid)
        self._module.add_binding(binding)
        return self

    def add_type(self, cls: type[T]) -> SetBindingBuilder[T]:
        """Add a class type to the set (will be instantiated)."""
        set_key = InstanceKey(set[self._target_type], None)  # type: ignore[name-defined]
        element_key = InstanceKey(self._target_type, self._generate_element_name())
        key = SetElementKey(set_key, element_key)
        functoid = set_element_functoid(class_functoid(cls))
        binding = Binding(key, functoid)
        self._module.add_binding(binding)
        return self

    def add_func(self, factory: Callable[..., T]) -> SetBindingBuilder[T]:
        """Add a factory function to the set."""
        set_key = InstanceKey(set[self._target_type], None)  # type: ignore[name-defined]
        element_key = InstanceKey(self._target_type, self._generate_element_name())
        key = SetElementKey(set_key, element_key)
        functoid = set_element_functoid(function_functoid(factory))
        binding = Binding(key, functoid)
        self._module.add_binding(binding)
        return self

    def ref(self, source_key: InstanceKey) -> SetBindingBuilder[T]:
        """Add a reference to an existing binding to the set."""
        from .model.operations import Lookup

        set_key = InstanceKey(set[self._target_type], None)  # type: ignore[name-defined]
        element_key = InstanceKey(self._target_type, self._generate_element_name())
        lookup_operation = Lookup(element_key, source_key, set_key)

        # Add the lookup operation to the module
        self._module.add_lookup_operation(lookup_operation)

        return self

    def weak(self, source_key: InstanceKey) -> SetBindingBuilder[T]:
        """Add a weak reference to an existing binding to the set.

        Weak references only remain in the graph if there are non-weak references to the same binding.
        """
        from .model.operations import Lookup

        set_key = InstanceKey(set[self._target_type], None)  # type: ignore[name-defined]
        element_key = InstanceKey(self._target_type, self._generate_element_name())
        lookup_operation = Lookup(element_key, source_key, set_key, is_weak=True)

        # Add the lookup operation to the module
        self._module.add_lookup_operation(lookup_operation)

        return self


class UsingBuilder[T]:
    """Builder for creating functoid-based bindings with a fluent API."""

    def __init__(self, target_type: type[T], finalize_callback: Callable[[Functoid[T]], None]):
        self._target_type = target_type
        self._finalize_callback = finalize_callback

    def value(self, instance: T) -> None:
        """Bind to a specific instance value."""
        functoid = value_functoid(instance)
        self._finalize_callback(functoid)

    def type(self, cls: type[T]) -> None:
        """Bind to a class that will be instantiated."""
        functoid = class_functoid(cls)
        self._finalize_callback(functoid)

    def func(self, factory: Callable[..., T]) -> None:
        """Bind to a factory function."""
        functoid = function_functoid(factory)
        self._finalize_callback(functoid)

    def factory_type(self, target_class: type[T]) -> None:  # type: ignore[valid-type]
        """Bind to a Factory[T] that creates class instances on-demand."""
        functoid: Functoid[T] = class_functoid(target_class)
        self._finalize_callback(functoid)

    def factory_func(self, factory_function: Callable[..., T]) -> None:
        """Bind to a Factory[T] that creates instances using a factory function on-demand."""
        functoid: Functoid[T] = function_functoid(factory_function)
        self._finalize_callback(functoid)


class SubcontextBuilder[T]:
    """Builder for creating subcontext bindings."""

    def __init__(self, target_type: type[T], module: ModuleDef):
        self._target_type = target_type
        self._module = module
        self._name: str | None = None
        self._submodule: ModuleDef | None = None
        self._local_dependency_keys: list[InstanceKey] = []
        self._finalized = False

    def named(self, name: str) -> SubcontextBuilder[T]:
        """Add a name to this subcontext binding."""
        self._name = name
        return self

    def withSubmodule(self, submodule: ModuleDef) -> SubcontextBuilder[T]:
        """Add a submodule with additional bindings for this subcontext."""
        self._submodule = submodule
        return self

    def localDependency(
        self, dependency_type: type, name: str | None = None
    ) -> SubcontextBuilder[T]:
        """Declare a local dependency that will be provided at runtime."""
        dependency_key = InstanceKey(dependency_type, name)
        self._local_dependency_keys.append(dependency_key)
        return self

    def __enter__(self) -> SubcontextBuilder[T]:
        """Support context manager syntax for finalizing the subcontext."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Finalize the subcontext binding when exiting context manager."""
        self._finalize()

    def __del__(self) -> None:
        """Auto-finalize when the builder is garbage collected."""
        if not self._finalized:
            self._finalize()

    def _finalize(self) -> None:
        """Finalize the subcontext binding."""
        if self._finalized:
            return

        from .subcontext import Subcontext

        # Create the subcontext key
        subcontext_key = InstanceKey(Subcontext, self._name)
        target_key = InstanceKey(self._target_type, None)

        # Get submodule bindings
        submodule_bindings = self._submodule.bindings if self._submodule else []

        # Determine parent dependencies by analyzing the submodule
        parent_dependencies: list[InstanceKey] = []
        if self._submodule:
            # Find all dependencies of the submodule that are not local dependencies
            # and are not satisfied within the submodule itself
            from .model.graph import DependencyGraph

            temp_graph = DependencyGraph()
            for binding in submodule_bindings:
                temp_graph.add_binding(binding)

            temp_graph.generate_operations()
            all_deps: set[InstanceKey] = set()
            operations = temp_graph.get_operations()

            # Get all keys that are provided by the submodule
            submodule_provided_keys = set(operations.keys())

            for operation in operations.values():
                all_deps.update(operation.dependencies())

            local_dep_set = set(self._local_dependency_keys)
            # Parent dependencies are those that are needed but not provided by submodule or local deps
            parent_dependencies = [
                dep
                for dep in all_deps
                if dep not in local_dep_set and dep not in submodule_provided_keys
            ]

        # Create the CreateSubcontext operation
        from .model.operations import CreateSubcontext

        create_subcontext_op = CreateSubcontext(
            subcontext_key=subcontext_key,
            target_key=target_key,
            submodule_bindings=submodule_bindings,
            local_dependency_keys=self._local_dependency_keys,
            parent_dependencies=parent_dependencies,
        )

        # Add the operation to the module
        self._module.add_lookup_operation(create_subcontext_op)
        self._finalized = True
