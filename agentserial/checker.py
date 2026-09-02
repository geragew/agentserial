from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from agentserial.invariants import (
    evaluate,
    validate_contract_effects,
    validate_contract_resources,
    values_equal,
)
from agentserial.models import (
    CheckResult,
    Contract,
    History,
    Operation,
    ResourceState,
    VerdictStatus,
    Witness,
)


@dataclass(frozen=True)
class _SearchSummary:
    safe: int = 0
    unsafe: int = 0
    safe_suffix: tuple[str, ...] | None = None
    unsafe_suffix: tuple[str, ...] | None = None
    unsafe_violations: tuple[str, ...] = ()


def check(
    history: History,
    contract: Contract,
    *,
    max_operations: int = 10,
    max_prefixes: int = 100_000,
    shrink: bool = True,
) -> CheckResult:
    base = {
        "history_id": history.history_id,
        "operations": len(history.operations),
        "agents": len({operation.agent for operation in history.operations}),
    }
    contract_errors = validate_contract_resources(contract, history.initial_state)
    contract_errors.extend(validate_contract_effects(contract, history))
    if contract_errors:
        return CheckResult(status=VerdictStatus.INVALID_CONTRACT, errors=contract_errors, **base)

    successful = {operation.id: operation for operation in history.operations if operation.status == "success"}
    if len(successful) > max_operations:
        return CheckResult(
            status=VerdictStatus.INCONCLUSIVE,
            errors=[f"successful operation limit exceeded: {len(successful)} > {max_operations}"],
            **base,
        )

    edges = _project_edges(history, set(successful))
    predecessors = {operation_id: set() for operation_id in successful}
    for before, after in edges:
        predecessors[after].add(before)

    explored = 0
    read_conflicts: list[str] = []
    limit_reached = False
    initial_violations = evaluate(contract, history.initial_state)
    cache: dict[tuple[Any, ...], _SearchSummary] = {}

    def visit(
        completed: frozenset[str],
        state: dict[str, ResourceState],
        violations: tuple[str, ...],
    ) -> _SearchSummary:
        nonlocal explored, limit_reached
        if limit_reached:
            return _SearchSummary()
        cache_key = (completed, _freeze_state(state), violations)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        if len(completed) == len(successful):
            if violations:
                return _SearchSummary(unsafe=1, unsafe_suffix=(), unsafe_violations=violations)
            return _SearchSummary(safe=1, safe_suffix=())

        ready = sorted(
            operation_id
            for operation_id in successful
            if operation_id not in completed and predecessors[operation_id] <= completed
        )
        safe_count = 0
        unsafe_count = 0
        safe_suffix: tuple[str, ...] | None = None
        unsafe_suffix: tuple[str, ...] | None = None
        unsafe_violations: tuple[str, ...] = ()
        for operation_id in ready:
            if explored >= max_prefixes:
                limit_reached = True
                break
            explored += 1
            operation = successful[operation_id]
            conflicts = _read_conflicts(operation, state)
            if conflicts:
                for conflict in conflicts:
                    if conflict not in read_conflicts:
                        read_conflicts.append(conflict)
                continue
            next_state = _apply(operation, state)
            next_violations = tuple(dict.fromkeys(violations + tuple(evaluate(contract, next_state))))
            child = visit(completed | {operation_id}, next_state, next_violations)
            safe_count += child.safe
            unsafe_count += child.unsafe
            if safe_suffix is None and child.safe_suffix is not None:
                safe_suffix = (operation_id,) + child.safe_suffix
            if unsafe_suffix is None and child.unsafe_suffix is not None:
                unsafe_suffix = (operation_id,) + child.unsafe_suffix
                unsafe_violations = child.unsafe_violations
        summary = _SearchSummary(
            safe=safe_count,
            unsafe=unsafe_count,
            safe_suffix=safe_suffix,
            unsafe_suffix=unsafe_suffix,
            unsafe_violations=unsafe_violations,
        )
        if not limit_reached:
            cache[cache_key] = summary
        return summary

    search = visit(frozenset(), deepcopy(history.initial_state), tuple(dict.fromkeys(initial_violations)))
    safe_count = search.safe
    unsafe_count = search.unsafe
    safe_witness = Witness(order=list(search.safe_suffix)) if search.safe_suffix is not None else None
    unsafe_witness = (
        Witness(order=list(search.unsafe_suffix), violations=list(search.unsafe_violations))
        if search.unsafe_suffix is not None
        else None
    )

    if limit_reached:
        return CheckResult(
            status=VerdictStatus.INCONCLUSIVE,
            feasible_replays=safe_count + unsafe_count,
            safe_replays=safe_count,
            unsafe_replays=unsafe_count,
            explored_prefixes=explored,
            safe_witness=safe_witness,
            unsafe_witness=unsafe_witness,
            read_conflicts=read_conflicts,
            errors=[f"explored prefix limit reached: {max_prefixes}"],
            **base,
        )
    if safe_count and unsafe_count:
        status = VerdictStatus.SCHEDULE_DEPENDENT
    elif safe_count:
        status = VerdictStatus.ROBUST_PASS
    elif unsafe_count:
        status = VerdictStatus.CONTRACT_FAIL
    else:
        status = VerdictStatus.INCONSISTENT_HISTORY

    result = CheckResult(
        status=status,
        feasible_replays=safe_count + unsafe_count,
        safe_replays=safe_count,
        unsafe_replays=unsafe_count,
        explored_prefixes=explored,
        safe_witness=safe_witness,
        unsafe_witness=unsafe_witness,
        read_conflicts=read_conflicts if status == VerdictStatus.INCONSISTENT_HISTORY else [],
        **base,
    )
    if shrink and status in {
        VerdictStatus.SCHEDULE_DEPENDENT,
        VerdictStatus.CONTRACT_FAIL,
        VerdictStatus.INCONSISTENT_HISTORY,
    }:
        from agentserial.shrink import shrink_history

        result.reduced_counterexample = shrink_history(
            history,
            contract,
            status,
            max_operations=max_operations,
            max_prefixes=max_prefixes,
        )
        reduced = set(result.reduced_counterexample)
        result.counterexample_operations = [
            operation for operation in history.operations if operation.id in reduced
        ]
    return result


