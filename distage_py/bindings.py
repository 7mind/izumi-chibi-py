"""
Binding definitions and types for PyDistage.
"""

from typing import Any, Type, Optional, Union, Callable, TYPE_CHECKING, Set
from dataclasses import dataclass
from enum import Enum

if TYPE_CHECKING:
    from .core import Tag
    from .activation import AxisChoiceDef


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
    activation_tags: Set[Any] = None  # Use Any to avoid circular import issues
    
    def __post_init__(self):
        if self.activation_tags is None:
            object.__setattr__(self, 'activation_tags', set())
    
    def matches_activation(self, activation: 'Activation') -> bool:
        """Check if this binding matches the given activation."""
        if not self.activation_tags:
            return True  # Untagged bindings match any activation
        
        # Import here to avoid circular import
        from .activation import Activation
        
        if isinstance(activation, Activation):
            return activation.is_compatible_with_tags(self.activation_tags)
        
        return True
    
    def __str__(self) -> str:
        impl_name = getattr(self.implementation, '__name__', str(self.implementation))
        tags_str = f" {{{', '.join(str(tag) for tag in self.activation_tags)}}}" if self.activation_tags else ""
        return f"{self.key} -> {impl_name}{tags_str} ({self.binding_type.value})"