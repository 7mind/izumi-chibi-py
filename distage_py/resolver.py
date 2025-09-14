"""
Dependency resolution and execution engine.
"""

from typing import Dict, Any, Type, List, Set, Optional, TYPE_CHECKING
import inspect

from .bindings import BindingKey, Binding, BindingType

from .graph import DependencyGraph
from .introspection import SignatureIntrospector


class DependencyResolver:
    """Resolves dependencies and creates instances."""
    
    def __init__(self, graph: DependencyGraph):
        self._graph = graph
        self._instances: Dict[BindingKey, Any] = {}
        self._resolving: Set[BindingKey] = set()
    
    def resolve(self, key: BindingKey) -> Any:
        """Resolve a dependency and return an instance."""
        # Check if already resolved
        if key in self._instances:
            return self._instances[key]
        
        # Check for circular dependency during resolution
        if key in self._resolving:
            raise ValueError(f"Circular dependency detected during resolution: {key}")
        
        self._resolving.add(key)
        
        try:
            instance = self._create_instance(key)
            self._instances[key] = instance
            return instance
        finally:
            self._resolving.discard(key)
    
    def _create_instance(self, key: BindingKey) -> Any:
        """Create an instance for the given key."""
        # Handle set bindings
        origin = getattr(key.target_type, '__origin__', None)
        if origin is set:
            return self._resolve_set_binding(key)
        
        binding = self._graph.get_binding(key)
        if not binding:
            # Check if we have set bindings for this type
            set_key = BindingKey(key.target_type, key.tag)  # Create set key
            set_bindings = self._graph.get_set_bindings(set_key)
            if set_bindings:
                return self._resolve_set_binding_direct(set_bindings)
            raise ValueError(f"No binding found for {key}")
        
        return self._create_from_binding(binding)
    
    def _resolve_set_binding(self, key: BindingKey) -> Set[Any]:
        """Resolve a set binding."""
        set_bindings = self._graph.get_set_bindings(key)
        return self._resolve_set_binding_direct(set_bindings)
    
    def _resolve_set_binding_direct(self, set_bindings: List['Binding']) -> Set[Any]:
        """Resolve set bindings directly from a list of bindings."""
        result_set = set()
        
        for binding in set_bindings:
            instance = self._create_from_binding(binding)
            result_set.add(instance)
        
        return result_set
    
    def _create_from_binding(self, binding: Binding) -> Any:
        """Create an instance from a specific binding."""
        if binding.binding_type == BindingType.INSTANCE:
            return binding.implementation
        
        elif binding.binding_type == BindingType.FACTORY:
            return self._call_factory(binding.implementation)
        
        elif binding.binding_type == BindingType.CLASS:
            return self._instantiate_class(binding.implementation)
        
        elif binding.binding_type == BindingType.SET_ELEMENT:
            # For set elements, treat them like regular bindings
            if inspect.isclass(binding.implementation):
                return self._instantiate_class(binding.implementation)
            elif callable(binding.implementation):
                return self._call_factory(binding.implementation)
            else:
                return binding.implementation
        
        else:
            raise ValueError(f"Unknown binding type: {binding.binding_type}")
    
    def _instantiate_class(self, cls: Type) -> Any:
        """Instantiate a class by resolving its dependencies."""
        dependencies = SignatureIntrospector.extract_dependencies(cls)
        kwargs = {}
        
        for dep in dependencies:
            # Skip Any types which are usually introspection failures
            if dep.type_hint == Any:
                continue
            if not dep.is_optional or dep.default_value == inspect.Parameter.empty:
                dep_key = BindingKey(dep.type_hint, None)
                kwargs[dep.name] = self.resolve(dep_key)
            # For optional dependencies with defaults, let the class handle them
        
        return cls(**kwargs)
    
    def _call_factory(self, factory: callable) -> Any:
        """Call a factory function by resolving its dependencies."""
        dependencies = SignatureIntrospector.extract_dependencies(factory)
        kwargs = {}
        
        for dep in dependencies:
            # Skip Any types which are usually introspection failures
            if dep.type_hint == Any:
                continue
            if not dep.is_optional or dep.default_value == inspect.Parameter.empty:
                dep_key = BindingKey(dep.type_hint, None)
                kwargs[dep.name] = self.resolve(dep_key)
            # For optional dependencies with defaults, let the factory handle them
        
        return factory(**kwargs)
    
    def clear_instances(self) -> None:
        """Clear all resolved instances (useful for testing)."""
        self._instances.clear()
    
    def get_instance_count(self) -> int:
        """Get the number of resolved instances."""
        return len(self._instances)
    
    def is_resolved(self, key: BindingKey) -> bool:
        """Check if a key has been resolved."""
        return key in self._instances