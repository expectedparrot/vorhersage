import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from vorhersage import market_data, workbench
from vorhersage.common import Error, digest, now, time
from vorhersage.evidence import capture_bundle
from vorhersage.workflow import Workflow


def snapshot(venue="kalshi", market_id="DEMO", bid=.69, ask=.71):
    terms = {"venue": venue, "market_id": market_id, "title": "Will the factory open?",
             "yes_description": "Factory opens", "rules": "Public opening before January 1, 2099.",
             "scheduled_close": "2099-01-01T00:00:00Z", "resolution_source": "City registry", "event_group": "factory"}
    return {"venue": venue, "market_id": market_id, "captured_at": now(), "contract": terms,
            "contract_sha256": digest(terms), "quote": market_data.summarize_book([[bid, 100]], [[ask, 150]]),
            "raw": [{"data": {"secret_price": .70}}]}


@pytest.fixture
def case(tmp_path):
    w = Workflow(tmp_path / "research")
    w.store.init("Research")
    q = w.question({"id": "factory", "text": "Will the factory open?", "yes": "Public opening before deadline",
                    "no": "No opening before deadline", "void": "Ambiguous record", "event_deadline": "2099-01-01T00:00:00Z",
                    "resolve_after": "2099-01-01T00:00:00Z", "resolution_source": "City registry",
                    "event_group": "factory", "domain": "business", "profile": "general", "kind": "simulation"})
    spec = {"question": q, "venue": "kalshi", "market_id": "DEMO", "mode": "simulation", "method": "Targeted research",
            "eligibility_rationale": "Fictional future opening", "contract_match_rationale": "Same event and deadline."}
    vault = tmp_path / "evaluator"
    opened = workbench.start(w.store, spec, vault, snapshot())
    return w, vault, opened["case_id"], spec


def initial(p=.5):
    return {"probability": p, "rationale": "Uncertain readiness", "assumptions": ["Permit may be pending"],
            "uncertainties": ["Permit status"], "research_status": "not_started", "evidence_refs": []}


def plan():
    return {"uncertainty": "Permit status", "why_it_matters": "Opening requires authorization",
            "higher_if": "Final permit issued", "lower_if": "Application rejected",
            "search_plan": "Check the city registry", "stopping_rule": "Stop after finding the current filing"}


def checkpoint(p=.65, refs=None):
    return {"probability": p, "rationale": "One prerequisite is complete", "findings": "Permit recorded",
            "changed_assumptions": ["Authorization complete"], "remaining_uncertainties": ["Construction"],
            "sources_checked": ["City registry"], "evidence_refs": refs or [], "limitations": ["Fictional evidence"]}


def finish():
    return {"stopping_reason": "Research budget exhausted", "outcome_status": "unresolved", "market_exposure": "none",
            "exposure_notes": "No odds sought or seen"}


def post(case, kind, payload):
    w, _, cid, _ = case
    revision = workbench.status(w.store, cid)["revision"]
    spec = {"kind": kind, "expected_revision": revision, "idempotency_key": f"step-{revision}", "payload": payload}
    return workbench.submit(w.store, cid, spec)


def test_hidden_target_never_enters_research_project_until_sealed_reveal(case, tmp_path):
    w, vault, cid, _ = case
    with w.store.connect() as c:
        bodies = [json.loads(r[0]) for r in c.execute("SELECT body FROM artifacts")]
    assert len(bodies) == 1
    assert '"quote"' not in json.dumps(bodies) and '"secret_price"' not in json.dumps(bodies)
    workbench.export_case(w.store, cid, tmp_path / "input.json")
    workbench.report(w.store, cid, tmp_path / "before.html")
    assert "70.0%" not in (tmp_path / "before.html").read_text()
    assert '"midpoint"' not in (tmp_path / "input.json").read_text()
    with pytest.raises(Error, match="Finish and seal"):
        workbench.reveal(w.store, cid, vault, skip_refresh=True)
    post(case, "initial", initial())
    post(case, "finish", finish())
    revealed = workbench.reveal(w.store, cid, vault, snapshot(bid=.74, ask=.76))
    assert revealed["comparison"]["target"]["midpoint"] == pytest.approx(.7)
    assert revealed["comparison"]["market_movement_pp"] == pytest.approx(5)
    assert revealed["comparison"]["rows"][0]["squared_market_error"] == pytest.approx(.04)
    assert not revealed["comparison"]["eligible_for_blind_comparison"]  # simulation
    with pytest.raises(Error, match="revealed case"):
        workbench.export_case(w.store, cid, tmp_path / "input.json")
    assert workbench.reveal(w.store, cid, vault, skip_refresh=True)["revealed_at"] == revealed["revealed_at"]


