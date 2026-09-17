"""Domain-configurable forecasting, review, issuance, and monitoring."""

import copy
import json
import math

from .common import canonical, digest, identifier, now, probability, require, time
from .evidence import validate_packet, audit as evidence_audit
from .scenarios import calculate as scenario_calculate
from .odds import calculate as odds_calculate
from . import timeline, research_model
from .relations import audit as coherence_audit
from .schemas import SCHEMAS, check
from .store import Store

INSTRUCTIONS = {
    "intake": "Name the model inputs and missing case facts before estimating. Link each unknown to input IDs and choose ask_user, search, assumption, or unobservable. Give a concrete action and explain why it matters. When several influential facts are known to the human user and ep is available, offer a short personal survey via ep humanize; explain which inputs the answers could inform. Chat answers also work. See vorhersage guide for survey creation and response capture. An empty unknown list needs an explanation in rationale.",
    "inquiry": "Carry out the declared research action. Ask the user for facts they know; use dated evidence for observations. Related ask_user questions can be collected through an optional ep humanize survey for that user; preserve the question-to-input mapping and capture the actual answers as self-reported evidence. Record an answer or explicitly leave this unresolved with reasons. Do not turn an interpretation into an observed fact.",
    "model_challenge": "Inspect the actual quantities in context.model_map. For each input, decide whether its cited passages support that quantity, merely inform an assumption, or concern a different quantity. Inspect influential inputs first. For scenario models test concrete boundary trajectories and a spike followed by reversal before the deadline; record zero/multiple matches honestly. Name material concerns and concrete actions: investigate now, await evidence, or retain an assumption with reasons. These are declared judgments, not automated verification.",
    "prior": "Establish a labeled judgmental prior or a reference class with cases and evidence. Explain comparability and limitations.",
    "drivers": "Map mechanisms and necessary steps, including concrete paths to YES and NO. Identify important unknowns.",
    "research": "Investigate this domain, including contrary evidence and net changes. Link frozen evidence or record an explicit unknown. Reconcile conflicts or explain remaining uncertainty.",
    "assessment": "Form a probability from the researched evidence. Label judgments; supply nested conditionals or exact ensemble membership when used. State limitations.",
    "review": "Challenge the estimate in both directions. Retain or revise with reasons, or request bounded additional research.",
    "issue": "Freeze the estimate with a stopping reason, review date, and observable update triggers.",
    "timeline_structure": "Register a deadline model and submit its timeline_model_id. Unresolved parameters and unweighted scenarios are valid. The package will create research tasks for its parameters; no starting probability is required.",
    "timeline_research": "Assess the named model parameter in every scenario using evidence or an explicit assumption. Unresolved inputs remain unresolved. Durations for in-progress tasks mean remaining days at the model cutoff.",
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


def verify_refs(c, refs, cutoff, *, context="the run information cutoff"):
    records = []
    for ref in refs:
        packet = Store.artifact(c, ref["packet_id"], "packet")
        require(time(packet["information_as_of"]) <= time(cutoff),
                f"Packet {ref['packet_id']} cutoff {packet['information_as_of']} is later than {context} {cutoff}. "
                "Preserve actual observation and retrieval times. For new evidence after an issued forecast, use revise; "
                "for future-dated records, correct only demonstrably erroneous timestamps.", "evidence_after_cutoff")
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
        with self.store.connect(True) as c:
            return self._question(c, spec, expected_version)

    @staticmethod
    def _question(c, spec, expected_version=None):
        """Register a question inside a caller-owned transaction."""
        check(spec, "question")
        require(time(spec["resolve_after"]) >= time(spec["event_deadline"]), "resolve_after must not precede event_deadline.")
        require(c.execute("SELECT 1 FROM profiles WHERE id=?", (spec["profile"],)).fetchone(), "Unknown research profile.")
        current = c.execute("SELECT MAX(version) FROM questions WHERE id=?", (spec["id"],)).fetchone()[0]
        require(current == expected_version, "Question already exists or expected version is stale.", "version_conflict")
        version = (current or 0) + 1
        c.execute("INSERT INTO questions VALUES (?,?,?,?)", (spec["id"], version, canonical(spec), now()))
        Store.event(c, "question.version", {"id": spec["id"], "version": version, "specification": spec})
        return {"question_id": spec["id"], "version": version}

    def import_packet(self, packet):
        packet = validate_packet(packet)
        checked_at = now()
        require(time(packet["information_as_of"]) <= time(checked_at) and time(packet["created_at"]) <= time(checked_at),
                f"Evidence packet is future-dated relative to current time {checked_at}. "
                "Use evidence add to record the current capture time; preserve genuine historical source times.", "future_evidence")
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
        previous = spec.get("previous_forecast_id")
        old = Store.artifact(c, previous, "forecast") if previous else None
        if protocol:
            default_workflow = "timeline" if protocol["method_spec"]["assessment_method"] == "timeline_model" else "standard"
        else:
            default_workflow = "timeline" if old and old.get("timeline_model_id") else "standard"
        workflow = spec.get("workflow", default_workflow)
        if protocol:
            require((workflow == "timeline") == (protocol["method_spec"]["assessment_method"] == "timeline_model"), "Workflow and registered method disagree.")
        cutoff_policy = spec.get("cutoff_policy", "live" if spec["mode"] == "prospective" and workflow != "timeline" else "fixed")
        require(cutoff_policy != "live" or spec["mode"] == "prospective", "Live cutoffs require prospective mode.")
        if spec["mode"] == "prospective":
            require(time(now()) < time(q["event_deadline"]), "Prospective forecasting deadline has passed.")
            require(not self._resolutions(c, q["id"], question["version"]), "Question already has a resolution; use a retrospective run.")
        if previous:
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
        if workflow == "timeline":
            body.update(workflow="timeline", workflow_version="timeline.v1")
        if spec.get("research_contract") == "structured_v2":
            body["workflow_version"] = workflow + ".structured_v2"
        state = {"pending": [task("prior"), task("drivers"), *[task("research", domain=d) for d in profile["domains"]],
                             task("assessment"), task("review"), task("issue")],
                 "artifact_ids": [previous] if previous else [], "evidence_refs": [], "coverage": {},
                 "used_searches": 0, "cost_usd": 0, "model_calls": 0, "extra_tasks": 0,
                 "probability": None, "forecast_id": None, "information_as_of": spec["information_as_of"]}
        if workflow == "timeline":
            state["pending"] = [task("timeline_structure"), task("assessment"), task("review"), task("issue")]
            state["prior_record"] = {"timing": "not_applicable", "qualification": "Timeline workflow has no starting-probability task."}
            if old and old.get("timeline_model_id"):
                self._bind_timeline(c, body, state, old["timeline_model_id"])
        if spec.get("research_contract") in ("structured_v1", "structured_v2"):
            state["pending"].insert(0, task("intake"))
        if spec.get("research_contract") == "structured_v2" and old:
            state["model_map"] = copy.deepcopy(old.get("model_map"))
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
            return self._next(c, run_id)

    def _next(self, c, run_id):
        """Read a task within the caller's consistent database snapshot."""
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
        if state.get("timeline_model_id"):
            spec = timeline.read(c, state["timeline_model_id"])["specification"]
            selected["timeline_context"] = {"timeline_model_id": state["timeline_model_id"],
                                            "model": spec, "analysis": timeline.analyze(spec)}
        if run.get("method_spec"):
            method = run["method_spec"]
            selected["instruction"] += "\n" + method["instructions"] + "\n" + method["task_instructions"].get(selected["kind"], "")
            if time(now()) >= time(run["forecast_cutoff"]):
                return {"disposition": "blocked", "run_id": run_id, "revision": revision,
                        "reason": "Experiment forecast cutoff passed."}
        packet_ids = sorted({r["packet_id"] for r in state["evidence_refs"]})
        payload_schema = copy.deepcopy(SCHEMAS[selected["kind"]])
        if run.get("research_contract") in ("structured_v1", "structured_v2"):
            extra = {"prior": "research_status_at_estimate", "assessment": "parameter_support", "review": "sensitivity_review"}.get(selected["kind"])
            if extra:
                payload_schema["required"].append(extra)
            if selected["kind"] == "assessment":
                selected["instruction"] += " Supply parameter_support for every numeric/model input, linking the intake input IDs. Distinguish what evidence measured from the target and declare transfer assumptions and ranges."
            if selected["kind"] == "review":
                selected["instruction"] += " Inspect context.sensitivity and model_inputs. Address influential assumptions and what obtainable evidence could narrow them in sensitivity_review."
        if run.get("research_contract") == "structured_v2":
            extra = {"assessment": "model_map", "review": "concern_resolutions"}.get(selected["kind"])
            if extra:
                payload_schema["required"].append(extra)
            if selected["kind"] == "inquiry":
                selected["instruction"] += " Reuse this answer for relevant profile domains through coverage [{domain, interpretation}]; this removes duplicate domain tasks. Mark unresolved gaps honestly."
            if selected["kind"] == "assessment":
                selected["instruction"] += " Supply a new model_map version, explicitly separating scenario weights from conditional event probabilities. Remap evidence if the model changed; explain changes in rationale. Use context.model_map for previous_version (0 initially)."
            if selected["kind"] == "prior":
                selected["instruction"] += " For an empirical reference_class, register dated reference cases and supply reference_query plus its returned cases. Unresolved episodes are censored, not failures; related proposals belong to one episode. Without a defensible denominator use judgment."
            if selected["kind"] == "review":
                for field in ("probability", "parameter_support", "research_tasks"):
                    payload_schema["properties"].pop(field, None)
                selected["instruction"] += " Resolve every context.model_challenge concern through concern_resolutions. Investigate creates linked inquiry tasks; await_evidence needs an observable trigger; retain_assumption explains the remaining uncertainty. Use revise to return to assessment and challenge (no inline replacement probability); research for new inquiries."
        return {"disposition": "actionable", "run_id": run_id, "revision": revision,
                "task": selected, "submission_schema": SCHEMAS["submit"], "payload_schema": payload_schema,
                "budget": {"searches_remaining": run["max_searches"] - state["used_searches"],
                           "extra_tasks_remaining": run["max_extra_tasks"] - state["extra_tasks"],
                           "reported_cost_usd": state["cost_usd"], "reported_model_calls": state["model_calls"]},
                "context": {"run": run, "coverage": state["coverage"], "current_probability": state["probability"],
                            "artifacts": {id: Store.artifact(c, id) for id in state["artifact_ids"]},
                            "evidence": verify_refs(c, state["evidence_refs"], run["information_as_of"]),
                            "evidence_audits": {id: evidence_audit(Store.artifact(c, id, "packet")) for id in packet_ids},
                            "prior_record": state.get("prior_record"),
                            "research_plan": state.get("research_plan"),
                            "inquiry_answers": state.get("inquiry_answers", {}),
                            "model_map": state.get("model_map"), "model_challenge": state.get("model_challenge"),
                            "concern_resolutions": state.get("concern_resolutions", []),
                            "reference_class": state.get("reference_class"),
                            "model_inputs": state.get("model_inputs", {}),
                            "sensitivity": state.get("sensitivity"),
                            "previous_forecast": Store.artifact(c, run["previous_forecast_id"], "forecast") if run.get("previous_forecast_id") else None}}

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
            require(state["used_searches"] + usage["searches"] <= run["max_searches"],
                    f"Research budget exhausted: {state['used_searches']} searches recorded + {usage['searches']} newly reported exceeds {run['max_searches']}. "
                    "Count a reused search only once, but never reduce actual usage to pass validation. Stop additional searches and report the overrun to the user.", "budget_exhausted")
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

    def _bind_timeline(self, c, run, state, model_id):
        body = timeline.read(c, model_id)
        spec = body["specification"]
        require(spec["question"] == {"question_id": run["question_id"], "version": run["question_version"]},
                "Timeline targets a different question version.")
        require(time(spec["information_as_of"]) <= time(run["information_as_of"]), "Timeline cutoff is after run cutoff.")
        refs = evidence_refs(spec)
        verify_refs(c, refs, run["information_as_of"])
        if run.get("method_spec"):
            require(all(r["packet_id"] in run["packet_ids"] for r in refs), "Experiment requires registered frozen packets.")
        state["artifact_ids"] = list(dict.fromkeys(state["artifact_ids"] + [model_id] + list(body["input_manifest"])))
        state["evidence_refs"] = list({canonical(r): r for r in state["evidence_refs"] + refs}.values())
        state["timeline_model_id"] = model_id
        return spec

    def _apply(self, c, run, state, selected, p):
        kind = selected["kind"]
        structured = run.get("research_contract") in ("structured_v1", "structured_v2")
        v2 = run.get("research_contract") == "structured_v2"
        if kind == "intake":
            research_model.validate_intake(p)
            state["research_plan"] = p
            state["inquiry_answers"] = {}
            state["pending"][1:1] = [task("inquiry", inquiry=q) for q in p["unknowns"]]
            return {"research_actions": len(p["unknowns"])}
        if kind == "inquiry":
            q = selected["inquiry"]
            require(q["route"] != "unobservable" or p["status"] == "unresolved",
                    "An unobservable input remains unresolved; explain the retained uncertainty.")
            require(p["status"] != "answered" or q["route"] not in ("ask_user", "search") or p["evidence_refs"],
                    "Answered user questions and searches need a captured finding; use evidence add.")
            state["inquiry_answers"][q["id"]] = p
            require(len({r["domain"] for r in p.get("coverage", [])}) == len(p.get("coverage", [])),
                    "Inquiry coverage domains must be unique.")
            for coverage in p.get("coverage", []):
                require(coverage["domain"] in run["profile"]["domains"], "Inquiry coverage names an unknown profile domain.")
                require(run.get("workflow") != "timeline", "Timeline parameter research requires its own assessments.")
                require(p["status"] != "answered" or p["evidence_refs"], "Assessed coverage needs evidence.")
                state["coverage"][coverage["domain"]] = {
                    "task_id": selected["id"], "inquiry_id": q["id"], "interpretation": coverage["interpretation"],
                    "disposition": "assessed" if p["status"] == "answered" else "unknown",
                    "evidence_refs": p["evidence_refs"], "unknowns": [p["answer"]] if p["status"] == "unresolved" else [],
                    "sources_checked": [], "conflicts": []}
                state["pending"] = [t for t in state["pending"] if not
                                    (t["kind"] == "research" and t["domain"] == coverage["domain"])]
            return {"input_ids": q["input_ids"], "status": p["status"]}
        if kind == "timeline_structure":
            spec = self._bind_timeline(c, run, state, p["timeline_model_id"])
            # Each structure pass owns its revisions, including repeated experiment trials.
            spec = copy.deepcopy(spec)
            spec.pop("previous_model_id", None)
            spec.update(id="timeline_" + run["id"] + "_" + selected["id"], version=1,
                        derived_from_model_id=p["timeline_model_id"])
            model_id = timeline._add(c, spec)
            self._bind_timeline(c, run, state, model_id)
            state["pending"][1:1] = [task("timeline_research", parameter_id=param["id"], description=param["description"])
                                       for param in spec["parameters"]]
            return {"timeline_model_id": model_id, "gaps": timeline.gaps(spec)}
        if kind == "timeline_research":
            model_id = state["timeline_model_id"]
            spec = copy.deepcopy(timeline.read(c, model_id)["specification"])
            pid = selected["parameter_id"]
            supplied = {a["scenario_id"]: a["assessment"] for a in p["assessments"]}
            require(len(supplied) == len(p["assessments"]) and set(supplied) == {s["id"] for s in spec["scenarios"]},
                    "Parameter research must cover each scenario exactly once.")
            require(all(a["parameter_id"] == pid for a in supplied.values()), "Research targets the wrong parameter.")
            for scenario in spec["scenarios"]:
                scenario["assessments"] = [a for a in scenario["assessments"] if a["parameter_id"] != pid] + [supplied[scenario["id"]]]
            spec.update(version=spec["version"] + 1, previous_model_id=model_id)
            new_id = timeline._add(c, spec)
            self._bind_timeline(c, run, state, new_id)
            state["coverage"][pid] = {"task_id": selected["id"], **p}
            return {"timeline_model_id": new_id, "gaps": timeline.gaps(spec)}
        if kind == "prior":
            status = run.get("research_status", "unspecified")
            require(not structured or "research_status_at_estimate" in p,
                    "Declare research_status_at_estimate; run-start status does not describe later research.")
            declared = p.get("research_status_at_estimate", status)
            observed_research = bool(state["used_searches"] or evidence_refs(p) or
                                     any(a["status"] == "answered" for a in state.get("inquiry_answers", {}).values()))
            after = observed_research or status in ("in_progress", "completed") or declared in ("in_progress", "completed")
            state["prior_record"] = {"research_status_at_run_start": status, "research_status_at_estimate": declared,
                                     "recorded_research_before_estimate": observed_research, "recorded_at": now(),
                                     "timing": "after_research_started" if after else
                                     "declared_before_research" if declared == "not_started" else "unspecified",
                                     "qualification": "Research status is an agent declaration; external research history is not independently observable."}
            if p["method"] == "judgment":
                require("probability" in p and not any(k in p for k in ("cases", "reference_query")),
                        "Judgment prior needs a probability, without reference-class cases or a reference query.")
                value = p["probability"]
            else:
                if v2:
                    from .reference import query_cases
                    require("reference_query" in p, "Empirical priors require reference_query over registered, dated episodes.")
                    require(time(p["reference_query"]["known_as_of"]) <= time(run["information_as_of"]),
                            "Reference query exceeds run cutoff.")
                    result = query_cases(c, p["reference_query"])
                    require(all(r["episode_id"] and r["eligibility"] for r in result["selected_episodes"]),
                            "Empirical priors need episode_id and eligibility for every selected reference case.")
                    require(p.get("cases") == result["cases"] and p.get("selection_rule") == result["selection"]["selection_rule"],
                            "Prior cases and selection rule must match reference query; censored cases are not failures.")
                    require(not result["dependent_episodes"], "Select one case per episode before using an empirical prior.")
                    selected_refs = evidence_refs(result["selected_episodes"])
                    verify_refs(c, selected_refs, run["information_as_of"])
                    if run.get("method_spec"):
                        require(all(r["packet_id"] in run["packet_ids"] for r in selected_refs),
                                "Experiment reference cases require registered frozen packets.")
                    state["evidence_refs"] = list({canonical(r): r for r in state["evidence_refs"] + selected_refs}.values())
                    state["reference_class"] = result
                    state["artifact_ids"] = list(dict.fromkeys(state["artifact_ids"] +
                                                               [r["artifact_id"] for r in result["selected_episodes"]]))
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
            if run.get("workflow") != "timeline":
                require(set(run["profile"]["domains"]) <= set(state["coverage"]), "Required research coverage is incomplete.")
            method = p["method"]
            require(run.get("workflow") != "timeline" or method == "timeline_model", "Timeline workflows require a timeline_model assessment.")
            require(method == "timeline_model" or "timeline_model_id" not in p, "Timeline fields require timeline_model method.")
            if method != "scenario_mixture":
                require(not any(k in p for k in ("scenarios", "partition_justification")), "Scenario fields require scenario_mixture method.")
            if method != "odds_ledger":
                require("odds_ledger" not in p, "Ledger fields require odds_ledger method.")
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
            elif method == "timeline_model":
                require("timeline_model_id" in p and not any(k in p for k in ("components", "members", "weights", "nested_events_justification")),
                        "Timeline assessment needs a model ID without other calculation fields.")
                if run.get("workflow") == "timeline":
                    old = timeline.read(c, state["timeline_model_id"])["specification"]
                    final = timeline.read(c, p["timeline_model_id"])["specification"]
                    def researched_inputs(model):
                        return {"nodes": model["nodes"], "parameters": model["parameters"], "target": model["target"],
                                "information_as_of": model["information_as_of"], "deadline_rule": model["deadline_rule"],
                                "scenarios": [{"id": s["id"], "assessments": s["assessments"]} for s in model["scenarios"]]}
                    require(researched_inputs(old) == researched_inputs(final),
                            "Assessment may add weights but cannot replace researched inputs; use a new structure/research pass.")
                spec = self._bind_timeline(c, run, state, p["timeline_model_id"])
                if run.get("workflow") == "timeline":
                    require({param["id"] for param in spec["parameters"]} <= set(state["coverage"]), "Model has parameters without research tasks; submit structure first.")
                calculation = timeline.analyze(spec)
                require(calculation["probability"] is not None,
                        "Timeline has no point probability: resolve target outcomes and declare scenario weights before issuing.", "incomplete_model")
                value = calculation["probability"]
            elif method == "odds_ledger":
                require("odds_ledger" in p and not any(k in p for k in ("components", "members", "weights", "nested_events_justification")),
                        "Odds ledger needs its declaration without path or ensemble fields.")
                calculation = odds_calculate(p["odds_ledger"])
                anchor = p["odds_ledger"]["anchor"]
                if anchor.get("prior_artifact_id"):
                    prior_id = anchor["prior_artifact_id"]
                    require(prior_id in state["artifact_ids"], "Anchor must reference this run's prior task result.")
                    prior = Store.artifact(c, prior_id, "task_result")
                    require(prior["task"]["kind"] == "prior", "Anchor reference must be a prior task result.")
                    require((anchor["basis"] == "empirical") == (prior["payload"]["method"] == "reference_class"),
                            "Anchor basis differs from linked prior method.")
                    require(math.isclose(anchor["probability"], prior["calculation"]["probability"], rel_tol=1e-9, abs_tol=0),
                            "Anchor probability differs from linked prior.")
                value = calculation["probability"]
            elif method == "scenario_mixture":
                require(not any(k in p for k in ("components", "members", "weights", "nested_events_justification")), "Scenario mixture cannot include path or ensemble fields.")
                require("scenarios" in p and "partition_justification" in p, "Scenario mixture needs scenarios and partition justification.")
                calculation = scenario_calculate(research_model.mixture(p))
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
            if structured or p.get("parameter_support"):
                plan = state.get("research_plan")
                require(plan is not None, "Parameter support requires an intake research plan.")
                research_model.validate_support(p, plan, spec if method == "timeline_model" else None)
            if v2:
                state["model_map"] = research_model.validate_map(p, state["research_plan"], state.get("model_map"),
                                                               spec if method == "timeline_model" else None)
                state["model_challenge"] = None
                state["concern_resolutions"] = []
                state["scenario_ids"] = [s["id"] for s in (spec["scenarios"] if method == "timeline_model" else p.get("scenarios", []))]
                state["pending"].insert(1, task("model_challenge"))
            state["model_inputs"] = research_model.model_inputs(p, spec if method == "timeline_model" else None)
            state["parameter_support"] = p.get("parameter_support", [])
            state["sensitivity"] = calculation if method == "scenario_mixture" else (
                {"probability": value, "bounded_range": p["parameter_support"][0]["plausible_range"],
                 "limitations": ["Declared assumption range, not a confidence interval."]}
                if method == "judgment" and p.get("parameter_support") else None)
            require("probability" not in p or math.isclose(p["probability"], value), "Supplied probability differs from computed estimate.")
            state["probability"] = value
            state["probability_basis"] = method
            return {"probability": value, "method": method, "assumptions_are_agent_supplied": True,
                    **({"timeline_analysis": calculation} if method == "timeline_model" else {}),
                    **({"odds_analysis": calculation} if method == "odds_ledger" else {}),
                    **({"scenario_analysis": calculation} if method == "scenario_mixture" else {})}
        if kind == "model_challenge":
            research_model.validate_challenge(p, state)
            state["model_challenge"] = p
            return {"map_version": p["map_version"], "concerns": len(p["concerns"])}
        if kind == "review":
            if v2:
                require(state.get("model_challenge") is not None, "Complete the model challenge before review.")
                require(not any(k in p for k in ("parameter_support", "probability", "research_tasks")),
                        "Structured v2 review uses concern_resolutions; decision revise returns to assessment without an inline probability.")
                inquiries = research_model.followup_inquiries(p, state)
                state["concern_resolutions"] = p["concern_resolutions"]
                reassess = ([task("timeline_structure")] if run.get("workflow") == "timeline" else []) + [task("assessment"), task("review")]
                if inquiries:
                    require(state["extra_tasks"] + len(inquiries) <= run["max_extra_tasks"],
                            "Extra-task budget exhausted; explicitly defer concerns or retain assumptions.", "budget_exhausted")
                    state["extra_tasks"] += len(inquiries)
                    state["pending"][1:1] = [*[task("inquiry", inquiry=q) for q in inquiries], *reassess]
                elif p["decision"] == "revise":
                    state["pending"][1:1] = reassess
            require("parameter_support" not in p or p["decision"] == "revise",
                    "New parameter support on a review requires decision revise; retain preserves the existing inputs.")
            if structured:
                require("sensitivity_review" in p,
                        "Supply sensitivity_review addressing influential inputs, assumption sensitivity, and obtainable next evidence.")
                require(set(p["sensitivity_review"]["influential_inputs"]) <= set(state.get("model_inputs", {})),
                        "Sensitivity review must name actual model_input paths.")
            require({o["direction"] for o in p["objections"]} == {"too_high", "too_low"}, "Review must challenge the estimate in both directions.")
            if v2:
                return {"probability": state["probability"], "decision": p["decision"]}
            if p["decision"] == "research":
                more = p.get("research_tasks", [])
                require(bool(more), "A research decision requires new tasks.")
                require(state["extra_tasks"] + len(more) <= run["max_extra_tasks"], "Extra-task budget exhausted; retain or revise with limitations.", "budget_exhausted")
                state["extra_tasks"] += len(more)
                if run.get("workflow") == "timeline":
                    spec = timeline.read(c, state["timeline_model_id"])["specification"]
                    require(all(r["domain"] in {p["id"] for p in spec["parameters"]} or r["domain"] == "structure" for r in more),
                            "Timeline review research domains must name parameters or structure.")
                    new = ([task("timeline_structure")] if any(r["domain"] == "structure" for r in more) else
                           [task("timeline_research", parameter_id=r["domain"], instruction=r["purpose"]) for r in more])
                else:
                    new = [task("research", domain=r["domain"], instruction=r["purpose"]) for r in more]
                state["pending"][1:1] = [*new, task("assessment"), task("review")]
            elif p["decision"] == "revise":
                require("probability" in p, "Revised review needs a probability.")
                if structured:
                    research_model.validate_support({**p, "method": "judgment"}, state["research_plan"])
                    state["parameter_support"] = p["parameter_support"]
                    state["model_inputs"] = {"probability": p["probability"]}
                    state["sensitivity"] = {"probability": p["probability"],
                                            "bounded_range": p["parameter_support"][0]["plausible_range"],
                                            "limitations": ["Declared review judgment range, not a confidence interval."]}
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
                        "research_plan": state.get("research_plan"), "inquiry_answers": state.get("inquiry_answers", {}),
                        "model_map": state.get("model_map"), "model_challenge": state.get("model_challenge"),
                        "concern_resolutions": state.get("concern_resolutions", []), "reference_class": state.get("reference_class"),
                        "parameter_support": state.get("parameter_support", []), "sensitivity": state.get("sensitivity"),
                        "searches": state["used_searches"], "model_calls": state["model_calls"], **p}
            if state.get("timeline_model_id"):
                forecast["timeline_model_id"] = state["timeline_model_id"]
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
            verify_refs(c, spec["evidence_refs"], now(), context="current time for signal registration")
            refs = {canonical(r) for r in spec["evidence_refs"]}
            affected = [f["id"] for f in Store.all(c, "forecast") if f["question_id"] == spec.get("question_id") or refs.intersection(canonical(r) for r in f["evidence_refs"])]
            require(affected or spec.get("question_id"),
                    "These new findings do not identify an existing forecast. Supply question_id, or use revise --project FOLDER --evidence PACKET:RECORD.")
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
                if row["kind"] == "timeline_model":
                    timeline.read(c, row["id"])
                    timeline.analyze(body["specification"])
                if row["kind"] in ("forecast", "evaluation", "replay_evaluation", "experiment", "experiment_evaluation",
                                   "joint_session", "joint_finalization", "joint_import", "joint_aggregation",
                                   "joint_event", "session_study", "session_study_trial", "session_evaluation"):
                    if row["kind"] == "forecast":
                        require(digest(body["input_manifest"]) == body["manifest_sha256"], "Forecast manifest hash mismatch.")
                    for id, expected in body["input_manifest"].items():
                        require(digest(Store.artifact(c, id)) == expected, "Forecast input has changed.", "integrity_error")
                if row["kind"] == "experiment":
                    for q in body["questions"]:
                        require(digest(Store.question(c, q["question_id"], q["version"])) == q["sha256"],
                                "Experiment question has changed.", "integrity_error")
                if row["kind"] == "joint_session":
                    for q in body["questions"]:
                        pinned = {k: v for k, v in q.items() if k != "sha256"}
                        current = Store.question(c, q["specification"]["id"], q["version"])
                        require(digest(pinned) == q["sha256"] == digest(current),
                                "Session question has changed.", "integrity_error")
                count += 1
            return {"ok": True, "artifacts_checked": count, "sqlite_integrity": integrity}
