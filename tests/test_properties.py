from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from agentserial.checker import check
from agentserial.models import Contract, History


@given(st.lists(st.integers(min_value=-10, max_value=10), min_size=1, max_size=6))
@settings(max_examples=100, deadline=None)
def test_check_is_deterministic_for_generated_histories(deltas: list[int]) -> None:
    history = History.model_validate(
        {
            "schema_version": "0.1",
            "history_id": "generated",
            "initial_state": {"balance": {"value": 0, "version": 0}},
            "operations": [
                {
                    "id": f"op-{index}",
                    "agent": f"agent-{index}",
                    "effects": [{"type": "increment", "resource": "balance", "value": delta}],
                }
                for index, delta in enumerate(deltas)
            ],
            "order": [
                {"before": f"op-{index}", "after": f"op-{index + 1}"} for index in range(len(deltas) - 1)
            ],
        }
    )
    contract = Contract.model_validate(
        {
            "version": "0.1",
            "invariants": [{"id": "floor", "type": "min_value", "resource": "balance", "min": -20}],
        }
    )
    first = check(history, contract, shrink=False)
    second = check(history, contract, shrink=False)
    assert first == second
    assert first.feasible_replays == first.safe_replays + first.unsafe_replays