def test_plans_precede_research_and_only_reflection_can_follow_reveal(case):
    w, vault, cid, _ = case
    with pytest.raises(Error):
        post(case, "checkpoint", checkpoint())
    post(case, "initial", initial())
    post(case, "plan", plan())
    with pytest.raises(Error):
        post(case, "plan", plan())
    with pytest.raises(Error):
        post(case, "finish", finish())
    post(case, "checkpoint", checkpoint())
    post(case, "plan", plan())
    post(case, "checkpoint", checkpoint(.72))
    post(case, "finish", finish())
    with pytest.raises(Error, match="sealed"):
        post(case, "initial", initial(.7))
    data = workbench.reveal(w.store, cid, vault, skip_refresh=True)
    rows = data["comparison"]["rows"]
    assert [r["squared_market_error"] for r in rows] == pytest.approx([.04, .0025, .0004])
    assert rows[1]["improvement_from_previous"] == pytest.approx(.0375)
    assert data["comparison"]["net_squared_error_improvement"] == pytest.approx(.0396)
    post(case, "reflection", {"what_helped": "Readiness check", "what_did_not": "Generic search", "next_method_change": "Check filings first"})
    assert workbench.status(w.store, cid)["comparison"]["rows"] == rows
    assert w.doctor()["ok"]


def test_retry_and_stale_revision_cannot_change_history(case):
    w, _, cid, _ = case
    spec = {"kind": "initial", "expected_revision": 0, "idempotency_key": "first", "payload": initial()}
    first = workbench.submit(w.store, cid, spec)
    assert workbench.submit(w.store, cid, spec)["entry_id"] == first["entry_id"]
    spec["payload"]["probability"] = .9
    with pytest.raises(Error, match="Idempotency"):
        workbench.submit(w.store, cid, spec)
    with pytest.raises(Error, match="Stale"):
        workbench.submit(w.store, cid, {"kind": "plan", "expected_revision": 0, "idempotency_key": "plan", "payload": plan()})
    assert workbench.status(w.store, cid)["revision"] == 1


def test_evidence_integrity_and_unavailable_evidence_are_explicit(case, tmp_path):
    w, _, cid, _ = case
    post(case, "initial", initial())
    post(case, "plan", plan())
    with pytest.raises(Error, match="Unknown artifact"):
        post(case, "checkpoint", checkpoint(refs=[{"packet_id": "missing", "record_id": "permit"}]))
    t = now()
    bundle = {"sources": [{"id": "registry", "url": "https://example.invalid/permit", "title": "Permit",
                           "excerpt": "Authorized", "retrieved_at": t}],
              "findings": [{"id": "permit", "claim": "Permit issued", "claim_type": "official_statement", "source_ids": ["registry"]}],
              "information_as_of": t, "limitations": ["Fictional"]}
    packet = w.import_packet(capture_bundle(bundle))
    post(case, "checkpoint", checkpoint(refs=[{"packet_id": packet["packet_id"], "record_id": "permit"}]))
    data = workbench.status(w.store, cid)
    assert next(iter(data["evidence"].values()))["claim"] == "Permit issued"
    workbench.report(w.store, cid, tmp_path / "report.html")
    assert "https://example.invalid/permit" in (tmp_path / "report.html").read_text()
    assert w.doctor()["ok"]


def test_no_snapshot_import_into_prospective_case_and_vault_not_nested(case):
    w, vault, cid, spec = case
    with pytest.raises(Error, match="non-nested"):
        workbench.start(w.store, spec, w.store.root / "secret", snapshot())
    real = {**spec, "mode": "prospective"}
    with pytest.raises(Error, match="reject supplied"):
        workbench._snapshot(real, snapshot())
    bad = snapshot()
    bad["quote"]["midpoint"] = .1
    with pytest.raises(Error, match="arithmetic"):
        workbench.start(w.store, spec, vault, bad)
    with pytest.raises(Error, match="selection limit"):
        workbench.start(w.store, spec, vault, snapshot(bid=.2, ask=.8))


def test_late_exposure_disclosure_updates_comparison_but_not_forecasts(case):
    w, vault, cid, _ = case
    post(case, "initial", initial())
    occurred = now()
    post(case, "finish", finish())
    first = workbench.reveal(w.store, cid, vault, skip_refresh=True)
    post(case, "exposure", {"kind": "market_probability", "description": "Odds in a search snippet", "occurred_at": occurred})
    after = workbench.status(w.store, cid)
    assert after["comparison"]["rows"] == first["comparison"]["rows"]
    assert any("search snippet" in s for s in after["comparison"]["qualification_reasons"])


