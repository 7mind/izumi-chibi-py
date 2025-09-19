"""
PlannerInput - Immutable structure containing all inputs needed for dependency injection planning.
"""

from __future__ import annotations

from dataclasses import dataclass

from .activation import Activation
from .dsl import ModuleDef
from .roots import Roots


@dataclass(frozen=True)
class PlannerInput:
    """
    Immutable structure containing all inputs needed for dependency injection planning.

    This matches the original distage library design where the Injector is stateless
    and takes PlannerInput as arguments to planning methods.
    """

    modules: tuple[ModuleDef, ...]
    roots: Roots
    activation: Activation

    def __init__(
        self,
        modules: tuple[ModuleDef, ...] | list[ModuleDef],
        roots: Roots | None = None,
        activation: Activation | None = None,
    ):
        """
        Create a new PlannerInput.

        Args:
            modules: The modules containing bindings
            roots: The roots configuration (defaults to everything)
            activation: The activation configuration (defaults to empty)
        """
        # Convert to tuple if list is provided
        modules_tuple = tuple(modules) if isinstance(modules, list) else modules

        # Use object.__setattr__ since we're frozen
        object.__setattr__(self, "modules", modules_tuple)
        object.__setattr__(self, "roots", roots or Roots.everything())
        object.__setattr__(self, "activation", activation or Activation.empty())

    def with_roots(self, roots: Roots) -> PlannerInput:
        """Create a new PlannerInput with different roots."""
        return PlannerInput(self.modules, roots, self.activation)

    def with_activation(self, activation: Activation) -> PlannerInput:
        """Create a new PlannerInput with different activation."""
        return PlannerInput(self.modules, self.roots, activation)

    def with_modules(self, *additional_modules: ModuleDef) -> PlannerInput:
        """Create a new PlannerInput with additional modules."""
        new_modules = self.modules + additional_modules
        return PlannerInput(new_modules, self.roots, self.activation)

    @staticmethod
    def target(
        modules: tuple[ModuleDef, ...] | list[ModuleDef], *target_types: type
    ) -> PlannerInput:
        """
        Create a PlannerInput targeting specific types.

        Args:
            modules: The modules containing bindings
            target_types: The types to target as roots

        Returns:
            A PlannerInput configured to only produce the specified types
        """
        roots = Roots.target(*target_types)
        return PlannerInput(modules, roots)

    @staticmethod
    def everything(modules: tuple[ModuleDef, ...] | list[ModuleDef]) -> PlannerInput:
        """
        Create a PlannerInput that produces everything.

        Args:
            modules: The modules containing bindings

        Returns:
            A PlannerInput configured to produce all available bindings
        """
        return PlannerInput(modules, Roots.everything())
