import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tracecanary.cli import main
from tracecanary.output import write_report
from tracecanary.campaign import campaign_summary, run_campaign
from tracecanary.contract import load_contract

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/v1"
class OutputTests(unittest.TestCase):
    def test_output_matches_stdout_and_preserves_inputs(self):
        args = ["check", "--contract", str(FIXTURES / "contract.json"), "--input", str(FIXTURES / "safe-export.json"), "--format", "json"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture):
                self.assertEqual(main(args), 0)
            self.assertEqual(main(args + ["--output", str(path)]), 0)
            self.assertEqual(path.read_bytes(), capture.getvalue().encode())
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args + ["--output", str(FIXTURES / "safe-export.json")]), 2)

    def test_contract_review_output_cannot_replace_the_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            contract = Path(directory) / "contract.json"
            contract.write_bytes((FIXTURES / "contract.json").read_bytes())
            before = contract.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["contract", "review", str(contract), "--output", str(contract)]), 2)
            self.assertEqual(contract.read_bytes(), before)
            self.assertEqual(main(["contract", "review", str(contract), "--output", str(Path(directory) / "review.txt")]), 0)

    def test_campaign_summary_cannot_replace_a_campaign_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = root / "contract.json"
            contract.write_bytes((FIXTURES / "contract.json").read_bytes())
            project = root / "project"
            project.mkdir()
            candidate = root / "candidate.json"
            candidate.write_bytes((FIXTURES / "leaked-prompt.json").read_bytes())
            before = candidate.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["project", "create", "--directory", str(project), "--project-id", "demo", "--contract", str(contract)]), 0)
                self.assertEqual(main(["campaign", "run", str(project), "--candidate", str(candidate), "--save-summary", str(candidate)]), 2)
            self.assertEqual(candidate.read_bytes(), before)

    def test_failed_atomic_replace_preserves_previous_report_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text("old")
            with patch("tracecanary.output.os.replace", side_effect=OSError), self.assertRaises(OSError):
                write_report(path, "new")
            self.assertEqual(path.read_text(), "old")
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_campaign_comparison_cannot_replace_either_summary_or_a_hardlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text = json.dumps(campaign_summary(run_campaign(load_contract(FIXTURES / "contract.json"),
                candidates=[("safe", FIXTURES / "safe-export.json")])))
            baseline, candidate, alias = (root / name for name in ("before.json", "after.json", "alias.json"))
            baseline.write_text(text, encoding="utf-8")
            candidate.write_text(text, encoding="utf-8")
            alias.hardlink_to(baseline)
            args = ["campaign", "compare", str(baseline), str(candidate), "--format", "json"]
            for target in (baseline, candidate, alias):
                with self.subTest(target=target.name), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(args + ["--output", str(target)]), 2)
                self.assertEqual(target.read_text(encoding="utf-8"), text)
            self.assertEqual(main(args + ["--output", str(root / "comparison.json")]), 0)

    def test_campaign_summary_stays_outside_an_external_batch(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            root = Path(directory)
            project, batch = root / "project", root / "batch"
            project.mkdir()
            batch.mkdir()
            candidate = batch / "safe.json"
            candidate.write_bytes((FIXTURES / "safe-export.json").read_bytes())
            original = candidate.read_bytes()
            self.assertEqual(main(["project", "create", "--directory", str(project), "--project-id", "demo",
                                   "--contract", str(FIXTURES / "contract.json")]), 0)
            args = ["campaign", "run", str(project), "--input-dir", str(batch)]
            self.assertEqual(main(args + ["--save-summary", str(batch / "summary.json")]), 2)
            self.assertEqual(list(batch.iterdir()), [candidate])
            self.assertEqual(candidate.read_bytes(), original)
            self.assertEqual(main(args + ["--save-summary", str(root / "summary.json")]), 0)
