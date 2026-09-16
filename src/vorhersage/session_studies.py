"""Registered whole-instrument arms and repetitions with isolated sessions."""

import copy

from . import sessions
from .common import digest, now, require
from .schemas import check
from .session_runtime import execute, audit_state
from .store import Store


def add(store, spec):
    check(spec, "session_study")
    sessions.unique([a["id"] for a in spec["arms"]], "study arms")
    require(len(spec["arms"]) * spec["repetitions"] <= 1000, "Study exceeds 1000 sessions.")
    template = spec["session_template"]
    require(template["provenance"]["kind"] == "native", "Study trials must be native sessions.")
    expected_policy = "fixed" if spec["evidence_policy"] == "frozen" else "live"
    require(all(a["execution"]["evidence_policy"] == expected_policy for a in spec["arms"]), "Arm evidence policy differs from study.")
    with store.connect(True) as c:
        for old in Store.all(c, "session_study"):
            if (old["specification"]["id"], old["specification"]["version"]) == (spec["id"], spec["version"]):
                require(old["specification"] == spec, "Study version is frozen.")
                return {"study_id": old["id"]}
        manifest = {i: digest(Store.artifact(c, i)) for field in ("packet_ids", "condition_ids", "relation_ids") for i in template[field]}
        questions = [Store.question(c, q["question_id"], q["version"]) for q in template["questions"]]
        id = "session_study_" + digest(spec)[:24]
        Store.put(c, "session_study", {"specification": spec, "registered_at": now(), "questions": questions,
                  "input_manifest": manifest}, id=id)
        # Session creation validates the complete contract. Roll back the study if any arm is invalid.
        plan = [(a, r) for a in spec["arms"] for r in range(1, spec["repetitions"] + 1)]
        for position, (arm, repetition) in enumerate(sorted(plan, key=lambda x: digest([spec["order_seed"], x[0]["id"], x[1]]))):
            trial_spec = copy.deepcopy(template)
            trial_spec.update(id=f"{id}:{arm['id']}:{repetition}", wave=id, forecaster=arm["id"],
                              repetition=repetition, protocol=f"{template['protocol']}:{arm['id']}",
                              configuration=arm["configuration"], execution=arm["execution"])
            session_id = sessions._create(c, trial_spec)
            Store.put(c, "session_study_trial", {"study_id": id, "session_id": session_id, "arm": arm["id"],
                      "repetition": repetition, "position": position,
                      "input_manifest": {session_id: digest(Store.artifact(c, session_id))}},
                      id="session_trial_" + digest([id, arm["id"], repetition])[:24])
    return {"study_id": id, "sessions": len(plan)}


def status(store, study_id):
    with store.connect() as c:
        study = Store.artifact(c, study_id, "session_study")
        trials = sorted([t for t in Store.all(c, "session_study_trial") if t["study_id"] == study_id], key=lambda t: t["position"])
        results = []
        for trial in trials:
            state = sessions._status(c, trial["session_id"])
            results.append({**trial, "disposition": state["disposition"], "revision": state["revision"],
                            "cells": len(state["cells"]), "expected_cells": state["expected_cells"],
                            "usage": state["usage"], "unknown_usage_attempts": state["unknown_usage_attempts"],
                            "protocol_audit": audit_state(state)})
        runs = [Store.artifact(c, r["id"]) for r in c.execute(
            "SELECT id FROM artifacts WHERE kind='session_study_execution' ORDER BY rowid")]
        runs = [r for r in runs if r["study_id"] == study_id]
    return {"study_id": study_id, "specification": study["specification"], "trials": results,
            "complete": all(t["disposition"] == "finalized" for t in results),
            "next_position": runs[-1]["next_position"] if runs else 0,
            "usage": {k: sum(t["usage"][k] for t in results) for k in ("searches", "model_calls", "cost_usd")},
            "limitations": ["A repetition is a whole session; its cells are dependent observations.",
                            "Frozen packets constrain accepted evidence; trusted workers require external isolation to prevent outside access.",
                            "Independent live research arms may observe different evidence and do not isolate transport effects."]}


def run(store, study_id, max_steps=20):
    from .monitoring import fcntl
    from .common import Error
    require(type(max_steps) is int and 1 <= max_steps <= 1000, "max_steps must be 1..1000.")
    require(fcntl is not None, "Study execution requires POSIX locking.")
    with (store.path.parent / (digest(study_id)[:24] + ".lock")).open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Error("study_busy", "Study already has a running controller.") from exc
        progress = status(store, study_id)
        trials = progress["trials"]
        cursor = progress["next_position"]
        for _ in range(max_steps):
            trial = trials[cursor % len(trials)]
            cursor = (cursor + 1) % len(trials)
            try:
                result = execute(store, trial["session_id"], 1)
                outcome = {"disposition": result["disposition"]}
            except (Error, OSError) as exc:
                outcome = {"error": getattr(exc, "code", type(exc).__name__)}
            with store.connect(True) as c:
                Store.put(c, "session_study_execution", {"study_id": study_id, "session_id": trial["session_id"],
                          "next_position": cursor, "outcome": outcome, "recorded_at": now()})
        return status(store, study_id)
