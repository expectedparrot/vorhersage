import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def test_errors_are_machine_readable_and_next_schema_is_discoverable(self):
        p = subprocess.run([sys.executable, "-m", "vorhersage", "bogus"], text=True, capture_output=True)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(p.stdout, "")
        self.assertEqual(json.loads(p.stderr)["errors"][0]["code"], "invalid_arguments")
        p = subprocess.run([sys.executable, "-m", "vorhersage", "schema", "research"], text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("evidence_refs", json.loads(p.stdout)["data"]["required"])

    def test_fresh_process_walkthrough_completes_revision_resolution_and_scoring(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "portfolio"
            p = subprocess.run([sys.executable, str(ROOT / "examples/factory/walkthrough.py"), str(project)],
                               text=True, capture_output=True, timeout=60)
            self.assertEqual(p.returncode, 0, p.stderr)
            summary = json.loads((project / "summary.json").read_text())
            self.assertTrue(summary["doctor"]["ok"])
            self.assertAlmostEqual(summary["matched_brier"]["agent:fixture"], 0.07625)
            self.assertEqual(summary["matched_brier"]["baseline:half"], 0.25)
            self.assertNotEqual(summary["questions"][0]["first_forecast"], summary["questions"][0]["final_forecast"])


class EpiqCLITests(unittest.TestCase):
    def test_generic_epiq_freeze_and_change_check_support_scalar_and_many(self):
        from vorhersage.evidence import Epiq
        from vorhersage.workflow import Workflow
        from vorhersage.common import now
        source = ROOT.parent / "epiq/epiq/src"
        db = ROOT / "examples/patriots_2027/epiq_integration/patriots.sqlite"
        if not source.exists() or not db.exists():
            self.skipTest("Local Epiq checkout and Patriots database are optional integration fixtures.")
        with tempfile.TemporaryDirectory() as tmp:
            w = Workflow(tmp)
            w.store.init("Epiq roundtrip")
            client = Epiq(db, source)
            packet = client.freeze({"information_as_of": now(), "cells": [
                {"kind": "ResearchFinding", "subject": "f_season", "question": "finding_text"},
                {"kind": "ResearchFinding", "subject": "f_season", "question": "about"}]})
            imported = w.import_packet(packet)
            self.assertEqual(len(imported["records"]), 2)
            self.assertEqual(len(packet["records"][1]["value"]), 2)
            self.assertEqual(client.changes(packet)["changes"], [])
            self.assertTrue(w.doctor()["ok"])


if __name__ == "__main__":
    unittest.main()
