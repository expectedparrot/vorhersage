"""Save authored workflow submissions and receipts for the pilot."""
import json
from pathlib import Path
from vorhersage.common import load
from vorhersage.workflow import Workflow

ROOT = Path(__file__).resolve().parent
W = Workflow(ROOT / "project")
RUN = load(ROOT / "run.json")["run_id"]


def submit(payload, searches=0):
    nxt = W.next(RUN)
    directory = ROOT / "submissions"
    directory.mkdir(exist_ok=True)
    stem = f'{nxt["revision"]:02d}_{nxt["task"]["kind"]}'
    body = {"task_id": nxt["task"]["id"], "expected_revision": nxt["revision"],
            "idempotency_key": nxt["task"]["id"], "payload": payload,
            "usage": {"searches": searches, "cost_usd": 0, "model_calls": 0}}
    (directory / (stem + ".json")).write_text(json.dumps(body, indent=2) + "\n")
    result = W.submit(RUN, body)
    (directory / (stem + "_receipt.json")).write_text(json.dumps(result, indent=2) + "\n")
    nxt = W.next(RUN)
    (ROOT / "next.json").write_text(json.dumps(nxt, indent=2) + "\n")
    print(json.dumps({"disposition": nxt["disposition"], "next_task": nxt.get("task"), "forecast_id": nxt.get("forecast_id")}))
    return nxt
