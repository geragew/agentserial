from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.release_metadata import build_manifest, package_versions, validate_versions


def package_root(tmp_path: Path, python_version: str, javascript_version: str) -> Path:
    (tmp_path / "sdk/javascript").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "agentserial"\nversion = "{python_version}"\n', encoding="utf-8"
    )
    (tmp_path / "sdk/javascript/package.json").write_text(
        json.dumps({"version": javascript_version}), encoding="utf-8"
    )
    return tmp_path


def test_package_versions_reads_both_ecosystems(tmp_path: Path) -> None:
    root = package_root(tmp_path, "1.2.3", "1.2.3")

    assert package_versions(root) == {"python": "1.2.3", "javascript": "1.2.3"}
    assert validate_versions("v1.2.3", root) == "1.2.3"


@pytest.mark.parametrize("javascript_version,ref", [("1.2.4", "v1.2.3"), ("1.2.3", "v2.0.0")])
def test_validate_versions_rejects_inconsistent_release(
    tmp_path: Path, javascript_version: str, ref: str
) -> None:
    root = package_root(tmp_path, "1.2.3", javascript_version)

    with pytest.raises(ValueError):
        validate_versions(ref, root)


@pytest.mark.parametrize("version", ["01.2.3", "1.2", "1.2.3rc1", "latest"])
def test_validate_versions_rejects_noncanonical_versions(tmp_path: Path, version: str) -> None:
    root = package_root(tmp_path, version, version)

    with pytest.raises(ValueError, match="unsupported release version"):
        validate_versions(None, root)


def test_manifest_is_deterministic_and_records_lineage(tmp_path: Path) -> None:
    root = package_root(tmp_path, "1.2.3", "1.2.3")
    artifacts = tmp_path / "dist"
    artifacts.mkdir()
    (artifacts / "agentserial-1.2.3.whl").write_bytes(b"wheel")
    (artifacts / "agentserial-1.2.3.tgz").write_bytes(b"npm")

    first = build_manifest(artifacts, "abc123", "v1.2.3", root)
    second = build_manifest(artifacts, "abc123", "v1.2.3", root)

    assert first == second
    assert first["source"] == {
        "repository": "https://github.com/geragew/agentserial",
        "commit": "abc123",
        "ref": "v1.2.3",
    }
    assert [artifact["name"] for artifact in first["artifacts"]] == [
        "agentserial-1.2.3.tgz",
        "agentserial-1.2.3.whl",
    ]
