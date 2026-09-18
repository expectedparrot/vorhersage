"""Versioned method/model/data arms and resumable experiments on frozen evidence."""

import copy
import subprocess

from .common import Error, digest, now, require, time
from .evaluation import average, evaluate
from .monitoring import fcntl, invoke
from .schemas import check
from .store import Store
from .workflow import Workflow


def _register(c, kind, spec, extra=None):
    existing = [x for x in Store.all(c, kind) if x["specification"]["id"] == spec["id"]
                and x["specification"]["version"] == spec["version"]]
    if existing:
        require(digest(existing[0]["specification"]) == digest(spec), "This version is frozen; increment version to change it.", "version_conflict")
        return existing[0]["id"]
    return Store.put(c, kind, {"specification": spec, "registered_at": now(), **(extra or {})})


def add_method(store, spec):
    check(spec, "method")
    stages = spec.get("stages")
    if stages is not None:
        order = ["prior", "drivers", "research", "assessment", "review", "issue"]
        require(stages == [s for s in order if s in stages] and "assessment" in stages and "issue" in stages,
                "Stages must be an ordered subset of prior, drivers, research, assessment, review, issue, including assessment and issue.")
        require(spec["assessment_method"] != "timeline_model" and not spec.get("research_contract"),
                "Custom stages are for standard methods; timeline and structured contracts retain their required stages.")
        require((spec["prior_method"] == "none") == ("prior" not in stages),
                "Use prior_method=none exactly when the prior stage is omitted.")
        require("research" in stages or not spec["research_domains"], "Omitting research requires empty research_domains.")
    else:
        require((spec["prior_method"] == "none") == (spec["assessment_method"] == "timeline_model"),
                "Timeline methods use prior_method=none; other methods require a prior.")
    require(len(set(spec["research_domains"])) == len(spec["research_domains"]), "Duplicate research domains.")
    # Each arm uses registered evidence; live research is a separate experiment design.
    require(spec["budget"]["max_searches"] == 0, "Frozen-packet methods require max_searches=0.")
    with store.connect(True) as c:
        id = _register(c, "method", spec)
        return {"method_id": id, **Store.artifact(c, id, "method")}


def add_arm(store, spec):
    """Freeze a reusable method/model/data combination independently of its experiment."""
    check(spec, "arm")
    questions = spec["data"]["questions"]
    keys = [(q["question_id"], q["version"]) for q in questions]
    require(len(keys) == len(set(keys)), "Duplicate questions in arm data.")
    with store.connect(True) as c:
        manifest = {spec["method_id"]: digest(Store.artifact(c, spec["method_id"], "method"))}
        snapshots = []
        for q in questions:
            snapshots.append({"question_id": q["question_id"], "version": q["version"],
                              "sha256": digest(Store.question(c, q["question_id"], q["version"]))})
            require(len(q["packet_ids"]) == len(set(q["packet_ids"])), "Duplicate packets in arm data.")
            for packet_id in q["packet_ids"]:
                manifest[packet_id] = digest(Store.artifact(c, packet_id, "packet"))
        id = _register(c, "arm", spec, {"input_manifest": manifest, "questions": snapshots})
        return {"arm_id": id, **Store.artifact(c, id, "arm")}


def _arm_ids(spec):
    return spec.get("arm_ids", spec.get("method_ids", []))


def _arms(c, spec):
    if "arm_ids" in spec:
        return [{"arm_id": id, **Store.artifact(c, id, "arm")["specification"]} for id in spec["arm_ids"]]
    return [{"arm_id": id, "method_id": id, "id": Store.artifact(c, id, "method")["specification"]["id"],
             "version": Store.artifact(c, id, "method")["specification"]["version"],
             "model": None, "data": {"label": "shared frozen packets", "questions": spec["questions"]}}
            for id in spec["method_ids"]]


