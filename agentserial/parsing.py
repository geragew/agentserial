from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel

from agentserial.models import Contract, History

ModelT = TypeVar("ModelT", bound=BaseModel)


def load_history(path: Path) -> History:
    return _load(path, History)


def load_contract(path: Path) -> Contract:
    return _load(path, Contract)


def _load(path: Path, model: type[ModelT]) -> ModelT:
    text = path.read_text(encoding="utf-8")
    return model.model_validate(parse_document(text, path.suffix))


def parse_document(text: str, suffix: str) -> dict[str, Any]:
    """Parse a JSON or YAML object without applying a domain schema."""
    try:
        if suffix.lower() == ".json":
            data = json.loads(text)
        elif suffix.lower() in {".yaml", ".yml"}:
            data = yaml.safe_load(text)
        else:
            raise ValueError(f"unsupported file extension: {suffix or '<none>'}")
    except yaml.YAMLError as error:
        raise ValueError(f"invalid YAML: {error}") from error
    if not isinstance(data, dict):
        raise ValueError("document root must be an object")
    return data
