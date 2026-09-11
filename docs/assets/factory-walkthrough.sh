#!/usr/bin/env bash
# Fictional documentation walkthrough; no network or model calls.
set -euo pipefail

forecast_project=$(mktemp -d "${TMPDIR:-/tmp}/vorhersage-guide.XXXXXX")
vf() { vorhersage --project "$forecast_project" "$@"; }
json_field() {
  python -c 'import json,sys; print(json.load(sys.stdin)["data"][sys.argv[1]])' "$1"
}
forecast_time() {
  python -c 'import sys; from datetime import datetime,timedelta,timezone; print((datetime.now(timezone.utc)+timedelta(days=float(sys.argv[1]))).isoformat())' "${1:-0}"
}
forecast_deadline=$(forecast_time 1)
forecast_review=$(forecast_time 0.5)
vf init --name "Factory tutorial"
printf 'Study directory: %s\n' "$forecast_project"

vf question add --from - <<JSON
{
  "id": "factory_east",
  "text": "Will fictional factory East ship by tomorrow?",
  "yes": "A qualifying shipment is recorded by the deadline.",
  "no": "No qualifying shipment occurs by the deadline.",
  "void": "The fictional event is withdrawn.",
  "event_deadline": "$forecast_deadline",
  "resolve_after": "$forecast_deadline",
  "resolution_source": "urn:vorhersage:fictional:dispatch",
  "event_group": "factory_east",
  "domain": "operations",
  "profile": "general",
  "kind": "simulation"
}
JSON

vf research capture --from - > "$forecast_project/packet.json" <<JSON
{
  "sources": [{
    "id": "initial",
    "url": "urn:vorhersage:fictional:initial",
    "title": "Fictional factory status",
    "excerpt": "Preparation is underway; dispatch remains uncertain.",
    "retrieved_at": "$(forecast_time)"
  }],
  "findings": [{
    "id": "readiness",
    "claim": "Preparation is underway; dispatch remains uncertain.",
    "claim_type": "observation",
    "source_ids": ["initial"]
  }],
  "limitations": ["Entirely fictional tutorial evidence."]
}
JSON
forecast_packet=$(json_field packet_id < "$forecast_project/packet.json")
vf packet show "$forecast_packet"
vf packet audit "$forecast_packet"

vf run start --from - > "$forecast_project/run.json" <<JSON
{
  "question_id": "factory_east",
  "question_version": 1,
  "forecaster": "agent:tutorial",
  "method": "fictional researched judgment",
  "mode": "simulation",
  "information_as_of": "$(forecast_time)",
  "research_status": "completed",
  "max_searches": 0,
  "max_extra_tasks": 0
}
JSON
forecast_run=$(json_field run_id < "$forecast_project/run.json")
vf next --run "$forecast_run"

submit_payload() {
  vf next --run "$forecast_run" > "$forecast_project/next.json"
  python -c '
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
step = json.loads((root / "next.json").read_text())["data"]
payload = json.load(sys.stdin)
(root / (step["task"]["kind"] + ".json")).write_text(json.dumps(payload))
print(json.dumps({
    "task_id": step["task"]["id"],
    "expected_revision": step["revision"],
    "idempotency_key": step["task"]["id"],
    "payload": payload,
    "usage": {"searches": 0, "cost_usd": 0, "model_calls": 0}
}))
' "$forecast_project" | vf submit --run "$forecast_run" --from -
}

submit_payload <<'JSON'
{
  "method": "judgment",
  "probability": 0.5,
  "rationale": "An assumed neutral starting point for this fixture.",
  "limitations": ["Not an empirical base rate or a blind prior."],
  "evidence_refs": []
}
JSON

submit_payload <<JSON
{
  "drivers": [{
    "name": "Readiness",
    "mechanism": "Dispatch needs a ready production line.",
    "evidence_refs": [{"packet_id": "$forecast_packet", "record_id": "readiness"}]
  }],
  "yes_path": "Preparation finishes and a shipment is dispatched.",
  "no_path": "A remaining dependency blocks dispatch past the deadline.",
  "unknowns": ["Time needed to finish preparation."]
}
JSON

for forecast_domain in base_rates current_state actors_and_process contrary_evidence; do
  submit_payload <<JSON
{
  "disposition": "assessed",
  "interpretation": "The fictional readiness report informs this review; it does not settle the timing.",
  "evidence_refs": [{"packet_id": "$forecast_packet", "record_id": "readiness"}],
  "sources_checked": ["Fictional factory status"],
  "unknowns": ["No additional fixture evidence for $forecast_domain."],
  "conflicts": []
}
JSON
done

