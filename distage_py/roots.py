"""
Roots system for defining what should be instantiated from the dependency graph.
"""

from typing import Type, TypeVar, Set, List, Any, Union
from dataclasses import dataclass

from .bindings import BindingKey

T = TypeVar('T')


@dataclass(frozen=True)
class DIKey:
    """A key that identifies a specific dependency in the object graph."""
    
    target_type: Type
    tag: Any = None
    
    @classmethod
    def get(cls, target_type: Type[T], tag: Any = None) -> 'DIKey':
        """Create a DIKey for the given type and optional tag."""
        return cls(target_type, tag)
    
    def to_binding_key(self) -> BindingKey:
        """Convert to a BindingKey."""
        return BindingKey(self.target_type, self.tag)
    
    def __str__(self) -> str:
        tag_str = f" {self.tag}" if self.tag else ""
        type_name = getattr(self.target_type, '__name__', str(self.target_type))
        return f"DIKey[{type_name}{tag_str}]"


class Roots:
    """Defines which objects should be instantiated from the dependency graph."""
    
    def __init__(self, keys: List[DIKey]):
        self._keys = keys
    
    @property
    def keys(self) -> List[DIKey]:
        """Get all root keys."""
        return self._keys.copy()
    
    @classmethod
    def target(cls, *target_types: Type) -> 'Roots':
        """Create roots targeting specific types."""
        keys = [DIKey.get(target_type) for target_type in target_types]
        return cls(keys)
    
    @classmethod
    def everything(cls) -> 'Roots':
        """Create roots that include everything (no garbage collection)."""
        return EverythingRoots()
    
    @classmethod
    def empty(cls) -> 'Roots':
        """Create empty roots."""
        return cls([])
    
    def __add__(self, other: 'Roots') -> 'Roots':
        """Combine two roots."""
        if isinstance(other, EverythingRoots):
            return other
        return Roots(self._keys + other._keys)
    
    def is_everything(self) -> bool:
        """Check if this represents everything roots."""
        return isinstance(self, EverythingRoots)
    
    def __str__(self) -> str:
        if not self._keys:
            return "Roots.empty()"
        
        keys_str = ", ".join(str(key) for key in self._keys)
        return f"Roots({keys_str})"


class EverythingRoots(Roots):
    """Special roots that include everything (no garbage collection)."""
    
    def __init__(self):
        super().__init__([])
    
    def __str__(self) -> str:
        return "Roots.everything()"


class RootsFinder:
    """Finds all dependencies reachable from the given roots."""
    
    @staticmethod
    def find_reachable_keys(roots: Roots, graph: 'DependencyGraph') -> Set[BindingKey]:
        """Find all binding keys reachable from the roots."""
        if roots.is_everything():
            # Include all bindings
            return set(graph.get_all_bindings().keys())
        
        visited = set()
        to_visit = set()
        
        # Start with root keys
        for root_key in roots.keys:
            binding_key = root_key.to_binding_key()
            to_visit.add(binding_key)
        
        # Perform DFS to find all reachable dependencies
        while to_visit:
            current_key = to_visit.pop()
            if current_key in visited:
                continue
            
            visited.add(current_key)
            
            # Get the node for this key
            node = graph.get_node(current_key)
            if node:
                # Add all dependencies to visit list
                for dep_key in node.dependencies:
                    if dep_key not in visited:
                        to_visit.add(dep_key)
        
        return visited
    
    @staticmethod
    def validate_roots(roots: Roots, graph: 'DependencyGraph') -> None:
        """Validate that all root keys exist in the graph."""
        if roots.is_everything():
            return
        
        for root_key in roots.keys:
            binding_key = root_key.to_binding_key()
            if not graph.get_binding(binding_key) and not graph.get_set_bindings(binding_key):
                raise ValueError(f"Root key not found in graph: {root_key}")