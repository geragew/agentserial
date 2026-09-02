from __future__ import annotations

from typing import Any

import pytest

from agentserial.checker import check
from agentserial.models import Contract, History, VerdictStatus


def history(
    name: str,
    state: dict[str, Any],
    operations: list[dict[str, Any]],
    order: list[tuple[str, str]] | None = None,
) -> History:
    return History.model_validate(
        {
            "schema_version": "0.1",
            "history_id": name,
            "initial_state": {key: {"value": value, "version": 0} for key, value in state.items()},
            "operations": operations,
            "order": [{"before": before, "after": after} for before, after in (order or [])],
        }
    )


def contract(*invariants: dict[str, Any]) -> Contract:
    return Contract.model_validate({"version": "0.1", "invariants": list(invariants)})


def op(
    operation_id: str,
    *effects: tuple[str, str, Any],
    reads: list[tuple[str, Any, int]] | None = None,
    status: str = "success",
) -> dict[str, Any]:
    return {
        "id": operation_id,
        "agent": f"agent-{operation_id}",
        "status": status,
        "reads": [
            {"resource": resource, "value": value, "version": version}
            for resource, value, version in (reads or [])
        ],
        "effects": [
            {"type": effect_type, "resource": resource, "value": value}
            for effect_type, resource, value in effects
        ],
    }


