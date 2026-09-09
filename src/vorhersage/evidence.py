"""Portable evidence snapshots. Epiq remains the shared research store."""

import copy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .common import canonical, digest, now, require, time
from .schemas import check


def validate_packet(value):
    check(value, "packet")
    packet = copy.deepcopy(value)
    supplied = packet.pop("sha256", None)
    require(supplied is None or supplied == digest(packet), "Evidence packet hash mismatch.", "integrity_error")
    cutoff = time(packet["information_as_of"])
    require(len({r["id"] for r in packet["records"]}) == len(packet["records"]), "Duplicate evidence record IDs.")
    for record in packet["records"]:
        require(time(record["observed_at"]) <= cutoff, "Evidence observation is after packet cutoff.")
        for source in record["sources"]:
            require(time(source["retrieved_at"]) <= cutoff, "Source retrieval is after packet cutoff.")
        if packet["kind"] == "epiq":
            provenance = record["provenance"]
            require(provenance.get("project_id") == packet["epiq"]["project"]["project_id"], "Epiq project identity mismatch.")
            lineage = provenance.get("lineage", [])
            values = record["value"] if provenance.get("cardinality") == "many" else [record["value"]]
            require(isinstance(values, list) and bool(lineage)
                    and all(x.get("claim_id") and x.get("evidence_id") and x.get("value") in values for x in lineage)
                    and {canonical(x["value"]) for x in lineage} == {canonical(x) for x in values}, "Missing or inconsistent Epiq lineage.")
            if "assertion_events" in provenance:
                assertions = {e["payload"]["claim_id"]: e for e in provenance["assertion_events"]}
                require({x["claim_id"] for x in lineage} <= set(assertions), "Missing Epiq assertion recording times.")
                for link in lineage:
                    event = assertions[link["claim_id"]]
                    require(time(event["recorded_at"]) <= time(packet["epiq"]["known_at"]), "Epiq assertion is after the recording cutoff.")
                    require(event["payload"]["value"] == link["value"], "Epiq assertion differs from projected lineage.")
    packet["sha256"] = digest(packet)
    return packet


