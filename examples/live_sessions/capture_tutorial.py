"""Capture one complete CLI run for the HTML tutorial. No paid or network calls."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def capture(destination):
    destination.mkdir(parents=True, exist_ok=False)
    kit = destination / "session-tutorial"
    shutil.copytree(ROOT / "docs/assets/session-tutorial", kit)
    project = destination / "forecast-study"
    records = []
    started_at = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()

    def command(name, args, cli=True, save=None):
        argv = [sys.executable, "-m", "vorhersage", "--project", str(project), *args] if cli else [sys.executable, str(kit / "prepare.py"), *args, str(project)]
        before = time.perf_counter()
        result = subprocess.run(argv, capture_output=True, text=True, check=True, cwd=destination)
        output = json.loads(result.stdout)
        if cli:
            assert output["status"] == "ok", output
        if save:
            (project / save).write_text(result.stdout)
        records.append({"name": name, "argv": argv, "elapsed_seconds": round(time.perf_counter()-before, 4), "output": output})
        return output["data"] if cli else output

    command("prepare-inputs", ["inputs"], cli=False)
    command("init", ["init", "--name", "Forecasting tutorial"])
    command("question", ["question", "add", "--from", str(project / "question.json")])
    command("condition", ["condition", "add", "--from", str(project / "condition.json")], save="condition-result.json")
    command("prepare-study", ["study"], cli=False)
    registered = command("register", ["session-study", "add", "--from", str(project / "study.json")], save="study-result.json")
    study_id = registered["study_id"]
    partial = command("first-run", ["session-study", "run", study_id, "--max-steps", "5"])
    status = command("status", ["session-study", "status", study_id])
    assert not partial["complete"]
    first = status["trials"][0]["session_id"]
    waiting = command("waiting", ["session", "show", first])
    assert waiting["disposition"] == "waiting"
    completed = command("resume", ["session-study", "run", study_id, "--max-steps", "20"])
    assert completed["complete"]
    audit = command("audit", ["session", "audit", first])
    command("report", ["session-study", "report", study_id, "--output", str(project / "comparison.html")])
    command("prepare-resolution", ["resolution"], cli=False)
    command("resolve", ["resolve", "--from", str(project / "resolution.json")])
    command("prepare-evaluation", ["evaluation"], cli=False)
    evaluation = command("evaluate", ["session", "evaluate", "--from", str(project / "evaluation.json")])
    doctor = command("doctor", ["doctor"])
    elapsed = round(time.perf_counter()-start, 3)
    public = ROOT / "docs/assets/session-run"
    public.mkdir(exist_ok=True)
    for record in records:
        (public / (record["name"] + ".json")).write_text(json.dumps(record, indent=2) + "\n")
    (public / "inputs").mkdir(exist_ok=True)
    for name in ("question.json", "study.json", "resolution.json", "evaluation.json"):
        shutil.copyfile(project / name, public / "inputs" / name)
    shutil.copyfile(project / "comparison.html", public / "comparison.html")
    from vorhersage import sessions
    from vorhersage.store import Store
    state = sessions.status(Store(project), first)
    usage = completed["usage"]
    assert usage == {"searches": 4, "model_calls": 8, "cost_usd": .1}
    assert [a["mean_session_brier"] for a in evaluation["arms"]] == [.5625, .0625]
    summary = {"started_at": started_at, "elapsed_seconds": elapsed, "actual_provider_calls": 0,
               "actual_provider_cost_usd": 0, "synthetic_reported_usage": usage,
               "study_id": study_id, "first_session_id": first, "arm_scores": evaluation["arms"], "doctor": doctor,
               "trace": [{"revision": e["revision"], "kind": e["kind"], "payload": e["payload"] if e["kind"] != "attempt_start"
                          else {k: v for k, v in e["payload"].items() if k != "request"}} for e in state["events"]],
               "finalized_at": state["finalization"]["finalized_at"],
               "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted((ROOT / "src/vorhersage").glob("*.py"))},
               "fixture_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(kit.glob("*.py"))},
               "note": "Actual CLI execution of an authored fixture; the printed model/tool usage is synthetic. Source hashes identify the working tree, including uncommitted changes."}
    (public / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in ("started_at", "elapsed_seconds", "actual_provider_calls", "synthetic_reported_usage", "doctor")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    capture(parser.parse_args().destination)
