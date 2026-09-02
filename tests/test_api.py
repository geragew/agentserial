from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agentserial.api import ApiSettings, app, create_app
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
    assert response.json() == {"status": "ok", "version": "0.7.0"}


def test_local_application_serves_workspace() -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/app/"
    workspace = client.get("/app/")
    assert workspace.status_code == 200
    assert "Analyze files" in workspace.text
    assert client.get("/app/app.js").status_code == 200


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


def test_optional_api_key_protects_analysis() -> None:
    protected = TestClient(create_app(ApiSettings(api_key="secret")))
    assert protected.get("/health").status_code == 200
    assert protected.post("/v1/check", json=PAYLOAD).status_code == 401
    response = protected.post("/v1/check", json=PAYLOAD, headers={"X-AgentSerial-Key": "secret"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]


def test_request_body_limit() -> None:
    limited = TestClient(create_app(ApiSettings(max_body_bytes=100)))
    response = limited.post("/v1/check", json=PAYLOAD)
    assert response.status_code == 413
    assert response.json() == {"detail": "request body too large"}


def test_upload_json_history_and_yaml_contract() -> None:
    files = {
        "history": ("history.json", HISTORY.model_dump_json(), "application/json"),
        "contract": (
            "contract.yaml",
            'version: "0.1"\ninvariants:\n'
            "  - id: non-negative\n"
            "    type: min_value\n"
            "    resource: balance\n"
            "    min: 0\n",
            "application/yaml",
        ),
    }
    response = client.post("/v1/check-files", files=files)
    assert response.status_code == 200
    assert response.json()["status"] == "SCHEDULE_DEPENDENT"


def test_rate_limit_protects_analysis_routes() -> None:
    limited = TestClient(create_app(ApiSettings(rate_limit_per_minute=1)))
    assert limited.post("/v1/check", json=PAYLOAD).status_code == 200
    response = limited.post("/v1/check", json=PAYLOAD)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert limited.get("/health").status_code == 200


@pytest.mark.parametrize(
    "settings",
    [
        {"max_body_bytes": 0},
        {"timeout_seconds": 0},
        {"rate_limit_per_minute": -1},
    ],
)
def test_api_settings_reject_invalid_limits(settings: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        ApiSettings(**settings)