def _freeze_state(state: dict[str, ResourceState]) -> tuple[Any, ...]:
    return tuple(
        (name, _freeze_value(resource.value), resource.version)
        for name, resource in sorted(state.items())
    )


def _freeze_value(value: Any) -> tuple[str, Any]:
    if isinstance(value, list):
        return ("list", tuple(_freeze_value(item) for item in value))
    return (type(value).__name__, value)


def _read_conflicts(operation: Operation, state: dict[str, ResourceState]) -> list[str]:
    conflicts: list[str] = []
    for read in operation.reads:
        actual = state[read.resource]
        if actual.version != read.version or not values_equal(actual.value, read.value):
            conflicts.append(
                f"{operation.id} read {read.resource}={read.value!r}@v{read.version}, "
                f"but replay state was {actual.value!r}@v{actual.version}"
            )
    return conflicts


def _apply(operation: Operation, state: dict[str, ResourceState]) -> dict[str, ResourceState]:
    next_state = deepcopy(state)
    touched: set[str] = set()
    for effect in operation.effects:
        resource = next_state[effect.resource]
        if effect.type == "set":
            resource.value = deepcopy(effect.value)
        elif effect.type == "increment":
            resource.value += effect.value
        else:
            resource.value.append(deepcopy(effect.value))
        touched.add(effect.resource)
    for resource_name in touched:
        next_state[resource_name].version += 1
    return next_state


def _project_edges(history: History, retained: set[str]) -> set[tuple[str, str]]:
    nodes = {operation.id for operation in history.operations}
    adjacency = {node: set() for node in nodes}
    for edge in history.order:
        adjacency[edge.before].add(edge.after)
    projected: set[tuple[str, str]] = set()
    for source in retained:
        pending = list(adjacency[source])
        seen: set[str] = set()
        while pending:
            target = pending.pop()
            if target in seen:
                continue
            seen.add(target)
            pending.extend(adjacency[target])
        projected.update((source, target) for target in seen if target in retained)
    return projected
