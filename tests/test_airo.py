"""Regression checks against the authors' frozen source records, not mock forecasts."""

import importlib.util
import json
import math
import shutil
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from statistics import median

from vorhersage.common import Error
from vorhersage.store import Store
from vorhersage.workflow import Workflow

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "airo"
spec = importlib.util.spec_from_file_location("airo_reproduce", EXAMPLE / "reproduce.py")
airo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(airo)


class AIROTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = EXAMPLE / "source"
        cls.manifest, cls.rows = airo.load_source(cls.source)
        cls.ladder = json.loads((cls.source / "data/autoarc_ladder.json").read_text())
        cls.questions = cls.ladder["questions"] + json.loads((cls.source / "data/autoarc_crosscutting.json").read_text())["questions"]

    def test_source_is_complete_and_counts_usage_once_per_original_call(self):
        self.assertEqual(len(self.rows), 1960)
        self.assertEqual(sum(len(r["forecasts"]) for r in self.rows), 11760)
        call_ids = {r["call_id"] for r in self.rows}
        self.assertEqual(len(call_ids), 4)
        costs = 0
        turns = 0
        for id in call_ids:
            group = [r for r in self.rows if r["call_id"] == id]
            self.assertEqual(len(group), 490)
            self.assertEqual(len({airo.source_condition(r) for r in group}), 14)
            usage = airo.shared(group, "usage")
            costs += usage["cost_usd"]
            turns += usage["turns"]
            self.assertEqual(airo.sha(airo.shared(group, "prompt").encode()), airo.shared(group, "prompt_sha256"))
        self.assertAlmostEqual(costs, 107.873051)
        self.assertEqual(turns, 87)

    def test_source_reproduces_headline_and_paired_multiplier(self):
        cells = {(r["label"], f["horizon"], airo.source_condition(r)): f["probability"]
                 for r in self.rows if r["question_id"] == "catastrophe:ai" for f in r["forecasts"]}
        for h, expected in (("2030", 0.00475), ("2050", 0.06), ("2100", 0.1225)):
            self.assertAlmostEqual(median(cells[(m, h, "unconditional")] for m in airo.MODELS), expected)
        multiplier = math.exp(median(math.log(cells[(m,"2030","eci_p90")] / cells[(m,"2030","unconditional")]) for m in airo.MODELS))
        self.assertAlmostEqual(multiplier, 2.213594362, places=8)

    def test_paper_coherence_denominator_and_different_window_brackets(self):
        edges = airo.edge_list(self.questions, self.ladder)
        self.assertEqual(Counter(e["kind"] for e in edges), {"HORIZON": 175, "LADDER": 168, "CROSS": 144, "SUBSET": 6, "BRACKET": 6})
        audit = airo.author_audit(self.rows, edges)
        self.assertEqual(audit["comparisons"], 1996)
        self.assertEqual(audit["violations"], [])
        self.assertEqual(len([e for e in edges if e["kind"] != "BRACKET"]), 493)

    def test_question_compilation_preserves_distinct_deadlines(self):
        with tempfile.TemporaryDirectory() as directory:
            w = Workflow(directory)
            w.store.init("AIRO contract test")
            refs, mapping = airo.register_questions(w, self.questions, airo.shared(self.rows, "resolves_on"))
            self.assertEqual(len(refs), 210)
            with w.store.connect() as c:
                incident = Store.question(c, airo.question_id("ladder:ai:100", "2030"))["specification"]
                catastrophe = Store.question(c, airo.question_id("catastrophe:ai", "2030"))["specification"]
            self.assertTrue(incident["event_deadline"].startswith("2030-12-31"))
            self.assertTrue(incident["resolve_after"].startswith("2033-12-31"))
            self.assertEqual(catastrophe["event_deadline"], catastrophe["resolve_after"])
            self.assertIn("December 31, 2025", catastrophe["yes"])
            self.assertIn("beginning on the elicitation date", incident["yes"])

    def test_policy_bindings_fix_own_median_and_shared_placeholders_are_not_data(self):
        instrument = json.loads((self.source / "data/combined_conditions.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            w = Workflow(directory)
            w.store.init("AIRO condition test")
            conditions, fields = airo.register_conditions(w, instrument, "2027-03-10")
            self.assertEqual(len(conditions), 14)
            self.assertEqual(fields["eci_p90"], "p90")
            self.assertTrue(all(fields[x] == "p50" for x in ["sq","p1","p2a","p2b","p3a","p3b","p4","p5"]))
        self.assertEqual(airo.shared([{"evidence": []}, {"evidence": [{"tool": "read_page"}]}], "evidence"), [{"tool": "read_page"}])
        with self.assertRaisesRegex(Error, "Inconsistent"):
            airo.shared([{"usage": {"cost": 1}}, {"usage": {"cost": 2}}], "usage")

    def test_corrupted_source_is_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            shutil.copytree(self.source, source)
            path = source / "data/combined_conditions.json"
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(Error, "Source integrity"):
                airo.load_source(source)


if __name__ == "__main__":
    unittest.main()
