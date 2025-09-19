"""
Automatic logger injection support for Python's standard logging module.

This module provides automatic creation of named loggers based on the location
where they are requested, eliminating the need for manual logger setup.
"""

from __future__ import annotations

import inspect
import logging
from types import FrameType
from typing import Any

from .bindings import Binding
from .functoid import function_functoid
from .keys import DIKey


class LoggerLocationIntrospector:
    """Introspects the call stack to determine where a logger is being requested."""

    @staticmethod
    def get_logger_location_name() -> str:
        """
        Introspect the call stack to find the location where a logger is needed.

        Returns a location name suitable for logger naming in the format:
        module_name.class_name or module_name.function_name
        """
        # Walk up the call stack to find the first frame outside the DI system
        frame = inspect.currentframe()
        if frame is None:
            return "__unknown__"

        try:
            # Skip frames within the DI system and look for the first meaningful user code
            frames_to_check: list[FrameType] = []
            current_frame = frame.f_back
            while current_frame is not None:
                filename: str = current_frame.f_code.co_filename
                # Skip frames within the distage package and other internal frames
                if (
                    "/distage/" not in filename
                    and "\\distage\\" not in filename
                    and not filename.endswith("beartype")
                    and "<" not in filename  # Skip dynamic code frames
                ):
                    frames_to_check.append(current_frame)
                current_frame = current_frame.f_back

            # Look for the best frame - prefer constructors and meaningful user code
            for check_frame in frames_to_check:
                frame_filename: str = check_frame.f_code.co_filename
                frame_function_name: str = check_frame.f_code.co_name

                # Look for constructor calls first, as that's where DI happens
                if frame_function_name == "__init__":
                    # For constructors, try to get a more specific name including the class
                    class_name = LoggerLocationIntrospector._get_class_name_from_frame(check_frame)
                    module_name = LoggerLocationIntrospector._get_module_name_from_filename(
                        frame_filename
                    )
                    if class_name:
                        return f"{module_name}.{class_name}"
                    else:
                        return LoggerLocationIntrospector._extract_location_from_frame(check_frame)

            # If no constructor found, look for other meaningful user code
            for check_frame in frames_to_check:
                frame_function_name2: str = check_frame.f_code.co_name

                # Skip internal methods but allow main functions
                if (
                    not frame_function_name2.startswith("_")
                    and frame_function_name2 not in ["<module>"]
                    and not frame_function_name2.startswith(
                        "test_"
                    )  # Skip test methods for cleaner names
                ):
                    return LoggerLocationIntrospector._extract_location_from_frame(check_frame)

            # If no good frame found, use the first available frame
            if frames_to_check:
                return LoggerLocationIntrospector._extract_location_from_frame(frames_to_check[0])

            return "__unknown__"
        finally:
            # Clean up frame references to avoid memory leaks
            del frame

    @staticmethod
    def _extract_location_from_frame(frame: FrameType) -> str:
        """Extract a meaningful location name from a stack frame."""
        code = frame.f_code
        filename = code.co_filename
        function_name = code.co_name

        # Try to get the module name from the filename
        module_name = LoggerLocationIntrospector._get_module_name_from_filename(filename)

        # Check if we're inside a class method
        class_name = LoggerLocationIntrospector._get_class_name_from_frame(frame)

        if class_name:
            return f"{module_name}.{class_name}"
        else:
            return f"{module_name}.{function_name}"

    @staticmethod
    def _get_module_name_from_filename(filename: str) -> str:
        """Extract module name from a filename."""
        # Handle different path separators by normalizing path
        import os

        # Normalize path separators to work on all systems
        normalized_path = filename.replace("\\", "/")
        name = os.path.basename(normalized_path)

        # Remove .py extension
        if name.endswith(".py"):
            name = name[:-3]

        # Handle special cases
        if name == "__main__":
            return "__main__"
        elif name == "<stdin>":
            return "__interactive__"
        elif name.startswith("<"):
            return "__dynamic__"
        else:
            return name

    @staticmethod
    def _get_class_name_from_frame(frame: FrameType) -> str | None:
        """Try to determine if we're inside a class method and get the class name."""
        # Look for 'self' or 'cls' parameters
        local_vars = frame.f_locals

        if "self" in local_vars:
            self_obj = local_vars["self"]
            return type(self_obj).__name__
        elif "cls" in local_vars:
            cls_obj = local_vars["cls"]
            if inspect.isclass(cls_obj):
                return cls_obj.__name__

        # Try to get class name from code context (less reliable)
        code = frame.f_code
        if code.co_varnames and len(code.co_varnames) > 0:
            first_param = code.co_varnames[0]
            if first_param in ["self", "cls"] and first_param in local_vars:
                obj = local_vars[first_param]
                if hasattr(obj, "__class__"):
                    return str(obj.__class__.__name__)
                elif inspect.isclass(obj):
                    return str(obj.__name__)

        return None


class AutoLoggerManager:
    """Manages automatic logger injection for the dependency injection system."""

    @staticmethod
    def create_logger_factory(logger_name: str) -> Any:
        """Create a factory function that creates a logger with the given name."""

        def logger_factory() -> logging.Logger:
            return logging.getLogger(logger_name)

        return logger_factory

    @staticmethod
    def create_logger_binding(location_name: str) -> Binding:
        """
        Create a binding for a logger with automatic naming.

        Args:
            location_name: The location-specific name for the logger

        Returns:
            A Binding that creates a logger with the appropriate name
        """
        # Create the logger name in the format __logger__.location_name
        logger_name = f"__logger__.{location_name}"

        # Create a factory function that creates the logger
        factory = AutoLoggerManager.create_logger_factory(location_name)

        # Create the binding key for the named logger
        logger_key = DIKey(logging.Logger, logger_name)

        # Create the functoid
        functoid = function_functoid(factory)

        # Create and return the binding
        return Binding(logger_key, functoid)

    @staticmethod
    def should_auto_inject_logger(key: DIKey) -> bool:
        """
        Check if a dependency key should trigger automatic logger injection.

        Args:
            key: The dependency key to check

        Returns:
            True if this key should trigger automatic logger injection
        """
        return (
            key.target_type is logging.Logger
            and key.name is None  # Only auto-inject for unnamed logger dependencies
        )

    @staticmethod
    def rewrite_logger_key(original_key: DIKey, location_name: str) -> DIKey:  # noqa: ARG004
        """
        Rewrite a logger dependency key to point to the auto-generated logger.

        Args:
            original_key: The original logger key (without name)
            location_name: The location where the logger is needed

        Returns:
            A new DIKey pointing to the location-specific logger
        """
        logger_name = f"__logger__.{location_name}"
        return DIKey(logging.Logger, logger_name)
