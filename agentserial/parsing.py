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
    data: Any
    try:
        if path.suffix.lower() == ".json":
            data = json.loads(text)
        elif path.suffix.lower() in {".yaml", ".yml"}:
            data = yaml.safe_load(text)
        else:
            raise ValueError(f"unsupported file extension: {path.suffix or '<none>'}")
    except yaml.YAMLError as error:
        raise ValueError(f"invalid YAML: {error}") from error
    if not isinstance(data, dict):
        raise ValueError("document root must be an object")
    return model.model_validate(data)
