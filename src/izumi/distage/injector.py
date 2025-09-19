"""
Injector - Stateless dependency injection container that produces Plans from PlannerInput.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypeVar

from .locator_base import Locator
from .logger_injection import AutoLoggerManager
from .model import DependencyGraph, DIKey, ExecutableOp, Plan
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
        # Use empty locator instead of None for cleaner null object pattern
        from .locator_base import Locator
        self._parent_locator = parent_locator if parent_locator is not None else Locator.empty()

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

        def resolve_instance(key: DIKey) -> Any:
            """Resolve a dependency and return an instance."""
            if plan.has_operation(key):
                return instances[key]
            else:
                return self._parent_locator.get(key.target_type, key.name)

        # Resolve all dependencies in topological order
        for binding_key in plan.get_execution_order():
            if binding_key not in instances:
                assert binding_key not in instances
                instance = self._create_instance(binding_key, plan, instances, resolve_instance)
                instances[binding_key] = instance

        from .locator_impl import LocatorImpl
        return LocatorImpl(plan, instances, self._parent_locator)

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
        if not self._parent_locator.is_empty():
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
        # Get operation for this key
        operations = plan.graph.get_operations()
        operation = operations.get(key)

        if not operation:
            # Check parent locator if available
            if not self._parent_locator.is_empty():
                try:
                    return self._parent_locator.get(key.target_type, key.name)  # pyright: ignore[reportUnknownVariableType]
                except ValueError:
                    pass  # Parent doesn't have it either, fall through to error

            raise ValueError(f"No operation found for {key}")

        return self._execute_operation(operation, resolve_fn)

    def _execute_operation(self, operation: ExecutableOp, resolve_fn: Callable[[DIKey], Any]) -> Any:
        """Execute an operation with resolved dependencies."""
        from .model import CreateFactory

        # Special handling for CreateFactory operations
        if isinstance(operation, CreateFactory):
            # Set the resolve function for the factory operation
            operation.resolve_fn = resolve_fn
            return operation.execute({})

        # Build resolved dependencies map for other operations
        resolved_deps: dict[DIKey, Any] = {}
        for dep_key in operation.dependencies():
            try:
                resolved_deps[dep_key] = resolve_fn(dep_key)
            except ValueError:
                # Check if this is an auto-injectable logger
                if AutoLoggerManager.should_auto_inject_logger(dep_key):
                    # Create an appropriate logger as fallback
                    from .logger_injection import LoggerLocationIntrospector

                    logger_name = LoggerLocationIntrospector.get_logger_location_name()
                    resolved_deps[dep_key] = logging.getLogger(logger_name)
                else:
                    # Re-raise the original error for non-logger dependencies
                    raise

        return operation.execute(resolved_deps)

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
