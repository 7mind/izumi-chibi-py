"""
Factory functions for creating locator instances.
"""

from __future__ import annotations

from .locator_base import Locator
from .locator_impl import LocatorImpl
from .model import DIKey, Plan


def create_locator(plan: Plan, instances: dict[DIKey, object] | None = None, parent: Locator | None = None) -> Locator:
    """
    Create a new locator instance.

    Args:
        plan: The plan to execute
        instances: Initial instances
        parent: Parent locator (defaults to empty locator)

    Returns:
        A new locator instance
    """
    if parent is None:
        parent = Locator.empty()
    return LocatorImpl(plan, instances or {}, parent)