SCENARIOS = [
    (
        "retail campaign overspends shared budget",
        history(
            "retail-overspend",
            {"spends": []},
            [op("ads", ("append", "spends", 700)), op("email", ("append", "spends", 500))],
        ),
        contract({"id": "budget", "type": "max_sum", "resource": "spends", "max": 1000}),
        VerdictStatus.CONTRACT_FAIL,
    ),
    (
        "two buyers rely on the same inventory version",
        history(
            "inventory-race",
            {"inventory": 1},
            [
                op("buyer-a", ("increment", "inventory", -1), reads=[("inventory", 1, 0)]),
                op("buyer-b", ("increment", "inventory", -1), reads=[("inventory", 1, 0)]),
            ],
        ),
        contract({"id": "stock", "type": "min_value", "resource": "inventory", "min": 0}),
        VerdictStatus.INCONSISTENT_HISTORY,
    ),
    (
        "airline seat is booked twice",
        history(
            "airline-double-booking",
            {"seats": []},
            [op("web", ("append", "seats", "12A")), op("desk", ("append", "seats", "12A"))],
        ),
        contract({"id": "seat-once", "type": "unique", "resource": "seats"}),
        VerdictStatus.CONTRACT_FAIL,
    ),
    (
        "parallel departments remain within budget",
        history(
            "safe-department-budget",
            {"spends": []},
            [op("sales", ("append", "spends", 200)), op("support", ("append", "spends", 300))],
        ),
        contract({"id": "budget", "type": "max_sum", "resource": "spends", "max": 1000}),
        VerdictStatus.ROBUST_PASS,
    ),
    (
        "individually valid configuration migrations conflict",
        history(
            "configuration-migration",
            {"code": 0, "deployment": 0},
            [
                op("migration-a", ("increment", "code", 1), ("set", "deployment", 1)),
                op("migration-b", ("set", "code", 1), ("increment", "deployment", 1)),
            ],
        ),
        contract({"id": "matching", "type": "equals", "left": "code", "right": "deployment"}),
        VerdictStatus.CONTRACT_FAIL,
    ),
    (
        "credit and debit are schedule dependent",
        history(
            "credit-debit",
            {"balance": 0},
            [op("credit", ("increment", "balance", 1)), op("debit", ("increment", "balance", -1))],
        ),
        contract({"id": "balance", "type": "min_value", "resource": "balance", "min": 0}),
        VerdictStatus.SCHEDULE_DEPENDENT,
    ),
    (
        "coupon is issued twice",
        history(
            "duplicate-coupon",
            {"issued": []},
            [op("loyalty", ("append", "issued", "SAVE20")), op("recovery", ("append", "issued", "SAVE20"))],
        ),
        contract({"id": "coupon-once", "type": "unique", "resource": "issued"}),
        VerdictStatus.CONTRACT_FAIL,
    ),
    (
        "API quota consumption depends on refill order",
        history(
            "api-quota",
            {"tokens": 0},
            [op("refill", ("increment", "tokens", 5)), op("consumer", ("increment", "tokens", -3))],
        ),
        contract({"id": "quota", "type": "min_value", "resource": "tokens", "min": 0}),
        VerdictStatus.SCHEDULE_DEPENDENT,
    ),
    (
        "different seats can be reserved safely",
        history(
            "distinct-seat-booking",
            {"seats": []},
            [op("mobile", ("append", "seats", "12A")), op("web", ("append", "seats", "12B"))],
        ),
        contract({"id": "seat-once", "type": "unique", "resource": "seats"}),
        VerdictStatus.ROBUST_PASS,
    ),
    (
        "revoked permission makes a recorded read stale",
        history(
            "permission-revocation",
            {"permission": True, "actions": []},
            [
                op("revoke", ("set", "permission", False)),
                op("deploy", ("append", "actions", "production"), reads=[("permission", True, 0)]),
            ],
            [("revoke", "deploy")],
        ),
        contract({"id": "action-once", "type": "unique", "resource": "actions"}),
        VerdictStatus.INCONSISTENT_HISTORY,
    ),
    (
        "two bank transfers preserve non-negative balances",
        history(
            "parallel-transfers",
            {"source": 100, "destination": 100},
            [
                op("transfer-a", ("increment", "source", -30), ("increment", "destination", 30)),
                op("transfer-b", ("increment", "source", -20), ("increment", "destination", 20)),
            ],
        ),
        contract(
            {"id": "source", "type": "min_value", "resource": "source", "min": 0},
            {"id": "destination", "type": "min_value", "resource": "destination", "min": 0},
        ),
        VerdictStatus.ROBUST_PASS,
    ),
    (
        "cash withdrawal depends on incoming deposit",
        history(
            "deposit-withdrawal",
            {"cash": 50},
            [op("deposit", ("increment", "cash", 30)), op("withdraw", ("increment", "cash", -70))],
        ),
        contract({"id": "cash", "type": "min_value", "resource": "cash", "min": 0}),
        VerdictStatus.SCHEDULE_DEPENDENT,
    ),
    (
        "initial state already violates the contract",
        history("invalid-initial-state", {"capacity": -1}, []),
        contract({"id": "capacity", "type": "min_value", "resource": "capacity", "min": 0}),
        VerdictStatus.CONTRACT_FAIL,
    ),
    (
        "failed worker has no committed effect",
        history(
            "failed-worker",
            {"balance": 0},
            [op("failed", status="failure"), op("credit", ("increment", "balance", 2))],
        ),
        contract({"id": "balance", "type": "min_value", "resource": "balance", "min": 0}),
        VerdictStatus.ROBUST_PASS,
    ),
    (
        "deployment read implies a causal update order",
        history(
            "causal-deployment",
            {"config": "v1", "deployments": []},
            [
                op("update", ("set", "config", "v2")),
                op("deploy", ("append", "deployments", "v2"), reads=[("config", "v2", 1)]),
            ],
        ),
        contract({"id": "deployment-once", "type": "unique", "resource": "deployments"}),
        VerdictStatus.ROBUST_PASS,
    ),
]


@pytest.mark.parametrize(("description", "scenario_history", "scenario_contract", "expected"), SCENARIOS)
def test_realistic_scenario(
    description: str,
    scenario_history: History,
    scenario_contract: Contract,
    expected: VerdictStatus,
) -> None:
    first = check(scenario_history, scenario_contract)
    second = check(scenario_history, scenario_contract)
    assert first.status == expected, description
    assert first.model_dump_json() == second.model_dump_json(), description


def test_initial_violation_reduces_to_empty_counterexample() -> None:
    _, scenario_history, scenario_contract, _ = SCENARIOS[12]
    result = check(scenario_history, scenario_contract)
    assert result.reduced_counterexample == []


def test_inconsistent_history_explains_the_stale_read() -> None:
    _, scenario_history, scenario_contract, _ = SCENARIOS[9]
    result = check(scenario_history, scenario_contract)
    assert result.read_conflicts
    assert "deploy read permission=True@v0" in result.read_conflicts[0]
