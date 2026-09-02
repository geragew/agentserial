from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "downloads" / "AgentSerial-v0.7.0.zip"
EXCLUDED_PARTS = {
    ".pytest_cache",
    ".ruff_cache",
    ".git",
    ".hypothesis",
    "__pycache__",
    "agentserial.egg-info",
    "build",
    "dist",
    "downloads",
    "node_modules",
    "test-results",
}
EXCLUDED_NAMES = {"Você está atuando como Principal Researc.txt"}


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not EXCLUDED_PARTS.intersection(path.relative_to(ROOT).parts)
        and path.name not in EXCLUDED_NAMES
        and path.suffix not in {".pyc"}
    )
    with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, Path("AgentSerial-v0.7.0") / path.relative_to(ROOT))
    print(f"created: {OUTPUT.relative_to(ROOT)}")
    print(f"files: {len(files)}")
    print(f"bytes: {OUTPUT.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
