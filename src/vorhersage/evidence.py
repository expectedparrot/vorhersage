"""Portable evidence snapshots. Epiq remains the shared research store."""

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .common import canonical, digest, now, require, time
from .schemas import check


def capture_finding(claim, *, url=None, title, excerpt, claim_type="reporting", observed_at=None,
                    inference_rationale=None, source_kind="public", attribution=None, message_ref=None):
    """Capture supplied text now. This does not claim to fetch or verify its source."""
    source = {"id": "source", "kind": source_kind, "access": "public" if source_kind == "public" else "private"}
    source.update({k: v for k, v in {"url": url, "attribution": attribution, "message_ref": message_ref}.items() if v is not None})
    captured = now()
    observed = observed_at or captured
    require(time(observed) <= time(captured), "An observation cannot be later than the current capture time.")
    require(claim_type != "inference" or inference_rationale,
            "An inference needs --inference-rationale explaining how the passage supports the claim.")
    return validate_packet({"schema_version": "vorhersage.evidence.v1", "kind": "manual",
                           "information_as_of": captured, "created_at": captured,
                           "limitations": ["Manually supplied finding; source text and interpretation are not independently verified."],
                           "records": [{"id": "finding", "claim": claim, "claim_type": claim_type,
                                        "value": excerpt, "entity_ids": [], "observed_at": observed,
                                        "claim_support": [{"source_id": "source", "passage": excerpt,
                                                           "relation": "inference" if claim_type == "inference" else "direct",
                                                           "rationale": inference_rationale or "Source passage supplied for this single claim."}],
                                        **({"inference_rationale": inference_rationale} if inference_rationale else {}),
                                        "provenance": {"adapter": "vorhersage.evidence_add.v1", "recorded_at": captured},
                                        "sources": [{**source, "title": title,
                                                     "excerpt": excerpt, "excerpt_kind": "paraphrase",
                                                     "retrieved_at": captured,
                                                     "capture": {"method": "manual", "captured_at": captured}}]}]})


def validate_packet(value):
    check(value, "packet")
    packet = copy.deepcopy(value)
    supplied = packet.pop("sha256", None)
    require(supplied is None or supplied == digest(packet), "Evidence packet hash mismatch.", "integrity_error")
    cutoff = time(packet["information_as_of"])
    require(len({r["id"] for r in packet["records"]}) == len(packet["records"]), "Duplicate evidence record IDs.")
    ids = {r["id"] for r in packet["records"]}
    links = set()
    for link in packet.get("relationships", []):
        require(link["from_record"] in ids and link["to_record"] in ids, "Evidence relationship references an unknown record.")
        require(link["from_record"] != link["to_record"], "Evidence relationships cannot be self-links.")
        signature = (link["from_record"], link["to_record"], link["relation"])
        require(signature not in links, "Duplicate evidence relationship.")
        links.add(signature)
    for record in packet["records"]:
        require(time(record["observed_at"]) <= cutoff, "Evidence observation is after packet cutoff.")
        sources = {s["id"]: s for s in record["sources"]}
        require(not record.get("claim_support") or len(sources) == len(record["sources"]),
                "Claim support needs unambiguous source IDs within the finding.")
        for support in record.get("claim_support", []):
            require(support["source_id"] in sources, "Claim support references an unknown source.")
            source = sources[support["source_id"]]
            text = source.get("capture", {}).get("content", source["excerpt"])
            require(support["passage"] in text, "Claim support passage must occur in the supplied excerpt or captured content.")
            require(record.get("claim_type") != "inference" or support["relation"] == "inference",
                    "Inference findings must label their support as inference.")
        if record.get("claim_support") and record.get("claim_type") == "inference":
            require(record.get("inference_rationale"), "Inference findings need an inference_rationale.")
        for source in record["sources"]:
            if source.get("kind", "public") == "public":
                require(source.get("url"), "Public sources require a URL.")
                require(source.get("access", "public") == "public", "Private sources need an explicit private kind.")
            else:
                require(source.get("attribution") and source.get("access") == "private",
                        "Private sources require attribution and private access.")
            capture = source.get("capture", {})
            if capture.get("method") == "exa_snapshot":
                require(capture.get("snapshot_as_of") and capture.get("content") and capture.get("captured_at"),
                        "Exa snapshot requires a cutoff, content, and actual capture time.")
                require(capture.get("metadata", {}).get("provider") == "exa"
                        and capture.get("metadata", {}).get("retrieval_id"), "Exa snapshot requires retrieval provenance.")
                require(time(capture["snapshot_as_of"]) <= cutoff, "Snapshot is after packet cutoff.")
                require(time(capture["snapshot_as_of"]) <= time(source["retrieved_at"])
                        <= time(packet["created_at"]), "Invalid snapshot retrieval chronology.")
            else:
                require("snapshot_as_of" not in capture, "Snapshot cutoff requires exa_snapshot capture.")
                require(time(source["retrieved_at"]) <= cutoff, "Source retrieval is after packet cutoff.")
            if capture.get("captured_at"):
                require(time(capture["captured_at"]) <= time(source["retrieved_at"]), "Capture time is after retrieval.")
            if capture.get("method") == "fetched":
                require(capture.get("content") and capture.get("captured_at"), "Fetched capture requires content and a capture time.")
            if capture.get("method") == "discovery":
                require("content" not in capture and "content_sha256" not in capture,
                        "Discovery metadata cannot claim a captured page body.")
            if "content" in capture:
                computed = hashlib.sha256(capture["content"].encode()).hexdigest()
                require(capture.get("content_sha256") == computed, "Captured content hash mismatch.")
                if source.get("excerpt_kind") == "quotation":
                    require(source["excerpt"] in capture["content"], "Quoted excerpt does not occur in captured content.")
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


