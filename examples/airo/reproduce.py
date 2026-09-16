#!/usr/bin/env python3
"""Reproduce the September 2026 AIRO panel using Vorhersage, without model calls."""

import argparse
import calendar
import csv
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from vorhersage import sessions
from vorhersage.common import canonical, now, require
from vorhersage.relations import add as add_relation
from vorhersage.workflow import Workflow

HERE = Path(__file__).resolve().parent
RUN = "2026-09-10T2141Z"
PROTOCOL = "unified-joint-combined-v5"
INSTRUMENT = "airo-incidents-prospective-v1"
MODELS = ["GPT-6 Astra", "Fable 5.1", "Opus 5", "GPT-5.5 Pro"]
HORIZONS = ["6mo", "12mo", "2028", "2030", "2050", "2100"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def load_source(source):
    manifest = json.loads((source / "manifest.json").read_text())
    for name, expected in manifest["files"].items():
        require(sha((source / name).read_bytes()) == expected, "Source integrity mismatch: " + name)
    raw = gzip.decompress((source / "selected-run.jsonl.gz").read_bytes())
    require(sha(raw) == manifest["selected_uncompressed_sha256"], "Selected source bytes have changed.")
    lines = raw.splitlines(keepends=True)
    require(len(lines) == len(manifest["selected_lines"]), "Source line manifest length mismatch.")
    for line, record in zip(lines, manifest["selected_lines"]):
        require(sha(line) == record["sha256"], "Selected source line has changed.")
    rows = [json.loads(line) for line in lines]
    require(len(rows) == 1960 and {r["run_id"] for r in rows} == {RUN}, "Wrong published run or row count.")
    require({r["protocol"] for r in rows} == {PROTOCOL}, "Mixed protocols.")
    require({r["instrument_version"] for r in rows} == {INSTRUMENT}, "Mixed instrument versions.")
    require({r["label"] for r in rows} == set(MODELS), "Wrong panel membership.")
    return manifest, rows


def shared(rows, field):
    # Large shared fields occur once per call; other rows have null or [] placeholders.
    values = {canonical(r[field]): r[field] for r in rows if r.get(field) is not None and r[field] != []}
    require(len(values) == 1, "Inconsistent or missing shared source field: " + field)
    return next(iter(values.values()))


def source_condition(row):
    return row["condition"]["id"] if row.get("condition") else "unconditional"


def question_id(qid, horizon):
    return f"airo:2026-09-10:{qid}:{horizon}"


def ref(qid, horizon):
    return {"question_id": question_id(qid, horizon), "version": 1}


def edge_list(questions, ladder):
    """The authors' adjacent checks, with their BRACKET assumption marked separately."""
    edges = []
    def edge(kind, a, b):
        edges.append({"kind": kind, "antecedent": a, "consequent": b})
    for q in questions:
        for a, b in zip(q["horizons"], q["horizons"][1:]):
            edge("HORIZON", (q["id"], a), (q["id"], b))
    for cause in ladder["causes"]:
        for a, b in zip(ladder["rungs"], ladder["rungs"][1:]):
            for h in HORIZONS:
                edge("LADDER", (f"ladder:{cause['key']}:{b['short']}", h), (f"ladder:{cause['key']}:{a['short']}", h))
    for cause in ladder["relations"]["cross"]["contained"]:
        for rung in ladder["rungs"]:
            for h in HORIZONS:
                edge("CROSS", (f"ladder:{cause}:{rung['short']}", h),
                     (f"ladder:{ladder['relations']['cross']['container']}:{rung['short']}", h))
    for pair in ladder["relations"]["subset"]:
        for h in HORIZONS:
            edge("SUBSET", (pair["narrower"], h), (pair["broader"], h))
    for pair in ladder["relations"]["bracket"]:
        for h in HORIZONS:
            edge("BRACKET", (pair["narrower"], h), (f"ladder:{pair['cause']}:{pair['rung']}", h))
    return edges


def register_questions(w, questions, resolves):
    refs, mapping = [], {}
    for q in questions:
        for h in q["horizons"]:
            end = date.fromisoformat(resolves[h])
            after = end
            if q["category"] == "incident":
                year = end.year + 3
                after = end.replace(year=year, day=min(end.day, calendar.monthrange(year, end.month)[1]))
            detail = "\n\n".join((q.get("details") or {}).values())
            wording = q["criteria"] + ("\n\n" + detail if detail else "")
            horizon_text = f"Selected horizon: {h}, ending {end.isoformat()} (inclusive UTC)."
            if q["category"] == "incident":
                horizon_text += " Incident onsets start 2026-09-10; count each eligible incident's first three years of harm."
            spec = {"id": question_id(q["id"], h), "text": q["text"] + "\n\n" + horizon_text,
                    "yes": wording + "\n\n" + horizon_text,
                    "no": "The event defined by the original YES criteria does not occur within this horizon's counting rules.",
                    "void": "Original criteria cannot be adjudicated; retain disputed or void status rather than invent an outcome.",
                    "event_deadline": end.isoformat() + "T23:59:59.999999Z",
                    "resolve_after": after.isoformat() + "T23:59:59.999999Z",
                    "resolution_source": "Original AIRO resolution criteria and specified expert adjudication.",
                    "event_group": "airo-global-ai-risk", "domain": q.get("cause", "catastrophe"),
                    "profile": "general", "kind": "real"}
            refs.append(w.question(spec))
            mapping[spec["id"]] = {"source_question_id": q["id"], "horizon": h, "source_question": q}
    return refs, mapping


def register_conditions(w, instrument, target):
    definitions = instrument["conditioning"]
    groups = {g["key"]: g for g in instrument["groups"]}
    conditions, bindings = {}, {}
    for c in [{"id": "unconditional"}, *instrument["conditions"]]:
        id = c["id"]
        if id == "unconditional":
            text = definitions["unconditional_forecast"]
            kind = "unconditional"
        else:
            group = groups[c["group"]]
            text = "\n\n".join(x for x in [definitions["instruction"], definitions["definitions"],
                    group["instruction"], group["assumption"], group["definitions"], group["horizon"],
                    c["label"], c["assume"], c["description"]] if x)
            kind = "intervention" if c["group"] == "policy" else "information"
        spec = {"id": "airo_20260910_" + id, "version": 1, "kind": kind,
                "description": text.replace("{target_date}", target)}
        if kind != "unconditional":
            # Policy prompts explicitly fix the same own-median capability trajectory.
            quantile = 0.5 if kind == "intervention" else int(c["field"][1:]) / 100
            spec["binding"] = {"variable": "frontier_eci", "unit": "ECI points", "target_at": target + "T00:00:00Z",
                               "vintage": "Epoch index as supplied in the 2026-09-10 prompt", "quantile": quantile, "tolerance": 2}
            bindings[id] = "p" + str(round(quantile * 100))
        conditions[id] = sessions.add_condition(w.store, spec)["condition_id"]
    return conditions, bindings


def evidence_packet(w, rows, completed):
    evidence = shared(rows, "evidence")
    records = []
    for index, call in enumerate(evidence):
        if call["tool"] != "read_page" or not call.get("result", {}).get("text"):
            continue
        result = call["result"]
        text = result["text"]
        record_id = f"page_{index}"
        records.append({"id": record_id, "claim": "The authors' log records this page-text excerpt returned to the model.",
                        "value": {"tool_index": index, "offset": result.get("offset"), "total_chars": result.get("total_chars")},
                        "entity_ids": [], "observed_at": completed,
                        "sources": [{"id": record_id, "url": result["url"], "title": "AIRO recorded page read",
                                     "excerpt": text[:500], "excerpt_kind": "quotation", "retrieved_at": completed,
                                     "capture": {"method": "manual", "content": text, "content_sha256": sha(text.encode()),
                                                 "metadata": {"timestamp_basis": "session completion upper bound; individual read time unavailable",
                                                              "source_call_id": rows[0]["call_id"]}}}],
                        "provenance": {"source_call_id": rows[0]["call_id"], "timestamp_basis": "session completion upper bound"},
                        "claim_type": "observation"})
    require(records, "No recorded page text for session.")
    imported = w.import_packet({"schema_version": "vorhersage.evidence.v1", "kind": "manual",
                                "information_as_of": completed, "created_at": now(), "records": records,
                                "limitations": ["Imported authors' tool output; sources were not independently fetched or fact-checked.",
                                                "Per-read timestamps are absent; completion is an upper bound, not the actual retrieval time.",
                                                "These are shared session sources; the export does not attribute individual claims to cells."]})
    return imported["packet_id"], [r["evidence_ref"] for r in imported["records"]]


def author_audit(rows, edges):
    cells = {(r["label"], r["question_id"], f["horizon"]): f["probability"]
             for r in rows if source_condition(r) == "unconditional" for f in r["forecasts"]}
    counts = defaultdict(lambda: {"comparisons": 0, "violations": 0})
    violations = []
    for model in MODELS:
        for e in edges:
            a, b = cells[(model, *e["antecedent"])], cells[(model, *e["consequent"])]
            bad = a > b + 1e-11  # Authors compare percentage values with EPS=1e-9.
            counts[e["kind"]]["comparisons"] += 1
            counts[e["kind"]]["violations"] += int(bad)
            if bad:
                violations.append({**e, "model": model, "antecedent_probability": a, "consequent_probability": b})
    return {"by_constraint": dict(counts), "comparisons": sum(c["comparisons"] for c in counts.values()),
            "violations": violations, "bracket_caveat": "The authors' BRACKET checks span different onset and harm windows; reproduced for fidelity, excluded from registered logical implications."}


def compare_published(source, panel, question_map, conditions, audit):
    rows = {(question_map[r["question_id"]]["source_question_id"], question_map[r["question_id"]]["horizon"], r["condition_id"]): r for r in panel["rows"]}
    checks = []
    def check_value(name, actual, expected, tolerance):
        checks.append({"name": name, "actual": actual, "published": expected,
                       "absolute_error": abs(actual - expected), "tolerance": tolerance,
                       "passed": abs(actual - expected) <= tolerance + 1e-12})
    g1 = json.loads((source / "results/graph1_data.json").read_text())
    for q in g1["questions"]:
        if not q["id"].startswith(("catastrophe:", "disempowerment")):
            continue
        for h, expected in q["median"].items():
            check_value(f"headline:{q['id']}:{h}", rows[(q["id"], h, conditions["unconditional"])]["median_probability"] * 100, expected, 0.0005)
    g2 = json.loads((source / "results/graph2_data.json").read_text())
    for h, block in g2["byHorizon"].items():
        for cause in block["causes"]:
            for rung in cause["rungs"]:
                actual = rows[(rung["qid"], h, conditions["unconditional"])]["median_probability"] * 100
                check_value(f"ladder:{rung['qid']}:{h}", actual, rung["median"], 0.0001)
    capability = json.loads((source / "results/capability_data.json").read_text())
    views = [json.loads((source / "results/conditional_data.json").read_text()),
             next(v for v in capability["variants"] if v["key"] == capability["defaultVariant"])]
    for view in views:
        for q in view["questions"]:
            for h, block in q["byHorizon"].items():
                if (q["id"], h, conditions["unconditional"]) not in rows:
                    continue  # Expected-loss composites are outside the paper's probability plots.
                for bar in block["bars"]:
                    actual = rows[(q["id"], h, conditions[bar["id"]])]
                    for field, expected, value, tolerance in (
                            ("ratio", bar["ratio"], actual["multiplier"], 0.00005),
                            ("probability_pct", bar["pMedian"], actual["median_probability"] * 100, 0.00005)):
                        check_value(f"conditional:{q['id']}:{h}:{bar['id']}:{field}", value, expected, tolerance)
    for kind, count in audit["by_constraint"].items():
        check_value("coherence:" + kind + ":n", count["comparisons"], g2["audit"]["byConstraint"][kind]["n"], 0)
        check_value("coherence:" + kind + ":bad", count["violations"], g2["audit"]["byConstraint"][kind]["bad"], 0)
    return {"checks": checks, "passed": sum(x["passed"] for x in checks), "failed": [x for x in checks if not x["passed"]],
            "note": "Comparisons use the precision of the authors' saved dashboard values; calculations retain unrounded source probabilities."}


def reproduce(source, output):
    manifest, raw = load_source(source)
    require(not output.exists(), "Use a new output directory; existing replication records are preserved.")
    output.mkdir(parents=True)
    w = Workflow(output / "project")
    w.store.init("AIRO September 2026 published-panel reproduction")
    ladder = json.loads((source / "data/autoarc_ladder.json").read_text())
    cross = json.loads((source / "data/autoarc_crosscutting.json").read_text())
    instrument = json.loads((source / "data/combined_conditions.json").read_text())
    questions = [*ladder["questions"], *cross["questions"]]
    require(len(questions) == 35, "Wrong instrument size.")
    question_refs, question_map = register_questions(w, questions, shared(raw, "resolves_on"))
    targets = {r["elicited"]["target_date"] for r in raw}
    require(len(targets) == 1, "Mixed capability target dates.")
    conditions, binding_fields = register_conditions(w, instrument, next(iter(targets)))
    edges = edge_list(questions, ladder)
    relation_ids = [add_relation(w.store, {"antecedent": ref(*e["antecedent"]), "consequent": ref(*e["consequent"]),
                    "rationale": "AIRO " + e["kind"] + " implication with matching counting criteria."})["relation_id"]
                    for e in edges if e["kind"] != "BRACKET"]
    write(output / "question-map.json", question_map)
    write(output / "condition-map.json", conditions)
    write(output / "source-manifest.json", manifest)
    write(output / "author-edges.json", edges)
    session_ids, session_summaries = [], []
    source_calls = defaultdict(list)
    for row in raw:
        source_calls[row["call_id"]].append(row)
    require(len(source_calls) == 4, "Expected exactly four independent source calls.")
    for call_id, rows in source_calls.items():
        label = shared(rows, "label")
        completed = shared(rows, "elicited_at")
        prompt = shared(rows, "prompt")
        require(sha(prompt.encode()) == shared(rows, "prompt_sha256"), "Original prompt hash mismatch.")
        elicited = shared(rows, "elicited")
        packet_id, evidence_refs = evidence_packet(w, rows, completed)
        cells = [{**ref(r["question_id"], f["horizon"]), "condition_id": conditions[source_condition(r)],
                  "probability": f["probability"], "evidence_refs": evidence_refs} for r in rows for f in r["forecasts"]]
        require(len(cells) == 2940 and len({sessions.cell_key(c) for c in cells}) == 2940, "Missing or duplicate source cells.")
        usage = shared(rows, "usage")
        evidence = shared(rows, "evidence")
        tools = Counter(x["tool"] for x in evidence)
        spec = {"id": call_id, "wave": RUN, "forecaster": label, "protocol": PROTOCOL, "repetition": 1,
                "mode": "prospective", "information_as_of": completed, "questions": question_refs,
                "condition_ids": list(conditions.values()), "packet_ids": [packet_id], "relation_ids": relation_ids,
                "numeric_forecasts": [{"variable": "frontier_eci", "unit": "ECI points",
                                       "target_at": elicited["target_date"] + "T00:00:00Z",
                                       "vintage": "Epoch index as supplied in the 2026-09-10 prompt",
                                       "quantiles": [{"level": p / 100, "value": elicited["eci_forecast"][f'p{p}']} for p in (10, 25, 50, 75, 90)]}],
                "bindings": [{"condition_id": conditions[cid], "value": elicited["eci_forecast"][field]} for cid, field in binding_fields.items()],
                "provenance": {"kind": "external", "source": manifest["repository"] + "/tree/" + manifest["commit"]},
                "configuration": {"model": shared(rows, "model"), "source_run_id": RUN, "instrument": INSTRUMENT,
                                  "original_panel_selection": shared(rows, "panel"), "prompt_sha256": sha(prompt.encode()),
                                  "information_cutoff_basis": "source session completion upper bound",
                                  "source_delivery": shared(rows, "delivery"), "source_attempts": shared(rows, "attempts"),
                                  "usage_basis": "Source turns mapped to model_calls; search calls counted from recorded tools; costs charged only once."}}
        bundle = {"session": spec, "submissions": [{"submitted_at": completed, "cells": cells,
                   "usage": {"searches": tools["web_search"], "model_calls": usage["turns"], "cost_usd": usage["cost_usd"]},
                   "raw_record": {"source_call_id": call_id, "source_rows": rows,
                                  "limitations": ["Expanded final-cell export: original incremental submit_cells values/timestamps are not available."]}}],
                   "finalized_at": completed, "rationale": shared(rows, "rationale")}
        imported = sessions.import_session(w.store, bundle)
        session_ids.append(imported["session_id"])
        state = sessions.status(w.store, imported["session_id"])
        coherence = state["finalization"]["coherence"]
        summary = {"label": label, "session_id": imported["session_id"], "source_call_id": call_id,
                   "finalized_at": completed, "probabilities": len(cells), "source_usage": usage,
                   "recorded_tool_calls": dict(tools), "shared_page_records": len(evidence_refs),
                   "eci_forecast": elicited["eci_forecast"], "coherence_comparisons": len(coherence["comparisons"]),
                   "coherence_violations": len(coherence["violations"]),
                   "coherence_details": coherence["violations"]}
        session_summaries.append(summary)
        write(output / "sessions" / (label.replace(" ", "_") + ".json"), summary)
        (output / "prompt.txt").write_text(prompt)
        (output / "system-prompt.txt").write_text(shared(rows, "system_prompt"))
        print(json.dumps({"imported": label, "probabilities": len(cells), "coherence_violations": summary["coherence_violations"]}), flush=True)
    panel_policy = {"session_ids": session_ids, "expected_forecasters": MODELS}
    panel = sessions.aggregate(w.store, panel_policy)
    alternative = sessions.aggregate(w.store, {**panel_policy, "baseline_condition_id": conditions["sq"]})
    # Save the full auditable reports compressed; publish compact CSVs for analysis.
    for name, report in (("panel", panel), ("status-quo-comparison", alternative)):
        (output / f"{name}.json.gz").write_bytes(gzip.compress(canonical(report).encode(), mtime=0))
    inverse = {v: k for k, v in conditions.items()}
    with (output / "panel.csv").open("w") as file:
        writer = csv.DictWriter(file, fieldnames=["question", "horizon", "condition", "median_probability", "multiplier"])
        writer.writeheader()
        for row in panel["rows"]:
            q = question_map[row["question_id"]]
            writer.writerow({"question": q["source_question_id"], "horizon": q["horizon"],
                             "condition": inverse[row["condition_id"]], "median_probability": row["median_probability"], "multiplier": row["multiplier"]})
    audit = author_audit(raw, edges)
    comparison = compare_published(source, panel, question_map, conditions, audit)
    write(output / "author-coherence.json", audit)
    write(output / "verification.json", comparison)
    summary = {"source_commit": manifest["commit"], "run_id": RUN, "models": MODELS, "sessions": session_summaries,
               "questions": len(questions), "question_horizon_cells": len(question_refs), "conditions": len(conditions),
               "probabilities": sum(x["probabilities"] for x in session_summaries),
               "matched_published_values": comparison["passed"], "mismatched_published_values": len(comparison["failed"]),
               "author_coherence_comparisons": audit["comparisons"], "author_coherence_violations": len(audit["violations"]),
               "source_reported_usage": panel["usage"], "new_model_calls": 0, "doctor": w.doctor(),
               "limitations": ["Reproduction of saved forecasts, not validation of catastrophic-risk accuracy.",
                               "Figures 6–9 principal panel only; validation experiments and additional Figure 10 elicitation are separate datasets.",
                               "Source tool outputs are preserved, not independently fact-checked; original submission chronology is unavailable.",
                               "BRACKET comparisons are reproduced as authors' diagnostics, not registered as logical implications."]}
    write(output / "summary.json", summary)
    require(not comparison["failed"], "Published-value mismatches; inspect verification.json.")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=HERE / "source")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(reproduce(args.source, args.out), indent=2))
