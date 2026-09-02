from __future__ import annotations

import argparse
import json
from pathlib import Path

from agentserial.models import Contract, History

ROOT = Path(__file__).parents[1]


def rendered_schemas() -> dict[Path, str]:
    return {
        ROOT / "schemas" / "history.schema.json": _render(History.model_json_schema()),
        ROOT / "schemas" / "contract.schema.json": _render(Contract.model_json_schema()),
    }


def _render(schema: dict) -> str:
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export AgentSerial JSON Schemas")
    parser.add_argument("--check", action="store_true", help="Fail if committed schemas are stale")
    args = parser.parse_args()
    stale: list[Path] = []
    for path, expected in rendered_schemas().items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != expected:
                stale.append(path)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8")
    if stale:
        for path in stale:
            print(f"stale schema: {path.relative_to(ROOT)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
