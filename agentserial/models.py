from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list[JsonScalar]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class ResourceState(StrictModel):
    value: JsonValue
    version: int = Field(default=0, ge=0)


class Read(StrictModel):
    resource: str = Field(min_length=1)
    value: JsonValue
    version: int = Field(ge=0)


class Effect(StrictModel):
    type: Literal["set", "increment", "append"]
    resource: str = Field(min_length=1)
    value: JsonValue


class Operation(StrictModel):
    id: str = Field(min_length=1)
    agent: str = Field(min_length=1)
    status: Literal["success", "failure"] = "success"
    reads: list[Read] = Field(default_factory=list)
    effects: list[Effect] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_operation(self) -> Operation:
        read_resources = [read.resource for read in self.reads]
        if len(read_resources) != len(set(read_resources)):
            raise ValueError("an operation cannot read the same resource twice")
        if self.status == "failure" and self.effects:
            raise ValueError("a failed operation cannot contain effects")
        return self


class OrderingConstraint(StrictModel):
    before: str = Field(min_length=1)
    after: str = Field(min_length=1)

    @model_validator(mode="after")
    def reject_self_edge(self) -> OrderingConstraint:
        if self.before == self.after:
            raise ValueError("an ordering constraint cannot be a self-edge")
        return self


class History(StrictModel):
    schema_version: Literal["0.1"]
    history_id: str = Field(min_length=1)
    initial_state: dict[str, ResourceState]
    operations: list[Operation]
    order: list[OrderingConstraint] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_structure(self) -> History:
        ids = [operation.id for operation in self.operations]
        if len(ids) != len(set(ids)):
            raise ValueError("operation IDs must be unique")
        known = set(ids)
        edges = [(edge.before, edge.after) for edge in self.order]
        if len(edges) != len(set(edges)):
            raise ValueError("ordering constraints must be unique")
        for before, after in edges:
            if before not in known or after not in known:
                raise ValueError(f"ordering constraint references unknown operation: {before} -> {after}")
        _assert_acyclic(known, edges)
        for operation in self.operations:
            for read in operation.reads:
                if read.resource not in self.initial_state:
                    raise ValueError(f"read references unknown resource: {read.resource}")
            for effect in operation.effects:
                if effect.resource not in self.initial_state:
                    raise ValueError(f"effect references unknown resource: {effect.resource}")
                _validate_effect_value(effect, self.initial_state[effect.resource].value)
        return self


class MaxSumInvariant(StrictModel):
    id: str = Field(min_length=1)
    type: Literal["max_sum"]
    resource: str = Field(min_length=1)
    max: float


class MinValueInvariant(StrictModel):
    id: str = Field(min_length=1)
    type: Literal["min_value"]
    resource: str = Field(min_length=1)
    min: float


class UniqueInvariant(StrictModel):
    id: str = Field(min_length=1)
    type: Literal["unique"]
    resource: str = Field(min_length=1)


class EqualsInvariant(StrictModel):
    id: str = Field(min_length=1)
    type: Literal["equals"]
    left: str = Field(min_length=1)
    right: str = Field(min_length=1)


Invariant = Annotated[
    MaxSumInvariant | MinValueInvariant | UniqueInvariant | EqualsInvariant,
    Field(discriminator="type"),
]


class Contract(StrictModel):
    version: Literal["0.1"]
    invariants: list[Invariant] = Field(min_length=1)

    @field_validator("invariants")
    @classmethod
    def unique_ids(cls, invariants: list[Invariant]) -> list[Invariant]:
        ids = [invariant.id for invariant in invariants]
        if len(ids) != len(set(ids)):
            raise ValueError("invariant IDs must be unique")
        return invariants


class VerdictStatus(StrEnum):
    ROBUST_PASS = "ROBUST_PASS"
    SCHEDULE_DEPENDENT = "SCHEDULE_DEPENDENT"
    CONTRACT_FAIL = "CONTRACT_FAIL"
    INCONSISTENT_HISTORY = "INCONSISTENT_HISTORY"
    INCONCLUSIVE = "INCONCLUSIVE"
    INVALID_HISTORY = "INVALID_HISTORY"
    INVALID_CONTRACT = "INVALID_CONTRACT"


class Witness(StrictModel):
    order: list[str]
    violations: list[str] = Field(default_factory=list)


class CheckResult(StrictModel):
    status: VerdictStatus
    history_id: str | None = None
    operations: int = 0
    agents: int = 0
    feasible_replays: int = 0
    safe_replays: int = 0
    unsafe_replays: int = 0
    explored_prefixes: int = 0
    safe_witness: Witness | None = None
    unsafe_witness: Witness | None = None
    reduced_counterexample: list[str] | None = None
    counterexample_operations: list[Operation] = Field(default_factory=list)
    read_conflicts: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


def _validate_effect_value(effect: Effect, current: JsonValue) -> None:
    if effect.type == "increment":
        if isinstance(current, bool) or not isinstance(current, (int, float)):
            raise ValueError(f"increment requires numeric resource: {effect.resource}")
        if isinstance(effect.value, bool) or not isinstance(effect.value, (int, float)):
            raise ValueError(f"increment requires numeric value: {effect.resource}")
    if effect.type == "append":
        if not isinstance(current, list):
            raise ValueError(f"append requires list resource: {effect.resource}")
        if isinstance(effect.value, list):
            raise ValueError(f"append requires scalar value: {effect.resource}")


def _assert_acyclic(nodes: set[str], edges: list[tuple[str, str]]) -> None:
    adjacency = {node: [] for node in nodes}
    indegree = {node: 0 for node in nodes}
    for before, after in edges:
        adjacency[before].append(after)
        indegree[after] += 1
    ready = [node for node, degree in indegree.items() if degree == 0]
    visited = 0
    while ready:
        node = ready.pop()
        visited += 1
        for successor in adjacency[node]:
            indegree[successor] -= 1
            if indegree[successor] == 0:
                ready.append(successor)
    if visited != len(nodes):
        raise ValueError("ordering constraints must be acyclic")
