import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from vorhersage import timeline, experiments
from vorhersage.common import Error, now
from vorhersage.schemas import check
from vorhersage.store import Store
from vorhersage.timeline_reports import export
from vorhersage.widget import export as export_widget
from vorhersage.workflow import Workflow
from test_workflow import packet, payload, question, run_spec, stamp
from test_experiments import method


def assessment(pid, value=None, basis="assumed", refs=None):
    return {"parameter_id": pid, "basis": basis, "rationale": "Declared test input.",
            "evidence_refs": refs or [], **({"value": value} if basis != "unresolved" else {})}


def node(id, kind, parents=(), parameter=None, **extra):
    return {"id": id, "kind": kind, "parents": list(parents), "state": "pending",
            "completion_condition": "Test milestone " + id, "rationale": "Declared test dependency.",
            "evidence_refs": [], **({"parameter_id": parameter} if parameter else {}), **extra}


def model(sequential=False):
    return {"id": "sequential" if sequential else "parallel", "version": 1,
            "question": {"question_id": "factory", "version": 1}, "description": "Hypothetical schedules, not a real forecast.",
            "information_as_of": "2026-09-15T00:00:00Z", "deadline": "2029-01-01T00:00:00Z",
            "deadline_rule": "before", "target": "launch", "limitations": ["Synthetic assumptions."],
            "parameters": [{"id": id, "kind": kind, "description": description} for id, kind, description in (
                ("authorization_date", "date", "date a usable authorization takes effect"),
                ("preparation_days", "duration_days", "elapsed preparation days"),
                ("rollout_days", "duration_days", "days to open paid public access"))],
            "nodes": [node("authorization", "event", parameter="authorization_date"),
                      node("preparation", "task", ["authorization"] if sequential else [], "preparation_days", not_before="2028-03-01T00:00:00Z"),
                      node("ready", "all", ["authorization", "preparation"]),
                      node("launch", "task", ["ready"], "rollout_days")],
            "scenarios": [{"id": id, "description": id + " authorization", "evidence_refs": [],
                           "assessments": [assessment("authorization_date", date), assessment("preparation_days", 184), assessment("rollout_days", 61)]}
                          for id, date in [("early", "2027-07-01T00:00:00Z"), ("late", "2028-07-01T00:00:00Z"), ("never", "never")]]}


def weighted(spec):
    spec = copy.deepcopy(spec)
    spec["partition_justification"] = "These three synthetic joint cases exhaust the fixture."
    for s, weight in zip(spec["scenarios"], [0.2, 0.5, 0.3]):
        s.update(weight=weight, weight_rationale="Synthetic assigned weight.")
    return spec


