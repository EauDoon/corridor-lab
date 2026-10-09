import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tracecanary.authoring import (
    empty_template,
    render_review_human,
    review_contract,
    validate_draft,
)
from tracecanary.contract import ContractError
from tracecanary.fixture import bundle
from tracecanary.gui_controller import TraceCanaryController


class AuthoringLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = bundle()

    def test_template_is_valid_and_placeholder_is_flagged_by_validation(self):
        template = empty_template()
        validate_draft(template)
        self.assertTrue(template["canaries"][0]["value"].startswith("TCANARY_"))

    def test_clean_contract_reviews_clean(self):
        report = review_contract(self.files["contract.json"])
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["review"]["findings"], [])
        self.assertNotIn("TCANARY", json.dumps(report))

    def test_conflicts_and_ineffective_paths_are_actionable(self):
        bad = {
            **self.files["contract.json"],
            "required_retained_fields": self.files["contract.json"]["required_retained_fields"]
            + [{"scope": "span", "key": "gen_ai.prompt"}],
            "forbidden_path_prefixes": [
                "/resourceSpans/*/scopeSpans/*/spans/*/attributes/*/key",
                "/resourceSpans/*/scopeSpans/*/spans/attributes/*",
            ],
        }
        report = review_contract(bad)
        self.assertEqual(report["status"], "regression")
        locations = {finding["location"] for finding in report["review"]["findings"]}
        self.assertIn("required_retained_fields[4]", locations)
        self.assertIn("forbidden_path_prefixes[1]", locations)
        for finding in report["review"]["findings"]:
            self.assertTrue(finding["message"])
            self.assertTrue(finding["suggestion"])
            self.assertNotIn("TCANARY", json.dumps(finding))

    def test_skipped_array_index_never_matches_and_is_not_a_pass(self):
        from tracecanary.canonical import pointer_matches

        prefix = "/resourceSpans/*/scopeSpans/*/spans/attributes/*/value/stringValue"
        leaf = ("resourceSpans", "0", "scopeSpans", "0", "spans", "0", "attributes", "0", "value", "stringValue")
        # spans is an array, so the next segment is an index. A literal
        # "attributes" there never reaches the scalar the prefix names.
        self.assertFalse(pointer_matches(prefix, leaf))
        self.assertTrue(pointer_matches(prefix.replace("/spans/attributes", "/spans/*/attributes"), leaf))
        draft = {**self.files["contract.json"], "forbidden_path_prefixes": [prefix]}
        report = review_contract(draft)
        self.assertEqual(report["status"], "regression")
        finding = report["review"]["findings"][0]
        self.assertEqual(finding["severity"], "malformed")
        self.assertEqual(finding["location"], "forbidden_path_prefixes[1]")

    def test_trailing_slash_on_a_value_leaf_is_an_empty_segment(self):
        from tracecanary.canonical import pointer_matches

        prefix = "/resourceSpans/*/scopeSpans/*/spans/*/attributes/*/value/stringValue/"
        leaf = ("resourceSpans", "0", "scopeSpans", "0", "spans", "0", "attributes", "0", "value", "stringValue")
        # The checker matches the prefix without the slash and misses it with one,
        # so a clean review would leave a rule that never fires.
        self.assertTrue(pointer_matches(prefix.rstrip("/"), leaf))
        self.assertFalse(pointer_matches(prefix, leaf))
        draft = {**self.files["contract.json"], "forbidden_path_prefixes": [prefix]}
        report = review_contract(draft)
        self.assertEqual(report["status"], "regression")
        finding = report["review"]["findings"][0]
        self.assertEqual(finding["severity"], "malformed")
        self.assertIn("empty", finding["message"])

    def test_malformed_paths_fail_with_suggestions(self):
        for prefix in ("//double//slash", "/resourceSpans/*/span*/key"):
            with self.subTest(prefix=prefix):
                draft = {**self.files["contract.json"], "forbidden_path_prefixes": [prefix]}
                report = review_contract(draft)
                self.assertEqual(report["status"], "regression")
                self.assertEqual(report["review"]["findings"][0]["severity"], "malformed")
        with self.assertRaisesRegex(ContractError, "JSON pointers"):
            review_contract({**self.files["contract.json"], "forbidden_path_prefixes": ["no-leading-slash"]})

    def test_shadowed_key_location_uses_the_same_one_based_ordinal(self):
        draft = {
            **self.files["contract.json"],
            "forbidden_attribute_keys": ["service.version", "enduser.id"],
            "forbidden_attribute_key_prefixes": ["enduser."],
        }
        report = review_contract(draft)
        locations = [finding["location"] for finding in report["review"]["findings"]]
        self.assertIn("forbidden_attribute_keys[2]", locations)
        self.assertNotIn("forbidden_attribute_keys[1]", locations)

    def test_shadowed_forbidden_key_is_reported_conservatively(self):
        draft = {
            **self.files["contract.json"],
            "forbidden_attribute_keys": ["enduser.id"],
            "forbidden_attribute_key_prefixes": ["enduser."],
        }
        report = review_contract(draft)
        self.assertEqual(report["status"], "regression")
        self.assertEqual(report["review"]["findings"][0]["severity"], "ineffective")

    def test_validator_rejects_what_it_catches_first(self):
        duplicate = {**self.files["contract.json"], "canaries": self.files["contract.json"]["canaries"] + [dict(self.files["contract.json"]["canaries"][0])]}
        with self.assertRaisesRegex(ContractError, "unique"):
            review_contract(duplicate)

    def test_human_render_explains_and_stays_value_free(self):
        draft = {**self.files["contract.json"], "forbidden_path_prefixes": ["/resourceSpans/*/scopeSpans/*/spans/attributes/*"]}
        human = render_review_human(review_contract(draft))
        self.assertIn("suggestion:", human)
        self.assertIn("not a privacy guarantee", human)
        self.assertNotIn("TCANARY", human)


