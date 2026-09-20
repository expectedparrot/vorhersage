"""Synthetic protocol tests; no tournament outcomes or network requests."""

import copy
import importlib.util
import io
import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from vorhersage.common import Error, load
from vorhersage.store import Store
from vorhersage.workflow import Workflow

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples/metaculus_cup_summer_2026/experiment.py"
spec = importlib.util.spec_from_file_location("cup_experiment", SCRIPT)
cup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cup)


def test_acquisition_requires_token_and_sends_correct_header():
    with patch.dict("os.environ", {"METACULUS_API_TOKEN": "", "METACULUS_API_KEY": ""}), patch.object(cup, "urlopen") as network:
        with pytest.raises(Error, match="All API requests require authentication"):
            cup.get("posts/1/")
        network.assert_not_called()
    with patch.dict("os.environ", {"METACULUS_API_TOKEN": "test-token"}), patch.object(cup, "urlopen") as network:
        network.return_value = io.BytesIO(b'{"id": 1}')
        assert cup.get("posts/1/") == {"id": 1}
        assert network.call_args.args[0].get_header("Authorization") == "Token test-token"
    with patch.dict("os.environ", {"METACULUS_API_TOKEN": "", "METACULUS_API_KEY": "alias-token"}), patch.object(cup, "urlopen") as network:
        network.return_value = io.BytesIO(b'{"id": 1}')
        cup.get("posts/1/")
        assert network.call_args.args[0].get_header("Authorization") == "Token alias-token"


def test_feed_acquisition_keeps_raw_pages_and_uses_documented_pagination(tmp_path):
    responses = [{"id": 33021}, {"results": [post()], "next": "ignored"}, {"results": []}]
    with patch.object(cup, "get", side_effect=responses) as get:
        result = cup.acquire(tmp_path / "cohort", feed_only=True)
    assert result["inventory_posts"] == 1
    paths = [call.args[0] for call in get.call_args_list]
    assert "tournaments=metaculus-cup-summer-2026" in paths[1]
    assert "include_descriptions=true" in paths[1]
    assert "order_by=published_at" in paths[1]
    assert "offset=100" in paths[2]
    assert len(load(tmp_path / "cohort/evaluator/feed_pages.json")) == 2


def post(pid=1):
    return {"id": pid, "title": f"Will fictional device {pid} ship before August 2026?",
            "description": "OUTCOME_LEAK", "comments": ["OUTCOME_LEAK"],
            "question": {"type": "binary", "open_time": "2026-05-04T17:00:00Z",
                         "resolution_criteria": "A documented shipment before August 1.",
                         "fine_print": "CURRENT_EDIT_LEAK", "resolution": "yes",
                         "actual_resolve_time": "2026-08-02T12:00:00Z",
                         "actual_close_time": "2026-08-01T00:00:00Z",
                         "aggregations": {"latest": "CROWD_LEAK"}}}


def prepared(tmp_path, protocol=None):
    protocol = protocol or load(SCRIPT.parent / "protocol.json")
    cohort, out = tmp_path / "cohort", tmp_path / "frozen"
    cup.import_posts([post(1), post(2), {"id": 3, "title": "Numeric", "question": {"type": "numeric"}}], cohort)
    review = load(cohort / "review.json")
    for pid in ("1", "2"):
        review[pid].update(approved=True, audit_note="Synthetic historical wording fixture.",
                           no="No qualifying shipment.", void="Invalid source resolution.",
                           event_deadline="2026-08-01T00:00:00Z", resolve_after="2026-08-02T00:00:00Z")
    (cohort / "review.json").write_text(json.dumps(review))
    cup.prepare(cohort, out, protocol)
    return out, protocol


def test_review_required_no_empty_cohort_or_overwrite(tmp_path):
    cohort = tmp_path / "cohort"
    cup.import_posts([post()], cohort)
    with pytest.raises(Error, match="fresh directory"):
        cup.import_posts([post()], cohort)
    with pytest.raises(Error, match="No eligible reviewed"):
        cup.prepare(cohort, tmp_path / "frozen", load(SCRIPT.parent / "protocol.json"))
    assert not (tmp_path / "frozen").exists()


