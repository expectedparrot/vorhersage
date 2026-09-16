"""Deterministic model/tool worker fixture. Makes no model or network calls."""
import json
import sys
from datetime import datetime, timezone

from vorhersage.evidence import validate_packet


def answer(request):
    context = request["context"]
    tool = request.get("tool_request")
    if tool and request["action"] == "execute":
        return {"status": "waiting", "usage": None, "continuation": {"fixture_job_id": request["attempt_id"]},
                "raw_record": {"fixture": True}, "actions": []}
    actions = []
    usage = {"searches": int(bool(tool)), "model_calls": int(not tool), "cost_usd": .005 if tool else .01}
    if tool:
        assert request["continuation"]["fixture_job_id"] == request["attempt_id"]
        at = datetime.now(timezone.utc).isoformat()
        packet = {"schema_version": "vorhersage.evidence.v1", "kind": "manual", "information_as_of": at,
                  "created_at": at, "limitations": ["Synthetic fixture, not a fetched page."],
                  "records": [{"id": "status", "claim": "Fictional readiness observation", "value": True,
                               "entity_ids": [], "observed_at": at, "provenance": {"synthetic": True},
                               "sources": [{"id": "fixture", "url": tool["arguments"]["url"], "title": "Fictional report",
                                            "excerpt": "The fictional factory is ready.", "retrieved_at": at}]}]}
        packet_id = "pkt_" + validate_packet(packet)["sha256"][:24]
        actions = [{"kind": "capture", "payload": packet}, {"kind": "research", "payload": {
            "attempt_id": request["attempt_id"], "tool": "read_page", "ok": True, "url": tool["arguments"]["url"],
            "evidence_refs": [{"packet_id": packet_id, "record_id": "status"}], "note": "Synthetic receipt for runner validation."}}]
    elif not context["research_receipts"]:
        actions = [{"kind": "tool_request", "payload": {"request_id": "research-1", "tool": "read_page", "arguments": {"url": "urn:fixture:readiness"}}}]
    else:
        refs = context["research_receipts"][0]["evidence_refs"]
        spec = context["specification"]
        p = request["worker_config"]["probability"]
        actions = [{"kind": "assessment", "payload": {"domain": "readiness", "disposition": "assessed",
                    "rationale": "The synthetic packet establishes readiness in this fixture.", "evidence_refs": refs}},
                   {"kind": "observation", "payload": {"requirement_id": "fixture", "actual": {"network_calls": 0},
                    "basis": "worker_reported", "failed": False, "note": "Deterministic fixture", "evidence_refs": []}},
                   {"kind": "submit", "payload": {"cells": [{**q, "condition_id": cond, "probability": p,
                    "evidence_refs": refs} for q in spec["questions"] for cond in spec["condition_ids"]], "raw_record": {"fixture": True}}},
                   {"kind": "finalize", "payload": {"rationale": "Complete synthetic session"}}]
    return {"status": "completed", "usage": usage, "continuation": {}, "raw_record": {"fixture": True}, "actions": actions}


if __name__ == "__main__":
    print(json.dumps(answer(json.load(sys.stdin))))