class ControllerAuthoringTests(unittest.TestCase):
    def test_template_round_trip_and_transactional_draft(self):
        controller = TraceCanaryController()
        template = controller.contract_template_text()
        self.assertEqual(controller.validate_draft_text(template), json.loads(template))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "contract.json"
            saved = controller.save_contract_draft(template, destination)
            self.assertEqual(saved.status, "pass")
            self.assertIn("canary configuration", saved.human)
            refused = controller.save_contract_draft(template, destination)
            self.assertEqual(refused.status, "unresolved")
            self.assertIn("must not replace", refused.human)
            broken = controller.save_contract_draft("{not json", Path(temporary) / "broken.json")
            self.assertEqual(broken.status, "unresolved")
            self.assertIn("not valid JSON", broken.human)
            invalid = controller.save_contract_draft(json.dumps({"contract_version": "wrong"}), Path(temporary) / "invalid.json")
            self.assertEqual(invalid.status, "unresolved")
            self.assertIn("failed validation", invalid.human)
            self.assertFalse((Path(temporary) / "invalid.json").exists())

    def test_duplicate_key_draft_is_rejected_and_not_saved(self):
        from tracecanary.canonical import InputError

        controller = TraceCanaryController()
        body = json.dumps(bundle()["contract.json"])
        duplicate = '{"contract_version":"tracecanary/v9",' + body[1:]
        with self.assertRaisesRegex(InputError, "duplicate"):
            controller.validate_draft_text(duplicate)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "contract.json"
            saved = controller.save_contract_draft(duplicate, destination)
            self.assertEqual(saved.status, "unresolved")
            self.assertFalse(destination.exists())
            # A collapsed parse would have kept the last contract_version and
            # written a file load_contract then refuses.
            self.assertNotIn("tracecanary/v9", saved.human)

    def test_review_via_controller_matches_cli(self):
        with tempfile.TemporaryDirectory() as temporary, redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            root = Path(temporary)
            bad = {
                **bundle()["contract.json"],
                "forbidden_path_prefixes": ["/resourceSpans/*/scopeSpans/*/spans/attributes/*"],
            }
            draft = root / "draft.json"
            draft.write_text(json.dumps(bad), encoding="utf-8")
            from tracecanary.cli import main

            self.assertEqual(main(["contract", "review", str(draft), "--format", "json", "--output", str(root / "review.json")]), 1)
            controller = TraceCanaryController()
            result = controller.review_contract(draft)
            self.assertEqual(result.status, "regression")
            self.assertEqual(json.loads(result.json), json.loads((root / "review.json").read_text(encoding="utf-8")))
            self.assertEqual(result.exit_code, 1)


class CanaryReportTextConflictTests(unittest.TestCase):
    """A canary that occurs in TraceCanary's own wording is flagged before any run."""

    @staticmethod
    def _draft(value: str) -> dict:
        draft = json.loads(json.dumps(bundle()["contract.json"]))
        draft["canaries"] = [{"label": "synthetic", "category": "test", "value": value}]
        return draft

    def test_canary_in_report_wording_is_a_value_free_conflict(self):
        report = review_contract(self._draft("PASS"))
        self.assertEqual(report["status"], "regression")
        conflicts = [finding for finding in report["review"]["findings"] if finding["location"] == "canaries[1]"]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["severity"], "conflict")
        self.assertIn("withheld (exit 2, no output)", conflicts[0]["message"])
        self.assertIn("TCANARY_", conflicts[0]["suggestion"])
        from tracecanary.report import render_json

        self.assertNotIn("PASS", render_json(report))
        self.assertNotIn("PASS", render_review_human(report))

    def test_lowercase_status_words_and_identifiers_are_also_wording(self):
        for value in ("pass", "tracecanary.batch/v1", "not a privacy pass", "finding(s)"):
            with self.subTest(value=value):
                locations = [finding["location"] for finding in review_contract(self._draft(value))["review"]["findings"]]
                self.assertIn("canaries[1]", locations)

    def test_conflict_ordinal_is_one_based_and_names_only_the_colliding_canary(self):
        draft = self._draft("TCANARY_UNIQUE_9b1d2e4f")
        draft["canaries"].append({"label": "second", "category": "test", "value": "REGRESSION"})
        locations = [finding["location"] for finding in review_contract(draft)["review"]["findings"]]
        self.assertEqual(locations, ["canaries[2]"])

    def test_unique_synthetic_canaries_raise_no_conflict(self):
        report = review_contract(self._draft("TCANARY_UNIQUE_3f9a0c12"))
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["review"]["findings"], [])
        self.assertEqual(review_contract(bundle()["contract.json"])["status"], "pass")
        self.assertEqual(review_contract(empty_template())["status"], "pass")

    def test_review_whose_own_text_contains_the_canary_is_withheld(self):
        from tracecanary.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            draft = Path(temporary) / "draft.json"
            draft.write_text(json.dumps(self._draft("TraceCanary")), encoding="utf-8")
            for output_format in ("human", "json"):
                out, err = StringIO(), StringIO()
                with self.subTest(output_format=output_format), redirect_stdout(out), redirect_stderr(err):
                    self.assertEqual(main(["contract", "review", str(draft), "--format", output_format]), 2)
                self.assertEqual(out.getvalue() + err.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
