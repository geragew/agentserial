from copy import deepcopy

from pydantic import ValidationError
import pytest

from agentserial.checker import check
from agentserial.models import Contract, History, VerdictStatus


def history_data() -> dict:
    return {
        "schema_version": "0.1",
        "history_id": "test",
        "initial_state": {"x": {"value": 0, "version": 0}},
        "operations": [
            {"id": "a", "agent": "a", "effects": [{"type": "increment", "resource": "x", "value": 1}]},
            {"id": "b", "agent": "b", "effects": [{"type": "increment", "resource": "x", "value": -1}]},
        ],
        "order": [],
    }


def contract() -> Contract:
    return Contract.model_validate({
        "version": "0.1",
        "invariants": [{"id": "floor", "type": "min_value", "resource": "x", "min": 0}],
    })


def test_order_constraint_can_make_schedule_robust() -> None:
    data = history_data()
    data["order"] = [{"before": "a", "after": "b"}]
    result = check(History.model_validate(data), contract())
    assert result.status == VerdictStatus.ROBUST_PASS
    assert result.feasible_replays == 1


def test_prefix_limit_is_inconclusive() -> None:
    result = check(History.model_validate(history_data()), contract(), max_prefixes=1)
    assert result.status == VerdictStatus.INCONCLUSIVE


def test_stale_version_is_inconsistent() -> None:
    data = history_data()
    data["operations"][1]["reads"] = [{"resource": "x", "value": 0, "version": 0}]
    data["order"] = [{"before": "a", "after": "b"}]
    result = check(History.model_validate(data), contract())
    assert result.status == VerdictStatus.INCONSISTENT_HISTORY


def test_failed_operation_preserves_transitive_order() -> None:
    data = history_data()
    data["operations"].insert(1, {"id": "failed", "agent": "c", "status": "failure"})
    data["order"] = [
        {"before": "a", "after": "failed"},
        {"before": "failed", "after": "b"},
    ]
    result = check(History.model_validate(data), contract())
    assert result.status == VerdictStatus.ROBUST_PASS
    assert result.safe_witness.order == ["a", "b"]


def test_cycle_is_invalid_history_schema() -> None:
    data = history_data()
    data["order"] = [{"before": "a", "after": "b"}, {"before": "b", "after": "a"}]
    with pytest.raises(ValidationError, match="acyclic"):
        History.model_validate(data)


def test_unknown_fields_are_rejected() -> None:
    data = history_data()
    data["surprise"] = True
    with pytest.raises(ValidationError, match="surprise"):
        History.model_validate(data)


def test_deterministic_result() -> None:
    history = History.model_validate(history_data())
    first = check(history, contract()).model_dump_json()
    second = check(history, contract()).model_dump_json()
    assert first == second


def test_contract_rejects_later_incompatible_value() -> None:
    data = history_data()
    data["operations"] = [
        {"id": "a", "agent": "a", "effects": [{"type": "set", "resource": "x", "value": "unknown"}]}
    ]
    result = check(History.model_validate(data), contract())
    assert result.status == VerdictStatus.INVALID_CONTRACT
    assert "cannot evaluate" in result.errors[0]
