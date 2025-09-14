"""
Core components for the PyDistage dependency injection framework.
"""

from typing import Any, Type, TypeVar, Generic, Dict, List, Set, Optional, Callable, Union
from dataclasses import dataclass
import inspect
from .bindings import Binding, BindingKey, BindingType
from .graph import DependencyGraph
from .resolver import DependencyResolver
from .roots import Roots, DIKey
from .activation import Activation, AxisChoiceDef

T = TypeVar('T')


@dataclass(frozen=True)
class Tag:
    """A tag for distinguishing between different bindings of the same type."""
    name: str
    
    def __str__(self) -> str:
        return f"@{self.name}"


class ModuleDef:
    """DSL for defining dependency injection bindings."""
    
    def __init__(self):
        self._bindings: List[Binding] = []
    
    def make(self, target_type: Type[T]) -> 'BindingBuilder[T]':
        """Create a binding for the given type."""
        return BindingBuilder(self, target_type)
    
    def many(self, target_type: Type[T]) -> 'SetBindingBuilder[T]':
        """Create a set binding for collecting multiple instances of the same type."""
        return SetBindingBuilder(self, target_type)
    
    def make_factory(self, factory_type: Type[T]) -> 'FactoryBindingBuilder[T]':
        """Create a factory binding."""
        return FactoryBindingBuilder(self, factory_type)
    
    def _add_binding(self, binding: Binding) -> None:
        """Internal method to add a binding."""
        self._bindings.append(binding)
    
    @property
    def bindings(self) -> List[Binding]:
        """Get all bindings defined in this module."""
        return self._bindings.copy()


class BindingBuilder(Generic[T]):
    """Builder for creating individual bindings."""
    
    def __init__(self, module: ModuleDef, target_type: Type[T], tag: Optional[Tag] = None, activation_tags: Set[AxisChoiceDef] = None):
        self._module = module
        self._target_type = target_type
        self._tag = tag
        self._activation_tags = activation_tags or set()
    
    def tagged(self, *tags: Union[Tag, AxisChoiceDef]) -> 'BindingBuilder[T]':
        """Add tags to this binding (supports both old-style Tags and AxisChoiceDef)."""
        new_tag = None
        new_activation_tags = self._activation_tags.copy()
        
        for tag in tags:
            if isinstance(tag, Tag):
                new_tag = tag
            elif isinstance(tag, AxisChoiceDef):
                new_activation_tags.add(tag)
        
        return BindingBuilder(self._module, self._target_type, new_tag, new_activation_tags)
    
    def from_(self, implementation: Union[Type[T], T, Callable[..., T]]) -> None:
        """Bind to a specific implementation, instance, or factory function."""
        key = BindingKey(self._target_type, self._tag)
        
        if inspect.isclass(implementation):
            binding = Binding(key, BindingType.CLASS, implementation, self._activation_tags)
        elif callable(implementation):
            binding = Binding(key, BindingType.FACTORY, implementation, self._activation_tags)
        else:
            binding = Binding(key, BindingType.INSTANCE, implementation, self._activation_tags)
        
        self._module._add_binding(binding)
    
    def to(self, implementation_type: Type[T]) -> None:
        """Bind to a specific implementation type."""
        self.from_(implementation_type)


class SetBindingBuilder(Generic[T]):
    """Builder for creating set bindings."""
    
    def __init__(self, module: ModuleDef, target_type: Type[T], tag: Optional[Tag] = None):
        self._module = module
        self._target_type = target_type
        self._tag = tag
    
    def add(self, implementation: Union[Type[T], T, Callable[..., T]]) -> 'SetBindingBuilder[T]':
        """Add an implementation to the set."""
        key = BindingKey(Set[self._target_type], self._tag)
        
        if inspect.isclass(implementation):
            binding = Binding(key, BindingType.SET_ELEMENT, implementation)
        elif callable(implementation):
            binding = Binding(key, BindingType.SET_ELEMENT, implementation)
        else:
            binding = Binding(key, BindingType.SET_ELEMENT, implementation)
        
        self._module._add_binding(binding)
        return self
    
    def ref(self, implementation_type: Type[T]) -> 'SetBindingBuilder[T]':
        """Add a reference to an existing binding to the set."""
        return self.add(implementation_type)


class FactoryBindingBuilder(Generic[T]):
    """Builder for creating factory bindings."""
    
    def __init__(self, module: ModuleDef, factory_type: Type[T]):
        self._module = module
        self._factory_type = factory_type
    
    def from_factory(self, factory_impl: Type[T]) -> None:
        """Bind the factory to a specific implementation."""
        key = BindingKey(self._factory_type, None)
        binding = Binding(key, BindingType.FACTORY, factory_impl)
        self._module._add_binding(binding)


class Injector:
    """Main dependency injection container."""
    
    def __init__(self, *modules: ModuleDef, roots: Optional[Roots] = None, activation: Optional[Activation] = None):
        self._modules = modules
        self._roots = roots or Roots.everything()
        self._activation = activation or Activation.empty()
        self._graph = self._build_graph()
        self._resolver = DependencyResolver(self._graph, self._activation, self._roots)
    
    def _build_graph(self) -> DependencyGraph:
        """Build the dependency graph from all modules."""
        graph = DependencyGraph()
        
        # Add all bindings to the graph first
        for module in self._modules:
            for binding in module.bindings:
                graph.add_binding(binding)
        
        # Filter bindings based on activation
        if not self._activation.choices:
            # No activation specified, keep all bindings
            pass
        else:
            # Filter bindings that don't match the activation
            graph.filter_bindings_by_activation(self._activation)
        
        graph.validate()
        
        # Validate roots and perform garbage collection if needed
        from .roots import RootsFinder
        RootsFinder.validate_roots(self._roots, graph)
        
        if not self._roots.is_everything():
            # Perform garbage collection - only keep reachable bindings
            reachable_keys = RootsFinder.find_reachable_keys(self._roots, graph)
            graph.garbage_collect(reachable_keys)
        
        return graph
    
    def get(self, target_type: Type[T], tag: Optional[Tag] = None) -> T:
        """Resolve and return an instance of the given type."""
        key = BindingKey(target_type, tag)
        return self._resolver.resolve(key)
    
    def produce_run(self, target_type: Type[T], tag: Optional[Tag] = None) -> T:
        """Resolve and return an instance, managing the full lifecycle."""
        return self.get(target_type, tag)
    
    @staticmethod
    def produce(modules: List[ModuleDef], roots: Roots, activation: Optional[Activation] = None) -> 'Injector':
        """Create an injector with specific roots and activation."""
        return Injector(*modules, roots=roots, activation=activation)