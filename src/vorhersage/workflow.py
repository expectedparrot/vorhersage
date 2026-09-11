"""Domain-configurable forecasting, review, issuance, and monitoring."""

import copy
import json
import math

from .common import canonical, digest, identifier, now, probability, require, time
from .evidence import validate_packet, audit as evidence_audit
from .scenarios import calculate as scenario_calculate
from .relations import audit as coherence_audit
from .schemas import SCHEMAS, check
from .store import Store

INSTRUCTIONS = {
    "prior": "Establish a labeled judgmental prior or a reference class with cases and evidence. Explain comparability and limitations.",
    "drivers": "Map mechanisms and necessary steps, including concrete paths to YES and NO. Identify important unknowns.",
    "research": "Investigate this domain, including contrary evidence and net changes. Link frozen evidence or record an explicit unknown. Reconcile conflicts or explain remaining uncertainty.",
    "assessment": "Form a probability from the researched evidence. Label judgments; supply nested conditionals or exact ensemble membership when used. State limitations.",
    "review": "Challenge the estimate in both directions. Retain or revise with reasons, or request bounded additional research.",
    "issue": "Freeze the estimate with a stopping reason, review date, and observable update triggers.",
}


def task(kind, **fields):
    return {"id": identifier("task"), "kind": kind, "instruction": INSTRUCTIONS[kind], **fields}


