from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
VERSION_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


def package_versions(root: Path = ROOT) -> dict[str, str]:
    with (root / "pyproject.toml").open("rb") as stream:
        python_version = tomllib.load(stream)["project"]["version"]
    javascript = json.loads((root / "sdk/javascript/package.json").read_text(encoding="utf-8"))
    return {"python": python_version, "javascript": javascript["version"]}


def validate_versions(ref: str | None = None, root: Path = ROOT) -> str:
    versions = package_versions(root)
    unique_versions = set(versions.values())
    if len(unique_versions) != 1:
        raise ValueError(f"package versions differ: {versions}")
    version = unique_versions.pop()
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"unsupported release version: {version!r}")
    if ref and ref.startswith("v") and ref != f"v{version}":
        raise ValueError(f"release ref {ref!r} does not match package version {version!r}")
    return version


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_manifest(directory: Path, commit: str, ref: str, root: Path = ROOT) -> dict[str, Any]:
    version = validate_versions(ref, root)
    artifacts = [path for path in sorted(directory.iterdir()) if path.is_file()]
    if not artifacts:
        raise ValueError(f"no release artifacts found in {directory}")
    return {
        "format_version": "1",
        "project": "AgentSerial",
        "version": version,
        "source": {
            "repository": "https://github.com/geragew/agentserial",
            "commit": commit,
            "ref": ref,
        },
        "compatibility": {
            "history_schema": "0.1",
            "contract_schema": "0.1",
            "python": ">=3.11",
            "node": ">=20",
        },
        "artifacts": [
            {"name": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)} for path in artifacts
        ],
    }


def write_manifest(directory: Path, output: Path, commit: str, ref: str) -> None:
    manifest = build_manifest(directory, commit, ref)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and describe AgentSerial release artifacts")
    parser.add_argument("--directory", type=Path, help="directory containing artifacts")
    parser.add_argument("--output", type=Path, help="manifest output path")
    parser.add_argument("--commit", default=os.environ.get("GITHUB_SHA", "local"))
    parser.add_argument("--ref", default=os.environ.get("GITHUB_REF_NAME", ""))
    arguments = parser.parse_args()

    try:
        version = validate_versions(arguments.ref or None)
        if arguments.directory or arguments.output:
            if not arguments.directory or not arguments.output:
                parser.error("--directory and --output must be used together")
            write_manifest(arguments.directory, arguments.output, arguments.commit, arguments.ref)
            print(f"release manifest: {arguments.output}")
        print(f"release version: {version}")
    except (KeyError, OSError, TypeError, ValueError) as error:
        print(f"release metadata error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
