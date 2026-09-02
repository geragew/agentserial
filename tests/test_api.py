from __future__ import annotations

from fastapi.testclient import TestClient

from agentserial.api import app
from agentserial.models import Contract, History


client = TestClient(app)

HISTORY = History.model_validate(
    {
        "schema_version": "0.1",
        "history_id": "api-schedule-dependent",
        "initial_state": {"balance": {"value": 0, "version": 0}},
        "operations": [
            {
                "id": "credit",
                "agent": "agent-a",
                "effects": [{"type": "increment", "resource": "balance", "value": 1}],
            },
            {
                "id": "debit",
                "agent": "agent-b",
                "effects": [{"type": "increment", "resource": "balance", "value": -1}],
            },
        ],
    }
)
CONTRACT = Contract.model_validate(
    {
        "version": "0.1",
        "invariants": [{"id": "non-negative", "type": "min_value", "resource": "balance", "min": 0}],
    }
)
PAYLOAD = {"history": HISTORY.model_dump(), "contract": CONTRACT.model_dump()}


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.2.1"}


def test_validate_documents() -> None:
    response = client.post("/v1/validate", json=PAYLOAD)
    assert response.status_code == 200
    assert response.json() == {"valid": True, "errors": []}


def test_check_history() -> None:
    response = client.post("/v1/check", json=PAYLOAD)
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "SCHEDULE_DEPENDENT"
    assert result["safe_replays"] == 1
    assert result["unsafe_replays"] == 1


def test_rejects_invalid_request() -> None:
    response = client.post("/v1/check", json={"history": {}, "contract": {}})
    assert response.status_code == 422
