import copy
import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from vorhersage.common import Error
from vorhersage.odds import calculate
from vorhersage.store import Store
from vorhersage.widget import export
from vorhersage.workflow import Workflow
from test_workflow import packet, question, response, run_spec


def ledger(ref):
    return {"anchor": {"probability": 0.2, "basis": "assumed", "rationale": "Illustrative base rate."},
            "entries": [{"finding_id": ref["record_id"], "evidence_refs": [ref], "lr": 2,
                         "lr_range": [0.5, 4], "direction": "supports", "dependence_group": "readiness",
                         "rationale": "Subjective likelihood ratio."}],
            "joint_declarations": [], "independence_rationale": "One group only.",
            "comparison_probability": 0.5}


class OddsTests(unittest.TestCase):
    def setUp(self):
        self.spec = ledger({"packet_id": "packet", "record_id": "ready"})

    def test_odds_and_single_ratio_sensitivity(self):
        result = calculate(self.spec)
        self.assertAlmostEqual(result["probability"], 1 / 3)
        row = result["sensitivity"][0]
        self.assertAlmostEqual(row["probability_range"][0], 1 / 9)
        self.assertEqual(row["probability_range"][1], 0.5)
        self.assertAlmostEqual(row["lr_to_match_comparison"], 4)
        self.assertFalse(row["crosses_comparison"])
        self.spec["entries"][0]["lr_range"][1] = 5
        self.assertTrue(calculate(self.spec)["sensitivity"][0]["crosses_comparison"])

    def test_dependency_requires_joint_replacement(self):
        second = copy.deepcopy(self.spec["entries"][0])
        second.update(finding_id="staff", evidence_refs=[{"packet_id": "packet", "record_id": "staff"}])
        self.spec["entries"].append(second)
        with self.assertRaisesRegex(Error, "explicit joint"):
            calculate(self.spec)
        self.spec["joint_declarations"] = [{"dependence_group": "readiness", "finding_ids": ["ready", "staff"],
                                            "lr": 3, "direction": "supports", "rationale": "Joint judgment."}]
        result = calculate(self.spec)
        self.assertAlmostEqual(result["probability"], 3 / 7)  # Not 4/5 from multiplying all three.
        self.assertEqual(len(result["terms"]), 1)
        self.spec["joint_declarations"][0]["finding_ids"] = ["ready", "missing"]
        with self.assertRaisesRegex(Error, "exactly every"):
            calculate(self.spec)

    def test_invalid_declarations(self):
        for field, value in [("lr", 0), ("lr", -1), ("lr", math.inf), ("lr", True),
                             ("direction", "opposes"), ("lr_range", [1, 2, 3]), ("lr_range", [3, 4]),
                             ("evidence_refs", [{"packet_id": "packet", "record_id": "wrong"}])]:
            with self.subTest(field=field, value=value):
                spec = copy.deepcopy(self.spec)
                spec["entries"][0][field] = value
                with self.assertRaises(Error):
                    calculate(spec)
        for p in [0, 1]:
            self.spec["anchor"]["probability"] = p
            with self.assertRaises(Error):
                calculate(self.spec)

    def test_extreme_ratios_cancel_without_overflow(self):
        entries = []
        for i, lr in enumerate([1e300, 1e300, 1e-300, 1e-300]):
            entries.append({"finding_id": str(i), "evidence_refs": [{"packet_id": "packet", "record_id": str(i)}],
                            "dependence_group": str(i), "lr": lr,
                            "direction": "supports" if lr > 1 else "opposes", "rationale": "Stress case."})
        self.spec["entries"] = entries
        result = calculate(self.spec)
        self.assertAlmostEqual(result["probability"], 0.2)
        json.dumps(result, allow_nan=False)


class LedgerWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.w = Workflow(self.tmp.name)
        self.w.store.init("Odds test")
        self.w.question(question())
        self.refs = [self.w.import_packet(packet())["records"][0]["evidence_ref"]]
        self.run = self.w.start(run_spec())["run_id"]
        self.prior_id = None
        while (step := self.w.next(self.run))["task"]["kind"] != "assessment":
            result = self.w.submit(self.run, response(step, self.refs))
            if step["task"]["kind"] == "prior":
                self.prior_id = result["artifact_id"]
        self.request = response(step, self.refs)
        self.request["payload"].pop("probability")
        self.request["payload"].update(method="odds_ledger", odds_ledger=ledger(self.refs[0]))

    def finish(self, revise=False):
        self.w.submit(self.run, self.request)
        while (step := self.w.next(self.run))["disposition"] == "actionable":
            req = response(step, self.refs)
            if revise and step["task"]["kind"] == "review":
                req["payload"].update(decision="revise", probability=0.7)
            self.w.submit(self.run, req)
        return step["forecast_id"]

    def test_anchor_validation_is_atomic(self):
        anchor = self.request["payload"]["odds_ledger"]["anchor"]
        anchor.update(prior_artifact_id=self.prior_id, basis="empirical", probability=0.3)
        before = self.w.next(self.run)
        with self.assertRaisesRegex(Error, "basis differs"):
            self.w.submit(self.run, self.request)
        self.assertEqual(before, self.w.next(self.run))
        anchor.update(basis="assumed", probability=0.2)
        with self.assertRaisesRegex(Error, "probability differs"):
            self.w.submit(self.run, self.request)
        anchor["probability"] = 0.3
        self.finish()

    def test_unknown_finding_is_rejected(self):
        entry = self.request["payload"]["odds_ledger"]["entries"][0]
        entry.update(finding_id="missing", evidence_refs=[{**self.refs[0], "record_id": "missing"}])
        with self.assertRaisesRegex(Error, "Unknown evidence"):
            self.w.submit(self.run, self.request)

    def test_empirical_anchor_links_actual_reference_cases(self):
        from test_workflow import reference_prior
        run = self.w.start(run_spec(forecaster="empirical"))["run_id"]
        step = self.w.next(run)
        req = response(step, self.refs)
        req["payload"] = reference_prior(self.w, self.refs)
        prior = self.w.submit(run, req)["artifact_id"]
        while (step := self.w.next(run))["task"]["kind"] != "assessment":
            self.w.submit(run, response(step, self.refs))
        req = response(step, self.refs)
        spec = ledger(self.refs[0])
        spec["anchor"].update(basis="empirical", probability=0.5, prior_artifact_id=prior)
        req["payload"].pop("probability")
        req["payload"].update(method="odds_ledger", odds_ledger=spec)
        self.w.submit(run, req)
        self.assertAlmostEqual(self.w.next(run)["context"]["current_probability"], 2 / 3)

    def test_export_rejects_nonledger_assessment(self):
        self.request["payload"].pop("odds_ledger")
        self.request["payload"].update(method="judgment", probability=0.4)
        fid = self.finish()
        with self.assertRaisesRegex(Error, "does not use an odds ledger"):
            export(self.w.store, fid, Path(self.tmp.name) / "bad.html")

    def test_widget_preserves_issue_and_review_and_escapes_text(self):
        self.request["payload"]["odds_ledger"]["anchor"]["rationale"] = '</script><img src=x onerror="alert(1)">'
        fid = self.finish(revise=True)
        with self.w.store.connect() as c:
            before = Store.artifact(c, fid)
        output = Path(self.tmp.name) / "audit.html"
        result = export(self.w.store, fid, output)
        self.assertEqual(result["issued_probability"], 0.7)
        self.assertAlmostEqual(result["ledger_probability"], 1 / 3)
        html = output.read_text()
        self.assertNotIn('<img src=x', html)
        self.assertIn('\\u003c/script', html)
        with self.w.store.connect() as c:
            self.assertEqual(before, Store.artifact(c, fid))
        command = [sys.executable, "-m", "vorhersage", "--project", self.tmp.name,
                   "export-widget", fid, "--output", str(output)]
        run = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["data"]["forecast_id"], fid)

    def test_export_rejects_mismatched_manifest(self):
        fid = self.finish()
        with self.w.store.connect(True) as c:
            f = Store.artifact(c, fid)
            f["manifest_sha256"] = "bad"
            fid = Store.put(c, "forecast", f)
        with self.assertRaisesRegex(Error, "manifest integrity"):
            export(self.w.store, fid, Path(self.tmp.name) / "bad.html")

    @unittest.skipUnless(shutil.which("node"), "Node is needed to exercise exported JavaScript")
    def test_javascript_controls_match_python(self):
        fid = self.finish()
        path = Path(self.tmp.name) / "widget.html"
        export(self.w.store, fid, path)
        html = path.read_text()
        data = html.split('type="application/json">', 1)[1].split('</script>', 1)[0]
        script = html.split('</script><script>', 1)[1].split('</script>', 1)[0]
        # A minimal DOM runs the exact exported script, including all input callbacks.
        harness = '''const assert=require('node:assert/strict');
class Element {constructor(){this.style={};this.children=[];this.value='';} append(...x){this.children.push(...x);}
replaceChildren(){this.children=[];}setAttribute(){} }
const elements={};const document={getElementById:id=>elements[id]??=(new Element()),
createElement:()=>new Element(),createTextNode:text=>text};
'''
        harness += 'document.getElementById("record").textContent=' + json.dumps(data) + ';\n'
        harness += script + '''
assert.equal(el('posterior').textContent,'33.33%');
controls[0].number.value=4;controls[0].number.oninput();assert.equal(el('posterior').textContent,'50.00%');
controls[0].check.checked=false;controls[0].check.onchange();assert.equal(el('posterior').textContent,'20.00%');
el('reset').onclick();assert.equal(el('posterior').textContent,'33.33%');
el('anchor-value').value=0.5;el('anchor-value').oninput();assert.equal(el('posterior').textContent,'66.67%');
controls[0].number.value=-2;controls[0].number.oninput();assert.equal(el('posterior').textContent,'Invalid input');
assert.equal(el('issued').textContent,'33.33%');
'''
        result = subprocess.run([shutil.which("node"), "-"], input=harness, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
