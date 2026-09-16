"""Build a standalone, offline HTML comparison from the two recorded AIRO runs."""

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent


def build(pilot, authors):
    read = lambda path: json.loads(path.read_text())
    summary, original = read(pilot / "summary.json"), read(authors / "summary.json")
    mapping = read(authors / "question-map.json")
    conditions = {v: k for k, v in read(authors / "condition-map.json").items()}
    panel = json.loads(gzip.decompress((authors / "panel.json.gz").read_bytes()))
    ranges = {}
    for r in panel["rows"]:
        q = mapping[r["question_id"]]
        ps = [m["probability"] for m in r["members"]]
        ranges[q["source_question_id"], q["horizon"], conditions[r["condition_id"]]] = [min(ps), max(ps)]
    rows = []
    with (pilot / "comparison.csv").open() as file:
        for r in csv.DictReader(file):
            key = (r["question"], r["horizon"], r["condition"])
            vals = [float(r[k]) if r[k] else None for k in (
                "fresh_probability", "authors_panel_median", "fresh_paired_multiplier", "authors_panel_paired_multiplier")]
            rows.append([*key, *vals, *ranges[key]])
    assert len(rows) == 2940 and len({tuple(r[:3]) for r in rows}) == 2940
    names = {"catastrophe:general": "General catastrophe", "catastrophe:ai": "AI catastrophe", "disempowerment": "Human disempowerment"}
    questions = {}
    for item in mapping.values():
        q = item["source_question"]
        questions[q["id"]] = {"label": names.get(q["id"], q.get("cause_label", "") + " · " + q.get("severity", {}).get("label", "")),
                              "text": q["text"], "criteria": q["criteria"], "details": q.get("details", {})}
    instrument = read(HERE / "source/data/combined_conditions.json")
    labels = {"unconditional": "Unconditional", "sq": "Status quo", "p1": "Federal preemption", "p2a": "Compute cap · US",
              "p2b": "Compute cap · US + China", "p3a": "Pre-release authorization · US", "p3b": "Pre-release authorization · international",
              "p4": "Strict liability", "p5": "Combined package", **{f"eci_p{n}": f"Own {n}th-percentile capability" for n in (10, 25, 50, 75, 90)}}
    data = {"rows": rows, "questions": questions, "labels": labels,
            "conditionDefinitions": {c["id"]: c["assume"] + "\n\n" + c["description"] for c in instrument["conditions"]},
            "pilot": {k: summary[k] for k in ("model", "started_at", "finalized_at", "usage", "successful_page_reads", "research_calls",
                       "successful_research_calls", "coherence_comparisons", "coherence_violations", "eci_forecast", "protocol_deviations", "transport_failures")},
            "authors": {"models": original["models"], "source_commit": original["source_commit"], "run_id": original["run_id"],
                        "checks": original["matched_published_values"], "conditional_violations": sum(s["coherence_violations"] for s in original["sessions"]),
                        "eci": {k: median(s["eci_forecast"][k] for s in original["sessions"]) for k in summary["eci_forecast"]}},
            "inputHashes": {"pilot_csv": hashlib.sha256((pilot / "comparison.csv").read_bytes()).hexdigest(),
                            "authors_panel": hashlib.sha256((authors / "panel.json.gz").read_bytes()).hexdigest()}}
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False, allow_nan=False).replace("<", "\\u003c").replace("&", "\\u0026")
    template = (HERE / "comparison_template.html").read_text()
    assert template.count("__COMPARISON_DATA__") == 1
    target = pilot / "comparison.html"
    target.write_text(template.replace("__COMPARISON_DATA__", payload))
    return {"html": str(target), "matched_cells": len(rows), "bytes": target.stat().st_size}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, default=HERE / "edsl_pilot_01")
    parser.add_argument("--authors", type=Path, default=HERE / "output")
    args = parser.parse_args()
    print(json.dumps(build(args.pilot, args.authors), indent=2))