def fingerprint(packet):
    """Substance identity for polling; fresh retrieval timestamps alone are not news."""
    records = copy.deepcopy(packet["records"])
    for record in records:
        record.pop("observed_at", None)
        for source in record["sources"]:
            source.pop("retrieved_at", None)
            source.get("capture", {}).pop("captured_at", None)
        record["sources"].sort(key=lambda s: canonical(s))
    return digest({"records": sorted(records, key=lambda r: r["id"]),
                   "relationships": sorted(packet.get("relationships", []), key=canonical)})


def capture_bundle(spec):
    """Normalize source-linked findings from any research provider, without retyping sources."""
    check(spec, "research_bundle")
    sources = {s["id"]: copy.deepcopy(s) for s in spec["sources"]}
    require(len(sources) == len(spec["sources"]), "Research source IDs must be unique.")
    for s in sources.values():
        capture = s.get("capture", {})
        if "content" in capture and "content_sha256" not in capture:
            capture["content_sha256"] = hashlib.sha256(capture["content"].encode()).hexdigest()
    records = []
    for f in spec["findings"]:
        require(set(f["source_ids"]) <= set(sources), "Finding references an unknown source.")
        selected = [sources[id] for id in dict.fromkeys(f["source_ids"])]
        records.append({"id": f["id"], "claim": f["claim"], "claim_type": f["claim_type"],
                        **{k: f[k] for k in ("claim_support", "inference_rationale") if k in f},
                        "value": f.get("value"), "entity_ids": f.get("entity_ids", []),
                        "sources": selected, "observed_at": max((
                            s["capture"]["snapshot_as_of"] if s.get("capture", {}).get("method") == "exa_snapshot"
                            else s["retrieved_at"] for s in selected), key=time),
                        "provenance": {"adapter": "vorhersage.research_bundle.v1", "recorded_at": now()}})
    return validate_packet({"schema_version": "vorhersage.evidence.v1", "kind": "manual",
                            "information_as_of": spec.get("information_as_of", now()), "created_at": now(),
                            "records": records, "relationships": spec.get("relationships", []),
                            "limitations": spec["limitations"]})


