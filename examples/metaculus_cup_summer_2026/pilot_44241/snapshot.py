"""Explicit, budgeted Exa Snapshot requests for this registered pilot."""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from vorhersage import research
from vorhersage.common import load, now, require
from vorhersage.store import Store

ROOT = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument("operation", choices=["definition", "search", "fetch"])
    p.add_argument("value")
    args = p.parse_args()
    for line in (ROOT.parents[2] / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            if key.strip() == "EXA_API_KEY":
                os.environ[key.strip()] = value.strip().strip("\"'")
    spec = load(ROOT / "registration.json")
    project = ROOT / "project"
    store = Store(project)
    if not store.path.exists():
        store.init("Lincoln Reflecting Pool historical pilot")
    if args.operation == "definition":
        require(args.value == "https://www.metaculus.com/questions/44241/", "Only the selected historical contract may be fetched.")
    elif args.operation == "fetch":
        host = (urlsplit(args.value).hostname or "").lower()
        require(host != "metaculus.com" and not host.endswith(".metaculus.com"), "Metaculus research is excluded.")
    with store.connect(write=True) as c:
        attempts = Store.all(c, "snapshot_attempt")
        require(len(attempts) < spec["research"]["max_requests"], "Request budget exhausted.")
        if args.operation == "search":
            require(sum(a["operation"] == "search" for a in attempts) < spec["research"]["max_searches"], "Search budget exhausted.")
        if args.operation == "definition":
            require(not any(a["operation"] == "definition" for a in attempts), "Definition request already attempted.")
        attempt = Store.put(c, "snapshot_attempt", {"operation": args.operation, "value": args.value, "started_at": now()})
    kwargs = {"provider": "exa", "snapshot_as_of": spec["information_as_of"]}
    if args.operation == "search":
        r = research.search(project, args.value, limit=5, exclude_domains=["metaculus.com"], **kwargs)
    else:
        r = research.fetch(project, args.value, **kwargs)
    (ROOT / "retrievals").mkdir(exist_ok=True)
    (ROOT / "retrievals" / (r["id"] + ".json")).write_text(json.dumps(r, indent=2) + "\n")
    print(json.dumps({"retrieval_id": r["id"], "attempt_id": attempt, "warnings": r["warnings"], "source_count": len(r["sources"])}))
    for s in r["sources"]:
        text = s["capture"].get("content", "")
        if args.operation == "definition":
            # Do not print forecasts, comments, or any other page section.
            start = text.find("Resolution Criteria")
            if start < 0:
                text = "No Resolution Criteria section found; historical definition unavailable."
            else:
                text = text[start:]
                ends = [text.find(marker, 20) for marker in ("Background", "Comments", "Forecast Timeline", "Community Prediction")]
                text = text[:min([i for i in ends if i >= 0] or [len(text)])]
        print(json.dumps({"source_id": s["id"], "url": s["url"], "title": s["title"], "text": text[:9000]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
