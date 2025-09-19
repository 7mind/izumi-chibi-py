"""
Injector - Stateless dependency injection container that produces Plans from PlannerInput.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from .bindings import Binding
from .functoid import Functoid
from .graph import DependencyGraph
from .introspection import SignatureIntrospector
from .keys import DIKey
from .locator import Locator
from .logger_injection import AutoLoggerManager
from .plan import Plan
from .planner_input import PlannerInput

T = TypeVar("T")


class Injector:
    """
    Stateless dependency injection container that produces Plans from PlannerInput.

    The Injector builds and validates dependency graphs but does not manage
    instances or store state. It produces Plans that can be executed by Locators.

    Supports locator inheritance: when a parent locator is provided, child locators
    will check parent locators for missing dependencies before failing.
    """

    def __init__(self, parent_locator: Locator | None = None):
        """
        Create a new Injector.

        Args:
            parent_locator: Optional parent locator for dependency inheritance.
                           When resolving dependencies, this locator will be checked
                           if dependencies are missing from the current bindings.
        """
        self._parent_locator = parent_locator

    def plan(self, input: PlannerInput) -> Plan:
        """
        Create a validated Plan from a PlannerInput.

        Args:
            input: The PlannerInput containing modules, roots, and activation

        Returns:
            A Plan that can be executed by Locators
        """
        graph = self._build_graph(input)
        topology = graph.get_topological_order()
        return Plan(graph, input.roots, input.activation, topology)

    def produce_run(self, input: PlannerInput, func: Callable[..., T]) -> T:
        """
        Execute a function by automatically resolving its dependencies.

        This method creates a Plan and Locator behind the scenes, then runs the function
        with automatically resolved dependencies.

        Args:
            input: The PlannerInput containing modules, roots, and activation
            func: A function whose arguments will be resolved from the dependency container

        Returns:
            The result returned by the function

        Example:
            ```python
            def my_app(service: MyService, config: Config) -> str:
                return service.process(config.value)

            input = PlannerInput([module])
            result = injector.produce_run(input, my_app)
            ```
        """
        plan = self.plan(input)
        locator = self.produce(plan)
        return locator.run(func)

    def produce(self, plan: Plan) -> Locator:
        """
        Create a Locator by instantiating all dependencies in the Plan.

        Args:
            plan: The validated Plan to execute

        Returns:
            A Locator containing all resolved instances
        """
        instances: dict[DIKey, Any] = {}
        resolving: set[DIKey] = set()

        def resolve_instance(key: DIKey) -> Any:
            """Resolve a dependency and return an instance."""
            # Check if already resolved
            if key in instances:
                return instances[key]

            # Check for circular dependency during resolution
            if key in resolving:
                raise ValueError(f"Circular dependency detected during resolution: {key}")

            resolving.add(key)

            try:
                instance = self._create_instance(key, plan, instances, resolve_instance)
                instances[key] = instance
                return instance
            finally:
                resolving.discard(key)

        # Resolve all dependencies in topological order
        for binding_key in plan.topology:
            if binding_key not in instances:
                resolve_instance(binding_key)

        return Locator(plan, instances, self._parent_locator)

    def get(self, input: PlannerInput, target_type: type[T] | Any, name: str | None = None) -> T:
        """
        Convenience method to resolve a single type.

        This creates a Plan and Locator behind the scenes to resolve a single type.
        Consider using produce_run() for better dependency injection patterns.

        Args:
            input: The PlannerInput containing modules, roots, and activation
            target_type: The type to resolve
            name: Optional name to distinguish between different bindings

        Returns:
            An instance of the requested type
        """
        plan = self.plan(input)
        locator = self.produce(plan)
        return locator.get(target_type, name)  # type: ignore[no-any-return]

    def _build_graph(self, input: PlannerInput) -> DependencyGraph:
        """Build the dependency graph from PlannerInput."""
        graph = DependencyGraph()

        # Add all bindings to the graph first
        for module in input.modules:
            for binding in module.bindings:
                graph.add_binding(binding)

        # Note: Automatic logger injection is handled directly in _instantiate_class and _call_factory

        # Filter bindings based on activation
        if not input.activation.choices:
            # No activation specified, keep all bindings
            pass
        else:
            # Filter bindings that don't match the activation
            graph.filter_bindings_by_activation(input.activation)

        # If we have a parent locator, we need to be more lenient with validation
        # because missing dependencies might be available from the parent
        if self._parent_locator is not None:
            graph.validate_with_parent_locator(self._parent_locator)
        else:
            graph.validate()

        # Validate roots and perform garbage collection if needed
        from .roots import RootsFinder

        RootsFinder.validate_roots(input.roots, graph)

        if not input.roots.is_everything():
            # Perform garbage collection - only keep reachable bindings
            reachable_keys = RootsFinder.find_reachable_keys(input.roots, graph)
            graph.garbage_collect(reachable_keys)

        return graph

    def _create_instance(
        self,
        key: DIKey,
        plan: Plan,
        instances: dict[DIKey, Any],  # noqa: ARG002
        resolve_fn: Callable[[DIKey], Any],
    ) -> Any:
        """Create an instance for the given key."""
        # Handle set bindings
        origin = getattr(key.target_type, "__origin__", None)
        if origin is set:
            return self._resolve_set_binding(key, plan, resolve_fn)

        binding = plan.graph.get_binding(key)
        if not binding:
            # Check if we have set bindings for this type
            set_key = DIKey(key.target_type, key.name)  # Create set key
            set_bindings = plan.graph.get_set_bindings(set_key)
            if set_bindings:
                return self._resolve_set_binding_direct(set_bindings, resolve_fn)

            # Check parent locator if available
            if self._parent_locator is not None:
                try:
                    return self._parent_locator.get(key.target_type, key.name)  # pyright: ignore[reportUnknownVariableType]
                except ValueError:
                    pass  # Parent doesn't have it either, fall through to error

            raise ValueError(f"No binding found for {key}")

        return self._create_from_binding(binding, resolve_fn)

    def _resolve_set_binding(
        self, key: DIKey, plan: Plan, resolve_fn: Callable[[DIKey], Any]
    ) -> set[Any]:
        """Resolve a set binding."""
        set_bindings = plan.graph.get_set_bindings(key)
        return self._resolve_set_binding_direct(set_bindings, resolve_fn)

    def _resolve_set_binding_direct(
        self, set_bindings: list[Binding], resolve_fn: Callable[[DIKey], Any]
    ) -> set[Any]:
        """Resolve set bindings directly from a list of bindings."""
        result_set: set[Any] = set()

        for binding in set_bindings:
            instance = self._create_from_binding(binding, resolve_fn)
            result_set.add(instance)

        return result_set

    def _create_from_binding(self, binding: Binding, resolve_fn: Callable[[DIKey], Any]) -> Any:
        """Create an instance from a specific binding."""
        functoid = binding.functoid

        # Handle factory bindings specially
        if binding.is_factory:
            # For factory bindings, create a Factory[T] instance
            # Extract the target type from Factory[T]
            if isinstance(binding.key, DIKey):
                if (
                    hasattr(binding.key.target_type, "__args__")
                    and binding.key.target_type.__args__  # pyright: ignore[reportUnknownMemberType]
                ):  # pyright: ignore[reportUnknownMemberType]
                    target_type = binding.key.target_type.__args__[0]  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
                    return self._create_factory(target_type, resolve_fn, functoid)  # pyright: ignore[reportUnknownArgumentType]
                else:
                    raise ValueError(f"Invalid Factory binding: {binding.key}")
            else:
                raise ValueError(
                    f"Factory bindings must use DIKey, not SetElementKey: {binding.key}"
                )
        else:
            # For all other functoids, resolve dependencies and call
            return self._call_functoid(functoid, resolve_fn)

    def _create_from_functoid_direct(
        self, functoid: Functoid[Any], resolve_fn: Callable[[DIKey], Any]
    ) -> Any:
        """Create an instance directly from a functoid."""
        return self._call_functoid(functoid, resolve_fn)

    def _call_functoid(self, functoid: Functoid[Any], resolve_fn: Callable[[DIKey], Any]) -> Any:
        """Call a functoid by resolving its dependencies."""
        # Get the functoid's dependencies
        dependency_keys = functoid.keys()

        # If no dependencies, just call it
        if not dependency_keys:
            return functoid.call()

        # For dependencies, we need to resolve them and call with proper parameter mapping
        # Use existing helper methods that handle parameter name mapping correctly
        if functoid.original_class is not None:
            return self._instantiate_class(functoid.original_class, resolve_fn)
        elif functoid.original_func is not None:
            return self._call_factory(functoid.original_func, resolve_fn)
        else:
            # For other cases (like composed functoids), try calling with no args
            return functoid.call()

    def _instantiate_class(
        self, cls: type | Any | Callable[..., Any], resolve_fn: Callable[[DIKey], Any]
    ) -> Any:
        """Instantiate a class by resolving its dependencies."""
        dependencies = SignatureIntrospector.extract_dependencies(cls)
        kwargs = {}

        for dep in dependencies:
            # Skip Any types which are usually introspection failures
            if dep.type_hint == Any:
                continue
            if (
                (not dep.is_optional or dep.default_value == inspect.Parameter.empty)
                and (isinstance(dep.type_hint, type) or hasattr(dep.type_hint, "__origin__"))
                and not isinstance(dep.type_hint, str)
            ):
                # Handle both regular types and generic types (like set[T]), but skip string forward references
                dep_key = DIKey(dep.type_hint, dep.dependency_name)

                # Special handling for automatic logger injection
                if AutoLoggerManager.should_auto_inject_logger(dep_key):
                    # First try to resolve through normal DI, fallback to auto-injection
                    try:
                        kwargs[dep.name] = resolve_fn(dep_key)
                    except ValueError:
                        # Create a class-specific logger as fallback
                        logger_name = f"{cls.__module__}.{cls.__name__}"
                        kwargs[dep.name] = logging.getLogger(logger_name)
                else:
                    kwargs[dep.name] = resolve_fn(dep_key)
            # For optional dependencies with defaults, let the class handle them

        return cls(**kwargs)

    def _call_factory(self, factory: Callable[..., Any], resolve_fn: Callable[[DIKey], Any]) -> Any:
        """Call a factory function by resolving its dependencies."""
        dependencies = SignatureIntrospector.extract_dependencies(factory)
        kwargs = {}

        for dep in dependencies:
            # Skip Any types which are usually introspection failures
            if dep.type_hint == Any:
                continue
            if (
                (not dep.is_optional or dep.default_value == inspect.Parameter.empty)
                and (isinstance(dep.type_hint, type) or hasattr(dep.type_hint, "__origin__"))
                and not isinstance(dep.type_hint, str)
            ):
                # Handle both regular types and generic types (like set[T]), but skip string forward references
                dep_key = DIKey(dep.type_hint, dep.dependency_name)

                # Special handling for automatic logger injection
                if AutoLoggerManager.should_auto_inject_logger(dep_key):
                    # First try to resolve through normal DI, fallback to auto-injection
                    try:
                        kwargs[dep.name] = resolve_fn(dep_key)
                    except ValueError:
                        # For factory functions, use the function name
                        logger_name = f"{factory.__module__}.{factory.__name__}"
                        kwargs[dep.name] = logging.getLogger(logger_name)
                else:
                    kwargs[dep.name] = resolve_fn(dep_key)
            # For optional dependencies with defaults, let the factory handle them

        return factory(**kwargs)

    def _create_factory(
        self, target_type: type, resolve_fn: Callable[[DIKey], Any], functoid: Functoid[Any]
    ) -> Any:
        """Create a Factory[T] instance for the given target type."""
        from .factory import Factory

        # Create a locator-like object that uses the resolve_fn
        class ResolverLocator:
            def __init__(self, resolve_fn: Callable[[DIKey], Any]):
                self._resolve_fn = resolve_fn

            def get(self, target_type: type, name: str | None = None) -> Any:  # noqa: A002
                key = DIKey(target_type, name)
                return self._resolve_fn(key)

        locator = ResolverLocator(resolve_fn)
        return Factory(target_type, locator, functoid)  # pyright: ignore[reportUnknownVariableType]

    @classmethod
    def inherit(cls, parent_locator: Locator) -> Injector:
        """
        Create a child Injector that inherits from a parent locator.

        Args:
            parent_locator: The parent locator to inherit from

        Returns:
            A new Injector that will check the parent locator for missing dependencies

        Example:
            ```python
            # Create parent injector and locator
            parent_injector = Injector()
            parent_plan = parent_injector.plan(parent_input)
            parent_locator = parent_injector.produce(parent_plan)

            # Create child injector that inherits from parent
            child_injector = Injector.inherit(parent_locator)
            child_plan = child_injector.plan(child_input)
            child_locator = child_injector.produce(child_plan)
            ```
        """
        return cls(parent_locator)