def audit(packet):
    """Expose dependence and missing provenance without inventing likelihood ratios."""
    packet = validate_packet(packet)
    rows = {r["id"]: r for r in packet["records"]}
    parents = {id: id for id in rows}
    def root(id):
        while parents[id] != id:
            id = parents[id]
        return id
    def join(a, b):
        parents[root(a)] = root(b)
    origins = {}
    for id, r in rows.items():
        for s in r["sources"]:
            # Shared URL or explicit original-report ID establishes dependence,
            # not independence between all other sources.
            for origin in (s.get("url"), s.get("origin_id"), s.get("message_ref")):
                if origin:
                    if origin in origins:
                        join(id, origins[origin])
                    origins[origin] = id
    for link in packet.get("relationships", []):
        if link["relation"] == "repeats":
            join(link["from_record"], link["to_record"])
    groups = {}
    for id in rows:
        groups.setdefault(root(id), []).append(id)
    confirmations = [l for l in packet.get("relationships", []) if l["relation"] == "independently_confirms"]
    conflicts = [l for l in confirmations if root(l["from_record"]) == root(l["to_record"])]
    gaps = []
    for id, r in rows.items():
        if not r.get("claim_support"):
            gaps.append({"record_id": id, "missing": "claim_support"})
        if r.get("claim_type", "unknown") == "unknown":
            gaps.append({"record_id": id, "missing": "claim_type"})
        for s in r["sources"]:
            for field in ("published_at", "excerpt_kind", "capture"):
                if not s.get(field):
                    gaps.append({"record_id": id, "source_id": s["id"], "missing": field})
    return {"dependence_groups": sorted(sorted(g) for g in groups.values()),
            "declared_independent_confirmations": confirmations, "independence_conflicts": conflicts,
            "contradictions": [l for l in packet.get("relationships", []) if l["relation"] == "contradicts"],
            "inference_records": [id for id, r in rows.items() if r.get("claim_type") == "inference"],
            "provenance_gaps": gaps,
            "limitations": ["Distinct groups are not proven independent sources. Counts are not probability multipliers.",
                            "Capture integrity verifies supplied text, not its truth or its origin on the claimed website."]}


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
                                    "published_at": source.get("published_at"), "origin_id": source["url"],
                                    "capture": {"method": "epiq", "metadata": {
                                        "provenance": link.get("provenance", {}), "support": link.get("support", []),
                                        "review": link.get("review", {}), "source_type": source.get("source_type"),
                                        "locator": source.get("locator", {})}}})
                record_id = "cell_" + digest([project["project_id"], row["entity_id"], selected["question"]])[:20]
                records.append({"id": record_id, "claim": row["name"] + " / " + selected["question"],
                                "value": cell["values"] if cardinality == "many" else cell["value"], "entity_ids": [row["entity_id"]],
                                "observed_at": max((s["retrieved_at"] for s in sources), key=time),
                                "claim_type": "inference" if any(x.get("derivation") or x["source"].get("source_type") == "model" for x in lineage) else "unknown",
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
                previous_lineage = digest(old["provenance"]["lineage"])
                current_lineage = digest(current.get("lineage", []))
                if current["state"] != "Answered" or current_value != old["value"] or old_claims != new_claims or previous_lineage != current_lineage:
                    changes.append({"record_id": old["id"], "selection": selected, "state": current["state"],
                                    "previous_claim_ids": old_claims, "current_claim_ids": new_claims,
                                    "previous_lineage_sha256": previous_lineage, "current_lineage_sha256": current_lineage})
            return {"changes": changes, "checked_at": now(), "selection": selection,
                    "limitations": ["Checks selected cells only; newly relevant subjects require research or a question-level signal."]}


def citation_anchor(evidence_id):
    """Opaque stable report footnote, without exposing a private locator."""
    return "evidence-" + hashlib.sha256(evidence_id.encode()).hexdigest()[:16]