class CalculationTests(unittest.TestCase):
    def test_overlap_changes_outcome_without_implied_weights(self):
        report = timeline.compare_specs(model(), model(True))
        late = next(r for r in report["matched_scenarios"] if r["scenario_id"] == "late")
        self.assertEqual(late["left_launch_at"], "2028-11-01T00:00:00+00:00")
        self.assertEqual(late["right_launch_at"], "2029-03-03T00:00:00+00:00")
        self.assertTrue(late["changes_outcome"])
        self.assertIsNone(report["left"]["probability"])
        self.assertEqual(report["left"]["disposition"], "unweighted")
        self.assertEqual(report["changed_fields"], ["nodes"])

    def test_joint_weights_count_outcomes_exactly(self):
        self.assertAlmostEqual(timeline.analyze(weighted(model()))["probability"], 0.7)
        self.assertAlmostEqual(timeline.analyze(weighted(model(True)))["probability"], 0.2)
        for change in ("partial", "sum", "rationale", "partition"):
            spec = weighted(model())
            if change == "partial": del spec["scenarios"][0]["weight"]
            if change == "sum": spec["scenarios"][0]["weight"] = 0.1
            if change == "rationale": del spec["scenarios"][0]["weight_rationale"]
            if change == "partition": del spec["partition_justification"]
            with self.subTest(change=change), self.assertRaises(Error): timeline.analyze(spec)

    def test_missing_is_distinct_from_never_and_returns_weight_bounds(self):
        spec = weighted(model())
        spec["scenarios"][1]["assessments"][0] = assessment("authorization_date", basis="unresolved")
        result = timeline.analyze(spec)
        self.assertEqual(result["scenarios"][1]["status"], "unresolved")
        self.assertIsNone(result["scenarios"][1]["meets_deadline"])
        self.assertEqual(result["scenarios"][2]["status"], "never")
        self.assertFalse(result["scenarios"][2]["meets_deadline"])
        self.assertIsNone(result["probability"])
        self.assertEqual(result["probability_bounds"], [0.2, 0.7])
        self.assertEqual(result["gaps"]["unresolved"][0]["parameter_id"], "authorization_date")

    def test_any_route_can_succeed_despite_another_never_finishing(self):
        spec = model()
        spec["nodes"][2]["kind"] = "any"
        # This is a synthetic alternative route, not a claim that preparation replaces permission.
        result = timeline.analyze(spec)
        never = result["scenarios"][2]
        self.assertTrue(never["meets_deadline"])
        self.assertEqual(never["schedule"][2]["controlling_parents"], ["preparation"])

    def test_deadline_boundary_timezone_and_zero_duration(self):
        spec = model()
        for s in spec["scenarios"]:
            s["assessments"][0]["value"] = "2028-12-31T19:00:00-05:00"
            s["assessments"][2]["value"] = 0
        self.assertFalse(timeline.analyze(spec)["scenarios"][0]["meets_deadline"])
        spec["deadline_rule"] = "on_or_before"
        self.assertTrue(timeline.analyze(spec)["scenarios"][0]["meets_deadline"])

    def test_started_tasks_use_remaining_duration(self):
        spec = model()
        spec["information_as_of"] = "2028-04-01T00:00:00Z"
        spec["nodes"][1].update(state="in_progress", started_at="2028-03-01T00:00:00Z", evidence_refs=[{"packet_id": "p", "record_id": "r"}])
        result = timeline.analyze(spec)
        prep = next(n for n in result["scenarios"][0]["schedule"] if n["node_id"] == "preparation")
        self.assertEqual(prep["start_at"], "2028-04-01T00:00:00+00:00")
        self.assertEqual(prep["finish_at"], "2028-10-02T00:00:00+00:00")
        self.assertEqual(prep["duration_semantics"], "remaining_at_cutoff")

    def test_completed_observations_are_preserved_and_must_fit_prerequisites(self):
        spec = model()
        spec["information_as_of"] = "2028-04-01T00:00:00Z"
        n = spec["nodes"][1]
        n.update(state="completed", completed_at="2028-03-15T00:00:00Z", evidence_refs=[{"packet_id": "p", "record_id": "r"}])
        del n["parameter_id"]
        spec["parameters"] = [p for p in spec["parameters"] if p["id"] != "preparation_days"]
        for s in spec["scenarios"]: s["assessments"] = [a for a in s["assessments"] if a["parameter_id"] != "preparation_days"]
        result = timeline.analyze(spec)
        self.assertEqual(result["scenarios"][0]["schedule"][1]["finish_at"], "2028-03-15T00:00:00+00:00")
        n["parents"] = ["authorization"]
        with self.assertRaisesRegex(Error, "contradicts"): timeline.analyze(spec)

    def test_validation_rejects_bad_structure_and_values(self):
        mutations = [lambda s: s["nodes"][0].update(kind="all", parents=["launch"]),
                     lambda s: s["nodes"][2].update(parents=["missing"]),
                     lambda s: s["nodes"].append(node("unused", "all", ["authorization"])),
                     lambda s: s["nodes"][1].update(parameter_id="authorization_date"),
                     lambda s: s["scenarios"][0]["assessments"][1].update(value=-1),
                     lambda s: s["scenarios"][0]["assessments"][1].update(value=True),
                     lambda s: s["scenarios"][0]["assessments"][0].update(value=None),
                     lambda s: s["scenarios"][0]["assessments"][0].update(value="2028-01-01"),
                     lambda s: s["scenarios"][0]["assessments"][0].update(basis="unresolved"),
                     lambda s: s["scenarios"][0]["assessments"].append(s["scenarios"][0]["assessments"][0])]
        for i, mutate in enumerate(mutations):
            spec = model(); mutate(spec)
            with self.subTest(case=i), self.assertRaises(Error): timeline.analyze(spec)

    def test_observed_values_cannot_vary_across_worlds(self):
        spec = model()
        spec["scenarios"][0]["assessments"][0] = assessment("authorization_date", "2026-09-01T00:00:00Z", "observed", [{"packet_id": "p", "record_id": "r"}])
        with self.assertRaisesRegex(Error, "agree across"): timeline.analyze(spec)

    def test_sensitivity_exposes_outcome_changing_parameter(self):
        report = timeline.sensitivity(model(True))
        flips = [r for r in report["substitutions"] if r["changes_outcome"]]
        self.assertTrue(any(r["scenario_id"] == "late" and r["parameter_id"] == "authorization_date" for r in flips))


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.w = Workflow(self.tmp.name); self.w.store.init("Timeline tests")
        q = question(); q.update(event_deadline=model()["deadline"], resolve_after="2029-01-02T00:00:00Z")
        self.w.question(q)

    def start(self, spec):
        id = timeline.add(self.w.store, spec)["timeline_model_id"]
        run = self.w.start(run_spec(workflow="timeline"))["run_id"]
        self.submit(run, {"timeline_model_id": id, "rationale": "Investigate these parameters first."})
        return run, id

    def submit(self, run, value):
        step = self.w.next(run)
        return self.w.submit(run, {"task_id": step["task"]["id"], "expected_revision": step["revision"],
                                   "idempotency_key": step["task"]["id"], "payload": value,
                                   "usage": {"searches": 0, "model_calls": 0, "cost_usd": 0}})

    def research(self, run, source):
        while (step := self.w.next(run))["task"]["kind"] == "timeline_research":
            pid = step["task"]["parameter_id"]
            value = {"rationale": "Parameter-focused research.", "assessments": [
                {"scenario_id": s["id"], "assessment": next(a for a in s["assessments"] if a["parameter_id"] == pid)} for s in source["scenarios"]]}
            self.submit(run, value)
        return step["task"]["timeline_context"]["timeline_model_id"]

    def finish(self, run, id):
        self.submit(run, {"method": "timeline_model", "timeline_model_id": id, "rationale": "Computed scenario outcome.", "limitations": [], "evidence_refs": []})
        while (step := self.w.next(run))["disposition"] == "actionable":
            self.submit(run, payload(step["task"]["kind"], []))
        return step["forecast_id"]

    def test_versioning_retries_and_question_pin(self):
        spec = model(); id = timeline.add(self.w.store, spec)["timeline_model_id"]
        self.assertEqual(timeline.add(self.w.store, spec)["timeline_model_id"], id)
        spec["description"] = "Different"
        with self.assertRaisesRegex(Error, "frozen"): timeline.add(self.w.store, spec)
        spec.update(version=2, previous_model_id=id)
        second = timeline.add(self.w.store, spec)["timeline_model_id"]
        with self.w.store.connect() as c:
            self.assertIn(id, timeline.read(c, second)["input_manifest"])
        spec.update(version=3, previous_model_id=second, deadline="2029-02-01T00:00:00Z")
        with self.assertRaisesRegex(Error, "deadline differs"): timeline.add(self.w.store, spec)

    def test_named_references_pin_versions_and_keep_artifact_ids(self):
        spec = model()
        first = timeline.add(self.w.store, spec)["timeline_model_id"]
        spec.update(version=2, previous_model_id=first, description="Second version")
        second = timeline.add(self.w.store, spec)["timeline_model_id"]
        with self.w.store.connect() as c:
            self.assertEqual(timeline.resolve(c, "parallel@1"), first)
            self.assertEqual(timeline.resolve(c, "parallel@2"), second)
            self.assertEqual(timeline.resolve(c, first), first)
            for ref in ("parallel", "parallel@0", "parallel@latest", "parallel@3", "missing@1"):
                with self.subTest(reference=ref), self.assertRaises(Error):
                    timeline.resolve(c, ref)

    def test_duration_shift_preserves_source_weights_and_records_lineage(self):
        spec = weighted(model())
        spec["scenarios"][2]["assessments"][2]["value"] = "never"
        source = timeline.add(self.w.store, spec)["timeline_model_id"]
        result = timeline.shift(self.w.store, "parallel@1", "rollout_days", 180, "slower", "Longer public rollout")
        alternative = result["specification"]
        self.assertEqual(alternative["derived_from_model_id"], source)
        self.assertIn(source, result["input_manifest"])
        self.assertEqual([s["weight"] for s in alternative["scenarios"]], [0.2, 0.5, 0.3])
        self.assertEqual([s["assessments"][2]["value"] for s in alternative["scenarios"]], [241, 241, "never"])
        self.assertAlmostEqual(timeline.analyze(alternative)["probability"], 0)
        with self.w.store.connect() as c:
            self.assertEqual(timeline.read(c, source)["specification"], spec)
        retry = timeline.shift(self.w.store, source, "rollout_days", 180, "slower", "Longer public rollout")
        self.assertEqual(retry["timeline_model_id"], result["timeline_model_id"])
        with self.assertRaisesRegex(Error, "frozen"):
            timeline.shift(self.w.store, source, "rollout_days", 90, "slower", "Different duration")

    def test_invalid_duration_variants_leave_no_partial_history(self):
        timeline.add(self.w.store, model())
        before = self.w.status()
        for parameter, days, name, reason in (
                ("rollout_days", -62, "negative", "Shorter"),
                ("rollout_days", 365250, "too_long", "Longer"),
                ("rollout_days", float("nan"), "nonfinite", "Longer"),
                ("authorization_date", 1, "date", "Longer"),
                ("missing", 1, "missing", "Longer"),
                ("rollout_days", 1, "parallel", "Same family"),
                ("rollout_days", 1, "blank", " ")):
            with self.subTest(name=name), self.assertRaises(Error):
                timeline.shift(self.w.store, "parallel@1", parameter, days, name, reason)
            self.assertEqual(self.w.status(), before)
        shortened = timeline.shift(self.w.store, "parallel@1", "rollout_days", -61, "instant", "Zero remaining days")
        self.assertEqual(shortened["specification"]["scenarios"][0]["assessments"][2]["value"], 0)

    def test_shift_rejects_unknown_and_observed_durations(self):
        spec = model()
        spec["scenarios"][0]["assessments"][2] = assessment("rollout_days", basis="unresolved")
        timeline.add(self.w.store, spec)
        with self.assertRaisesRegex(Error, "unresolved"):
            timeline.shift(self.w.store, "parallel@1", "rollout_days", 10, "unknown", "Longer")
        ref = self.w.import_packet(packet())["records"][0]["evidence_ref"]
        spec = model()
        spec.update(id="observed", information_as_of=now())
        for scenario in spec["scenarios"]:
            scenario["assessments"][2] = assessment("rollout_days", 61, "observed", [ref])
        timeline.add(self.w.store, spec)
        with self.assertRaisesRegex(Error, "observed"):
            timeline.shift(self.w.store, "observed@1", "rollout_days", 10, "changed_observation", "Longer")

    def test_cli_named_models_readable_output_and_json_compatibility(self):
        timeline.add(self.w.store, weighted(model()))

        def cli(*args):
            result = subprocess.run([sys.executable, "-m", "vorhersage", "--project", self.tmp.name,
                                     "timeline", *args], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout

        self.assertAlmostEqual(json.loads(cli("analyze", "parallel@1"))["data"]["probability"], 0.7)
        self.assertIn("Probability: 70.0%", cli("analyze", "parallel@1", "--format", "text"))
        self.assertIn("Saved slower@1", cli("shift", "parallel@1", "--parameter", "rollout_days", "--days", "180",
                                            "--name", "slower", "--rationale", "Longer rollout", "--format", "text"))
        comparison = cli("compare", "parallel@1", "slower@1", "--format", "text")
        self.assertIn("Left probability:  70.0%", comparison)
        self.assertIn("Right probability: 0.0%", comparison)
        output = Path(self.tmp.name) / "named-report.html"
        self.assertIn("Report:", cli("report", "parallel@1", "--compare", "slower@1", "--output", str(output), "--format", "text"))
        self.assertTrue(output.exists())
        draft = model()
        draft["id"] = "draft"
        draft["scenarios"][0]["assessments"][2] = assessment("rollout_days", basis="unresolved")
        timeline.add(self.w.store, draft)
        self.assertIn("Probability: unresolved", cli("analyze", "draft@1", "--format", "text"))
        self.assertIn("Unresolved parameters: 1", cli("gaps", "draft@1", "--format", "text"))

    def test_repeated_experiment_trials_own_their_model_revisions(self):
        with self.assertRaisesRegex(Error, "prior_method=none"):
            experiments.add_method(self.w.store, method(assessment_method="timeline_model"))
        mid = experiments.add_method(self.w.store, method(prior_method="none", assessment_method="timeline_model"))["method_id"]
        eid = experiments.add_experiment(self.w.store, {
            "id": "timeline_trials", "version": 1, "description": "Two model-first trials.",
            "questions": [{"question_id": "factory", "version": 1, "packet_ids": []}],
            "method_ids": [mid], "repetitions": 2, "mode": "simulation", "information_as_of": now(),
            "forecast_cutoff": stamp(0.5), "evidence_policy": "frozen_packets", "order_seed": "fixed"})["experiment_id"]
        trials = experiments.start(self.tmp.name, eid)["trials"]
        source = weighted(model()); source_id = timeline.add(self.w.store, source)["timeline_model_id"]
        final_ids = []
        for trial in trials:
            run = trial["run_id"]
            self.assertEqual(self.w.next(run)["task"]["kind"], "timeline_structure")
            self.submit(run, {"timeline_model_id": source_id, "rationale": "Shared starting structure."})
            final_ids.append(self.research(run, source))
            self.finish(run, final_ids[-1])
        self.assertNotEqual(*final_ids)
        with self.w.store.connect() as c:
            for id in final_ids:
                self.assertEqual(timeline.read(c, id)["specification"]["derived_from_model_id"], source_id)
            self.assertEqual(timeline.read(c, source_id)["specification"]["version"], 1)

    def test_research_failure_is_atomic_and_retry_does_not_add_versions(self):
        run, _ = self.start(model())
        step = self.w.next(run)
        before = self.w.status()
        with self.assertRaisesRegex(Error, "each scenario"):
            self.submit(run, {"rationale": "Incomplete declaration.", "assessments": [
                {"scenario_id": "early", "assessment": assessment("authorization_date", "never")}]})
        self.assertEqual(self.w.status(), before)
        pid = step["task"]["parameter_id"]
        result = {"task_id": step["task"]["id"], "expected_revision": step["revision"], "idempotency_key": "retry",
                  "payload": {"rationale": "Declared inputs.", "assessments": [
                      {"scenario_id": s["id"], "assessment": next(a for a in s["assessments"] if a["parameter_id"] == pid)} for s in model()["scenarios"]]}}
        self.w.submit(run, result)
        with self.w.store.connect() as c: count = len(Store.all(c, "timeline_model"))
        self.assertTrue(self.w.submit(run, result)["duplicate"])
        with self.w.store.connect() as c: self.assertEqual(len(Store.all(c, "timeline_model")), count)

    def test_structure_first_unresolved_research_then_weighted_issue(self):
        draft = model()
        for s in draft["scenarios"]: s["assessments"] = []
        run, original_id = self.start(draft)
        step = self.w.next(run)
        self.assertEqual(step["task"]["kind"], "timeline_research")
        self.assertIsNone(step["context"]["current_probability"])
        id = self.research(run, model())
        before = self.w.next(run)
        with self.assertRaisesRegex(Error, "no point probability"):
            self.finish(run, id)
        self.assertEqual(before, self.w.next(run))
        with self.w.store.connect() as c: spec = copy.deepcopy(timeline.read(c, id)["specification"])
        spec = weighted(spec); spec.update(version=spec["version"] + 1, previous_model_id=id)
        final_id = timeline.add(self.w.store, spec)["timeline_model_id"]
        fid = self.finish(run, final_id)
        with self.w.store.connect() as c:
            f = Store.artifact(c, fid)
            self.assertAlmostEqual(f["probability"], 0.7)
            self.assertEqual(f["prior_record"]["timing"], "not_applicable")
            self.assertIn(final_id, f["input_manifest"])
            self.assertIn(original_id, f["input_manifest"])
        self.assertTrue(self.w.doctor()["ok"])
        output = Path(self.tmp.name) / "forecast.html"
        export_widget(self.w.store, fid, output)
        self.assertIn('timeline.v1', output.read_text())

    def test_assessment_cannot_silently_change_researched_dependencies(self):
        spec = weighted(model()); run, _ = self.start(spec); id = self.research(run, spec)
        with self.w.store.connect() as c: changed = copy.deepcopy(timeline.read(c, id)["specification"])
        changed["nodes"][1]["parents"] = ["authorization"]
        changed.update(version=changed["version"] + 1, previous_model_id=id)
        other = timeline.add(self.w.store, changed)["timeline_model_id"]
        with self.assertRaisesRegex(Error, "cannot replace researched"): self.finish(run, other)

    def test_evidence_cutoff_and_unknown_record_are_checked(self):
        imported = self.w.import_packet(packet()); ref = imported["records"][0]["evidence_ref"]
        spec = model(); spec["nodes"][0]["evidence_refs"] = [ref]
        with self.assertRaisesRegex(Error, "cutoff"): timeline.add(self.w.store, spec)
        spec["information_as_of"] = now()
        spec["nodes"][0]["evidence_refs"][0]["record_id"] = "missing"
        with self.assertRaisesRegex(Error, "Unknown evidence"): timeline.add(self.w.store, spec)

    def test_revision_retains_timeline_workflow_without_automatic_date_updates(self):
        source = weighted(model()); run, _ = self.start(source)
        id = self.research(run, source); fid = self.finish(run, id)
        revision = self.w.start(run_spec(previous_forecast_id=fid))["run_id"]
        step = self.w.next(revision)
        self.assertEqual(step["task"]["kind"], "timeline_structure")
        self.assertEqual(step["task"]["timeline_context"]["timeline_model_id"], id)
        self.assertEqual(step["task"]["timeline_context"]["model"]["information_as_of"], source["information_as_of"])
        self.assertIsNone(step["context"]["current_probability"])

    def test_review_research_returns_to_targeted_parameter(self):
        spec = weighted(model()); run, _ = self.start(spec); id = self.research(run, spec)
        self.submit(run, {"method": "timeline_model", "timeline_model_id": id, "rationale": "Assess.", "limitations": [], "evidence_refs": []})
        review = payload("review", [])
        review.update(decision="research", research_tasks=[{"domain": "authorization_date", "purpose": "Check the decisive date."}])
        self.submit(run, review)
        self.assertEqual(self.w.next(run)["task"]["parameter_id"], "authorization_date")

    def test_cli_and_report_escape_input(self):
        spec = model(); spec["description"] = '</script><img src=x onerror="alert(1)">'
        id = timeline.add(self.w.store, spec)["timeline_model_id"]
        other = timeline.add(self.w.store, model(True))["timeline_model_id"]
        output = Path(self.tmp.name) / "comparison.html"
        for args in [("gaps", id), ("analyze", id, "--sensitivity"), ("compare", id, other), ("report", id, "--compare", other, "--output", str(output))]:
            run = subprocess.run([sys.executable, "-m", "vorhersage", "--project", self.tmp.name, "timeline", *args], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["status"], "ok")
        html = output.read_text(); self.assertNotIn('<img src=x', html); self.assertIn('\\u003c/script', html)

    @unittest.skipUnless(shutil.which("node"), "Node required for report interaction")
    def test_report_scenario_selection(self):
        id = timeline.add(self.w.store, model())["timeline_model_id"]
        other = timeline.add(self.w.store, model(True))["timeline_model_id"]
        output = Path(self.tmp.name) / "comparison.html"; export(self.w.store, id, output, other)
        html = output.read_text(); data = html.split('type="application/json">', 1)[1].split('</script>', 1)[0]
        script = html.split('</script><script>', 1)[1].split('</script>', 1)[0]
        harness = '''const assert=require('node:assert/strict');
class Element {constructor(){this.style={};this.children=[];this.value='';} append(...x){this.children.push(...x);}replaceChildren(){this.children=[];}}
const elements={};const document={getElementById:id=>elements[id]??=new Element(),createElement:()=>new Element()};
'''
        harness += 'document.getElementById("record").textContent=' + json.dumps(data) + ';\n' + script
        harness += '''
el('scenario').value='late';el('scenario').onchange();
assert.equal(el('schedules').children.length,2);
assert.equal(el('schedules').children[0].children[1].textContent,'Meets deadline');
assert.equal(el('schedules').children[1].children[1].textContent,'Misses deadline');
el('scenario').value='never';el('scenario').onchange();
assert.equal(el('schedules').children[0].children[1].textContent,'Misses deadline');
assert.equal(data.models[0].analysis.probability,null);
'''
        result = subprocess.run(['node', '-'], input=harness, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
