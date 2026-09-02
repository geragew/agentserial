from __future__ import annotations

import subprocess
import sys
import tempfile
import venv
from pathlib import Path


ROOT = Path(__file__).parents[1]


def run(*command: str, cwd: Path = ROOT, expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != expected:
        raise RuntimeError(
            f"command returned {result.returncode}, expected {expected}: {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def main() -> int:
    temporary_path: Path
    with tempfile.TemporaryDirectory(prefix="agentserial-release-test-") as directory:
        temporary_path = Path(directory)
        distribution = temporary_path / "dist"
        run(sys.executable, "-m", "build", "--outdir", str(distribution))
        wheels = sorted(distribution.glob("*.whl"))
        sdists = sorted(distribution.glob("*.tar.gz"))
        if len(wheels) != 1 or len(sdists) != 1:
            raise RuntimeError("build must produce exactly one wheel and one sdist")

        environment = temporary_path / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        scripts = environment / ("Scripts" if sys.platform == "win32" else "bin")
        python = scripts / ("python.exe" if sys.platform == "win32" else "python")
        cli = scripts / ("agentserial.exe" if sys.platform == "win32" else "agentserial")
        run(str(python), "-m", "pip", "install", f"{wheels[0]}[api]", "--disable-pip-version-check")
        help_result = run(str(cli), "--help")
        if "check" not in help_result.stdout:
            raise RuntimeError("installed CLI does not expose the check command")
        api_import = run(str(python), "-c", "from agentserial.api import app; print(app.title)")
        if "AgentSerial API" not in api_import.stdout:
            raise RuntimeError("installed API extra did not expose the application")
        built_in_demo = run(str(cli), "demo")
        if "SCHEDULE_DEPENDENT" not in built_in_demo.stdout:
            raise RuntimeError("installed built-in demo returned the wrong classification")
        imported_history = temporary_path / "imported-history.json"
        run(
            str(cli),
            "import-jsonl",
            str(ROOT / "examples" / "08_jsonl_trace" / "events.jsonl"),
            "--output",
            str(imported_history),
        )
        run(
            str(cli),
            "validate",
            str(imported_history),
            "--contract",
            str(ROOT / "examples" / "08_jsonl_trace" / "contract.yaml"),
        )
        otel_history = temporary_path / "otel-history.json"
        run(
            str(cli),
            "import-otel",
            str(ROOT / "examples" / "09_opentelemetry" / "traces.json"),
            "--output",
            str(otel_history),
        )
        otel_demo = run(
            str(cli),
            "check",
            str(otel_history),
            "--contract",
            str(ROOT / "examples" / "09_opentelemetry" / "contract.yaml"),
            "--json",
            expected=1,
        )
        if "SCHEDULE_DEPENDENT" not in otel_demo.stdout:
            raise RuntimeError("installed OpenTelemetry flow returned the wrong classification")
        report = temporary_path / "agentserial-report.html"
        run(
            str(cli),
            "report",
            str(ROOT / "examples" / "01_overspend" / "history.json"),
            "--contract",
            str(ROOT / "examples" / "01_overspend" / "contract.yaml"),
            "--output",
            str(report),
        )
        if "CONTRACT_FAIL" not in report.read_text(encoding="utf-8"):
            raise RuntimeError("installed report command produced incomplete HTML")
        demo = run(
            str(cli),
            "check",
            str(ROOT / "examples" / "06_schedule_dependent" / "history.json"),
            "--contract",
            str(ROOT / "examples" / "06_schedule_dependent" / "contract.yaml"),
            "--json",
            expected=1,
        )
        if "SCHEDULE_DEPENDENT" not in demo.stdout:
            raise RuntimeError("installed CLI returned the wrong demo classification")
        print(f"wheel: {wheels[0].name}")
        print(f"sdist: {sdists[0].name}")
        print("installed CLI: PASS")
        print("installed API extra: PASS")
        print("JSONL import and validation: PASS")
        print("OpenTelemetry import and check: PASS")
        print("Standalone HTML report: PASS")
        print("schedule-dependent demo: PASS")
    print(f"temporary directory removed: {not temporary_path.exists()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