class Epiq:
    def __init__(self, db, source=None):
        self.db = Path(db).resolve()
        self.source = Path(source).resolve() if source else None

    def call(self, *args):
        env = os.environ.copy()
        prefix = ["epiq"]
        if self.source:
            require((self.source / "epiq/__main__.py").is_file(), "--epiq-source must point to Epiq's src directory.")
            env["PYTHONPATH"] = str(self.source)
            prefix = [sys.executable, "-m", "epiq"]
        p = subprocess.run([*prefix, "--db", str(self.db), *args], text=True, capture_output=True, timeout=60, env=env)
        require(p.returncode == 0, "Epiq failed: " + (p.stderr or p.stdout), "epiq_error")
        result = json.loads(p.stdout)
        require(result.get("schema_version") == "1.0" and result.get("status") == "ok", "Unsupported Epiq envelope.")
        return result["data"]

    def search(self, kind, text="", subject=None, question=None):
        table = self.call("matrix", "--kind", kind)
        return [{"kind": kind, "subject": row["name"], "subject_id": row["entity_id"],
                 "question": name, "cell": cell}
                for row in table["rows"] for name, cell in row["cells"].items()
                if (subject is None or subject in (row["name"], row["entity_id"]))
                and (question is None or name == question)
                and text.casefold() in canonical({"subject": row["name"], "question": name, "cell": cell}).casefold()]

    def freeze(self, selection):
        check(selection, "epiq_selection")
        known_at = selection.get("known_at", now())
        require(time(known_at) <= time(now()), "Epiq known_at cannot be in the future.")
        with tempfile.TemporaryDirectory(prefix="vorhersage-epiq-") as directory:
            snapshot = Path(directory) / "snapshot.sqlite"
            self.call("export", "--format", "sqlite", "--output-path", str(snapshot))
            frozen = Epiq(snapshot, self.source)
            project = frozen.call("schema")["project"]
            assertion_events = {e["payload"]["claim_id"]: e for e in frozen.call("history")
                                if e["event_type"] == "claim.assert"}
            tables = {}
            records = []
            for selected in selection["cells"]:
                kind = selected["kind"]
                if kind not in tables:
                    tables[kind] = frozen.call("matrix", "--kind", kind, "--known-at", known_at)
                rows = [r for r in tables[kind]["rows"] if selected["subject"] in (r["name"], r["entity_id"])]
                require(len(rows) == 1, "Missing or ambiguous Epiq subject: " + selected["subject"])
                row = rows[0]
                require(selected["question"] in row["cells"], "Unknown Epiq question.")
                cell = row["cells"][selected["question"]]
                require(cell["state"] == "Answered", "Reconcile Epiq cell before freezing: " + selected["subject"] + " / " + cell["state"])
                lineage = cell["lineage"]
                question_schema = next(q for q in tables[kind]["questions"] if q["name"] == selected["question"])
                cardinality = question_schema.get("definition", {}).get("cardinality", "one")
                sources = []
                def dated(value):
                    # Day-only dates are conservatively treated as available at day's end.
                    return value + "T23:59:59.999999Z" if len(value) == 10 else value
                for link in lineage:
                    source = link["source"]
                    sources.append({"id": link["evidence_id"], "url": source["url"],
                                    "title": source["title"], "excerpt": link["excerpt"],
                                    "retrieved_at": dated(source["retrieved_at"]),
                                    "published_at": source.get("published_at"), "origin_id": source["url"]})
                record_id = "cell_" + digest([project["project_id"], row["entity_id"], selected["question"]])[:20]
                records.append({"id": record_id, "claim": row["name"] + " / " + selected["question"],
                                "value": cell["values"] if cardinality == "many" else cell["value"], "entity_ids": [row["entity_id"]],
                                "observed_at": max((s["retrieved_at"] for s in sources), key=time),
                                "sources": sources, "provenance": {"project_id": project["project_id"],
                                "selection": selected, "lineage": lineage, "cardinality": cardinality,
                                "assertion_events": [assertion_events[id] for id in sorted({x["claim_id"] for x in lineage})]}})
            return validate_packet({"schema_version": "vorhersage.evidence.v1", "kind": "epiq",
                                    "information_as_of": selection["information_as_of"], "created_at": now(),
                                    "records": records, "epiq": {"project": project, "known_at": known_at,
                                    "version": frozen.call("version"), "selection": selection},
                                    "limitations": ["Import/recording times do not prove historical public availability.",
                                    "Day-only retrieval dates use end of day; shared URLs do not establish all source dependencies."]})

    def changes(self, packet):
        require(packet["kind"] == "epiq", "Change checking requires an Epiq packet.")
        # Refresh at today's information and recording cutoffs, retaining selected cells.
        selection = {"cells": packet["epiq"]["selection"]["cells"], "information_as_of": now()}
        # A contested/retracted cell should be reported rather than preventing other comparisons.
        with tempfile.TemporaryDirectory(prefix="vorhersage-check-") as directory:
            snapshot = Path(directory) / "snapshot.sqlite"
            self.call("export", "--format", "sqlite", "--output-path", str(snapshot))
            client = Epiq(snapshot, self.source)
            require(client.call("schema")["project"]["project_id"] == packet["epiq"]["project"]["project_id"], "Epiq project does not match packet.")
            changes = []
            for old in packet["records"]:
                selected = old["provenance"]["selection"]
                cells = client.search(selected["kind"], subject=selected["subject"], question=selected["question"])
                current = cells[0]["cell"] if len(cells) == 1 else {"state": "Missing"}
                old_claims = sorted({x["claim_id"] for x in old["provenance"]["lineage"]})
                new_claims = sorted({x["claim_id"] for x in current.get("lineage", [])})
                current_value = current.get("values") if old["provenance"].get("cardinality") == "many" else current.get("value")
                if current["state"] != "Answered" or current_value != old["value"] or old_claims != new_claims:
                    changes.append({"record_id": old["id"], "selection": selected, "state": current["state"],
                                    "previous_claim_ids": old_claims, "current_claim_ids": new_claims})
            return {"changes": changes, "checked_at": now(), "selection": selection,
                    "limitations": ["Checks selected cells only; newly relevant subjects require research or a question-level signal."]}