def add_experiment(store, spec):
    check(spec, "experiment")
    require(("arm_ids" in spec) != ("method_ids" in spec), "Supply exactly one of arm_ids or legacy method_ids.")
    keys = [(q["question_id"], q["version"]) for q in spec["questions"]]
    require(len(set(keys)) == len(keys), "Duplicate questions in experiment.")
    require(len(set(_arm_ids(spec))) == len(_arm_ids(spec)),
            "Duplicate arms in experiment." if "arm_ids" in spec else "Duplicate methods in experiment.")
    require(len(keys) * len(_arm_ids(spec)) * spec["repetitions"] <= 10000, "Experiment exceeds 10000 trials.")
    require(all(("packet_ids" not in q) if "arm_ids" in spec else ("packet_ids" in q) for q in spec["questions"]),
            "Arm experiments take packets from each arm's data; legacy method experiments require question packet_ids.")
    require(time(spec["information_as_of"]) <= time(now()), "Information cutoff cannot be in the future.")
    require(time(spec["information_as_of"]) <= time(spec["forecast_cutoff"]), "Forecast cutoff precedes information cutoff.")
    with store.connect(True) as c:
        # Exact retries work even after the experiment's cutoff has passed.
        for old in Store.all(c, "experiment"):
            if (old["specification"]["id"], old["specification"]["version"]) == (spec["id"], spec["version"]):
                require(digest(old["specification"]) == digest(spec), "This version is frozen; increment version to change it.", "version_conflict")
                return {"experiment_id": old["id"], **Store.artifact(c, old["id"], "experiment")}
        require(time(now()) < time(spec["forecast_cutoff"]), "Experiment forecast cutoff has passed.")
        manifest, questions = {}, []
        for arm in _arms(c, spec):
            method_id = arm["method_id"]
            manifest[method_id] = digest(Store.artifact(c, method_id, "method"))
            if "arm_ids" in spec:
                body = Store.artifact(c, arm["arm_id"], "arm")
                manifest[arm["arm_id"]] = digest(body)
                for input_id, expected in body["input_manifest"].items():
                    require(digest(Store.artifact(c, input_id)) == expected, "Arm input integrity check failed.", "integrity_error")
                for q in body["questions"]:
                    require(digest(Store.question(c, q["question_id"], q["version"])) == q["sha256"], "Arm question integrity check failed.", "integrity_error")
            require({(q["question_id"], q["version"]) for q in arm["data"]["questions"]} == set(keys),
                    "Every arm's data must cover exactly the experiment question versions.")
            for q in arm["data"]["questions"]:
                require(len(set(q["packet_ids"])) == len(q["packet_ids"]), "Duplicate packets for question.")
                for packet_id in q["packet_ids"]:
                    packet = Store.artifact(c, packet_id, "packet")
                    require(time(packet["information_as_of"]) <= time(spec["information_as_of"]), "Packet cutoff is later than experiment information cutoff.")
                    manifest[packet_id] = digest(packet)
        for q in spec["questions"]:
            frozen = Store.question(c, q["question_id"], q["version"])
            require((frozen["specification"]["kind"] == "simulation") == (spec["mode"] == "simulation"), "Question kind and experiment mode disagree.")
            if spec["mode"] == "prospective":
                require(time(spec["forecast_cutoff"]) <= time(frozen["specification"]["event_deadline"]), "Forecast cutoff must not follow a prospective event deadline.")
                require(not Workflow._resolutions(c, q["question_id"], q["version"]), "Prospective experiment question is already resolved.")
            questions.append({**q, "snapshot": frozen, "sha256": digest(frozen)})
        id = _register(c, "experiment", spec, {"questions": questions, "input_manifest": manifest})
        return {"experiment_id": id, **Store.artifact(c, id, "experiment")}


