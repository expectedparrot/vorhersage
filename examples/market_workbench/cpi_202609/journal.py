"""CLI driver for this live case; never opens the evaluator store."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "research"
CASE = "workbench_1ae01f8856bf4dc5926f"


def cli(*args):
    run = subprocess.run([sys.executable, "-m", "vorhersage", "--project", str(PROJECT), *map(str, args)],
                         capture_output=True, text=True, check=True)
    return json.loads(run.stdout)["data"]


def submit(kind, payload):
    revision = cli("workbench", "show", CASE)["revision"]
    spec = {"kind": kind, "payload": payload, "expected_revision": revision, "idempotency_key": f"cpi-{revision}-{kind}"}
    path = PROJECT / "inputs" / f"{revision:02d}-{kind}.json"
    path.write_text(json.dumps(spec, indent=2) + "\n")
    result = cli("workbench", "submit", CASE, "--from", path)
    path.with_suffix(".receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    if sys.argv[1] == "capture":
        result = cli("research", "capture", "--from", sys.argv[2])
    else:
        result = submit(sys.argv[1], json.loads(Path(sys.argv[2]).read_text()))
    print(json.dumps(result, indent=2))
