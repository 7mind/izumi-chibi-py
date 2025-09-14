"""
Core components for the PyDistage dependency injection framework.
"""

from typing import Any, Type, TypeVar, Generic, Dict, List, Set, Optional, Callable, Union
from dataclasses import dataclass
import inspect
from .bindings import Binding, BindingKey, BindingType
from .graph import DependencyGraph
from .resolver import DependencyResolver

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
    
    def __init__(self, module: ModuleDef, target_type: Type[T], tag: Optional[Tag] = None):
        self._module = module
        self._target_type = target_type
        self._tag = tag
    
    def tagged(self, tag: Tag) -> 'BindingBuilder[T]':
        """Add a tag to this binding."""
        return BindingBuilder(self._module, self._target_type, tag)
    
    def from_(self, implementation: Union[Type[T], T, Callable[..., T]]) -> None:
        """Bind to a specific implementation, instance, or factory function."""
        key = BindingKey(self._target_type, self._tag)
        
        if inspect.isclass(implementation):
            binding = Binding(key, BindingType.CLASS, implementation)
        elif callable(implementation):
            binding = Binding(key, BindingType.FACTORY, implementation)
        else:
            binding = Binding(key, BindingType.INSTANCE, implementation)
        
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
    
    def __init__(self, *modules: ModuleDef):
        self._modules = modules
        self._graph = self._build_graph()
        self._resolver = DependencyResolver(self._graph)
    
    def _build_graph(self) -> DependencyGraph:
        """Build the dependency graph from all modules."""
        graph = DependencyGraph()
        
        for module in self._modules:
            for binding in module.bindings:
                graph.add_binding(binding)
        
        graph.validate()
        return graph
    
    def get(self, target_type: Type[T], tag: Optional[Tag] = None) -> T:
        """Resolve and return an instance of the given type."""
        key = BindingKey(target_type, tag)
        return self._resolver.resolve(key)
    
    def produce_run(self, target_type: Type[T], tag: Optional[Tag] = None) -> T:
        """Resolve and return an instance, managing the full lifecycle."""
        return self.get(target_type, tag)