submit_payload <<JSON
{
  "method": "judgment",
  "probability": 0.4,
  "rationale": "Preparation is unfinished; this fixture assigns a substantial chance of delay.",
  "limitations": ["Authored fictional probability; not fitted from data."],
  "evidence_refs": [{"packet_id": "$forecast_packet", "record_id": "readiness"}]
}
JSON
submit_payload <<'JSON'
{
  "decision": "retain",
  "rationale": "Retain the estimate after checking both directions.",
  "objections": [
    {"direction": "too_high", "objection": "Dispatch could fail after preparation.", "response": "The estimate allows substantial failure risk."},
    {"direction": "too_low", "objection": "Preparation might finish quickly.", "response": "Success is plausible but remains uncertain."}
  ],
  "evidence_refs": []
}
JSON

submit_payload <<JSON
{
  "stopping_reason": "The available fictional evidence has been reviewed.",
  "review_at": "$forecast_review",
  "triggers": [{"description": "A new report about factory readiness.", "evidence_refs": []}]
}
JSON
forecast_first=$(vf next --run "$forecast_run" | json_field forecast_id)
vf forecast show "$forecast_first"
vf report --question factory_east --format markdown

vf research capture --from - > "$forecast_project/update.json" <<JSON
{
  "sources": [{
    "id": "update",
    "url": "urn:vorhersage:fictional:update",
    "title": "Fictional readiness update",
    "excerpt": "The remaining readiness dependency is now complete.",
    "retrieved_at": "$(forecast_time)"
  }],
  "findings": [{
    "id": "ready_now",
    "claim": "The remaining readiness dependency is now complete.",
    "claim_type": "observation",
    "source_ids": ["update"]
  }],
  "limitations": ["Entirely fictional tutorial evidence."]
}
JSON
forecast_update=$(json_field packet_id < "$forecast_project/update.json")
vf signal --from - <<JSON
{
  "question_id": "factory_east",
  "reason": "A fictional readiness dependency was completed.",
  "idempotency_key": "factory-readiness-update",
  "evidence_refs": [{"packet_id": "$forecast_update", "record_id": "ready_now"}]
}
JSON
vf monitor

vf run start --from - > "$forecast_project/revision.json" <<JSON
{
  "question_id": "factory_east",
  "question_version": 1,
  "forecaster": "agent:tutorial",
  "method": "fictional researched judgment",
  "mode": "simulation",
  "information_as_of": "$(forecast_time)",
  "research_status": "completed",
  "previous_forecast_id": "$forecast_first",
  "max_searches": 0,
  "max_extra_tasks": 0
}
JSON
forecast_run=$(json_field run_id < "$forecast_project/revision.json")
python - "$forecast_project" "$forecast_update" <<'PYTHON'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
new_ref = {"packet_id": sys.argv[2], "record_id": "ready_now"}
for kind in ("research", "assessment"):
    path = root / (kind + ".json")
    payload = json.loads(path.read_text())
    payload["evidence_refs"].append(new_ref)
    if kind == "research":
        payload["interpretation"] = "Readiness has improved; dispatch still carries execution risk."
        payload["sources_checked"].append("Fictional readiness update")
        payload["unknowns"] = ["Remaining dispatch risk."]
    else:
        payload["probability"] = 0.75
        payload["rationale"] = "The completed dependency supports a higher fictional estimate."
    path.write_text(json.dumps(payload))
PYTHON
for forecast_task in prior drivers research research research research assessment review issue; do
  submit_payload < "$forecast_project/$forecast_task.json"
done
vf report --question factory_east --format markdown

vf research capture --from - > "$forecast_project/outcome.json" <<JSON
{
  "sources": [{
    "id": "shipment",
    "url": "urn:vorhersage:fictional:shipment",
    "title": "Fictional dispatch record",
    "excerpt": "A qualifying shipment occurred before the deadline.",
    "retrieved_at": "$(forecast_time)"
  }],
  "findings": [{
    "id": "shipment_occurred",
    "claim": "A qualifying shipment occurred before the deadline.",
    "claim_type": "observation",
    "source_ids": ["shipment"]
  }],
  "limitations": ["Entirely fictional tutorial evidence."]
}
JSON
forecast_outcome=$(json_field packet_id < "$forecast_project/outcome.json")
vf resolve --from - <<JSON
{
  "question_id": "factory_east",
  "question_version": 1,
  "outcome": "yes",
  "reason": "The fictional dispatch record meets the YES criterion.",
  "known_at": "$(forecast_time)",
  "evidence_refs": [{"packet_id": "$forecast_outcome", "record_id": "shipment_occurred"}],
  "previous_resolution_id": null,
  "idempotency_key": "resolve-factory-east"
}
JSON

vf evaluate --from - > "$forecast_project/evaluation.json" <<JSON
{
  "question_versions": [{"question_id": "factory_east", "version": 1}],
  "forecasters": ["agent:tutorial"],
  "cutoff": "$(forecast_time)",
  "resolution_as_of": "$(forecast_time)",
  "mode": "simulation"
}
JSON
python - "$forecast_project/evaluation.json" <<'PYTHON'
import json, sys
report = json.load(open(sys.argv[1]))["data"]
print(json.dumps(report["summaries"], indent=2))
PYTHON
vf doctor