def test_rule_changes_and_followup_timing_do_not_silently_replace_target(case):
    w, vault, cid, _ = case
    old = snapshot()
    post(case, "initial", initial())
    post(case, "finish", finish())
    with pytest.raises(Error, match="precedes finish"):
        workbench.reveal(w.store, cid, vault, old)
    changed = snapshot(bid=.79, ask=.81)
    changed["contract"]["rules"] = "Different deadline"
    changed["contract_sha256"] = digest(changed["contract"])
    data = workbench.reveal(w.store, cid, vault, changed)["comparison"]
    assert data["contract_changed"]
    assert data["market_movement_pp"] is None
    assert data["target"]["midpoint"] == pytest.approx(.7)


def response(data):
    return {"data": data, "retrieved_at": now(), "request_started_at": now(), "url": "fixture", "response_sha256": "fixture"}


@pytest.mark.parametrize("fixed", [True, False])
def test_kalshi_complementary_bids_and_fixed_point_formats(monkeypatch, fixed):
    m = {"ticker": "ABC", "title": "Will X happen?", "status": "active", "result": "", "rules_primary": "X happens",
         "close_time": "2099-01-01T00:00:00Z"}
    book = {"orderbook_fp": {"yes_dollars": [["0.40", "20"], ["0.45", "30"]], "no_dollars": [["0.52", "40"]]}} if fixed else {
        "orderbook": {"yes": [[40, 20], [45, 30]], "no": [[52, 40]]}}
    monkeypatch.setattr(market_data, "get", lambda url: response(book if "orderbook" in url else {"market": m}))
    snap = market_data.snapshot("kalshi", "ABC")
    assert snap["quote"]["bid"] == .45
    assert snap["quote"]["ask"] == .48
    assert snap["quote"]["midpoint"] == pytest.approx(.465)
    assert snap["quote"]["ask_size"] == 40
    m["result"] = "yes"
    with pytest.raises(Error, match="unresolved"):
        market_data.snapshot("kalshi", "ABC")


def test_polymarket_selects_yes_token_even_when_second_and_ignores_display_price(monkeypatch):
    m = {"id": "123", "question": "Will X happen?", "description": "X happens", "active": True, "closed": False,
         "acceptingOrders": True, "enableOrderBook": True, "endDate": "2099-01-01T00:00:00Z",
         "outcomes": '["No", "Yes"]', "clobTokenIds": '["no-token", "yes-token"]', "outcomePrices": '["0.9", "0.1"]'}
    urls = []
    def get(url):
        urls.append(url)
        return response({"asset_id": "yes-token", "bids": [{"price": ".6", "size": "50"}],
                         "asks": [{"price": ".62", "size": "100"}]} if "/book?" in url else m)
    monkeypatch.setattr(market_data, "get", get)
    snap = market_data.snapshot("polymarket", "123")
    assert urls[-1].endswith("token_id=yes-token")
    assert snap["quote"]["midpoint"] == .61
    assert '"outcomePrices"' not in json.dumps(market_data.inspect("polymarket", "123"))


def test_bounded_discovery_hides_prices_and_supports_pagination(monkeypatch):
    calls = []
    def get(url):
        calls.append(url)
        index = len(calls)
        return response({"markets": [{"ticker": str(index), "title": "Rocket" if index == 2 else "Other",
                                       "rules_primary": "Launch", "yes_bid_dollars": ".99"}], "cursor": str(index) if index < 3 else ""})
    monkeypatch.setattr(market_data, "get", get)
    data = market_data.browse("kalshi", "rocket", limit=1, pages=3)
    assert len(calls) == 2
    assert data["candidates"][0]["market_id"] == "2"
    assert '"yes_bid_dollars"' not in json.dumps(data)
    assert data["more_available"]


def test_report_escapes_untrusted_research_text(case, tmp_path):
    data = initial()
    data["rationale"] = "<script>alert('bad')</script>"
    post(case, "initial", data)
    workbench.report(case[0].store, case[2], tmp_path / "report.html")
    report = (tmp_path / "report.html").read_text()
    assert "<script>" not in report and "&lt;script&gt;" in report