def start(project, experiment_id):
    """Create the complete trial matrix atomically, or return its existing runs."""
    w = Workflow(project)
    with w.store.connect(True) as c:
        experiment = Store.artifact(c, experiment_id, "experiment")
        spec = experiment["specification"]
        existing = [t for t in Store.all(c, "experiment_trial") if t["experiment_id"] == experiment_id]
        if existing:
            return {"experiment_id": experiment_id, "trials": existing, "duplicate": True}
        require(time(now()) < time(spec["forecast_cutoff"]), "Experiment forecast cutoff has passed.")
        for id, expected in experiment["input_manifest"].items():
            require(digest(Store.artifact(c, id)) == expected, "Experiment input integrity check failed.", "integrity_error")
        for q in experiment["questions"]:
            require(digest(Store.question(c, q["question_id"], q["version"])) == q["sha256"],
                    "Experiment question integrity check failed.", "integrity_error")
        plan = []
        arms = _arms(c, spec)
        for q in spec["questions"]:
            for arm in arms:
                arm_id, method_id = arm["arm_id"], arm["method_id"]
                data = next(row for row in arm["data"]["questions"] if (row["question_id"], row["version"]) == (q["question_id"], q["version"]))
                for repetition in range(1, spec["repetitions"] + 1):
                    key = [experiment_id, q["question_id"], q["version"], arm_id, repetition]
                    plan.append({"trial_id": "trial_" + digest(key)[:24], "question": data, "arm": arm,
                                 "method_spec_id": method_id, "repetition": repetition,
                                 "order_key": digest([spec["order_seed"], q, arm_id, repetition])})
        trials = []
        for position, item in enumerate(sorted(plan, key=lambda t: t["order_key"])):
            q, method_id = item["question"], item["method_spec_id"]
            method = Store.artifact(c, method_id, "method")["specification"]
            arm = item["arm"]
            forecaster = f"{experiment_id}:{arm['arm_id']}:r{item['repetition']}"
            protocol = {"experiment_id": experiment_id, "method_spec_id": method_id, "method_spec": method,
                        "trial_id": item["trial_id"], "repetition": item["repetition"],
                        "packet_ids": q["packet_ids"], "forecast_cutoff": spec["forecast_cutoff"]}
            arm_fields = {"arm_id": arm["arm_id"], "model_spec": arm["model"], "data_label": arm["data"]["label"]} if "arm_ids" in spec else {}
            protocol.update(arm_fields)
            result = w._start(c, {"question_id": q["question_id"], "question_version": q["version"],
                                 "forecaster": forecaster, "method": method_id, "mode": spec["mode"],
                                 "information_as_of": spec["information_as_of"], "cutoff_policy": "fixed",
                                 "research_status": "unspecified", "max_searches": method["budget"]["max_searches"],
                                 "max_extra_tasks": method["budget"]["max_extra_tasks"],
                                 **({"research_contract": method["research_contract"]} if "research_contract" in method else {})}, protocol)
            trial = {"experiment_id": experiment_id, "trial_id": item["trial_id"], "run_id": result["run_id"],
                     "question_id": q["question_id"], "question_version": q["version"], "method_spec_id": method_id,
                     "repetition": item["repetition"], "forecaster": forecaster, "position": position, **arm_fields}
            Store.put(c, "experiment_trial", trial, id=item["trial_id"])
            trials.append(trial)
        return {"experiment_id": experiment_id, "trials": trials, "duplicate": False}


def status(project, experiment_id):
    w = Workflow(project)
    with w.store.connect() as c:
        experiment = Store.artifact(c, experiment_id, "experiment")
        trials = [t for t in Store.all(c, "experiment_trial") if t["experiment_id"] == experiment_id]
        results = []
        for trial in sorted(trials, key=lambda t: t["position"]):
            run, state, revision = Store.run(c, trial["run_id"])
            blocked = bool(state["pending"]) and (time(now()) >= time(run["forecast_cutoff"]) or
                      (run["mode"] == "prospective" and bool(Workflow._resolutions(c, run["question_id"], run["question_version"]))))
            results.append({**trial, "revision": revision, "forecast_id": state["forecast_id"],
                            "disposition": "issued" if state["forecast_id"] else ("blocked" if blocked else "pending"),
                            "pending_tasks": len(state["pending"]), "cost_usd": state["cost_usd"],
                            "model_calls": state["model_calls"]})
        executions = [e for e in Store.all(c, "experiment_execution") if e["experiment_id"] == experiment_id]
    spec = experiment["specification"]
    return {"experiment_id": experiment_id, "expected_trials": len(spec["questions"]) * len(_arm_ids(spec)) * spec["repetitions"],
            "started_trials": len(results), "issued_trials": sum(bool(t["forecast_id"]) for t in results),
            "trials": results, "latest_execution": executions[-1] if executions else None}


