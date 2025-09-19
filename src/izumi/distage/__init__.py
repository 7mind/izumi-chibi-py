"""
Chibi Izumi - A Python re-implementation of core concepts from Scala's distage library.

This library provides dependency injection with:
- DSL for defining bindings
- Signature introspection for extracting names and types
- Dependency graph formation and validation
- Dependency resolution and execution
"""

# Enable beartype runtime type checking for specific modules
import warnings

from beartype import BeartypeConf, beartype
from beartype.roar import BeartypeCallHintViolation

from .activation import Activation, AxisChoiceDef, StandardAxis
from .bindings import Binding
from .dsl import ModuleDef
from .factory import Factory
from .functoid import Functoid
from .graph import DependencyGraph
from .injector import Injector
from .keys import DIKey, Id
from .locator import Locator
from .plan import Plan
from .planner_input import PlannerInput
from .resolver import DependencyResolver
from .roots import Roots
from .tag import Tag

# Configure beartype to throw errors for type violations
_beartype_conf = BeartypeConf(
    warning_cls_on_decorator_exception=UserWarning,  # Still warn on decorator issues to avoid startup failures
    is_color=False,  # Disable colors for better compatibility
    violation_type=BeartypeCallHintViolation,  # Throw errors for type violations
    is_debug=False,  # Disable debug mode for performance
)


# Function to safely apply beartype to a class
def _safe_beartype_class(cls: type) -> type:
    """Apply beartype to a class, with error handling."""
    try:
        return beartype(cls, conf=_beartype_conf)  # type: ignore[call-overload,no-any-return]
    except Exception as e:
        warnings.warn(f"Beartype failed to apply to {cls.__name__}: {e}", UserWarning, stacklevel=2)
        return cls


# Apply beartype to key classes that users interact with most
Injector = _safe_beartype_class(Injector)  # type: ignore[misc,assignment]
ModuleDef = _safe_beartype_class(ModuleDef)  # type: ignore[misc,assignment]
Plan = _safe_beartype_class(Plan)  # type: ignore[misc,assignment]
PlannerInput = _safe_beartype_class(PlannerInput)  # type: ignore[misc,assignment]
Locator = _safe_beartype_class(Locator)  # type: ignore[misc,assignment]
Tag = _safe_beartype_class(Tag)  # type: ignore[misc,assignment]

# Note: We avoid applying beartype to classes with complex generics or forward references
# to prevent the issues we saw earlier

__all__ = [
    "ModuleDef",
    "Injector",
    "Plan",
    "PlannerInput",
    "Locator",
    "Tag",
    "Binding",
    "DependencyGraph",
    "DependencyResolver",
    "Roots",
    "DIKey",
    "Id",
    "Activation",
    "StandardAxis",
    "AxisChoiceDef",
    "Factory",
    "Functoid",
]
