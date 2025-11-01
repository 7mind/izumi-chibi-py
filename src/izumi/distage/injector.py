"""
Injector - Stateless dependency injection container that produces Plans from PlannerInput.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from .locator_base import Locator
from .logger_injection import AutoLoggerManager
from .model import DependencyGraph, DIKey, ExecutableOp, InstanceKey, Plan
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

    def plan(self, input: PlannerInput | list[InstanceKey], *args: Any) -> Plan:
        """
        Create a validated Plan from a PlannerInput or convenience parameters.

        Args:
            input: The PlannerInput containing modules, roots, and activation,
                   OR a list of root keys when using the convenience overload
            *args: When using convenience overload: modules (optional)

        Returns:
            A Plan that can be executed by Locators
        """
        if isinstance(input, list):
            # Convenience overload: plan(keys, module)
            from .dsl import ModuleDef
            from .roots import Roots

            keys = input
            modules = [args[0]] if args else [ModuleDef()]
            if keys:
                # Extract types from InstanceKeys
                target_types = [key.target_type for key in keys]
                roots = Roots.target(*target_types)
            else:
                roots = Roots.everything()

            planner_input = PlannerInput(modules, roots)
            return self.plan(planner_input)
        else:
            # Normal usage: plan(PlannerInput)
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
        return self.plan_produce(input).run(func)

    def plan_produce(self, input: PlannerInput) -> Locator:
        plan = self.plan(input)
        locator = self.produce(plan)
        return locator

    def produce(self, plan: Plan) -> Locator:
        """
        Create a Locator by instantiating all dependencies in the Plan.

        Args:
            plan: The validated Plan to execute

        Returns:
            A Locator containing all resolved instances
        """
        instances: dict[DIKey, Any] = {}

        def resolve_instance(key: InstanceKey) -> Any:
            """Resolve a dependency and return an instance."""
            if plan.has_operation(key):
                return instances[key]
            else:
                return self._parent_locator.get(key)  # pyright: ignore[reportUnknownVariableType]

        # Resolve all dependencies in topological order
        for binding_key in plan.get_execution_order():
            assert binding_key not in instances
            instance = self._create_instance(binding_key, plan, instances, resolve_instance)
            instances[binding_key] = instance

        from .locator_impl import LocatorImpl

        return LocatorImpl(plan, instances, self._parent_locator)

    async def produce_async(self, plan: Plan) -> Any:  # Returns AsyncLocator
        """
        Create an AsyncLocator by instantiating all dependencies in the Plan,
        supporting async operations and lifecycle management.

        This method handles async factory functions, async lifecycle acquire,
        and tracks resources for automatic cleanup.

        Args:
            plan: The validated Plan to execute

        Returns:
            An AsyncLocator containing all resolved instances with cleanup support

        Example:
            async with injector.produce_async(plan) as locator:
                result = await locator.run(my_async_function)
        """
        instances: dict[DIKey, Any] = {}
        lifecycle_resources: list[
            tuple[InstanceKey, Any, Any]
        ] = []  # [(key, instance, lifecycle), ...]

        def resolve_instance(key: InstanceKey) -> Any:
            """Resolve a dependency and return an instance."""
            if plan.has_operation(key):
                return instances[key]
            else:
                return self._parent_locator.get(key)  # pyright: ignore[reportUnknownVariableType]

        # Resolve all dependencies in topological order
        for binding_key in plan.get_execution_order():
            assert binding_key not in instances
            instance = await self._create_instance_async(
                binding_key, plan, instances, resolve_instance
            )
            instances[binding_key] = instance

            # Track lifecycle resources for cleanup
            operations = plan.graph.get_operations()
            operation = operations.get(binding_key)
            if operation:
                from .model.operations import Provide

                if isinstance(operation, Provide) and operation.binding.lifecycle:
                    lifecycle_resources.append((binding_key, instance, operation.binding.lifecycle))

        from .async_locator import AsyncLocator

        return AsyncLocator(plan, instances, self._parent_locator, lifecycle_resources)

    def _build_graph(self, input: PlannerInput) -> DependencyGraph:
        """Build the dependency graph from PlannerInput."""
        graph = DependencyGraph()

        # Add all bindings to the graph first
        for module in input.modules:
            for binding in module.bindings:
                graph.add_binding(binding)

        # Add all lookup operations to the graph
        for module in input.modules:
            if hasattr(module, "lookup_operations"):
                for lookup_op in module.lookup_operations:
                    graph.add_lookup_operation(lookup_op)

        # Filter bindings based on activation using tracing
        if not input.activation.choices:
            # No activation specified, keep all bindings
            pass
        else:
            # Determine root keys for tracing
            if input.roots.is_everything():
                # For everything roots, we need to trace from all top-level bindings
                # Use all bindings as potential roots
                root_keys = set(graph.get_all_bindings().keys())
            else:
                # Use specified roots
                root_keys = set(input.roots.keys)

            # Filter bindings using path-aware tracing
            graph.filter_bindings_by_activation_traced(input.activation, root_keys)

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
        key: InstanceKey,
        plan: Plan,
        instances: dict[DIKey, Any],  # noqa: ARG002
        resolve_fn: Callable[[InstanceKey], Any],
    ) -> Any:
        """Create an instance for the given key."""
        # Get operation for this key
        operations = plan.graph.get_operations()
        operation = operations.get(key)

        if not operation:
            # Check parent locator if available
            if not self._parent_locator.is_empty():
                try:
                    return self._parent_locator.get(key)  # pyright: ignore[reportUnknownVariableType]
                except ValueError:
                    pass  # Parent doesn't have it either, fall through to error

            raise ValueError(f"No operation found for {key}")

        return self._execute_operation(operation, resolve_fn)

    def _execute_operation(
        self, operation: ExecutableOp, resolve_fn: Callable[[InstanceKey], Any]
    ) -> Any:
        """Execute an operation with resolved dependencies."""
        from .model import CreateFactory

        # Special handling for CreateFactory operations
        if isinstance(operation, CreateFactory):
            # Set the resolve function for the factory operation
            operation.resolve_fn = resolve_fn
            return operation.execute({})

        # Build resolved dependencies map for other operations
        resolved_deps: dict[InstanceKey, Any] = {}
        for dep_key in operation.dependencies():
            try:
                resolved_deps[dep_key] = resolve_fn(dep_key)
            except ValueError:
                # Check if this is an auto-injectable logger
                if AutoLoggerManager.should_auto_inject_logger(dep_key):
                    # Get the target class that's requesting the logger
                    target_key = operation.key()
                    target_class = target_key.target_type

                    # Determine logger name from target class
                    if hasattr(target_class, "__name__"):
                        from .logger_injection import LoggerLocationIntrospector

                        module_name = LoggerLocationIntrospector.get_module_name_from_string(
                            target_class.__module__
                            if hasattr(target_class, "__module__")
                            else "__unknown__"
                        )
                        logger_name = f"{module_name}.{target_class.__name__}"
                    else:
                        from .logger_injection import LoggerLocationIntrospector

                        logger_name = LoggerLocationIntrospector.get_logger_location_name()

                    resolved_deps[dep_key] = logging.getLogger(logger_name)
                else:
                    # Re-raise the original error for non-logger dependencies
                    raise

        return operation.execute(resolved_deps)

    async def _create_instance_async(
        self,
        key: InstanceKey,
        plan: Plan,
        instances: dict[DIKey, Any],  # noqa: ARG002
        resolve_fn: Callable[[InstanceKey], Any],
    ) -> Any:
        """Create an instance for the given key, supporting async operations."""
        # Get operation for this key
        operations = plan.graph.get_operations()
        operation = operations.get(key)

        if not operation:
            # Check parent locator if available
            if not self._parent_locator.is_empty():
                try:
                    return self._parent_locator.get(key)  # pyright: ignore[reportUnknownVariableType]
                except ValueError:
                    pass  # Parent doesn't have it either, fall through to error

            raise ValueError(f"No operation found for {key}")

        return await self._execute_operation_async(operation, resolve_fn)

    async def _execute_operation_async(
        self, operation: ExecutableOp, resolve_fn: Callable[[InstanceKey], Any]
    ) -> Any:
        """Execute an operation with resolved dependencies, supporting async operations."""
        from .model import CreateFactory

        # Special handling for CreateFactory operations
        if isinstance(operation, CreateFactory):
            # Set the resolve function for the factory operation
            operation.resolve_fn = resolve_fn
            return operation.execute({})

        # Build resolved dependencies map for other operations
        resolved_deps: dict[InstanceKey, Any] = {}
        for dep_key in operation.dependencies():
            try:
                resolved_deps[dep_key] = resolve_fn(dep_key)
            except ValueError:
                # Check if this is an auto-injectable logger
                if AutoLoggerManager.should_auto_inject_logger(dep_key):
                    # Get the target class that's requesting the logger
                    target_key = operation.key()
                    target_class = target_key.target_type

                    # Determine logger name from target class
                    if hasattr(target_class, "__name__"):
                        from .logger_injection import LoggerLocationIntrospector

                        module_name = LoggerLocationIntrospector.get_module_name_from_string(
                            target_class.__module__
                            if hasattr(target_class, "__module__")
                            else "__unknown__"
                        )
                        logger_name = f"{module_name}.{target_class.__name__}"
                    else:
                        from .logger_injection import LoggerLocationIntrospector

                        logger_name = LoggerLocationIntrospector.get_logger_location_name()

                    resolved_deps[dep_key] = logging.getLogger(logger_name)
                else:
                    # Re-raise the original error for non-logger dependencies
                    raise

        # Execute the operation
        result = operation.execute(resolved_deps)

        # If the result is a coroutine (async operation), await it
        if inspect.iscoroutine(result):
            return await result

        return result

    def create_locator_with_preresolved(
        self, plan: Plan, preresolved_deps: dict[InstanceKey, Any]
    ) -> Locator:
        """
        Create a Locator with some dependencies already resolved.

        Args:
            plan: The validated Plan to execute
            preresolved_deps: Dependencies that are already resolved

        Returns:
            A Locator containing all resolved instances
        """
        instances: dict[InstanceKey, Any] = preresolved_deps.copy()

        def resolve_instance(key: InstanceKey) -> Any:
            """Resolve a dependency and return an instance."""
            if key in instances:
                return instances[key]
            elif plan.has_operation(key):
                # This should have been resolved already in topological order
                return instances[key]
            else:
                return self._parent_locator.get(key)  # pyright: ignore[reportUnknownVariableType]

        # Resolve all dependencies in topological order (skip already resolved ones)
        instances_dict: dict[DIKey, Any] = instances  # type: ignore[assignment]
        for binding_key in plan.get_execution_order():
            if binding_key not in instances_dict:
                instance = self._create_instance(
                    binding_key, plan, instances_dict, resolve_instance
                )
                instances_dict[binding_key] = instance

        from .locator_impl import LocatorImpl

        return LocatorImpl(plan, instances_dict, self._parent_locator)

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