def execute(project, experiment_id, max_tasks=20):
    """Bounded execution; accepted steps persist, failed/deferred trials do not stop peers."""
    require(type(max_tasks) is int and 1 <= max_tasks <= 10000, "max_tasks must be between 1 and 10000.")
    require(fcntl is not None, "Experiment execution requires POSIX file locking (macOS/Linux).")
    w = Workflow(project)
    require(w.store.path.exists(), "Initialize the project before running experiments.")
    with (w.store.path.parent / "experiment.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Error("experiment_busy", "Another experiment worker is active in this project.")
        start(project, experiment_id)
        attempts, events = 0, []
        progress = status(project, experiment_id)
        trial_count = len(progress["trials"])
        next_position = (progress["latest_execution"] or {}).get("next_position", 0)
        # Resume a round-robin cursor; low-budget retries must not keep selecting
        # the same failing/deferred trials while other arms never get a turn.
        trials = sorted(progress["trials"], key=lambda t: (t["position"] - next_position) % trial_count)
        while trials and attempts < max_tasks:
            remaining = []
            for trial in trials:
                if attempts >= max_tasks:
                    break
                step = w.next(trial["run_id"])
                if step["disposition"] != "actionable":
                    continue
                method = step["context"]["run"]["method_spec"]
                budget = method["budget"]
                if step["budget"]["reported_model_calls"] >= budget["max_model_calls"] or (
                        budget["max_cost_usd"] > 0 and step["budget"]["reported_cost_usd"] >= budget["max_cost_usd"]):
                    events.append({"trial_id": trial["trial_id"], "error": "budget_exhausted"})
                    continue
                attempts += 1
                next_position = (trial["position"] + 1) % trial_count
                try:
                    config = copy.deepcopy(method["worker"]["config"])
                    model = step["context"]["run"].get("model_spec")
                    if model is not None:
                        config.update(provider=model["provider"], model=model["name"], model_parameters=model["parameters"])
                    answer = invoke(method["worker"]["command"], {"protocol": "vorhersage.experiment.agent.v1",
                                    "action": "submit", "next": step, "worker_config": config},
                                    method["worker"]["timeout_seconds"])
                    if set(answer) == {"defer"}:
                        require(isinstance(answer["defer"], str) and answer["defer"].strip(), "defer must explain why.")
                        events.append({"trial_id": trial["trial_id"], "deferred": answer["defer"]})
                        continue
                    require(set(answer) == {"payload", "usage"}, "Worker must return payload and usage, or defer.")
                    w.submit(trial["run_id"], {"task_id": step["task"]["id"], "expected_revision": step["revision"],
                                             "idempotency_key": "experiment-" + step["task"]["id"], **answer})
                    remaining.append(trial)
                except (Error, OSError, ValueError, subprocess.SubprocessError) as exc:
                    # Do not retain worker stdout/stderr, which may contain credentials.
                    events.append({"trial_id": trial["trial_id"], "error": getattr(exc, "code", type(exc).__name__)})
            trials = remaining
        execution = {"experiment_id": experiment_id, "attempts": attempts, "events": events,
                     "next_position": next_position, "recorded_at": now()}
        with w.store.connect(True) as c:
            execution_id = Store.put(c, "experiment_execution", execution)
        return {"execution_id": execution_id, **execution, "status": status(project, experiment_id)}


def score(project, experiment_id, resolution_as_of):
    store = Store(project)
    with store.connect() as c:
        experiment = Store.artifact(c, experiment_id, "experiment")
        spec = experiment["specification"]
        trials = [t for t in Store.all(c, "experiment_trial") if t["experiment_id"] == experiment_id]
        require(trials, "Start the experiment before evaluating it.")
        states = {t["run_id"]: Store.run(c, t["run_id"])[1] for t in trials}
        forecast_ids = [states[t["run_id"]]["forecast_id"] for t in trials]
        arms = _arms(c, spec)
        methods = {a["method_id"]: Store.artifact(c, a["method_id"], "method")["specification"] for a in arms}
        forecasts = {id: Store.artifact(c, id, "forecast") for id in forecast_ids if id}
    # An interim report has an explicit effective cutoff; the registered deadline remains frozen.
    cutoff = min((now(), spec["forecast_cutoff"]), key=time)
    policy = {"question_versions": [{"question_id": q["question_id"], "version": q["version"]} for q in spec["questions"]],
              "forecasters": sorted({t["forecaster"] for t in trials}), "cutoff": cutoff,
              "resolution_as_of": resolution_as_of, "mode": spec["mode"]}
    report = evaluate(store, policy, forecast_ids=[id for id in forecast_ids if id], input_ids=[experiment_id])
    common = {}
    for row in report["selected"]:
        key = (row["question_id"], row["question_version"])
        common.setdefault(key, []).append(row)
    common = {k: rows for k, rows in common.items() if len(rows) == len(policy["forecasters"])}
    by_forecaster = {t["forecaster"]: t.get("arm_id", t["method_spec_id"]) for t in trials}
    arm_scores = {}
    for arm in arms:
        arm_id, method_id = arm["arm_id"], arm["method_id"]
        per_question = []
        for (qid, version), rows in sorted(common.items()):
            selected = [r for r in rows if by_forecaster[r["forecaster"]] == arm_id]
            before = [forecasts[r["forecast_id"]].get("assessment_probability") for r in selected]
            assessment_brier = average([(p - r["outcome"]) ** 2 for p, r in zip(before, selected)]) if all(p is not None for p in before) else None
            per_question.append({"question_id": qid, "version": version, "event_group": selected[0]["event_group"],
                                 "mean_brier": average([r["brier"] for r in selected]), "repetitions": len(selected),
                                 "assessment_brier": assessment_brier})
        own = [states[t["run_id"]] for t in trials if t.get("arm_id", t["method_spec_id"]) == arm_id]
        arm_scores[arm_id] = {"arm_name": arm["id"], "arm_version": arm["version"], "method_id": method_id,
                                    "method_name": methods[method_id]["id"], "method_version": methods[method_id]["version"],
                                    "model": arm["model"], "data_label": arm["data"]["label"],
                                    "registered_budget": methods[method_id]["budget"],
                                    "expected_trials": len(spec["questions"]) * spec["repetitions"],
                                    "issued_trials": sum(bool(s["forecast_id"]) for s in own),
                                    "all_trials_reported_cost_usd": sum(s["cost_usd"] for s in own),
                                    "all_trials_reported_model_calls": sum(s["model_calls"] for s in own),
                                    "matched_questions": len(per_question), "by_question": per_question,
                                    "matched_brier": average([r["mean_brier"] for r in per_question]),
                                    "matched_assessment_brier": average([r["assessment_brier"] for r in per_question])
                                    if all(r["assessment_brier"] is not None for r in per_question) else None}
    comparisons = []
    for index, left in enumerate(arms):
        for right in arms[index + 1:]:
            lscore, rscore = arm_scores[left["arm_id"]], arm_scores[right["arm_id"]]
            differences = [{"question_id": l["question_id"], "version": l["version"], "event_group": l["event_group"],
                            "brier_difference": l["mean_brier"] - r["mean_brier"]}
                           for l, r in zip(lscore["by_question"], rscore["by_question"])]
            dimensions = [name for name, same in (
                ("method", left["method_id"] == right["method_id"]),
                ("model", digest(left["model"]) == digest(right["model"])),
                ("data", {(q["question_id"], q["version"]): sorted(q["packet_ids"]) for q in left["data"]["questions"]} ==
                         {(q["question_id"], q["version"]): sorted(q["packet_ids"]) for q in right["data"]["questions"]})) if not same]
            comparisons.append({"left": left["arm_id"], "right": right["arm_id"], "changed_dimensions": dimensions,
                                "n": len(differences), "event_groups": len({r["event_group"] for r in differences}),
                                "mean_brier_difference": average([r["brier_difference"] for r in differences]),
                                "by_question": differences, "interpretation": "Negative favors left; no significance or causal attribution claim."})
    body = {"experiment_id": experiment_id, "evaluation_id": report["evaluation_id"],
            "registered_forecast_cutoff": spec["forecast_cutoff"], "effective_cutoff": cutoff,
            "arm_scores": arm_scores, "comparisons": comparisons, "created_at": now(),
            **({"method_scores": arm_scores} if "method_ids" in spec else {}),
            "limitations": ["Arms share the cohort complete across every arm and repetition; inspect exclusions in the evaluation.",
                            "Brier losses are averaged across repetitions within question, then equally across questions. No significance claim.",
                            "Changing several arm dimensions compares combined configurations; it does not isolate any one component's effect.",
                            "Assessment scores use the last assessment before issuance. Review can commission further assessments; this is not a randomized estimate of review's effect.",
                            "Model settings are instructions to trusted workers, not independent attestation of the model actually called.",
                            "Workers are trusted processes; frozen packet references do not certify absence of external access or outcome knowledge.",
                            "Usage caps rely on reported usage; rejected or interrupted calls can incur unrecorded costs."]}
    with store.connect(True) as c:
        # Costs include unfinished trials, so freeze their accepted task results too.
        inputs = {experiment_id, report["evaluation_id"], *[t["trial_id"] for t in trials]}
        inputs.update(id for state in states.values() for id in state["artifact_ids"])
        inputs.update(id for id in forecast_ids if id)
        body["input_manifest"] = {id: digest(Store.artifact(c, id)) for id in sorted(inputs)}
        id = Store.put(c, "experiment_evaluation", body)
    return {"experiment_evaluation_id": id, **body, "evaluation": report}
