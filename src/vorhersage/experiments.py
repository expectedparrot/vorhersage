"""Frozen method specifications and resumable, packet-controlled experiments."""

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
    require(len(set(spec["research_domains"])) == len(spec["research_domains"]), "Duplicate research domains.")
    # This first runner compares procedures on identical packets, without search.
    require(spec["budget"]["max_searches"] == 0, "Frozen-packet methods require max_searches=0.")
    with store.connect(True) as c:
        id = _register(c, "method", spec)
        return {"method_id": id, **Store.artifact(c, id, "method")}


def add_experiment(store, spec):
    check(spec, "experiment")
    keys = [(q["question_id"], q["version"]) for q in spec["questions"]]
    require(len(set(keys)) == len(keys), "Duplicate questions in experiment.")
    require(len(set(spec["method_ids"])) == len(spec["method_ids"]), "Duplicate methods in experiment.")
    require(len(keys) * len(spec["method_ids"]) * spec["repetitions"] <= 10000, "Experiment exceeds 10000 trials.")
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
        for method_id in spec["method_ids"]:
            manifest[method_id] = digest(Store.artifact(c, method_id, "method"))
        for q in spec["questions"]:
            frozen = Store.question(c, q["question_id"], q["version"])
            require((frozen["specification"]["kind"] == "simulation") == (spec["mode"] == "simulation"), "Question kind and experiment mode disagree.")
            if spec["mode"] == "prospective":
                require(time(spec["forecast_cutoff"]) <= time(frozen["specification"]["event_deadline"]), "Forecast cutoff must not follow a prospective event deadline.")
                require(not Workflow._resolutions(c, q["question_id"], q["version"]), "Prospective experiment question is already resolved.")
            questions.append({**q, "snapshot": frozen, "sha256": digest(frozen)})
            require(len(set(q["packet_ids"])) == len(q["packet_ids"]), "Duplicate packets for question.")
            for packet_id in q["packet_ids"]:
                packet = Store.artifact(c, packet_id, "packet")
                require(time(packet["information_as_of"]) <= time(spec["information_as_of"]), "Packet cutoff is later than experiment information cutoff.")
                manifest[packet_id] = digest(packet)
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
        for q in spec["questions"]:
            for method_id in spec["method_ids"]:
                for repetition in range(1, spec["repetitions"] + 1):
                    key = [experiment_id, q["question_id"], q["version"], method_id, repetition]
                    plan.append({"trial_id": "trial_" + digest(key)[:24], "question": q,
                                 "method_spec_id": method_id, "repetition": repetition,
                                 "order_key": digest([spec["order_seed"], q, method_id, repetition])})
        trials = []
        for position, item in enumerate(sorted(plan, key=lambda t: t["order_key"])):
            q, method_id = item["question"], item["method_spec_id"]
            method = Store.artifact(c, method_id, "method")["specification"]
            forecaster = f"{experiment_id}:{method_id}:r{item['repetition']}"
            protocol = {"experiment_id": experiment_id, "method_spec_id": method_id, "method_spec": method,
                        "trial_id": item["trial_id"], "repetition": item["repetition"],
                        "packet_ids": q["packet_ids"], "forecast_cutoff": spec["forecast_cutoff"]}
            result = w._start(c, {"question_id": q["question_id"], "question_version": q["version"],
                                 "forecaster": forecaster, "method": method_id, "mode": spec["mode"],
                                 "information_as_of": spec["information_as_of"], "cutoff_policy": "fixed",
                                 "research_status": "unspecified", "max_searches": method["budget"]["max_searches"],
                                 "max_extra_tasks": method["budget"]["max_extra_tasks"]}, protocol)
            trial = {"experiment_id": experiment_id, "trial_id": item["trial_id"], "run_id": result["run_id"],
                     "question_id": q["question_id"], "question_version": q["version"], "method_spec_id": method_id,
                     "repetition": item["repetition"], "forecaster": forecaster, "position": position}
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
    return {"experiment_id": experiment_id, "expected_trials": len(spec["questions"]) * len(spec["method_ids"]) * spec["repetitions"],
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
                    answer = invoke(method["worker"]["command"], {"protocol": "vorhersage.experiment.agent.v1",
                                    "action": "submit", "next": step, "worker_config": method["worker"]["config"]},
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
        methods = {id: Store.artifact(c, id, "method")["specification"] for id in spec["method_ids"]}
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
    by_forecaster = {t["forecaster"]: t["method_spec_id"] for t in trials}
    method_scores = {}
    for method_id in spec["method_ids"]:
        per_question = []
        for (qid, version), rows in sorted(common.items()):
            arm = [r for r in rows if by_forecaster[r["forecaster"]] == method_id]
            per_question.append({"question_id": qid, "version": version,
                                 "mean_brier": average([r["brier"] for r in arm]), "repetitions": len(arm)})
        own = [states[t["run_id"]] for t in trials if t["method_spec_id"] == method_id]
        method_scores[method_id] = {"method_name": methods[method_id]["id"], "method_version": methods[method_id]["version"],
                                    "registered_budget": methods[method_id]["budget"],
                                    "issued_trials": sum(bool(s["forecast_id"]) for s in own),
                                    "all_trials_reported_cost_usd": sum(s["cost_usd"] for s in own),
                                    "all_trials_reported_model_calls": sum(s["model_calls"] for s in own),
                                    "matched_questions": len(per_question), "by_question": per_question,
                                    "matched_brier": average([r["mean_brier"] for r in per_question])}
    body = {"experiment_id": experiment_id, "evaluation_id": report["evaluation_id"],
            "registered_forecast_cutoff": spec["forecast_cutoff"], "effective_cutoff": cutoff,
            "method_scores": method_scores, "created_at": now(),
            "limitations": ["Methods share the cohort complete across every method and repetition; inspect exclusions in the evaluation.",
                            "Brier losses are averaged across repetitions within question, then equally across questions. No significance claim.",
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
