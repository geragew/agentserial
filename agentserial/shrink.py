from __future__ import annotations

from agentserial.models import Contract, History, OrderingConstraint, VerdictStatus


def shrink_history(
    history: History,
    contract: Contract,
    target: VerdictStatus,
    *,
    max_operations: int,
    max_prefixes: int,
) -> list[str]:
    from agentserial.checker import check

    retained = sorted(operation.id for operation in history.operations if operation.status == "success")
    changed = True
    while changed:
        changed = False
        for operation_id in list(retained):
            candidate_ids = [item for item in retained if item != operation_id]
            candidate = _subset(history, set(candidate_ids))
            result = check(
                candidate,
                contract,
                max_operations=max_operations,
                max_prefixes=max_prefixes,
                shrink=False,
            )
            if result.status == target:
                retained = candidate_ids
                changed = True
                break
    return retained


def _subset(history: History, retained: set[str]) -> History:
    nodes = {operation.id for operation in history.operations}
    adjacency = {node: set() for node in nodes}
    for edge in history.order:
        adjacency[edge.before].add(edge.after)
    projected: list[OrderingConstraint] = []
    for source in sorted(retained):
        pending = list(adjacency[source])
        seen: set[str] = set()
        while pending:
            target = pending.pop()
            if target in seen:
                continue
            seen.add(target)
            pending.extend(adjacency[target])
        for target in sorted(seen & retained):
            projected.append(OrderingConstraint(before=source, after=target))
    return history.model_copy(
        update={
            "operations": [operation for operation in history.operations if operation.id in retained],
            "order": projected,
        }
    )

