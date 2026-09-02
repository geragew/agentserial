from __future__ import annotations

from fastapi import FastAPI
from pydantic import Field

from agentserial.checker import check
from agentserial.invariants import validate_contract_effects, validate_contract_resources
from agentserial.models import CheckResult, Contract, History, StrictModel


class CheckRequest(StrictModel):
    history: History
    contract: Contract
    max_operations: int = Field(default=10, ge=1, le=100)
    max_prefixes: int = Field(default=100_000, ge=1, le=10_000_000)


class ValidationResponse(StrictModel):
    valid: bool
    errors: list[str]


app = FastAPI(
    title="AgentSerial API",
    summary="Correctness checks for parallel AI-agent effect histories.",
    description=(
        "Validate recorded agent histories against global contracts and classify "
        "their feasible execution orders. The API is deterministic and does not "
        "call an LLM or external service."
    ),
    version="0.2.1",
    license_info={"name": "MIT", "identifier": "MIT"},
)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.2.1"}


@app.post("/v1/validate", response_model=ValidationResponse, tags=["analysis"])
def validate_documents(request: CheckRequest) -> ValidationResponse:
    errors = validate_contract_resources(request.contract, request.history.initial_state)
    errors.extend(validate_contract_effects(request.contract, request.history))
    return ValidationResponse(valid=not errors, errors=errors)


@app.post("/v1/check", response_model=CheckResult, tags=["analysis"])
def check_history(request: CheckRequest) -> CheckResult:
    return check(
        request.history,
        request.contract,
        max_operations=request.max_operations,
        max_prefixes=request.max_prefixes,
    )
