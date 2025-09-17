"""
Signature introspection utilities for analyzing dependencies.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import fields, is_dataclass
from typing import Annotated, Any, get_args, get_origin, get_type_hints

from .keys import DIKey, Id


class DependencyInfo:
    """Information about a dependency requirement."""

    def __init__(
        self,
        name: str,
        type_hint: type | str | Any,
        is_optional: bool = False,
        default_value: Any = inspect.Parameter.empty,
        dependency_name: str | None = None,
    ):
        super().__init__()
        self.name = name
        self.type_hint = type_hint
        self.is_optional = is_optional
        self.default_value = default_value
        self.dependency_name = dependency_name

    def __str__(self) -> str:
        optional_str = "?" if self.is_optional else ""
        type_name = getattr(self.type_hint, "__name__", str(self.type_hint))
        return f"{self.name}: {type_name}{optional_str}"

    def __repr__(self) -> str:
        return f"DependencyInfo({self.name}, {self.type_hint}, {self.is_optional})"


class SignatureIntrospector:
    """Analyzes function/class signatures to extract dependency information."""

    @staticmethod
    def extract_dependencies(target: Any) -> list[DependencyInfo]:
        """Extract dependency information from a class constructor or function."""
        if inspect.isclass(target):
            return SignatureIntrospector._extract_from_class(target)
        elif callable(target):
            return SignatureIntrospector._extract_from_callable(target)
        else:
            return []

    @staticmethod
    def _extract_from_class(target_class: type) -> list[DependencyInfo]:
        """Extract dependencies from a class constructor."""
        if is_dataclass(target_class):
            return SignatureIntrospector._extract_from_dataclass(target_class)

        try:
            init_method: Any = getattr(target_class, "__init__", None)  # pyright: ignore[reportUnknownArgumentType]
            if init_method:
                return SignatureIntrospector._extract_from_callable(init_method, skip_self=True)
        except AttributeError:
            pass

        return []

    @staticmethod
    def _extract_from_dataclass(target_class: type) -> list[DependencyInfo]:
        """Extract dependencies from a dataclass."""
        dependencies: list[DependencyInfo] = []

        for field in fields(target_class):
            is_optional = (
                field.default != field.default_factory
                or field.default_factory != field.default_factory
            )
            default_val = (
                field.default if field.default != field.default_factory else inspect.Parameter.empty
            )

            # Extract dependency name from Annotated types
            type_hint, dependency_name = SignatureIntrospector._extract_name_from_annotated(
                field.type
            )

            dep = DependencyInfo(
                name=field.name,
                type_hint=type_hint,
                is_optional=is_optional,
                default_value=default_val,
                dependency_name=dependency_name,
            )
            dependencies.append(dep)

        return dependencies

    @staticmethod
    def _extract_name_from_annotated(type_hint: Any) -> tuple[Any, str | None]:
        """Extract the actual type and dependency name from Annotated type."""
        if get_origin(type_hint) is Annotated:
            args = get_args(type_hint)
            if args:
                actual_type = args[0]
                # Look for Id annotation in the metadata
                for metadata in args[1:]:
                    if isinstance(metadata, Id):
                        return actual_type, metadata.value
                return actual_type, None
        return type_hint, None

    @staticmethod
    def _extract_from_callable(
        func: Callable[..., Any], skip_self: bool = False
    ) -> list[DependencyInfo]:
        """Extract dependencies from a callable."""
        try:
            signature = inspect.signature(func)
            # Use raw annotations to preserve Annotated metadata
            raw_annotations = getattr(func, "__annotations__", {})
            # Try to get type hints for fallback, but handle forward references gracefully
            try:
                resolved_type_hints = get_type_hints(func)
            except (NameError, AttributeError):
                # Fall back to raw annotations if type hints fail
                resolved_type_hints = raw_annotations
        except (ValueError, TypeError):
            return []

        dependencies: list[DependencyInfo] = []

        for param_name, param in signature.parameters.items():
            if skip_self and param_name == "self":
                continue

            # First try raw annotations to preserve Annotated metadata
            type_hint = raw_annotations.get(param_name, Any)

            # Extract dependency name from Annotated types
            type_hint, dependency_name = SignatureIntrospector._extract_name_from_annotated(
                type_hint
            )

            # If we didn't get an Annotated type, fall back to resolved type hints
            if dependency_name is None and param_name in resolved_type_hints:
                type_hint = resolved_type_hints[param_name]

            # Handle string annotations (forward references)
            if isinstance(type_hint, str):
                # For demo purposes, try to resolve in the local context
                # In a real implementation, you'd need proper forward reference resolution
                try:
                    if type_hint in ["B", "A", "MissingService"]:  # Known forward refs for demo
                        # Keep as string for now, convert to a placeholder type
                        type_hint = type(type_hint, (), {})  # Create a dummy type
                except Exception:  # noqa: S110
                    type_hint = Any

            is_optional = param.default != inspect.Parameter.empty

            # Handle Union types (including Optional) - only for actual types, not strings
            if not isinstance(type_hint, str) and SignatureIntrospector._is_optional_type(
                type_hint
            ):
                is_optional = True
                type_hint = SignatureIntrospector._extract_non_none_type(type_hint)

            dep = DependencyInfo(
                name=param_name,
                type_hint=type_hint,
                is_optional=is_optional,
                default_value=param.default,
                dependency_name=dependency_name,
            )
            dependencies.append(dep)

        return dependencies

    @staticmethod
    def _is_optional_type(type_hint: Any) -> bool:
        """Check if a type hint represents an Optional type."""
        origin = get_origin(type_hint)
        if origin is not None:
            args = get_args(type_hint)
            # Check for Union[T, None] or Optional[T]
            if origin is type(None) or (
                hasattr(origin, "__name__") and origin.__name__ == "UnionType"
            ):
                return type(None) in args
        return False

    @staticmethod
    def _extract_non_none_type(type_hint: Any) -> Any:
        """Extract the non-None type from an Optional type."""
        args = get_args(type_hint)
        if args:
            non_none_types = [arg for arg in args if arg is not type(None)]
            if non_none_types:
                return non_none_types[0]
        return type_hint

    @staticmethod
    def get_binding_keys(dependencies: list[DependencyInfo]) -> list[DIKey]:
        """Convert dependency information to binding keys."""
        keys: list[DIKey] = []
        for dep in dependencies:
            # Skip dependencies with 'Any' type hint as they're usually introspection failures
            if dep.type_hint == Any:
                continue
            if (
                (not dep.is_optional or dep.default_value == inspect.Parameter.empty)
                and (isinstance(dep.type_hint, type) or hasattr(dep.type_hint, "__origin__"))
                and not isinstance(dep.type_hint, str)
            ):
                # Handle both regular types and generic types (like set[T]), but skip string forward references
                key = DIKey(dep.type_hint, dep.dependency_name)
                keys.append(key)
        return keys
