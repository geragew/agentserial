from pathlib import Path

import pytest

from agentserial.checker import check
from agentserial.models import VerdictStatus
from agentserial.parsing import load_contract, load_history


ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize(
    ("directory", "expected"),
    [
        ("01_overspend", VerdictStatus.CONTRACT_FAIL),
        ("02_inventory_race", VerdictStatus.INCONSISTENT_HISTORY),
        ("03_double_booking", VerdictStatus.CONTRACT_FAIL),
        ("04_safe_parallel", VerdictStatus.ROBUST_PASS),
        ("05_config_mismatch", VerdictStatus.CONTRACT_FAIL),
        ("06_schedule_dependent", VerdictStatus.SCHEDULE_DEPENDENT),
    ],
)
def test_examples(directory: str, expected: VerdictStatus) -> None:
    path = ROOT / "examples" / directory
    result = check(load_history(path / "history.json"), load_contract(path / "contract.yaml"))
    assert result.status == expected


def test_schedule_dependent_has_both_witnesses() -> None:
    path = ROOT / "examples" / "06_schedule_dependent"
    result = check(load_history(path / "history.json"), load_contract(path / "contract.yaml"))
    assert result.safe_witness is not None
    assert result.unsafe_witness is not None
    assert result.safe_witness.order == ["credit", "debit"]
    assert result.unsafe_witness.order == ["debit", "credit"]


def test_overspend_shrinks_to_both_operations() -> None:
    path = ROOT / "examples" / "01_overspend"
    result = check(load_history(path / "history.json"), load_contract(path / "contract.yaml"))
    assert result.reduced_counterexample == ["spend-a", "spend-b"]


def test_config_mismatch_is_compositional() -> None:
    path = ROOT / "examples" / "05_config_mismatch"
    history = load_history(path / "history.json")
    contract = load_contract(path / "contract.yaml")
    result = check(history, contract)
    assert result.reduced_counterexample == ["migration-a", "migration-b"]
    for operation in history.operations:
        isolated = history.model_copy(update={"operations": [operation], "order": []})
        assert check(isolated, contract).status == VerdictStatus.ROBUST_PASS
