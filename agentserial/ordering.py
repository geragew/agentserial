from __future__ import annotations

from collections.abc import Iterable

from agentserial.models import OrderingConstraint

Edge = tuple[str, str]


def project_order(
    operation_ids: Iterable[str],
    constraints: Iterable[OrderingConstraint],
    retained: set[str],
) -> set[Edge]:
    """Preserve reachability when operations are removed from an ordering DAG."""
    adjacency = {operation_id: set() for operation_id in operation_ids}
    for constraint in constraints:
        adjacency[constraint.before].add(constraint.after)

    projected: set[Edge] = set()
    for source in retained:
        pending = list(adjacency[source])
        reachable: set[str] = set()
        while pending:
            target = pending.pop()
            if target in reachable:
                continue
            reachable.add(target)
            pending.extend(adjacency[target])
        projected.update((source, target) for target in reachable & retained)
    return projected
