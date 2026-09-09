import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from vorhersage.common import Error, digest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("forecast_model_example", ROOT / "examples/backtesting/model_runs.py")
example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(example)


class ModelPromptTests(unittest.TestCase):
    def test_posthoc_extraction_is_explicit_and_rejects_ambiguous_or_broken_json(self):
        answer = {"probability": 0.4, "rationale": "Uncertain.", "recognizes_outcome": False}
        text = 'Explanation.\n```json\n' + json.dumps(answer) + '\n```\nEnd.'
        with self.assertRaises(ValueError):
            example.parse_answer(text, "plain")
        self.assertEqual(example.parse_answer(text, "plain", True), answer)
        with self.assertRaisesRegex(Error, "exactly one"):
            example.parse_answer(text + text, "plain", True)
        with self.assertRaises(ValueError):
            example.parse_answer('```json\n{"probability":0.4 "rationale":"Missing comma"}\n```', "plain", True)

    def test_prompt_uses_only_whitelisted_question_fields(self):
        case = {"id": "x", "information_as_of": "2020-01-01T00:00:00Z", "criteria_available": True,
                "question": {"text": "Question", "yes": "Yes criteria", "no": "No criteria",
                             "resolution_source": "SECRET_URL"}, "outcome": "SECRET_LABEL"}
        for arm in ("plain", "structured"):
            prompt = example.build_prompt(case, arm)
            self.assertNotIn("SECRET_", prompt)
            self.assertIn("2020-01-01", prompt)

    def test_bad_probability_or_extra_fields_are_not_silently_repaired(self):
        valid = {"probability": 0.4, "rationale": "Uncertain.", "recognizes_outcome": False}
        self.assertEqual(example.parse_answer("```json\n" + json.dumps(valid) + "\n```", "plain"), valid)
        for changed in ({**valid, "probability": 40}, {**valid, "probability": float("nan")},
                        {**valid, "extra": "field"}, {**valid, "recognizes_outcome": "false"}):
            with self.assertRaises(Error):
                example.parse_answer(changed, "plain")


@unittest.skipUnless(importlib.util.find_spec("edsl"), "EDSL is an optional model-run integration")
class ModelImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        # Reuse one public input, without loading any labels or historical forecasts.
        self.bundle = json.loads((ROOT / "examples/backtesting/halawi_validation_20/agent/cases.json").read_text())
        self.bundle["cases"] = self.bundle["cases"][:1]
        self.path = self.root / "cases.json"
        example.write(self.path, self.bundle)
        self.prepared = self.root / "prepared"
        self.registration = example.prepare(self.path, self.prepared)

    def results(self, tamper=False):
        from edsl import Agent, Scenario, Result, Results, Survey, QuestionFreeText
        from edsl.inference_services.services.google_service import GoogleService
        request = json.loads((self.prepared / "requests.json").read_text())[0]
        if tamper:
            request["prompt"] += "Tampered"
        survey = Survey([QuestionFreeText(question_name="forecast", question_text="{{ prompt }}")])
        result = Result(agent=Agent(), scenario=Scenario(request),
                        model=GoogleService.create_model(self.registration["models"][0]["model"])(
                            **self.registration["models"][0]["parameters"]), iteration=0,
                        answer={"forecast": json.dumps({"probability": 0.4, "rationale": "Fixture answer.", "recognizes_outcome": False})},
                        raw_model_response={"forecast_cost": 0.012}, survey=survey)
        output = self.root / "results.json"
        example.write(output, Results(survey=survey, data=[result]).to_dict())
        return output

    def test_registered_import_marks_missing_rows_and_retains_actual_cost(self):
        report = example.ingest(self.prepared, self.results(), self.root / "project")
        self.assertEqual(report["valid_forecasts"], 1)
        self.assertEqual(len(report["failures"]), 3)
        self.assertEqual(report["imported"][0]["reported_cost_usd"], 0.012)
        self.assertTrue(report["doctor"]["ok"])
        self.assertEqual(report["registration_sha256"], digest(self.registration))

    def test_changed_prompt_is_rejected_before_any_forecast_is_imported(self):
        with self.assertRaisesRegex(Error, "prompt differs"):
            example.ingest(self.prepared, self.results(tamper=True), self.root / "project")
        self.assertFalse((self.root / "project").exists())
