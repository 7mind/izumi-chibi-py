"""
Dependency graph formation and validation.
"""

from typing import Dict, List, Set, Optional, Any
from collections import defaultdict, deque
from dataclasses import dataclass

from .bindings import Binding, BindingKey, BindingType
from .introspection import SignatureIntrospector, DependencyInfo


class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected."""
    
    def __init__(self, cycle: List[BindingKey]):
        self.cycle = cycle
        cycle_str = " -> ".join(str(key) for key in cycle)
        super().__init__(f"Circular dependency detected: {cycle_str}")


class MissingBindingError(Exception):
    """Raised when a required binding is not found."""
    
    def __init__(self, key: BindingKey, dependent: Optional[BindingKey] = None):
        self.key = key
        self.dependent = dependent
        msg = f"No binding found for {key}"
        if dependent:
            msg += f" (required by {dependent})"
        super().__init__(msg)


@dataclass
class GraphNode:
    """A node in the dependency graph."""
    key: BindingKey
    binding: Binding
    dependencies: List[BindingKey]
    dependents: Set[BindingKey]
    
    def __post_init__(self):
        self.dependents = set()


class DependencyGraph:
    """Manages the dependency graph for the entire application."""
    
    def __init__(self):
        self._bindings: Dict[BindingKey, Binding] = {}
        self._nodes: Dict[BindingKey, GraphNode] = {}
        self._set_bindings: Dict[BindingKey, List[Binding]] = defaultdict(list)
        self._validated = False
    
    def add_binding(self, binding: Binding) -> None:
        """Add a binding to the graph."""
        if binding.binding_type == BindingType.SET_ELEMENT:
            self._set_bindings[binding.key].append(binding)
        else:
            if binding.key in self._bindings:
                raise ValueError(f"Duplicate binding for {binding.key}")
            self._bindings[binding.key] = binding
        
        self._validated = False
    
    def get_binding(self, key: BindingKey) -> Optional[Binding]:
        """Get a binding by key."""
        return self._bindings.get(key)
    
    def get_set_bindings(self, key: BindingKey) -> List[Binding]:
        """Get all set bindings for a key."""
        return self._set_bindings.get(key, [])
    
    def get_all_bindings(self) -> Dict[BindingKey, Binding]:
        """Get all regular bindings."""
        return self._bindings.copy()
    
    def get_node(self, key: BindingKey) -> Optional[GraphNode]:
        """Get a graph node by key."""
        return self._nodes.get(key)
    
    def validate(self) -> None:
        """Validate the dependency graph."""
        if self._validated:
            return
        
        self._build_graph()
        self._check_missing_dependencies()
        self._check_circular_dependencies()
        self._validated = True
    
    def _build_graph(self) -> None:
        """Build the dependency graph nodes."""
        self._nodes.clear()
        
        # Create nodes for all bindings
        for key, binding in self._bindings.items():
            dependencies = self._extract_dependencies(binding)
            node = GraphNode(key, binding, dependencies, set())
            self._nodes[key] = node
        
        # Build dependent relationships
        for node in self._nodes.values():
            for dep_key in node.dependencies:
                dep_node = self._nodes.get(dep_key)
                if dep_node:
                    dep_node.dependents.add(node.key)
    
    def _extract_dependencies(self, binding: Binding) -> List[BindingKey]:
        """Extract dependency keys from a binding."""
        if binding.binding_type == BindingType.INSTANCE:
            return []
        
        try:
            dependencies = SignatureIntrospector.extract_dependencies(binding.implementation)
            return SignatureIntrospector.get_binding_keys(dependencies)
        except Exception:
            # If introspection fails, assume no dependencies
            return []
    
    def _check_missing_dependencies(self) -> None:
        """Check for missing dependencies."""
        for node in self._nodes.values():
            for dep_key in node.dependencies:
                if dep_key not in self._bindings and dep_key not in self._set_bindings:
                    raise MissingBindingError(dep_key, node.key)
    
    def _check_circular_dependencies(self) -> None:
        """Check for circular dependencies using DFS."""
        WHITE = 0  # Not visited
        GRAY = 1   # Currently being processed
        BLACK = 2  # Completely processed
        
        colors: Dict[BindingKey, int] = defaultdict(lambda: WHITE)
        parent: Dict[BindingKey, Optional[BindingKey]] = {}
        
        def dfs(key: BindingKey, path: List[BindingKey]) -> None:
            if colors[key] == GRAY:
                # Found a back edge - circular dependency
                cycle_start = path.index(key)
                cycle = path[cycle_start:] + [key]
                raise CircularDependencyError(cycle)
            
            if colors[key] == BLACK:
                return
            
            colors[key] = GRAY
            path.append(key)
            
            node = self._nodes.get(key)
            if node:
                for dep_key in node.dependencies:
                    if dep_key in self._nodes:  # Only check dependencies that exist
                        parent[dep_key] = key
                        dfs(dep_key, path)
            
            path.pop()
            colors[key] = BLACK
        
        # Start DFS from all unvisited nodes
        for key in self._nodes:
            if colors[key] == WHITE:
                dfs(key, [])
    
    def get_topological_order(self) -> List[BindingKey]:
        """Get a topological ordering of the dependency graph."""
        if not self._validated:
            self.validate()
        
        in_degree: Dict[BindingKey, int] = defaultdict(int)
        
        # Calculate in-degrees
        for node in self._nodes.values():
            for dep_key in node.dependencies:
                if dep_key in self._nodes:
                    in_degree[dep_key] += 1
        
        # Initialize queue with nodes that have no dependencies
        queue = deque()
        for key in self._nodes:
            if in_degree[key] == 0:
                queue.append(key)
        
        result = []
        
        while queue:
            key = queue.popleft()
            result.append(key)
            
            node = self._nodes[key]
            for dep_key in node.dependencies:
                if dep_key in self._nodes:
                    in_degree[dep_key] -= 1
                    if in_degree[dep_key] == 0:
                        queue.append(dep_key)
        
        if len(result) != len(self._nodes):
            # This shouldn't happen if circular dependency check passed
            raise CircularDependencyError([])
        
        return result