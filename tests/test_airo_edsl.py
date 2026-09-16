"""Validate the live tool bridge without making model or network calls."""

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from vorhersage.common import Error

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/airo"
spec = importlib.util.spec_from_file_location("airo_edsl_driver", EXAMPLE / "edsl_pilot.py")
pilot = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(EXAMPLE))
try:
    spec.loader.exec_module(pilot)
finally:
    sys.path.pop(0)


class AIROEDSLTests(unittest.TestCase):
    def setUp(self):
        self.reg = {"question_ids": ["q"], "condition_ids": ["unconditional", "p1"], "max_research_calls": 40}
        self.state = {"cells": {}, "quantiles": None, "final": None}
        self.quantiles = {f"p{p}": v for p, v in zip((10, 25, 50, 75, 90), (1, 2, 3, 4, 5))}
        self.receipts = [{"ok": True, "action": {"tool": "read_page", "url": "https://example.org/report"}} for _ in range(10)]
        self.submit = {"tool": "submit_cells", "eci_forecast": self.quantiles,
                       "rows": [{"question_id": "q", "probabilities": {"unconditional": [0.2]*6, "p1": [0.1]*6}}]}
        self.final = {"tool": "submit_forecast", "eci_forecast": self.quantiles, "rationale": "Brief rationale.",
                      "key_sources": ["https://example.org/report"]}

    def test_gate_counts_successful_receipts_not_failed_requests(self):
        with self.assertRaisesRegex(Error, "ten successful"):
            pilot.validate_actions({"actions": [self.submit]}, self.reg, self.state,
                                   self.receipts[:9] + [{"ok": False}])

    def test_whole_batch_is_atomic_and_preserves_original_state(self):
        before = copy.deepcopy(self.state)
        bad = copy.deepcopy(self.final)
        bad["key_sources"] = ["https://never-read.example.org"]
        with self.assertRaisesRegex(Error, "page-read"):
            pilot.validate_actions({"actions": [self.submit, bad]}, self.reg, self.state, self.receipts)
        self.assertEqual(self.state, before)

    def test_full_grid_can_finalize_and_quantiles_cannot_drift(self):
        result, research = pilot.validate_actions({"actions": [self.submit, self.final]}, self.reg, self.state, self.receipts)
        self.assertFalse(research)
        self.assertEqual(result["cells"]["q"]["p1"], [0.1]*6)
        result["final"] = None
        other = copy.deepcopy(self.submit)
        other["eci_forecast"]["p90"] = 6
        with self.assertRaisesRegex(Error, "already fixed"):
            pilot.validate_actions({"actions": [other]}, self.reg, result, self.receipts)

    def test_missing_cells_bad_probabilities_and_inverted_quantiles_rejected(self):
        with self.assertRaisesRegex(Error, "incomplete"):
            pilot.validate_actions({"actions": [self.final]}, self.reg, self.state, self.receipts)
        bad = copy.deepcopy(self.submit)
        bad["rows"][0]["probabilities"]["p1"][0] = True
        with self.assertRaises(Error):
            pilot.validate_actions({"actions": [bad]}, self.reg, self.state, self.receipts)
        bad = copy.deepcopy(self.submit)
        bad["eci_forecast"]["p10"] = 100
        with self.assertRaisesRegex(Error, "ordered"):
            pilot.validate_actions({"actions": [bad]}, self.reg, self.state, self.receipts)

    def test_tools_must_be_known_separate_and_within_limit(self):
        for actions in ([{"tool": "shell", "command": "echo unsafe"}],
                        [{"tool": "read_page", "url": "file:///etc/passwd"}],
                        [{"tool": "web_search", "query": "test"}, self.submit]):
            with self.assertRaises(Error):
                pilot.validate_actions({"actions": actions}, self.reg, self.state, self.receipts)
        with self.assertRaisesRegex(Error, "limit"):
            pilot.validate_actions({"actions": [{"tool": "web_search", "query": "test"}]}, self.reg, self.state, self.receipts*4)

    def test_only_one_json_object_no_ambiguous_prose_extraction(self):
        value = {"actions": [{"tool": "web_search", "query": "test"}]}
        self.assertEqual(pilot.parse_action("```json\n" + json.dumps(value) + "\n```"), value)
        self.assertEqual(pilot.parse_action("```json\n" + json.dumps(value)), value)
        with self.assertRaises(ValueError):
            pilot.parse_action(json.dumps(value) + "\n" + json.dumps(value))

    def test_expanded_gate_requires_distinct_pages_and_later_turn_search(self):
        reg = {**self.reg, **pilot.ENHANCED_RESEARCH}
        searches = [{"ok": True, "requested_turn": 1, "action": {
            "tool": "web_search", "query": f"query {i}", "recent_days": 30}} for i in range(10)]
        pages = [{"ok": True, "requested_turn": 2, "action": {
            "tool": "read_page", "url": f"https://example.org/{i}"}} for i in range(6)]
        self.assertFalse(pilot.research_status(reg, searches + pages)["ready"])
        same_turn = {"ok": True, "requested_turn": 2, "action": {"tool": "web_search", "query": "same turn"}}
        self.assertFalse(pilot.research_status(reg, searches + pages + [same_turn])["ready"])
        followup = {**same_turn, "requested_turn": 3}
        self.assertTrue(pilot.research_status(reg, searches + pages + [followup])["ready"])
        repeated = [pages[0]] * 6
        self.assertFalse(pilot.research_status(reg, searches + repeated + [followup])["ready"])
        with self.assertRaisesRegex(Error, "Research gate requirements"):
            pilot.validate_actions({"actions": [self.submit]}, reg, self.state, searches + repeated + [followup])

    def test_expanded_output_limit_applies_across_actions(self):
        reg = {**self.reg, "max_questions_per_turn": 1}
        with self.assertRaisesRegex(Error, "Total question rows"):
            pilot.validate_actions({"actions": [self.submit, self.submit]}, reg, self.state, self.receipts)

    def test_pagination_and_result_limits_validate_types(self):
        for action in [{"tool": "read_page", "url": "https://example.org", "offset": -1},
                       {"tool": "read_page", "url": "https://example.org", "offset": True},
                       {"tool": "web_search", "query": "test", "max_results": 11}]:
            with self.assertRaises(Error):
                pilot.validate_actions({"actions": [action]}, self.reg, self.state, [])
        pilot.validate_actions({"actions": [{"tool": "read_page", "url": "https://example.org", "offset": 7000}]}, self.reg, self.state, [])

    def test_empty_provider_failure_is_explicit_and_costed_before_continuation(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            reg = {}
            for name, key in [("prompt.txt", "prompt_sha256"), ("system-prompt.txt", "system_sha256"), ("bridge.txt", "bridge_sha256")]:
                (out/name).write_text("frozen")
                reg[key] = pilot.airo.sha(b"frozen")
            jobs = {"models": [{"model": "test"}], "agents": [{}], "scenarios": [{}]}
            record = {"model": jobs["models"][0], "agent": {}, "scenario": {}, "answer": {"action": ""},
                      "raw_model_response": {"action_cost": 0.25, "action_raw_model_response": {
                          "candidates": [{"finish_reason": "MALFORMED_FUNCTION_CALL"}]}}}
            state = {**self.state, "submissions": [], "events": [], "turn": 0, "reported_cost_usd": 0,
                     "registration_sha256": pilot.digest(reg), "pending": {"kind": "model", "directory": "turn-01", "jobs_sha256": pilot.digest(jobs)}}
            for path, value in [("registration.json", reg), ("state.json", state), ("turn-01/jobs.json", jobs),
                                ("turn-01/record.json", record), ("turn-01/request.json", {"jobs_sha256": pilot.digest(jobs)})]:
                pilot.write(out/path, value)
            with patch.object(pilot, "next_job", return_value={"mock": True}):
                result = pilot.resume_empty_function_call(out)
            self.assertEqual(result["failed_call_cost_usd"], 0.25)
            saved = pilot.checked(out)[1]
            self.assertEqual(saved["reported_cost_usd"], 0.25)
            self.assertEqual(saved["cells"], {})
            self.assertEqual(len(saved["amendments"]), 1)
            self.assertEqual(pilot.load(out/"registration.json"), reg)
            with self.assertRaises(Error):
                pilot.resume_empty_function_call(out)

    def test_token_limit_amendment_preserves_partial_text_without_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            reg = {"model": {"model": "test", "parameters": {"maxOutputTokens": 32768}}}
            for name, key in [("prompt.txt", "prompt_sha256"), ("system-prompt.txt", "system_sha256"), ("bridge.txt", "bridge_sha256")]:
                (out/name).write_text("frozen")
                reg[key] = pilot.airo.sha(b"frozen")
            jobs = {"models": [reg["model"]], "agents": [{}], "scenarios": [{}]}
            record = {"model": reg["model"], "agent": {}, "scenario": {}, "answer": {"action": '{"actions":['},
                      "raw_model_response": {"action_cost": 0.5, "action_raw_model_response": {
                          "candidates": [{"finish_reason": "MAX_TOKENS"}]}}}
            state = {**self.state, "submissions": [], "events": [], "turn": 0, "reported_cost_usd": 0,
                     "registration_sha256": pilot.digest(reg), "pending": {"kind": "model", "directory": "turn-01", "jobs_sha256": pilot.digest(jobs)}}
            for path, value in [("registration.json", reg), ("state.json", state), ("turn-01/jobs.json", jobs),
                                ("turn-01/record.json", record), ("turn-01/request.json", {"jobs_sha256": pilot.digest(jobs)})]:
                pilot.write(out/path, value)
            with patch.object(pilot, "next_job", return_value={}):
                pilot.resume_token_limit(out)
            saved = pilot.checked(out)[1]
            self.assertEqual(saved["model_override"]["parameters"]["maxOutputTokens"], 65536)
            self.assertEqual(saved["reported_cost_usd"], 0.5)
            self.assertEqual(saved["cells"], {})
            self.assertEqual(pilot.load(out/"turn-01/accepted.json")["transcript"]["content"], record["answer"]["action"])
            self.assertEqual(pilot.load(out/"registration.json"), reg)

    def failed_output_fixture(self, out, answer, stop_reason):
        reg = {"model": {"inference_service": "anthropic", "model": "test", "parameters": {
            "max_tokens": 20000, "output_config": {"effort": "max"}}}}
        for name, key in [("prompt.txt", "prompt_sha256"), ("system-prompt.txt", "system_sha256"), ("bridge.txt", "bridge_sha256")]:
            (out/name).write_text("frozen")
            reg[key] = pilot.airo.sha(b"frozen")
        jobs = {"models": [reg["model"]], "agents": [{}], "scenarios": [{}]}
        record = {"model": reg["model"], "agent": {}, "scenario": {}, "answer": {"action": answer},
                  "raw_model_response": {"action_cost": 0.5, "action_raw_model_response": {"stop_reason": stop_reason}}}
        state = {**self.state, "submissions": [], "events": [], "turn": 0, "reported_cost_usd": 0,
                 "transport_instruction": "", "registration_sha256": pilot.digest(reg),
                 "pending": {"kind": "model", "directory": "turn-01", "jobs_sha256": pilot.digest(jobs)}}
        for path, value in [("registration.json", reg), ("state.json", state), ("turn-01/jobs.json", jobs),
                            ("turn-01/record.json", record), ("turn-01/request.json", {"jobs_sha256": pilot.digest(jobs)})]:
            pilot.write(out/path, value)
        return reg

    def test_refusal_is_costed_terminal_and_cannot_be_retried_as_bad_json(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            self.failed_output_fixture(out, "", "refusal")
            with self.assertRaisesRegex(Error, "refusals are terminal"):
                pilot.resume_invalid_output(out)
            pilot.record_refusal(out)
            state = pilot.checked(out)[1]
            self.assertEqual(state["reported_cost_usd"], 0.5)
            self.assertEqual(state["terminal_failure"]["kind"], "provider_refusal")
            self.assertIsNone(state["pending"])
            self.assertEqual(state["cells"], {})

    def test_invalid_json_is_preserved_and_no_probabilities_are_repaired(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            text = '{"actions":[{"number":0. nineteen}]}'
            reg = self.failed_output_fixture(out, text, "end_turn")
            with patch.object(pilot, "next_job", return_value={}):
                pilot.resume_invalid_output(out)
            state = pilot.checked(out)[1]
            self.assertEqual(state["cells"], {})
            self.assertEqual(state["reported_cost_usd"], 0.5)
            self.assertEqual(pilot.load(out/"turn-01/accepted.json")["transcript"]["content"], text)
            self.assertEqual(pilot.load(out/"registration.json"), reg)

    def test_thinking_limit_amendment_retains_requested_and_changed_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            reg = self.failed_output_fixture(out, "", "max_tokens")
            with patch.object(pilot, "next_job", return_value={}):
                pilot.resume_invalid_output(out, lower_effort=True)
            state = pilot.checked(out)[1]
            self.assertEqual(state["model_override"]["parameters"]["output_config"]["effort"], "high")
            self.assertEqual(reg["model"]["parameters"]["output_config"]["effort"], "max")
            self.assertEqual(pilot.load(out/"registration.json"), reg)


if __name__ == "__main__":
    unittest.main()