def evidence_refs(value):
    """Only explicit evidence_refs fields establish a forecast dependency."""
    refs = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "evidence_refs":
                refs.extend(child)
            else:
                refs.extend(evidence_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.extend(evidence_refs(child))
    return list({canonical(r): r for r in refs}.values())


def verify_refs(c, refs, cutoff):
    records = []
    for ref in refs:
        packet = Store.artifact(c, ref["packet_id"], "packet")
        require(time(packet["information_as_of"]) <= time(cutoff), "Packet cutoff is later than the run's information cutoff.")
        matches = [r for r in packet["records"] if r["id"] == ref["record_id"]]
        require(len(matches) == 1, "Unknown evidence record: " + ref["record_id"], "not_found")
        records.append({"reference": ref, "record": matches[0]})
    return records


class Workflow:
    def __init__(self, project):
        self.store = Store(project)

    def add_profile(self, spec):
        check(spec, "profile")
        require(len(set(spec["domains"])) == len(spec["domains"]), "Duplicate research domains.")
        with self.store.connect(True) as c:
            c.execute("INSERT INTO profiles VALUES (?,?)", (spec["id"], canonical(spec)))
            Store.event(c, "profile.add", spec)
        return spec

    def question(self, spec, expected_version=None):
        check(spec, "question")
        require(time(spec["resolve_after"]) >= time(spec["event_deadline"]), "resolve_after must not precede event_deadline.")
        with self.store.connect(True) as c:
            require(c.execute("SELECT 1 FROM profiles WHERE id=?", (spec["profile"],)).fetchone(), "Unknown research profile.")
            row = c.execute("SELECT MAX(version) FROM questions WHERE id=?", (spec["id"],)).fetchone()
            current = row[0]
            require(current == expected_version, "Question already exists or expected version is stale.", "version_conflict")
            version = (current or 0) + 1
            c.execute("INSERT INTO questions VALUES (?,?,?,?)", (spec["id"], version, canonical(spec), now()))
            Store.event(c, "question.version", {"id": spec["id"], "version": version, "specification": spec})
        return {"question_id": spec["id"], "version": version}

    def import_packet(self, packet):
        packet = validate_packet(packet)
        id = "pkt_" + packet["sha256"][:24]
        with self.store.connect(True) as c:
            Store.put(c, "packet", packet, id=id)
        return {"packet_id": id, "sha256": packet["sha256"],
                "records": [{"record_id": r["id"], "claim": r["claim"], "evidence_ref": {"packet_id": id, "record_id": r["id"]}} for r in packet["records"]]}

    def start(self, spec):
        with self.store.connect(True) as c:
            return self._start(c, spec)

    def _start(self, c, spec, protocol=None):
        """Internal transactional start, also used for atomic experiment creation."""
        check(spec, "run")
        require(time(spec["information_as_of"]) <= time(now()), "Information cutoff cannot be in the future.")
        question = Store.question(c, spec["question_id"], spec.get("question_version"))
        q = question["specification"]
        require((q["kind"] == "simulation") == (spec["mode"] == "simulation"), "Question kind and run mode disagree.")
        cutoff_policy = spec.get("cutoff_policy", "live" if spec["mode"] == "prospective" else "fixed")
        require(cutoff_policy != "live" or spec["mode"] == "prospective", "Live cutoffs require prospective mode.")
        if spec["mode"] == "prospective":
            require(time(now()) < time(q["event_deadline"]), "Prospective forecasting deadline has passed.")
            require(not self._resolutions(c, q["id"], question["version"]), "Question already has a resolution; use a retrospective run.")
        previous = spec.get("previous_forecast_id")
        if previous:
            old = Store.artifact(c, previous, "forecast")
            require(old["question_id"] == q["id"] and old["question_version"] == question["version"], "A revision must retain the exact question version.")
            require(old["forecaster"] == spec["forecaster"] and old["mode"] == spec["mode"], "Revision forecaster/mode changed.")
            require(time(spec["information_as_of"]) >= time(old["information_as_of"]), "Revision cutoff precedes the previous forecast.")
            latest = self._latest(c, q["id"], question["version"], spec["forecaster"], spec["mode"])
            require(latest and latest["id"] == previous, "Revise the latest forecast.")
        profile = json.loads(c.execute("SELECT body FROM profiles WHERE id=?", (q["profile"],)).fetchone()[0])
        if protocol:
            profile = {"id": protocol["method_spec_id"], "description": "Frozen method research domains",
                       "domains": protocol["method_spec"]["research_domains"]}
        id = identifier("run")
        body = {**spec, "cutoff_policy": cutoff_policy, "id": id, "question_version": question["version"], "question": q,
                "research_status": spec.get("research_status", "unspecified"),
                "profile": profile, "created_at": now(), "workflow_version": "1", **(protocol or {})}
        state = {"pending": [task("prior"), task("drivers"), *[task("research", domain=d) for d in profile["domains"]],
                             task("assessment"), task("review"), task("issue")],
                 "artifact_ids": [previous] if previous else [], "evidence_refs": [], "coverage": {},
                 "used_searches": 0, "cost_usd": 0, "model_calls": 0, "extra_tasks": 0,
                 "probability": None, "forecast_id": None, "information_as_of": spec["information_as_of"]}
        if protocol:
            state["artifact_ids"].extend([protocol["method_spec_id"], protocol["experiment_id"], *protocol["packet_ids"]])
        c.execute("INSERT INTO runs VALUES (?,?,?,0)", (id, canonical(body), canonical(state)))
        Store.event(c, "run.start", body)
        return {"run_id": id, "revision": 0}

    @staticmethod
    def _resolutions(c, question, version):
        return [r for r in Store.all(c, "resolution") if r["question_id"] == question and r["question_version"] == version]

    @staticmethod
    def _latest(c, question, version, forecaster, mode, cutoff=None):
        rows = [f for f in Store.all(c, "forecast") if f["question_id"] == question and f["question_version"] == version
                and f["forecaster"] == forecaster and f["mode"] == mode
                and (cutoff is None or time(f["issued_at"]) <= time(cutoff))]
        return max(rows, key=lambda f: (time(f["issued_at"]), f["id"])) if rows else None

    def next(self, run_id):
        with self.store.connect() as c:
            run, state, revision = Store.run(c, run_id)
            if not state["pending"]:
                resolutions = self._resolutions(c, run["question_id"], run["question_version"])
                return {"disposition": "complete" if resolutions and resolutions[-1]["outcome"] != "disputed" else "waiting",
                        "run_id": run_id, "revision": revision, "forecast_id": state["forecast_id"],
                        "monitor": self._monitor(c, run["question_id"])}
            if run["mode"] == "prospective" and (time(now()) >= time(run["question"]["event_deadline"])
                    or self._resolutions(c, run["question_id"], run["question_version"])):
                return {"disposition": "blocked", "run_id": run_id, "revision": revision,
                        "reason": "Prospective deadline passed or a resolution was recorded. Preserve this run; any hindsight work needs a separate retrospective run."}
            selected = copy.deepcopy(state["pending"][0])
            if run.get("method_spec"):
                method = run["method_spec"]
                selected["instruction"] += "\n" + method["instructions"] + "\n" + method["task_instructions"].get(selected["kind"], "")
                if time(now()) >= time(run["forecast_cutoff"]):
                    return {"disposition": "blocked", "run_id": run_id, "revision": revision,
                            "reason": "Experiment forecast cutoff passed."}
            packet_ids = sorted({r["packet_id"] for r in state["evidence_refs"]})
            return {"disposition": "actionable", "run_id": run_id, "revision": revision,
                    "task": selected, "submission_schema": SCHEMAS["submit"], "payload_schema": SCHEMAS[selected["kind"]],
                    "budget": {"searches_remaining": run["max_searches"] - state["used_searches"],
                               "extra_tasks_remaining": run["max_extra_tasks"] - state["extra_tasks"],
                               "reported_cost_usd": state["cost_usd"], "reported_model_calls": state["model_calls"]},
                    "context": {"run": run, "coverage": state["coverage"], "current_probability": state["probability"],
                                "artifacts": {id: Store.artifact(c, id) for id in state["artifact_ids"]},
                                "evidence": verify_refs(c, state["evidence_refs"], run["information_as_of"]),
                                "evidence_audits": {id: evidence_audit(Store.artifact(c, id, "packet")) for id in packet_ids},
                                "prior_record": state.get("prior_record")}}

    def submit(self, run_id, result):
        check(result, "submit")
        with self.store.connect(True) as c:
            retry = Store.receipt(c, run_id, result["idempotency_key"], result)
            if retry:
                return retry
            run, state, revision = Store.run(c, run_id)
            require(result["expected_revision"] == revision, "Run revision is stale; read next again.", "version_conflict")
            if run["mode"] == "prospective":
                require(time(now()) < time(run["question"]["event_deadline"]), "Prospective forecasting deadline has passed.")
                require(not self._resolutions(c, run["question_id"], run["question_version"]), "Question resolved while this run was active.")
            require(bool(state["pending"]), "Run has already issued a forecast.")
            selected = state["pending"][0]
            require(selected["id"] == result["task_id"], "Submit the currently actionable task.", "task_conflict")
            p = copy.deepcopy(result["payload"])
            check(p, selected["kind"])
            if run["cutoff_policy"] == "live":
                run["information_as_of"] = now()
                state["information_as_of"] = run["information_as_of"]
            refs = evidence_refs(p)
            verify_refs(c, refs, run["information_as_of"])
            if run.get("method_spec"):
                require(time(now()) < time(run["forecast_cutoff"]), "Experiment forecast cutoff passed.")
                method = run["method_spec"]
                require(all(ref["packet_id"] in run["packet_ids"] for ref in refs), "Experiment requires registered frozen packets.")
                if selected["kind"] in ("prior", "assessment"):
                    require(p["method"] == method[selected["kind"] + "_method"], "Submission does not follow the registered method.")
                require("usage" in result, "Experiment submissions must report usage.")
                usage = result["usage"]
                require(state["model_calls"] + usage["model_calls"] <= method["budget"]["max_model_calls"] and
                        state["cost_usd"] + usage["cost_usd"] <= method["budget"]["max_cost_usd"],
                        "Experiment reported model/cost budget exhausted.", "budget_exhausted")
            usage = result.get("usage", {"searches": 0, "cost_usd": 0, "model_calls": 0})
            require(state["used_searches"] + usage["searches"] <= run["max_searches"], "Research budget exhausted; submit existing evidence or explicit unknowns.", "budget_exhausted")
            state["used_searches"] += usage["searches"]
            state["cost_usd"] += usage["cost_usd"]
            state["model_calls"] += usage["model_calls"]
            state["evidence_refs"] = list({canonical(r): r for r in state["evidence_refs"] + refs}.values())
            calculated = self._apply(c, run, state, selected, p)
            artifact = {"task": selected, "payload": p, "calculation": calculated, "usage": usage,
                        "submitted_at": now(), "information_as_of": run["information_as_of"], "revision": revision + 1}
            artifact_id = Store.put(c, "task_result", artifact, run_id)
            state["artifact_ids"].append(artifact_id)
            state["pending"].pop(0)
            c.execute("UPDATE runs SET state=?,revision=? WHERE id=? AND revision=?", (canonical(state), revision + 1, run_id, revision))
            response = {"accepted": True, "duplicate": False, "run_id": run_id, "revision": revision + 1,
                        "artifact_id": artifact_id, "forecast_id": state["forecast_id"]}
            Store.remember(c, run_id, result["idempotency_key"], result, response)
            Store.event(c, "task.submit", {"run_id": run_id, **response})
            return response

    def _apply(self, c, run, state, selected, p):
        kind = selected["kind"]
        if kind == "prior":
            status = run.get("research_status", "unspecified")
            state["prior_record"] = {"research_status_at_run_start": status, "recorded_at": now(),
                                     "timing": "declared_before_research" if status == "not_started" else
                                     ("after_research_started" if status in ("in_progress", "completed") else "unspecified"),
                                     "qualification": "Research status is an agent declaration; external research history is not independently observable."}
            if p["method"] == "judgment":
                require("probability" in p and "cases" not in p, "Judgment prior needs a probability, without reference-class cases.")
                value = p["probability"]
            else:
                require(bool(p.get("cases")) and bool(p.get("selection_rule")), "Reference class needs cases and a selection rule.")
                require(len({x["id"] for x in p["cases"]}) == len(p["cases"]), "Duplicate reference-class cases.")
                value = math.fsum(x["outcome"] for x in p["cases"]) / len(p["cases"])
                require("probability" not in p or math.isclose(value, p["probability"]), "Claimed reference-class rate differs from cases.")
            state["probability"] = probability(value)
            state["probability_basis"] = "prior_" + p["method"]
            return {"probability": value, "sample_size": len(p.get("cases", [])), "prior_record": state["prior_record"]}
        if kind == "research":
            require(p["disposition"] != "assessed" or bool(p["evidence_refs"]), "Assessed research needs evidence.")
            require(p["disposition"] != "unknown" or bool(p["unknowns"]), "Unknown research needs an explicit unresolved question/reason.")
            state["coverage"][selected["domain"]] = {"task_id": selected["id"], **p}
        if kind == "assessment":
            require(set(run["profile"]["domains"]) <= set(state["coverage"]), "Required research coverage is incomplete.")
            method = p["method"]
            if method != "scenario_mixture":
                require(not any(k in p for k in ("scenarios", "partition_justification")), "Scenario fields require scenario_mixture method.")
            if method == "judgment":
                require("probability" in p and not any(k in p for k in ("components", "members", "weights")), "Judgment assessment requires only its supplied probability.")
                value = p["probability"]
            elif method == "conditional_path":
                require(bool(p.get("components")) and bool(p.get("nested_events_justification")), "Conditional path needs components and a nesting justification.")
                require("members" not in p and "weights" not in p, "Conditional path cannot include ensemble fields.")
                previous = None
                ids = set()
                for component in p["components"]:
                    require(component["conditional_on"] == previous and component["id"] not in ids, "Components must form a unique nested chain, starting with an unconditional event.")
                    previous = component["id"]
                    ids.add(previous)
                require(previous == "target", "Final conditional component must be named target.")
                value = math.prod(component["probability"] for component in p["components"])
            elif method == "scenario_mixture":
                require(not any(k in p for k in ("components", "members", "weights", "nested_events_justification")), "Scenario mixture cannot include path or ensemble fields.")
                require("scenarios" in p and "partition_justification" in p, "Scenario mixture needs scenarios and partition justification.")
                calculation = scenario_calculate({k: p[k] for k in ("scenarios", "partition_justification")})
                value = calculation["probability"]
            else:
                require(bool(p.get("members")) and "components" not in p, "Ensemble needs forecast member IDs.")
                members = [Store.artifact(c, id, "forecast") for id in p["members"]]
                require(len({m["forecaster"] for m in members}) == len(members), "Ensemble requires one eligible forecast per forecaster.")
                for id, member in zip(p["members"], members):
                    require(member["question_id"] == run["question_id"] and member["question_version"] == run["question_version"] and member["mode"] == run["mode"], "Ensemble event version/mode mismatch.")
                    latest = self._latest(c, run["question_id"], run["question_version"], member["forecaster"], run["mode"], run["information_as_of"])
                    require(latest and latest["id"] == id, "Ensemble member is not the latest eligible forecast at this cutoff.")
                weights = p.get("weights", [1 / len(members)] * len(members))
                require(len(weights) == len(members) and math.isclose(math.fsum(weights), 1), "Ensemble weights must match members and sum to one.")
                value = math.fsum(w * m["probability"] for w, m in zip(weights, members))
                state["artifact_ids"] = list(dict.fromkeys(state["artifact_ids"] + p["members"]))
            probability(value)
            require("probability" not in p or math.isclose(p["probability"], value), "Supplied probability differs from computed estimate.")
            state["probability"] = value
            state["probability_basis"] = method
            return {"probability": value, "method": method, "assumptions_are_agent_supplied": True,
                    **({"scenario_analysis": calculation} if method == "scenario_mixture" else {})}
        if kind == "review":
            require({o["direction"] for o in p["objections"]} == {"too_high", "too_low"}, "Review must challenge the estimate in both directions.")
            if p["decision"] == "research":
                more = p.get("research_tasks", [])
                require(bool(more), "A research decision requires new tasks.")
                require(state["extra_tasks"] + len(more) <= run["max_extra_tasks"], "Extra-task budget exhausted; retain or revise with limitations.", "budget_exhausted")
                state["extra_tasks"] += len(more)
                new = [task("research", domain=r["domain"], instruction=r["purpose"]) for r in more]
                state["pending"][1:1] = [*new, task("assessment"), task("review")]
            elif p["decision"] == "revise":
                require("probability" in p, "Revised review needs a probability.")
                state["probability"] = p["probability"]
                state["probability_basis"] = "review_judgment"
            else:
                require("probability" not in p or p["probability"] == state["probability"], "Retain cannot change the probability.")
            return {"probability": state["probability"], "decision": p["decision"]}
        if kind == "issue":
            require(time(p["review_at"]) > time(run["information_as_of"]), "Review time must follow the information cutoff.")
            probability(state["probability"])
            if run["mode"] == "prospective":
                require(time(now()) < time(run["question"]["event_deadline"]), "Prospective forecasting deadline has passed.")
                require(not self._resolutions(c, run["question_id"], run["question_version"]), "Question resolved while this run was active.")
            latest = self._latest(c, run["question_id"], run["question_version"], run["forecaster"], run["mode"])
            if run.get("previous_forecast_id"):
                require(latest and latest["id"] == run["previous_forecast_id"], "Another revision has issued; start from the latest forecast.", "version_conflict")
            packets = sorted({r["packet_id"] for r in state["evidence_refs"]})
            ids = list(dict.fromkeys(state["artifact_ids"] + packets))
            manifest = {id: digest(Store.artifact(c, id)) for id in ids}
            forecast = {"question_id": run["question_id"], "question_version": run["question_version"],
                        "question": run["question"], "run_id": run["id"], "forecaster": run["forecaster"],
                        "profile": run["profile"], "workflow_version": run["workflow_version"],
                        "method": run["method"], "mode": run["mode"], "probability": state["probability"],
                        "probability_basis": state["probability_basis"],
                        "information_as_of": run["information_as_of"], "issued_at": now(),
                        "initial_information_as_of": run["initial_information_as_of"], "cutoff_policy": run["cutoff_policy"],
                        "previous_forecast_id": run.get("previous_forecast_id"), "coverage": state["coverage"],
                        "input_manifest": manifest, "manifest_sha256": digest(manifest),
                        "evidence_refs": state["evidence_refs"], "cost_usd": state["cost_usd"],
                        "prior_record": state.get("prior_record", {"timing": "unspecified"}),
                        "searches": state["used_searches"], "model_calls": state["model_calls"], **p}
            if run.get("experiment_id"):
                forecast.update({key: run[key] for key in ("experiment_id", "method_spec_id", "trial_id", "repetition")})
            coherence = coherence_audit(c, {**forecast, "id": "pending"})
            require(run.get("coherence_policy", "warn") != "strict" or not coherence["violations"],
                    "Forecast violates a registered implication; revise or use the warn policy with review.", "incoherent_forecast")
            forecast["coherence"] = coherence
            for comparison in coherence["comparisons"]:
                for rid in comparison["relation_ids"]:
                    manifest[rid] = digest(Store.artifact(c, rid))
                for fid in (comparison["antecedent_forecast"], comparison["consequent_forecast"]):
                    if fid != "pending":
                        manifest[fid] = digest(Store.artifact(c, fid))
            forecast["manifest_sha256"] = digest(manifest)
            state["forecast_id"] = Store.put(c, "forecast", forecast, run["id"])
            return {"forecast_id": state["forecast_id"], "probability": state["probability"]}
        return None

    def signal(self, spec):
        check(spec, "signal")
        require(spec.get("question_id") or spec["evidence_refs"], "Signal requires a question or affected evidence references.")
        with self.store.connect(True) as c:
            retry = Store.receipt(c, "signal", spec["idempotency_key"], spec)
            if retry:
                return retry
            if spec.get("question_id"):
                Store.question(c, spec["question_id"])
            verify_refs(c, spec["evidence_refs"], now())
            refs = {canonical(r) for r in spec["evidence_refs"]}
            affected = [f["id"] for f in Store.all(c, "forecast") if f["question_id"] == spec.get("question_id") or refs.intersection(canonical(r) for r in f["evidence_refs"])]
            id = Store.put(c, "signal", {**spec, "affected_forecast_ids": affected, "recorded_at": now()})
            result = {"signal_id": id, "affected_forecast_ids": affected}
            Store.remember(c, "signal", spec["idempotency_key"], spec, result)
            return result

    def _monitor(self, c, question_id=None):
        current = {}
        for f in Store.all(c, "forecast"):
            key = (f["question_id"], f["question_version"], f["forecaster"], f["mode"])
            if key not in current or time(f["issued_at"]) > time(current[key]["issued_at"]):
                current[key] = f
        due = []
        signals = Store.all(c, "signal")
        for f in current.values():
            if question_id and f["question_id"] != question_id:
                continue
            resolutions = self._resolutions(c, f["question_id"], f["question_version"])
            if resolutions and resolutions[-1]["outcome"] != "disputed":
                continue
            reasons = [s["reason"] for s in signals if f["id"] in s["affected_forecast_ids"]]
            if time(f["review_at"]) <= time(now()):
                reasons.append("Scheduled review is due.")
            for trigger in f["triggers"]:
                if trigger.get("at") and time(f["issued_at"]) < time(trigger["at"]) <= time(now()):
                    reasons.append("Calendar trigger: " + trigger["description"])
            if time(f["question"]["resolve_after"]) <= time(now()):
                reasons.append("Resolution research is due.")
            if reasons:
                due.append({"forecast_id": f["id"], "question_id": f["question_id"], "reasons": reasons,
                            "action": "Resolve if evidence establishes the outcome; otherwise start a run referencing previous_forecast_id."})
        return due

    def monitor(self):
        with self.store.connect() as c:
            return {"due": self._monitor(c), "checked_at": now(), "mutates": False}

    def resolve(self, spec):
        check(spec, "resolution")
        require(time(spec["known_at"]) <= time(now()), "Resolution known_at cannot be in the future.")
        with self.store.connect(True) as c:
            retry = Store.receipt(c, "resolution", spec["idempotency_key"], spec)
            if retry:
                return retry
            Store.question(c, spec["question_id"], spec["question_version"])
            verify_refs(c, spec["evidence_refs"], spec["known_at"])
            previous = self._resolutions(c, spec["question_id"], spec["question_version"])
            require(spec["previous_resolution_id"] == (previous[-1]["id"] if previous else None), "Resolution correction must reference the latest resolution.", "version_conflict")
            id = Store.put(c, "resolution", {**spec, "recorded_at": now()})
            response = {"resolution_id": id, "outcome": spec["outcome"]}
            Store.remember(c, "resolution", spec["idempotency_key"], spec, response)
            return response

    def report(self, question_id):
        with self.store.connect() as c:
            question = Store.question(c, question_id)
            forecasts = [f for f in Store.all(c, "forecast") if f["question_id"] == question_id]
            return {"question": question, "forecasts": forecasts,
                    "resolutions": [r for r in Store.all(c, "resolution") if r["question_id"] == question_id],
                    "due": self._monitor(c, question_id)}

    def status(self):
        with self.store.connect() as c:
            return {"project": dict(c.execute("SELECT key,value FROM meta").fetchall()),
                    "questions": [{"id": r["id"], "version": r["version"], "specification": json.loads(r["body"])} for r in c.execute("SELECT * FROM questions ORDER BY id,version")],
                    "runs": [{"run": Store.run(c, r["id"])[0], "revision": r["revision"], "pending_tasks": len(json.loads(r["state"])["pending"]), "forecast_id": json.loads(r["state"])["forecast_id"]} for r in c.execute("SELECT * FROM runs ORDER BY rowid")],
                    "forecast_count": len(Store.all(c, "forecast")), "due": self._monitor(c)}

    def doctor(self):
        with self.store.connect() as c:
            integrity = c.execute("PRAGMA integrity_check").fetchone()[0]
            require(integrity == "ok", "SQLite integrity check failed.", "integrity_error")
            count = 0
            for row in c.execute("SELECT * FROM artifacts"):
                body = Store.artifact(c, row["id"])
                if row["kind"] == "packet":
                    validate_packet(body)
                if row["kind"] in ("forecast", "evaluation", "replay_evaluation", "experiment", "experiment_evaluation"):
                    if row["kind"] == "forecast":
                        require(digest(body["input_manifest"]) == body["manifest_sha256"], "Forecast manifest hash mismatch.")
                    for id, expected in body["input_manifest"].items():
                        require(digest(Store.artifact(c, id)) == expected, "Forecast input has changed.", "integrity_error")
                if row["kind"] == "experiment":
                    for q in body["questions"]:
                        require(digest(Store.question(c, q["question_id"], q["version"])) == q["sha256"],
                                "Experiment question has changed.", "integrity_error")
                count += 1
            return {"ok": True, "artifacts_checked": count, "sqlite_integrity": integrity}
