"""
Path-aware activation context for tracing dependency resolution.

This module implements the tracing logic from the original Scala distage,
where axis point validation is path-aware during dependency traversal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .activation import Activation, Axis, AxisChoiceDef

if TYPE_CHECKING:
    from .model.bindings import Binding


@dataclass(frozen=True)
class ActivationContext:
    """
    Tracks valid axis choices during dependency traversal.

    The context maintains two sets of axis points:
    1. User-selected choices (from Activation)
    2. Implied choices from bindings selected on the current path

    When traversing dependencies, if we select a binding with tags [axis1:1, axis2:1],
    then those axis points become part of the context. Any binding requiring
    conflicting axis points (e.g., axis2:2) becomes invalid for the rest of this path.
    """

    user_activation: Activation
    implied_choices: frozenset[AxisChoiceDef]

    @staticmethod
    def from_activation(activation: Activation) -> ActivationContext:
        """Create a context from user activation."""
        return ActivationContext(
            user_activation=activation,
            implied_choices=frozenset(),
        )

    def with_binding_tags(self, binding: Binding) -> ActivationContext:
        """
        Extend the context with tags from a selected binding.

        This creates a new context that includes the axis points from the binding's tags.
        These become "implied choices" that constrain valid bindings further down the path.
        """
        if not binding.activation_tags:
            return self

        new_implied = set(self.implied_choices)
        new_implied.update(binding.activation_tags)

        return ActivationContext(
            user_activation=self.user_activation,
            implied_choices=frozenset(new_implied),
        )

    def is_binding_valid(self, binding: Binding) -> bool:
        """
        Check if a binding is valid in this context.

        A binding is valid if:
        1. For each axis where user/context has made a choice: binding must either
           have NO choice for that axis, or have a matching choice
        2. Bindings can have tags for axes that user hasn't selected (these are allowed)
        """
        if not binding.activation_tags:
            return True

        # Group binding's tags by their axis
        binding_tags_by_axis = self._group_tags_by_axis(binding.activation_tags)

        # Check each axis that the binding has tags for
        for axis_type, tag_choices in binding_tags_by_axis.items():
            # The binding should have exactly one choice per axis
            if len(tag_choices) > 1:
                # This shouldn't happen - a binding having multiple choices for same axis
                return False

            tag_choice = tag_choices[0]

            # Check if user has selected a choice for this axis
            user_choice = self.user_activation.get_choice(axis_type)
            if user_choice is not None and tag_choice != user_choice:
                # Binding conflicts with user's choice
                return False

            # Check if there's an implied choice for this axis from the traversal path
            implied_choice = self._get_implied_choice_for_axis(axis_type)
            if implied_choice is not None and tag_choice != implied_choice:
                # Binding conflicts with implied choice from path
                return False

        return True

    def get_all_choices(self) -> dict[type[Axis], AxisChoiceDef]:
        """
        Get all active choices (user + implied).

        This combines user choices with implied choices from the traversal path.
        """
        choices = dict(self.user_activation.choices)

        # Add implied choices, grouping by axis
        for implied_tag in self.implied_choices:
            axis_type = self._find_axis_for_tag(implied_tag)
            if axis_type is not None:
                # Implied choices override user choices (they are more specific)
                choices[axis_type] = implied_tag

        return choices

    def _group_tags_by_axis(
        self, tags: set[AxisChoiceDef]
    ) -> dict[type[Axis], list[AxisChoiceDef]]:
        """Group tags by their axis type."""
        result: dict[type[Axis], list[AxisChoiceDef]] = {}

        for tag in tags:
            axis_type = self._find_axis_for_tag(tag)
            if axis_type is not None:
                if axis_type not in result:
                    result[axis_type] = []
                result[axis_type].append(tag)

        return result

    def _get_implied_choice_for_axis(self, axis_type: type[Axis]) -> AxisChoiceDef | None:
        """Get the implied choice for a specific axis from the current path."""
        for implied_tag in self.implied_choices:
            if self._tag_belongs_to_axis(implied_tag, axis_type):
                return implied_tag
        return None

    def _find_axis_for_tag(self, tag: AxisChoiceDef) -> type[Axis] | None:
        """Find which axis type a tag belongs to."""
        # First check user activation's axes
        for axis_type, choice in self.user_activation.choices.items():
            if self._tag_belongs_to_axis(tag, axis_type):
                return axis_type

        # If not found in user choices, check implied choices
        # This handles cases where we're looking for a tag that's part of
        # an axis we've encountered during traversal
        for implied_tag in self.implied_choices:
            # Try to find the axis for this implied tag
            for axis_type in self.user_activation.choices.keys():
                if self._tag_belongs_to_axis(implied_tag, axis_type):
                    # Check if the original tag also belongs to this axis
                    if self._tag_belongs_to_axis(tag, axis_type):
                        return axis_type

        # Fallback: check StandardAxis for backward compatibility
        from .activation import StandardAxis

        for axis_name in ["Mode", "Repo", "World"]:
            if hasattr(StandardAxis, axis_name):
                axis_class = getattr(StandardAxis, axis_name)
                if self._tag_belongs_to_axis(tag, axis_class):
                    return axis_class

        return None

    def _tag_belongs_to_axis(self, tag: AxisChoiceDef, axis_type: type[Axis]) -> bool:
        """Check if a tag belongs to a specific axis."""
        # Check if the axis type has an attribute with the tag's name
        # and if that attribute equals the tag
        if hasattr(axis_type, tag.name):
            axis_value = getattr(axis_type, tag.name)
            # Check both direct equality and string equality
            if axis_value == tag or str(axis_value) == str(tag):
                return True

        return False

    def __str__(self) -> str:
        user_str = str(self.user_activation)
        if self.implied_choices:
            implied_str = ", ".join(str(tag) for tag in self.implied_choices)
            return f"ActivationContext({user_str}, implied=[{implied_str}])"
        return f"ActivationContext({user_str})"
