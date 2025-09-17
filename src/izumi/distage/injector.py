"""
Injector - Stateless dependency injection container that produces Plans from PlannerInput.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, TypeVar

from .bindings import Binding, BindingType
from .graph import DependencyGraph
from .introspection import SignatureIntrospector
from .keys import DIKey
from .locator import Locator
from .plan import Plan
from .planner_input import PlannerInput
from .tag import Tag

T = TypeVar("T")


class Injector:
    """
    Stateless dependency injection container that produces Plans from PlannerInput.

    The Injector builds and validates dependency graphs but does not manage
    instances or store state. It produces Plans that can be executed by Locators.
    """

    def __init__(self, *modules, roots=None, activation=None):
        """Create an Injector. Can be empty for new API or take modules for backward compatibility."""
        from .activation import Activation
        from .core import ModuleDef
        from .roots import Roots

        # For backward compatibility, store modules, roots, and activation as defaults
        if modules:
            # Old API: Injector(module) or Injector(module1, module2, ...)
            if len(modules) == 1 and isinstance(modules[0], ModuleDef):
                self._default_modules = list(modules)
            else:
                # Assume multiple modules or other iterable
                self._default_modules = list(modules)
        else:
            self._default_modules = []

        self._default_roots = roots if roots is not None else Roots.everything()
        self._default_activation = activation if activation is not None else Activation()

    @property
    def roots(self):
        """Get default roots for backward compatibility."""
        return self._default_roots

    def plan(self, input: PlannerInput | None = None, roots = None, activation = None) -> Plan:
        """
        Create a validated Plan from a PlannerInput or using defaults for backward compatibility.

        Args:
            input: The PlannerInput containing modules, roots, and activation (optional for backward compatibility)
            roots: Override roots (for backward compatibility)
            activation: Override activation (for backward compatibility)

        Returns:
            A Plan that can be executed by Locators
        """
        if input is None:
            # Backward compatibility: use defaults
            actual_roots = roots if roots is not None else self._default_roots
            actual_activation = activation if activation is not None else self._default_activation
            input = PlannerInput(self._default_modules, actual_roots, actual_activation)

        graph = self._build_graph(input)
        topology = graph.get_topological_order()
        return Plan(graph, input.roots, input.activation, topology)

    def produce_run(self, input_or_func, func: Callable[..., T] | None = None) -> T:
        """
        Execute a function by automatically resolving its dependencies.

        This method creates a Plan and Locator behind the scenes, then runs the function
        with automatically resolved dependencies.

        Args:
            input_or_func: Either PlannerInput (new API) or function (backward compatibility)
            func: Function when using new API, None when using backward compatibility

        Returns:
            The result returned by the function

        Example:
            ```python
            # New API
            def my_app(service: MyService, config: Config) -> str:
                return service.process(config.value)

            input = PlannerInput([module])
            result = injector.produce_run(input, my_app)

            # Backward compatibility API
            injector = Injector(module)
            result = injector.produce_run(my_app)
            ```
        """
        if func is None:
            # Backward compatibility: input_or_func is actually the function
            func = input_or_func
            input = PlannerInput(self._default_modules, self._default_roots, self._default_activation)
        else:
            # New API: input_or_func is PlannerInput
            input = input_or_func

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

        return Locator(plan, instances)

    def get(self, input: PlannerInput, target_type: type[T], tag: Tag | None = None) -> T:
        """
        Convenience method to resolve a single type.

        This creates a Plan and Locator behind the scenes to resolve a single type.
        Consider using produce_run() for better dependency injection patterns.

        Args:
            input: The PlannerInput containing modules, roots, and activation
            target_type: The type to resolve
            tag: Optional tag to distinguish between different bindings

        Returns:
            An instance of the requested type
        """
        plan = self.plan(input)
        locator = self.produce(plan)
        return locator.get(target_type, tag)

    def get(self, target_type: type[T], tag: Tag | None = None) -> T:
        """
        Convenience method to resolve a single type using default modules/roots/activation.

        This creates a Plan and Locator behind the scenes to resolve a single type.
        This is for backward compatibility - consider using the new PlannerInput API.

        Args:
            target_type: The type to resolve
            tag: Optional tag to distinguish between different bindings

        Returns:
            An instance of the requested type
        """
        # Use default PlannerInput
        input = PlannerInput(self._default_modules, self._default_roots, self._default_activation)
        plan = self.plan(input)
        locator = self.produce(plan)
        return locator.get(target_type, tag)

    def _build_graph(self, input: PlannerInput) -> DependencyGraph:
        """Build the dependency graph from PlannerInput."""
        graph = DependencyGraph()

        # Add all bindings to the graph first
        for module in input.modules:
            for binding in module.bindings:
                graph.add_binding(binding)

        # Filter bindings based on activation
        if not input.activation.choices:
            # No activation specified, keep all bindings
            pass
        else:
            # Filter bindings that don't match the activation
            graph.filter_bindings_by_activation(input.activation)

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
        self, key: DIKey, plan: Plan, instances: dict[DIKey, Any], resolve_fn: Callable[[DIKey], Any]
    ) -> Any:
        """Create an instance for the given key."""
        # Handle set bindings
        origin = getattr(key.target_type, "__origin__", None)
        if origin is set:
            return self._resolve_set_binding(key, plan, resolve_fn)

        binding = plan.graph.get_binding(key)
        if not binding:
            # Check if we have set bindings for this type
            set_key = DIKey(key.target_type, key.tag)  # Create set key
            set_bindings = plan.graph.get_set_bindings(set_key)
            if set_bindings:
                return self._resolve_set_binding_direct(set_bindings, resolve_fn)
            raise ValueError(f"No binding found for {key}")

        return self._create_from_binding(binding, resolve_fn)

    def _resolve_set_binding(self, key: DIKey, plan: Plan, resolve_fn: Callable[[DIKey], Any]) -> set[Any]:
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
        if binding.binding_type == BindingType.INSTANCE:
            return binding.implementation

        elif binding.binding_type == BindingType.FACTORY:
            return self._call_factory(binding.implementation, resolve_fn)

        elif binding.binding_type == BindingType.CLASS:
            return self._instantiate_class(binding.implementation, resolve_fn)

        elif binding.binding_type == BindingType.SET_ELEMENT:
            # For set elements, treat them like regular bindings
            if inspect.isclass(binding.implementation):
                return self._instantiate_class(binding.implementation, resolve_fn)
            elif callable(binding.implementation):
                return self._call_factory(binding.implementation, resolve_fn)
            else:
                return binding.implementation

        else:
            raise ValueError(f"Unknown binding type: {binding.binding_type}")

    def _instantiate_class(self, cls: type | Any | Callable[..., Any], resolve_fn: Callable[[DIKey], Any]) -> Any:
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
                dep_key = DIKey(dep.type_hint, None)
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
                dep_key = DIKey(dep.type_hint, None)
                kwargs[dep.name] = resolve_fn(dep_key)
            # For optional dependencies with defaults, let the factory handle them

        return factory(**kwargs)
