"""
Binding definitions and types for PyDistage.
"""

from typing import Any, Type, Optional, Union, Callable, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum

if TYPE_CHECKING:
    from .core import Tag


class BindingType(Enum):
    """Types of bindings supported."""
    CLASS = "class"
    INSTANCE = "instance" 
    FACTORY = "factory"
    SET_ELEMENT = "set_element"


@dataclass(frozen=True)
class BindingKey:
    """Unique key identifying a binding."""
    target_type: Type
    tag: Optional[Any] = None  # Use Any to avoid circular import
    
    def __str__(self) -> str:
        tag_str = f" {self.tag}" if self.tag else ""
        type_name = getattr(self.target_type, '__name__', str(self.target_type))
        return f"{type_name}{tag_str}"
    
    def __hash__(self) -> int:
        return hash((self.target_type, self.tag))


@dataclass(frozen=True)
class Binding:
    """A dependency injection binding."""
    key: BindingKey
    binding_type: BindingType
    implementation: Union[Type, Any, Callable]
    
    def __str__(self) -> str:
        impl_name = getattr(self.implementation, '__name__', str(self.implementation))
        return f"{self.key} -> {impl_name} ({self.binding_type.value})"