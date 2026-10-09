import json
import tempfile
import tomllib
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import corridor_lab
from corridor_lab.cli import main
from helpers import route, scenario

PACKAGE = Path(__file__).resolve().parents[1]
FIXTURE = PACKAGE / "examples" / "fictional-corridor" / "embedded-scenario.json"


class EvidenceCliTests(unittest.TestCase):
    def test_report_and_evidence_cannot_share_a_destination(self):
        with tempfile.TemporaryDirectory() as temporary, redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            output = Path(temporary) / "report.json"
            args = ["evaluate", str(FIXTURE), "--output", str(output), "--evidence", str(output)]
            self.assertEqual(main(args), 2)
            self.assertFalse(output.exists())
            output.write_text("previous report", encoding="utf-8")
            self.assertEqual(main(args), 2)
            self.assertEqual(output.read_text(encoding="utf-8"), "previous report")

    def test_evidence_accompanies_a_report_and_explains_itself(self):
        with tempfile.TemporaryDirectory() as temporary, redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            root = Path(temporary)
            scenario_path = root / "scenario.json"
            scenario_path.write_text(json.dumps(scenario(routes=[route("fictional-embedded")])), encoding="utf-8")
            report = root / "report.json"
            evidence = root / "evidence.json"
            self.assertEqual(main(["evaluate", str(scenario_path), "--format", "json", "--output", str(report),
                                   "--evidence", str(evidence)]), 0)
            document = json.loads(evidence.read_text(encoding="utf-8"))
            self.assertEqual(document["evidence_version"], "corridor-lab.evidence/v1")
            self.assertEqual(document["report"], json.loads(report.read_text(encoding="utf-8")))
            self.assertEqual(document["inputs"]["scenario"], str(scenario_path))
            self.assertIn("declared fiction", document["limitations"])
            # evidence cannot replace the scenario input
            self.assertEqual(main(["evaluate", str(scenario_path), "--evidence", str(scenario_path)]), 2)
            # report still written normally when evidence is absent
            self.assertEqual(main(["evaluate", str(scenario_path), "--output", str(root / "plain.json")]), 0)
            self.assertTrue((root / "plain.json").exists())

    def test_batch_and_robustness_evidence_export(self):
        with tempfile.TemporaryDirectory() as temporary, redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            root = Path(temporary)
            portfolio = root / "portfolio"
            portfolio.mkdir()
            (portfolio / "one.json").write_text(json.dumps(scenario(routes=[route("fictional-embedded")])), encoding="utf-8")
            evidence = root / "batch-evidence.json"
            self.assertEqual(main(["batch", str(portfolio), "--evidence", str(evidence)]), 0)
            document = json.loads(evidence.read_text(encoding="utf-8"))
            self.assertEqual(document["analysis"], "scenario batch")
            self.assertEqual(main(["batch", str(portfolio), "--evidence", str(portfolio / "inside.json")]), 2)
            self.assertFalse((portfolio / "inside.json").exists())
            first = root / "a.json"
            first.write_text(json.dumps(scenario(routes=[route("fictional-shared")])), encoding="utf-8")
            other = scenario(routes=[route("fictional-shared")])
            other["transaction"]["deadline_hours"] = "0.1"
            other["scenario_id"] = "fictional-strained"
            second = root / "b.json"
            second.write_text(json.dumps(other), encoding="utf-8")
            self.assertEqual(main(["robustness-review", str(first), str(second), "--constraint",
                                   "probability_by_deadline_at_least=0.8", "--evidence", str(root / "rb.json")]), 0)
            robust_document = json.loads((root / "rb.json").read_text(encoding="utf-8"))
            self.assertEqual(robust_document["analysis"], "robustness-review")

    def test_evidence_names_the_inputs_each_command_actually_read(self):
        with tempfile.TemporaryDirectory() as temporary, redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            root = Path(temporary)
            portfolio = root / "portfolio"
            portfolio.mkdir()
            (portfolio / "one.json").write_text(json.dumps(scenario(routes=[route("fictional-embedded")])), encoding="utf-8")
            self.assertEqual(main(["batch", str(portfolio), "--evidence", str(root / "batch.json")]), 0)
            batch_inputs = json.loads((root / "batch.json").read_text(encoding="utf-8"))["inputs"]
            self.assertEqual(batch_inputs["scenario"], f"each JSON scenario in {portfolio}")
            self.assertNotIn("built-in", batch_inputs["scenario"])
            self.assertEqual(batch_inputs["routes"], "routes embedded in each scenario")
            self.assertIsNone(batch_inputs["baseline"])

            first, second = root / "a.json", root / "b.json"
            first.write_text(json.dumps(scenario(routes=[route("fictional-shared")])), encoding="utf-8")
            second.write_text(json.dumps(scenario(routes=[route("fictional-shared")])), encoding="utf-8")
            self.assertEqual(main(["robustness-review", str(first), str(second), "--constraint",
                                   "probability_by_deadline_at_least=0.5", "--evidence", str(root / "rb.json")]), 0)
            robust_inputs = json.loads((root / "rb.json").read_text(encoding="utf-8"))["inputs"]
            self.assertEqual(robust_inputs["scenario"], f"{first}; {second}")

            self.assertEqual(main(["diff", str(second), "--baseline", str(first), "--evidence", str(root / "diff.json")]), 0)
            diff_inputs = json.loads((root / "diff.json").read_text(encoding="utf-8"))["inputs"]
            self.assertEqual(diff_inputs["scenario"], str(second))
            self.assertEqual(diff_inputs["baseline"], str(first))

    def test_evidence_collision_is_refused_before_the_report_is_written(self):
        with tempfile.TemporaryDirectory() as temporary, redirect_stdout(StringIO()), redirect_stderr(StringIO()) as err:
            root = Path(temporary)
            victim = root / "victim.json"
            victim.write_text(json.dumps(scenario(routes=[route("fictional-embedded")])), encoding="utf-8")
            before = victim.read_bytes()
            output = root / "out" / "report.json"
            self.assertEqual(main(["evaluate", str(victim), "--output", str(output), "--evidence", str(victim)]), 2)
            self.assertIn("must not replace an input", err.getvalue())
            self.assertFalse(output.exists())
            self.assertFalse(output.parent.exists())
            self.assertEqual(victim.read_bytes(), before)
            portfolio = root / "portfolio"
            portfolio.mkdir()
            (portfolio / "one.json").write_text(json.dumps(scenario(routes=[route("fictional-embedded")])), encoding="utf-8")
            batch_output = root / "batch.json"
            self.assertEqual(main(["batch", str(portfolio), "--output", str(batch_output),
                                   "--evidence", str(portfolio / "evidence.json")]), 2)
            self.assertFalse(batch_output.exists())

    def test_evidence_reports_the_declared_package_version(self):
        project = tomllib.loads((PACKAGE / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        self.assertEqual(corridor_lab.__version__, project["version"])
        with tempfile.TemporaryDirectory() as temporary, redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            root = Path(temporary)
            evidence = root / "evidence.json"
            self.assertEqual(main(["evaluate", str(FIXTURE), "--evidence", str(evidence)]), 0)
            document = json.loads(evidence.read_text(encoding="utf-8"))
            self.assertEqual(document["tool"], {"name": "corridor-lab", "version": corridor_lab.__version__})


if __name__ == "__main__":
    unittest.main()
