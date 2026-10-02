"""Run with an installed wheel: python -I tests/installed_journey.py."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import corridor_lab


def main():
    assert Path(corridor_lab.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)

        def run(*args, expected=0):
            result = subprocess.run([sys.executable, "-I", "-m", "corridor_lab", *map(str, args)],
                                    cwd=root, capture_output=True, text=True, timeout=30)
            assert result.returncode == expected, result.stdout + result.stderr
            return result.stdout

        project = root / "project"
        project.mkdir()
        scenario = project / "scenario.json"
        run("init", "--output", scenario)
        run("project", "create", "--directory", project, "--project-id", "fictional-installed",
            "--scenario", scenario, "--experiment", "deadlines:transaction-sweep:parameter=deadline_hours;values=1,24")
        run("project", "add-variant", project, "--variant", "fast", "--changes", "transaction.deadline_hours=1")
        run("project", "add-variant", project, "--variant", "busy", "--base", "fast",
            "--changes", "transaction.volume_per_period=100")
        before = run("project", "run-variants", project, "--experiment", "deadlines", "--format", "json")
        moved = root / "moved"
        project.rename(moved)
        run("project", "validate", moved)
        run("project", "open", moved)
        assert run("project", "run-variants", moved, "--experiment", "deadlines", "--format", "json") == before
        scenario = moved / "scenario.json"
        original = scenario.read_bytes()
        evidence = root / "evidence.json"
        run("evaluate", scenario, "--evidence", evidence)
        assert json.loads(evidence.read_text(encoding="utf-8"))["tool"]["version"] == corridor_lab.__version__
        saved_evidence = evidence.read_bytes()
        run("evaluate", scenario, "--output", evidence, "--evidence", evidence, expected=2)
        assert evidence.read_bytes() == saved_evidence
        run("evaluate", scenario, "--output", scenario, expected=2)
        assert scenario.read_bytes() == original
        scenario.write_bytes(original + b"\n")
        run("project", "validate", moved, expected=2)
    print("INSTALLED_CORRIDOR_JOURNEY_OK")


if __name__ == "__main__":
    main()
