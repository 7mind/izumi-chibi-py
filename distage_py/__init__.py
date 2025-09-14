"""
PyDistage - A Python re-implementation of core concepts from Scala's distage library.

This library provides dependency injection with:
- DSL for defining bindings
- Signature introspection for extracting names and types
- Dependency graph formation and validation
- Dependency resolution and execution
"""

from .core import ModuleDef, Injector, Tag
from .bindings import Binding, BindingKey
from .graph import DependencyGraph
from .resolver import DependencyResolver
from .roots import Roots, DIKey
from .activation import Activation, StandardAxis, AxisChoiceDef

__all__ = [
    'ModuleDef', 
    'Injector', 
    'Tag',
    'Binding',
    'BindingKey', 
    'DependencyGraph',
    'DependencyResolver',
    'Roots',
    'DIKey',
    'Activation',
    'StandardAxis',
    'AxisChoiceDef'
]