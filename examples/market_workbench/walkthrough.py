"""Offline CLI demonstration: one fictional question, two research steps, reveal."""
import json
import subprocess
import sys
from pathlib import Path

from vorhersage.common import digest, now
from vorhersage.market_data import summarize_book


def main():
    root = Path(sys.argv[1]).resolve()
    root.mkdir(parents=True, exist_ok=False)
    research, vault = root / "research", root / "evaluator"
    vault.mkdir()

    def write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n")
        return str(path)

    def cli(*args):
        result = subprocess.run([sys.executable, "-m", "vorhersage", "--project", str(research), *map(str, args)],
                                text=True, capture_output=True, check=True)
        return json.loads(result.stdout)["data"]

    cli("init", "--name", "Fictional research workbench")
    question = {"id": "factory-demo", "text": "Will the fictional factory open before January 1, 2099?",
                "yes": "Public opening strictly before deadline", "no": "No qualifying opening",
                "void": "Unverifiable outcome", "event_deadline": "2099-01-01T00:00:00Z",
                "resolve_after": "2099-01-01T00:00:00Z", "resolution_source": "Fictional city registry",
                "event_group": "factory-demo", "domain": "business", "profile": "general", "kind": "simulation"}
    ref = cli("question", "add", "--from", write(research / "question.json", question))
    terms = {"venue": "kalshi", "market_id": "FICTIONAL-FACTORY", "title": question["text"],
             "yes_description": question["yes"], "rules": "Fictional full public opening before January 1, 2099.",
             "scheduled_close": question["event_deadline"], "resolution_source": question["resolution_source"],
             "event_group": "factory-demo"}

    def snapshot(bid, ask):
        return {"venue": "kalshi", "market_id": "FICTIONAL-FACTORY", "captured_at": now(),
                "contract": terms, "contract_sha256": digest(terms),
                "quote": summarize_book([[bid, 200]], [[ask, 250]]), "raw": [], "fictional": True}

    spec = {"question": ref, "venue": "kalshi", "market_id": "FICTIONAL-FACTORY", "mode": "simulation",
            "method": "Readiness checks followed by a reference class", "eligibility_rationale": "Fictional unresolved event",
            "contract_match_rationale": "Same opening definition and deadline"}
    case = cli("workbench", "start", "--from", write(research / "start.json", spec), "--vault", vault,
               "--snapshot", write(vault / "opening.json", snapshot(.69, .71)))
    cid, revision = case["case_id"], 0

    def submit(kind, payload):
        nonlocal revision
        data = {"kind": kind, "expected_revision": revision, "idempotency_key": str(revision), "payload": payload}
        result = cli("workbench", "submit", cid, "--from", write(research / f"{revision:02d}-{kind}.json", data))
        revision = result["revision"]

    cli("workbench", "export", cid, "--output", research / "researcher-input.json")
    submit("initial", {"probability": .50, "rationale": "Readiness is uncertain", "assumptions": ["Authorization may be incomplete"],
                       "uncertainties": ["Permit status", "Frequency of late delays"], "research_status": "not_started", "evidence_refs": []})
    for index, (topic, probability, finding) in enumerate([
        ("Authorization", .72, "The fictional registry records a final operating permit."),
        ("Comparable opening delays", .65, "Two of ten fictional comparable openings missed their announced window despite permits.")
    ]):
        submit("plan", {"uncertainty": topic, "why_it_matters": "This assumption affects opening risk",
                        "higher_if": "Evidence shows less remaining work or fewer analogous delays",
                        "lower_if": "Remaining work or comparable delays are substantial",
                        "search_plan": "Read fictional registry and supplied fictional comparison cases",
                        "stopping_rule": "Stop after checking the specified source"})
        t = now()
        bundle = {"sources": [{"id": "source", "url": f"https://example.invalid/factory/{index}", "title": topic,
                               "excerpt": finding, "excerpt_kind": "paraphrase", "retrieved_at": t}],
                  "findings": [{"id": "finding", "claim": finding, "claim_type": "observation", "source_ids": ["source"]}],
                  "information_as_of": t, "limitations": ["Entirely fictional demonstration"]}
        packet = cli("research", "capture", "--from", write(research / f"evidence-{index}.json", bundle))
        submit("checkpoint", {"probability": probability, "rationale": "Subjective revision using the recorded finding",
                              "findings": finding, "changed_assumptions": [topic], "remaining_uncertainties": ["Actual completion date"],
                              "sources_checked": [f"Fictional source {index}"],
                              "evidence_refs": [{"packet_id": packet["packet_id"], "record_id": "finding"}],
                              "limitations": ["Illustrative probabilities, not calibrated estimates"],
                              "usage": {"searches": 0, "model_calls": 0, "cost_usd": 0}})
    cli("workbench", "report", cid, "--output", root / "before-reveal.html")
    submit("finish", {"stopping_reason": "Two planned research steps complete", "outcome_status": "unresolved",
                      "market_exposure": "none", "exposure_notes": "Fictional CLI demonstration; no independent model was run"})
    result = cli("workbench", "reveal", cid, "--vault", vault,
                 "--snapshot", write(vault / "later.json", snapshot(.73, .75)))
    submit("reflection", {"what_helped": "Authorization research moved the estimate closer to the target",
                          "what_did_not": "The reference-class adjustment moved it farther away; that does not establish it was bad evidence",
                          "next_method_change": "Check comparability more explicitly on a fresh question"})
    cli("workbench", "report", cid, "--output", root / "comparison.html")
    summary = {"case_id": cid, "comparison": result["comparison"], "doctor": cli("doctor")}
    write(root / "summary.json", summary)
    print(json.dumps({"case_id": cid, "report": str(root / "comparison.html"), "doctor": summary["doctor"]}, indent=2))


if __name__ == "__main__":
    main()