def test_prepare_allowlist_cutoff_and_unsupported_inventory(tmp_path):
    out, _ = prepared(tmp_path)
    cases = load(out / "agent/cases.json")
    text = json.dumps(cases)
    for forbidden in ("OUTCOME_LEAK", "CROWD_LEAK", "CURRENT_EDIT_LEAK", '"resolution"', '"outcome"'):
        assert forbidden not in text
    assert len(cases["cases"]) == 2
    assert cases["cases"][0]["information_as_of"] == "2026-05-11T17:00:00+00:00"
    assert load(out / "evaluator/labels.json")["labels"][0]["outcome"] == 1
    assert load(out / "manifest.json")["exclusions"][0]["reason"] == "unsupported_question_type"


def test_shared_project_pins_cutoff_domains_and_budget_even_on_failure(tmp_path):
    protocol = load(SCRIPT.parent / "protocol.json")
    protocol["research"]["max_searches_per_case"] = 1
    out, protocol = prepared(tmp_path, protocol)
    args = Namespace(action="start", cases=out / "agent/cases.json", case="metaculus_1", project=tmp_path / "project")
    first = cup.run_case(args, protocol)
    args.case = "metaculus_2"
    cup.run_case(args, protocol)
    with Store(args.project).connect() as c:
        run, _, _ = Store.run(c, first["run_id"])
        assert run["cutoff_policy"] == "fixed" and run["mode"] == "retrospective"
        assert run["research_effort"] == "deep"
    args.action, args.query, args.case = "search", "device plans", "metaculus_1"
    with patch.dict("os.environ", {"EXA_API_KEY": "test"}), patch("vorhersage.research.urlopen") as network:
        network.return_value = io.BytesIO(json.dumps({"results": []}).encode())
        cup.run_case(args, protocol)
        payload = json.loads(network.call_args.args[0].data)
        assert payload["contents"]["snapshotAsOf"] == "2026-05-11T17:00:00+00:00"
        assert payload["excludeDomains"] == ["metaculus.com"]
        with pytest.raises(Error, match="budget exhausted"):
            cup.run_case(args, protocol)
        network.assert_called_once()
        args.case = "metaculus_2"
        network.side_effect = TimeoutError()
        with pytest.raises(Error, match="request failed"):
            cup.run_case(args, protocol)
        with pytest.raises(Error, match="budget exhausted"):
            cup.run_case(args, protocol)
        assert network.call_count == 2
    args.action, args.url = "fetch", "https://www.metaculus.com/questions/1/"
    with pytest.raises(Error, match="excluded"):
        cup.run_case(args, protocol)
    changed = copy.deepcopy(protocol)
    changed["cutoff"]["days"] = 8
    with pytest.raises(Error, match="Protocol changed"):
        cup.run_case(args, changed)
    assert Workflow(args.project).doctor()["ok"]


def test_live_sources_cannot_be_smuggled_into_snapshot_packet(tmp_path):
    from vorhersage import research
    project = tmp_path / "project"
    Store(project).init("test")
    with patch.dict("os.environ", {"EXA_API_KEY": "test"}), patch("vorhersage.research.urlopen") as network:
        body = {"results": [{"url": "https://example.com", "text": "Content."}]}
        network.return_value = io.BytesIO(json.dumps(body).encode())
        historical = research.search(project, "x", snapshot_as_of="2026-05-01T00:00:00Z")
        network.return_value = io.BytesIO(json.dumps(body).encode())
        live = research.search(project, "x", include_content=True)
    ids = [r["sources"][0]["id"] for r in (historical, live)]
    findings = {"information_as_of": "2026-05-01T00:00:00Z", "limitations": [],
                "findings": [{"id": "a", "claim": "Content.", "claim_type": "reporting", "source_ids": ids}]}
    with pytest.raises(Error, match="after packet cutoff"):
        research.capture(project, [historical["id"], live["id"]], findings)
