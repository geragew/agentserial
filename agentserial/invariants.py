from __future__ import annotations

import json

from agentserial.models import (
    Contract,
    EqualsInvariant,
    History,
    MaxSumInvariant,
    MinValueInvariant,
    ResourceState,
    UniqueInvariant,
)


def validate_contract_resources(contract: Contract, state: dict[str, ResourceState]) -> list[str]:
    errors: list[str] = []
    for invariant in contract.invariants:
        names = [invariant.left, invariant.right] if isinstance(invariant, EqualsInvariant) else [invariant.resource]
        missing = False
        for name in names:
            if name not in state:
                errors.append(f"invariant {invariant.id!r} references unknown resource {name!r}")
                missing = True
        if missing:
            continue
        if isinstance(invariant, MaxSumInvariant):
            value = state[invariant.resource].value
            if not isinstance(value, list) or any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
                errors.append(f"invariant {invariant.id!r} requires a list of numbers")
        elif isinstance(invariant, MinValueInvariant):
            value = state[invariant.resource].value
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"invariant {invariant.id!r} requires a numeric resource")
        elif isinstance(invariant, UniqueInvariant):
            if not isinstance(state[invariant.resource].value, list):
                errors.append(f"invariant {invariant.id!r} requires a list resource")
    return errors


def validate_contract_effects(contract: Contract, history: History) -> list[str]:
    errors: list[str] = []
    for invariant in contract.invariants:
        for operation in history.operations:
            for effect in operation.effects:
                if isinstance(invariant, MaxSumInvariant) and effect.resource == invariant.resource:
                    if effect.type == "append" and (
                        isinstance(effect.value, bool) or not isinstance(effect.value, (int, float))
                    ):
                        errors.append(
                            f"invariant {invariant.id!r} cannot evaluate non-numeric append in {operation.id!r}"
                        )
                elif isinstance(invariant, MinValueInvariant) and effect.resource == invariant.resource:
                    if effect.type == "set" and (
                        isinstance(effect.value, bool) or not isinstance(effect.value, (int, float))
                    ):
                        errors.append(
                            f"invariant {invariant.id!r} cannot evaluate non-numeric set in {operation.id!r}"
                        )
    return errors


def evaluate(contract: Contract, state: dict[str, ResourceState]) -> list[str]:
    violations: list[str] = []
    for invariant in contract.invariants:
        if isinstance(invariant, MaxSumInvariant):
            actual = sum(state[invariant.resource].value)
            if actual > invariant.max:
                violations.append(f"{invariant.id}: sum({invariant.resource})={actual} exceeds {invariant.max}")
        elif isinstance(invariant, MinValueInvariant):
            actual = state[invariant.resource].value
            if actual < invariant.min:
                violations.append(f"{invariant.id}: {invariant.resource}={actual} is below {invariant.min}")
        elif isinstance(invariant, UniqueInvariant):
            values = state[invariant.resource].value
            encoded = [json.dumps(value, sort_keys=True, separators=(",", ":")) for value in values]
            if len(encoded) != len(set(encoded)):
                violations.append(f"{invariant.id}: {invariant.resource} contains duplicate values")
        elif isinstance(invariant, EqualsInvariant):
            left = state[invariant.left].value
            right = state[invariant.right].value
            if _encoded(left) != _encoded(right):
                violations.append(f"{invariant.id}: {invariant.left}={left!r} differs from {invariant.right}={right!r}")
    return violations


def values_equal(left: object, right: object) -> bool:
    return _encoded(left) == _encoded(right)


def _encoded(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
