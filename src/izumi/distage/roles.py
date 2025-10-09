from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .activation import Activation
from .dsl import ModuleDef
from .injector import Injector
from .model import InstanceKey
from .planner_input import PlannerInput
from .roots import Roots


@dataclass(frozen=True)
class EntrypointArgs:
    role_id: str
    raw_args: list[str]


class RoleDescriptor(ABC):
    @property
    @abstractmethod
    def id(self) -> str:
        pass


class RoleService(ABC):
    @abstractmethod
    def start(self, args: EntrypointArgs) -> Any:
        pass


class RoleTask(ABC):
    @abstractmethod
    def start(self, args: EntrypointArgs) -> Any:
        pass


@dataclass(frozen=True)
class RoleInvocation:
    role_id: str
    args: list[str]


def parse_role_args(argv: list[str]) -> list[RoleInvocation]:
    invocations: list[RoleInvocation] = []
    current_role: str | None = None
    current_args: list[str] = []

    for arg in argv:
        if arg.startswith(":"):
            if current_role is not None:
                invocations.append(RoleInvocation(current_role, current_args))
            current_role = arg[1:]
            current_args = []
        else:
            if current_role is not None:
                current_args.append(arg)

    if current_role is not None:
        invocations.append(RoleInvocation(current_role, current_args))

    return invocations


class RoleAppMain:
    def __init__(self) -> None:
        self._modules: list[ModuleDef] = []
        self._activation: Activation = Activation.empty()

    def add_module(self, module: ModuleDef) -> RoleAppMain:
        self._modules.append(module)
        return self

    def with_activation(self, activation: Activation) -> RoleAppMain:
        self._activation = activation
        return self

    def main(self, argv: list[str] | None = None) -> None:
        if argv is None:
            argv = sys.argv[1:]

        invocations = parse_role_args(argv)

        if not invocations:
            print("No roles specified. Use :rolename to specify a role.")
            return

        role_bindings_map: dict[str, tuple[type, InstanceKey]] = {}
        for module in self._modules:
            for binding in module.bindings:
                key = binding.key
                if isinstance(key, InstanceKey) and hasattr(key.target_type, "__mro__"):
                    for base in key.target_type.__mro__:
                        if base in (RoleService, RoleTask):
                            if hasattr(key.target_type, "id"):
                                role_id: str = key.target_type.id  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
                                role_bindings_map[role_id] = (key.target_type, key)
                            break

        for invocation in invocations:
            role_id = invocation.role_id
            if role_id not in role_bindings_map:
                print(f"Role '{role_id}' not found.")
                continue

            role_type, role_key = role_bindings_map[role_id]
            roots = Roots.target(role_type)
            planner_input = PlannerInput(self._modules, roots, self._activation)

            injector = Injector()
            plan = injector.plan(planner_input)
            locator = injector.produce(plan)

            role_instance = locator.get(role_key)
            entrypoint_args = EntrypointArgs(role_id, invocation.args)
            role_instance.start(entrypoint_args)