def test_cli_workbench_schema_is_discoverable():
    result = subprocess.run([sys.executable, "-m", "vorhersage", "schema", "workbench_plan"], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert "higher_if" in json.loads(result.stdout)["data"]["required"]


def test_complete_cli_walkthrough_preserves_opening_target_and_evidence(tmp_path):
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "walkthrough"
    result = subprocess.run([sys.executable, str(root / "examples/market_workbench/walkthrough.py"), str(output)],
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    summary = json.loads((output / "summary.json").read_text())
    assert summary["doctor"]["ok"]
    assert summary["comparison"]["target"]["midpoint"] == pytest.approx(.7)
    assert summary["comparison"]["followup_quote"]["midpoint"] == pytest.approx(.74)
    assert [r["probability"] for r in summary["comparison"]["rows"]] == [.5, .72, .65]
    assert "70.0%" not in (output / "before-reveal.html").read_text()
    assert "70.0%" in (output / "comparison.html").read_text()
    assert "registry records a final operating permit" in (output / "comparison.html").read_text()


def test_prospective_comparison_and_network_failure_preserve_baseline(tmp_path, monkeypatch):
    w = Workflow(tmp_path / "research")
    w.store.init("Live-adapter test")
    ref = w.question({"id": "live", "text": "Will X happen?", "yes": "X occurs", "no": "X does not occur",
                      "void": "Disputed", "event_deadline": "2099-01-01T00:00:00Z", "resolve_after": "2099-01-01T00:00:00Z",
                      "resolution_source": "Registry", "event_group": "live", "domain": "other", "profile": "general", "kind": "real"})
    spec = {"question": ref, "venue": "kalshi", "market_id": "DEMO", "mode": "prospective", "method": "Test",
            "eligibility_rationale": "Unresolved", "contract_match_rationale": "Exact same event"}
    monkeypatch.setattr(market_data, "snapshot", lambda *args: snapshot())
    vault = tmp_path / "evaluator"
    opened = workbench.start(w.store, spec, vault)
    case = w, vault, opened["case_id"], spec
    post(case, "initial", initial())
    post(case, "finish", finish())
    def unavailable(*args):
        raise Error("market_fetch_failed", "Public GET unavailable")
    monkeypatch.setattr(market_data, "snapshot", unavailable)
    data = workbench.reveal(w.store, opened["case_id"], vault)["comparison"]
    assert data["eligible_for_blind_comparison"]
    assert "unavailable" in data["followup_error"]
    assert data["target"]["midpoint"] == pytest.approx(.7)
    assert data["followup_quote"] is None


def test_deadline_during_research_can_be_closed_without_issuing_a_late_checkpoint(case, monkeypatch):
    w, vault, cid, _ = case
    post(case, "initial", initial())
    post(case, "plan", plan())
    monkeypatch.setattr(workbench, "now", lambda: "2099-01-02T00:00:00Z")
    with pytest.raises(Error, match="deadline"):
        post(case, "checkpoint", checkpoint())
    payload = finish()
    payload["outcome_status"] = "uncertain"
    post(case, "finish", payload)
    data = workbench.reveal(w.store, cid, vault, skip_refresh=True)["comparison"]
    assert not data["eligible_for_blind_comparison"]
    assert len(data["rows"]) == 1


def test_future_evidence_and_future_exposure_are_rejected(case):
    w, _, cid, _ = case
    post(case, "initial", initial())
    post(case, "plan", plan())
    future = (time(now()) + timedelta(days=1)).isoformat()
    future_packet = capture_bundle({
        "sources": [{"id": "s", "url": "https://example.invalid", "title": "Future", "excerpt": "Text", "retrieved_at": future}],
        "findings": [{"id": "f", "claim": "Future claim", "claim_type": "observation", "source_ids": ["s"]}],
        "information_as_of": future, "limitations": []})
    with pytest.raises(Error, match="future-dated"):
        w.import_packet(future_packet)
    # Older releases admitted future packets; checkpoint validation still guards
    # such a record if it is present in a pre-existing project.
    with w.store.connect(True) as c:
        packet_id = workbench.Store.put(c, "packet", future_packet)
    with pytest.raises(Error, match="cutoff"):
        post(case, "checkpoint", checkpoint(refs=[{"packet_id": packet_id, "record_id": "f"}]))
    with pytest.raises(Error, match="future"):
        post(case, "exposure", {"kind": "outcome", "description": "Future event", "occurred_at": future})


def test_wrong_evaluator_cannot_substitute_a_target(case, tmp_path):
    w, _, cid, _ = case
    post(case, "initial", initial())
    post(case, "finish", finish())
    wrong = workbench.Store(tmp_path / "wrong-vault")
    wrong.init("Wrong target")
    public = workbench.status(w.store, cid)
    with wrong.connect(True) as c:
        workbench.Store.put(c, "market_target", {"case_id": cid, "baseline": snapshot(bid=.1, ask=.12)}, id=public["target_id"])
    with pytest.raises(Error, match="commitment"):
        workbench.reveal(w.store, cid, wrong.root, skip_refresh=True)
    assert workbench.status(w.store, cid)["state"] == "sealed"
