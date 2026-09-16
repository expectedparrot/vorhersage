"""Offline, read-only question reports in HTML, LaTeX and JSON.

Both document renderers consume the same sections. External text is always data,
never HTML or TeX markup. Report attachments do not become forecast evidence.
"""

import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from .common import digest, now, require
from .store import Store


def question_data(store, question_id):
    from .workflow import Workflow
    from .workbench import status

    data = Workflow(store.root).report(question_id)
    with store.connect() as c:
        data["question_versions"] = [Store.question(c, question_id, r[0]) for r in c.execute(
            "SELECT version FROM questions WHERE id=? ORDER BY version", (question_id,))]
        runs = []
        for row in c.execute("SELECT id FROM runs ORDER BY rowid"):
            run, state, revision = Store.run(c, row[0])
            if run["question_id"] == question_id:
                runs.append({"run": run, "state": state, "revision": revision})
        data["runs"] = runs
        ids = {r["run"]["id"] for r in runs}
        pending = [r["id"] for r in c.execute("SELECT id,run_id FROM artifacts ORDER BY created_at,id")
                   if r["run_id"] in ids]
        pending += [aid for run in runs for aid in run["state"].get("artifact_ids", [])]
        pending += [f["id"] for f in data["forecasts"] + data["resolutions"]]
        artifacts = {}
        while pending:
            aid = pending.pop(0)
            if aid in artifacts:
                continue
            kind = c.execute("SELECT kind FROM artifacts WHERE id=?", (aid,)).fetchone()
            require(kind is not None, "Unknown report artifact: " + aid)
            # Never traverse a private evaluator target, even in a mixed project.
            require(kind[0] != "market_target", "Private market targets cannot be report inputs.")
            record = Store.artifact(c, aid)
            artifacts[aid] = {"kind": kind[0], "record": record}
            for linked, expected in record.get("input_manifest", {}).items():
                require(digest(Store.artifact(c, linked)) == expected,
                        "Report input integrity failure.", "integrity_error")
                pending.append(linked)
            pending.extend(ref["packet_id"] for ref in _refs(record))
            if record.get("timeline_model_id"):
                pending.append(record["timeline_model_id"])
        data["artifacts"] = artifacts
        case_ids = [r["id"] for r in Store.all(c, "workbench")
                    if r["specification"]["question"]["question_id"] == question_id]
    data["workbenches"] = [status(store, cid) for cid in case_ids]
    return data


def _refs(value):
    if isinstance(value, dict):
        if "packet_id" in value and "record_id" in value:
            yield value
        for item in value.values():
            yield from _refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from _refs(item)


def _label(key):
    return str(key).replace("_", " ").capitalize()


def _scalar(value):
    if value is None:
        return "Not recorded"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _percent(value):
    return f"{value:.1%}" if value is not None else "Not recorded"


def audit_sections(data):
    """Build readable sections without interpreting or inventing agent claims."""
    result = []

    def add(title, value=None, paragraphs=(), table=None):
        result.append({"title": title, "value": value, "paragraphs": list(paragraphs), "table": table})

    cases = [data] if "case_id" in data else data.get("workbenches", [])
    summary = []
    for case in cases:
        estimates = [e for e in case["journal"] if e["kind"] in ("initial", "checkpoint")]
        if estimates:
            summary.append(f"Workbench {case['case_id']}: latest estimate {_percent(estimates[-1]['payload']['probability'])}; {case['state']}.")
    for forecast in data.get("forecasts", [])[-1:]:
        summary.append(f"Most recently issued forecast: {_percent(forecast['probability'])} by {forecast['forecaster']}, question version {forecast['question_version']}, {forecast['issued_at']}. Other forecasters and versions are shown separately below.")
    add("Summary", paragraphs=summary or ["No predictions have been recorded."])
    add("Question and resolution", data["question"])
    if "question_versions" in data and len(data["question_versions"]) > 1:
        add("Question versions", data["question_versions"],
            ["Forecasts retain their original question version; different event definitions are not pooled."])
    if "forecasts" in data:
        add("Issued predictions", paragraphs=["Only formally issued forecasts appear here; workbench estimates are listed separately."],
            table=(["Issued at", "Version", "Forecaster", "Mode", "Probability", "Basis"], [
                [f["issued_at"], f["question_version"], f["forecaster"], f["mode"],
                 _percent(f["probability"]), f["probability_basis"]] for f in data["forecasts"]]))
        for f in data["forecasts"]:
            add("Issued forecast: " + f["id"], f)
        for run in data.get("runs", []):
            add("Workflow run: " + run["run"]["id"], run)
        for aid, artifact in data.get("artifacts", {}).items():
            if artifact["kind"] not in ("forecast", "packet", "resolution"):
                add("Research and model record: " + aid, artifact)
        add("Resolutions and scheduled reviews", {"resolutions": data["resolutions"], "due": data["due"]})

    for case in cases:
        journal = case["journal"]
        estimates = [e for e in journal if e["kind"] in ("initial", "checkpoint")]
        finish = next((e for e in journal if e["kind"] == "finish"), None)
        add("Workbench overview", {"case_id": case["case_id"], "state": case["state"],
            "question_version": case["question"]["version"],
            "method": case["specification"]["method"], "mode": case["specification"]["mode"],
            "latest_estimate": _percent(estimates[-1]["payload"]["probability"]) if estimates else "Not recorded",
            "sealed_at": finish["recorded_at"] if finish else None,
            "market_status": "Revealed" if case.get("comparison") else "Market target is hidden",
            "opening_target_captured_at": case["baseline_captured_at"]})
        add("Frozen contract and case selection", {"question": case["question"],
            "contract": case["contract"], "selection": case["specification"]})
        comparison = case.get("comparison")
        rows = comparison["rows"] if comparison else [
            {"label": e["kind"].title(), "probability": e["payload"]["probability"],
             "recorded_at": e["recorded_at"]} for e in estimates]
        headers = ["Stage", "Probability", "Recorded at"]
        if comparison:
            headers += ["Gap to opening market (pp)", "Squared market error", "Step improvement"]
        table_rows = []
        for row in rows:
            cells = [row["label"], _percent(row["probability"]), row["recorded_at"]]
            if comparison:
                improvement = row["improvement_from_previous"]
                cells += [f"{row['difference_pp']:+.2f}", f"{row['squared_market_error']:.6f}",
                          "Not applicable" if improvement is None else f"{improvement:+.6f}"]
            table_rows.append(cells)
        add("Prediction history", table=(headers, table_rows), paragraphs=[
            "Checkpoints are recorded judgments, not necessarily issued forecasts. All timestamps retain their recorded time zones."])
        if comparison:
            opening = comparison["target"]
            quote_summary = [f"Frozen opening midpoint: {_percent(opening['midpoint'])}; bid–ask {_percent(opening['bid'])}–{_percent(opening['ask'])}. Captured {comparison['target_captured_at']}."]
            later = comparison["followup_quote"]
            if later:
                quote_summary.append(f"Later midpoint: {_percent(later['midpoint'])}; bid–ask {_percent(later['bid'])}–{_percent(later['ask'])}. Captured {comparison['followup_captured_at']}.")
            add("Market comparison", {k: v for k, v in comparison.items() if k != "rows"}, [
                *quote_summary,
                "Squared market error = (estimate − opening midpoint)². Positive step improvement means closer agreement.",
                "Market agreement is not an outcome score. The later quote is separate from the frozen opening target."])
        for e in journal:
            payload = dict(e["payload"])
            if "probability" in payload:
                payload["probability"] = _percent(payload["probability"])
            add(f"Research journal {e['revision']}: {_label(e['kind'])}", payload,
                [f"Recorded {e['recorded_at']} · {e['phase']}",
                 f"Entry {e['id']}" + (f" · Research plan {e['plan_id']}" if e.get("plan_id") else "")])
        if case["models"]:
            for aid, model in case["models"].items():
                add("Model and calculation: " + aid, model)
        else:
            add("Model and calculation", paragraphs=[
                "No structured model artifact was attached to this case. The recorded rationales and assumptions above are the available model description. Supplemental files, if supplied, are identified separately below."])
        add("Limitations and research cost", {"case_limitations": case["limitations"],
            "reported_usage": [e["payload"]["usage"] for e in journal if "usage" in e["payload"]],
            "usage_note": "Usage is agent-reported. Missing usage is unmetered, not zero; partial records are not a total."})

    for attachment in data.get("report_attachments", []):
        add("Supplemental model or research file: " + attachment["name"], attachment, [
            "Supplied at report generation. This is not automatically part of the sealed research record; its hash can be compared with a previously recorded commitment. No code in this file was executed."])
    evidence = {}
    for case in cases:
        evidence.update(case["evidence"])
    for aid, artifact in data.get("artifacts", {}).items():
        if artifact["kind"] == "packet":
            add("Evidence packet context: " + aid,
                {k: v for k, v in artifact["record"].items() if k != "records"})
            for record in artifact["record"]["records"]:
                evidence[aid + ":" + record["id"]] = record
    sources = {}
    for ref, record in evidence.items():
        for source in record.get("sources", []):
            key = digest(source)
            if key not in sources:
                sources[key] = (len(sources) + 1, source)
        citations = [sources[digest(s)][0] for s in record.get("sources", [])]
        add("Finding: " + ref, {k: v for k, v in record.items() if k != "sources"},
            ["Sources: " + ", ".join(f"[{i}]" for i in citations)] if citations else ["No source records attached."])
    for number, source in sources.values():
        add(f"Source [{number}]: " + source.get("title", source.get("id", "Untitled")), source)
    if not evidence:
        add("Evidence and sources", paragraphs=["No source-linked findings were attached."])
    add("Report provenance", data["report_metadata"], [
        "This report renders stored records without new research, model calls, or probability revisions. Missing work remains missing. The JSON export preserves the complete report input."])
    return result


def _evidence(data):
    records = {}
    for case in ([data] if "case_id" in data else data.get("workbenches", [])):
        records.update(case["evidence"])
    for aid, artifact in data.get("artifacts", {}).items():
        if artifact["kind"] == "packet":
            records.update({aid + ":" + r["id"]: r for r in artifact["record"]["records"]})
    return records


def _section(title, paragraphs=(), table=None, sources=()):
    return {"title": title, "paragraphs": list(paragraphs), "table": table, "value": None, "sources": list(sources)}


def sections(data):
    """The reading view: an explanation, with the complete records in an appendix."""
    evidence = _evidence(data)
    narrative = data.get("report_narrative")
    if narrative:
        result = [_section("Assessment", [narrative["summary"]])]
        for item in narrative["sections"]:
            sources = {}
            for ref in item.get("finding_refs", []):
                for source in evidence[ref].get("sources", []):
                    sources[digest(source)] = source
            table = item.get("table")
            result.append(_section(item["heading"], item["paragraphs"],
                (table["headers"], table["rows"]) if table else None, sources.values()))
            if "flowchart" in item:
                result[-1]["flowchart"] = item["flowchart"]
        result.append(_section("About this report", [
            "This explanation was written at report generation from the recorded research. It does not change the sealed predictions. The complete evidence and calculation records are in the technical appendix."]))
        return result

    q = data["question"]["specification"]
    result = [_section("The question", [q["text"], "Yes: " + q["yes"],
        "No: " + q["no"], "Settlement source: " + q["resolution_source"],
        "Deadline: " + q["event_deadline"]])]
    for case in ([data] if "case_id" in data else data.get("workbenches", [])):
        estimates = [e for e in case["journal"] if e["kind"] in ("initial", "checkpoint")]
        if not estimates:
            result.append(_section("Assessment", ["Research has not yet produced an estimate."]))
            continue
        last = estimates[-1]["payload"]
        result.insert(0, _section("Assessment", [
            f"The latest estimate is {_percent(last['probability'])}. " + last["rationale"]]))
        rows = [["Starting estimate" if i == 0 else f"After research step {i}",
                 _percent(e["payload"]["probability"])] for i, e in enumerate(estimates)]
        result.append(_section("How the estimate changed", table=(["Stage", "Probability"], rows)))
        plans = {e["id"]: e["payload"] for e in case["journal"] if e["kind"] == "plan"}
        for i, e in enumerate(estimates[1:], 1):
            p, plan = e["payload"], plans[e["plan_id"]]
            sources = {}
            for ref in p.get("evidence_refs", []):
                for source in evidence[ref["packet_id"] + ":" + ref["record_id"]].get("sources", []):
                    sources[digest(source)] = source
            result.append(_section(f"Research {i}: {plan['uncertainty']}", [
                plan["why_it_matters"], "What we checked: " + plan["search_plan"], p["findings"],
                f"Estimate after this step: {_percent(p['probability'])}. " + p["rationale"]], sources=sources.values()))
        result.append(_section("Assumptions and open questions",
            list(dict.fromkeys(["Starting assumption: " + a for a in estimates[0]["payload"].get("assumptions", [])]
                              + ["Revised assumption: " + a for a in last.get("changed_assumptions", [])]
                              + last.get("remaining_uncertainties", last.get("uncertainties", []))
                              + last.get("limitations", [])))))
        comp = case.get("comparison")
        if comp:
            p = comp["target"]
            paragraphs = [f"The market quote saved before research was {_percent(p['midpoint'])}, with a bid–ask spread of {_percent(p['bid'])} to {_percent(p['ask'])}. Our final estimate was {_percent(last['probability'])}."]
            if comp["followup_quote"]:
                paragraphs.append(f"The later market quote was {_percent(comp['followup_quote']['midpoint'])}. This later observation does not replace the original comparison target.")
            paragraphs += comp["qualification_reasons"] + ["Market agreement is not an outcome score or proof of accuracy."]
        else:
            paragraphs = ["Market target is hidden. Finish the research and reveal it before making a comparison."]
        result.append(_section("Comparison with the market", paragraphs))
        for e in case["journal"]:
            if e["kind"] == "reflection":
                result.append(_section("What we learned", [e["payload"][k] for k in
                    ("what_helped", "what_did_not", "next_method_change")]))
    forecasts = data.get("forecasts", [])
    if forecasts:
        result.append(_section("Issued predictions", table=(["Forecaster", "Probability", "Question version"],
            [[f["forecaster"], _percent(f["probability"]), f["question_version"]] for f in forecasts])))
        for artifact in data.get("artifacts", {}).values():
            if artifact["kind"] == "task_result":
                record = artifact["record"]
                p = record.get("payload", {})
                paragraphs = [p[k] for k in ("rationale", "interpretation", "stopping_reason") if isinstance(p.get(k), str)]
                if paragraphs:
                    result.append(_section(_label(record["task"]["kind"]), paragraphs))
    return result


def _validate_narrative(narrative, data):
    require(isinstance(narrative, dict), "Narrative must be a JSON object.")
    require(narrative.get("record_sha256") == digest(data),
            "Narrative belongs to another report snapshot; update it against the current records.", "version_conflict")
    for key in ("title", "summary"):
        require(isinstance(narrative.get(key), str) and narrative[key].strip(), "Narrative needs " + key + ".")
    require(isinstance(narrative.get("sections"), list) and narrative["sections"], "Narrative needs sections.")
    evidence = _evidence(data)
    for section in narrative["sections"]:
        require(isinstance(section, dict) and isinstance(section.get("heading"), str), "Narrative section needs a heading.")
        require(isinstance(section.get("paragraphs"), list) and all(isinstance(p, str) for p in section["paragraphs"]), "Narrative paragraphs must be text.")
        refs = section.get("finding_refs", [])
        require(isinstance(refs, list) and all(isinstance(r, str) and r in evidence for r in refs), "Narrative cites an unknown finding.")
        if "flowchart" in section:
            chart = section["flowchart"]
            require(isinstance(chart, dict) and isinstance(chart.get("caption"), str)
                    and isinstance(chart.get("steps"), list) and 2 <= len(chart["steps"]) <= 12,
                    "Flowchart needs a caption and 2 to 12 steps.")
            for step in chart["steps"]:
                require(isinstance(step, dict), "Flowchart steps must be objects.")
                inputs = step.get("inputs", [])
                require(isinstance(inputs, list) and len(inputs) <= 3, "Flowchart allows up to three inputs per step.")
                for node in [step, *inputs]:
                    require(isinstance(node, dict) and all(isinstance(node.get(k), str) and node[k].strip()
                            for k in ("title", "text")), "Flowchart nodes need a title and text.")
                    require(node.get("kind", "process") in ("process", "data", "judgment", "result"),
                            "Unknown flowchart node kind.")
        if "table" in section:
            table = section["table"]
            require(isinstance(table, dict) and isinstance(table.get("headers"), list)
                    and table["headers"] and all(isinstance(h, str) for h in table["headers"])
                    and isinstance(table.get("rows"), list), "Narrative table needs headers and rows.")
            require(all(isinstance(r, list) and len(r) == len(table["headers"])
                        and all(type(v) in (str, int, float) for v in r) for r in table["rows"]), "Narrative table rows must match its headers.")


def _safe_url(value):
    try:
        return isinstance(value, str) and not any(ord(c) < 32 for c in value) and urlsplit(value).scheme.lower() in ("http", "https")
    except ValueError:
        return False


def _html_value(value):
    esc = lambda x: html.escape(_scalar(x), quote=True)
    if isinstance(value, dict):
        return "<dl>" + "".join(f"<dt>{esc(_label(k))}</dt><dd>{_html_value(v)}</dd>" for k, v in value.items()) + "</dl>" if value else "<p>None recorded.</p>"
    if isinstance(value, list):
        if value and all(isinstance(row, dict) for row in value) and all(
                not isinstance(v, (dict, list)) for row in value for v in row.values()):
            keys = list(dict.fromkeys(k for row in value for k in row))
            if 0 < len(keys) <= 6:
                return _html_table([_label(k) for k in keys], [[row.get(k) for k in keys] for row in value])
        return "<ul>" + "".join("<li>" + _html_value(v) + "</li>" for v in value) + "</ul>" if value else "<p>None recorded.</p>"
    if _safe_url(value):
        return f'<a href="{esc(value)}" rel="noreferrer">{esc(value)}</a>'
    return '<span class="text">' + esc(value) + "</span>"


def _html_table(headers, rows):
    esc = lambda x: html.escape(_scalar(x), quote=True)
    return ('<div class="table-wrap"><table><thead><tr>' + ''.join('<th scope="col">' + esc(h) + '</th>' for h in headers)
            + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + esc(v) + '</td>' for v in row) + '</tr>' for row in rows)
            + '</tbody></table></div>' + ('<p>No predictions recorded.</p>' if not rows else ''))


FLOW_LABELS = {"process": "Process", "data": "Evidence", "judgment": "Assumption", "result": "Calculation / decision"}


def _html_flowchart(chart):
    def card(node):
        kind = node.get("kind", "process")
        return (f'<div class="flow-card flow-{kind}"><span class="flow-kind">{FLOW_LABELS[kind]}</span>'
                f'<strong>{html.escape(node["title"])}</strong><span>{html.escape(node["text"])}</span></div>')
    items = []
    for step in chart["steps"]:
        inputs = step.get("inputs", [])
        branch = ('<div class="flow-inputs">' + ''.join('<div>' + card(n)
                  + '<span class="flow-arrow" aria-hidden="true">↓</span></div>' for n in inputs) + '</div>') if inputs else ''
        items.append('<li>' + branch + card(step) + '</li>')
    return ('<figure class="flowchart"><ol>' + ''.join(items) + '</ol><figcaption>'
            + html.escape(chart["caption"]) + '</figcaption></figure>')


def render_html(data):
    title = html.escape(data.get("report_narrative", {}).get("title", data["question"]["specification"]["text"]))
    def render_section(section, i):
        heading = html.escape(section["title"])
        body = ''.join('<p>' + html.escape(p) + '</p>' for p in section["paragraphs"])
        if section.get("flowchart"):
            body += _html_flowchart(section["flowchart"])
        if section["table"]:
            body += _html_table(*section["table"])
        if section["value"] is not None:
            body += _html_value(section["value"])
        if section.get("sources"):
            links = []
            for source in section["sources"]:
                label = html.escape(source.get("title", "Source"))
                url = source.get("url", "")
                links.append(f'<a href="{html.escape(url, quote=True)}">{label}</a>' if _safe_url(url) else label)
            body += '<p class="citations">Sources: ' + ' · '.join(links) + '</p>'
        return f'<section id="section-{i}"><h2>{heading}</h2>{body}</section>'
    reading = sections(data)
    parts = [render_section(section, i) for i, section in enumerate(reading)]
    toc = [f'<a href="#section-{i}">{html.escape(s["title"])}</a>' for i, s in enumerate(reading)]
    appendix = ''.join('<details><summary>' + html.escape(s["title"]) + '</summary>'
                       + render_section(s, "audit-" + str(i)) + '</details>' for i, s in enumerate(audit_sections(data)))
    audit = html.escape(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False))
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Expected Parrot | {title}</title><style>
:root{{color-scheme:light;--ep-green:#428a5f;--ep-green-light:#5ba97a;--ep-dark-green:#214d35;--ep-green-soft:#edf7f1;--ep-ink:#17201a;--ep-muted:#667069;--ep-paper:#f5f7f5;--ep-rule:#dfe5e0}}*{{box-sizing:border-box}}body{{margin:0;background:var(--ep-paper);color:var(--ep-ink);font:18px/1.75 Georgia,serif;overflow-wrap:anywhere}}
main{{max-width:860px;margin:auto;padding:40px 32px 64px;background:#fff}}h1{{font-size:clamp(32px,5vw,50px);line-height:1.14;font-weight:500;letter-spacing:-.025em;margin:18px 0 30px}}h2{{font:600 25px/1.3 Georgia,'Times New Roman',serif;color:var(--ep-dark-green);margin:0 0 16px}}a{{color:var(--ep-dark-green);text-decoration-thickness:1px;text-underline-offset:3px}}a:hover{{color:var(--ep-green)}}
.report-brand{{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px 24px;padding:0 0 22px;margin-bottom:32px;border-bottom:3px solid var(--ep-green)}}.brand{{display:flex;align-items:center;gap:12px;text-decoration:none;color:var(--ep-green)}}.brand-mark{{font:500 28px/1 Georgia,serif;white-space:nowrap}}.brand-name{{display:block;font:700 23px/1.2 Georgia,serif}}.brand-tagline{{display:block;margin-top:5px;color:var(--ep-muted);font:600 10px/1.4 system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase}}.brand-product{{font:13px/1.5 system-ui,sans-serif;color:var(--ep-muted)}}.report-footer{{margin-top:44px;padding-top:20px;border-top:3px solid var(--ep-green);color:var(--ep-muted);font:13px/1.7 system-ui,sans-serif}}.report-footer strong{{font-family:Georgia,serif;font-size:16px;color:var(--ep-dark-green)}}
section{{padding:32px 0;border-bottom:1px solid #dddcd4}}p{{margin:0 0 18px}}section:first-child{{font-size:21px}}nav{{display:flex;flex-wrap:wrap;gap:8px 20px;padding:20px 0;border-block:1px solid #dddcd4;font:13px/1.6 system-ui,sans-serif}}
.citations{{font:12px/1.65 system-ui,sans-serif;color:#687069;margin-top:20px}}.table-wrap{{overflow:auto;margin:24px 0}}table{{border-collapse:collapse;width:100%;font:14px/1.5 system-ui,sans-serif}}th,td{{text-align:left;vertical-align:top;padding:12px 10px;border-bottom:1px solid #dddcd4;overflow-wrap:anywhere}}th{{font-weight:600;min-width:6em}}td{{font-variant-numeric:tabular-nums}}thead{{background:#eeeee7}}
.text{{white-space:pre-wrap}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}}summary{{cursor:pointer;font:600 15px/1.5 system-ui,sans-serif;padding:16px 0}}details{{border-bottom:1px solid var(--ep-rule)}}.technical{{margin-top:40px;font:14px/1.6 system-ui,sans-serif}}.technical section{{padding:16px 0}}dt{{font-weight:600;margin-top:12px}}dd{{margin-left:18px}}.eyebrow{{text-transform:uppercase;letter-spacing:.15em;color:var(--ep-dark-green);font:600 11px system-ui,sans-serif}}
.flowchart{{margin:26px 0;font:14px/1.5 system-ui,sans-serif}}.flowchart ol{{list-style:none;padding:0;margin:0 auto;max-width:700px}}.flowchart li{{position:relative;padding:0 0 30px;margin:0}}.flowchart li:not(:last-child)::after{{content:'↓';position:absolute;bottom:0;left:calc(50% - 8px);font-size:23px;color:#63736b}}.flow-card{{border:1px solid #b7c6bf;border-radius:8px;background:#fff;padding:12px 18px;text-align:center;display:flex;flex-direction:column;gap:3px}}.flow-card strong{{font-size:16px}}.flow-kind{{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:#53665c}}.flow-data{{background:#eef5fa;border-color:#a8c2d3}}.flow-judgment{{background:#fff3de;border-color:#d5b576}}.flow-result{{background:#e6f1e8;border-color:#90b09a}}.flow-inputs{{display:flex;gap:12px;align-items:stretch}}.flow-inputs>div{{flex:1;min-width:0;display:flex;flex-direction:column}}.flow-inputs .flow-card{{flex:1;padding:12px}}.flow-inputs strong{{font-size:14px}}.flow-arrow{{text-align:center;font-size:23px;color:#63736b}}figcaption{{color:#647066;font-size:13px;margin-top:8px}}
thead{{background:var(--ep-dark-green);color:white}}tbody tr:nth-child(even){{background:#f7f9f7}}.flow-result{{background:var(--ep-green-soft);border-color:#afd0ba}}.flow-arrow,.flowchart li:not(:last-child)::after{{color:var(--ep-green)}}
@media(max-width:650px){{main{{padding:30px 20px}}body{{font-size:17px}}nav{{gap:6px 14px}}.brand-name{{font-size:21px}}}}
@media print{{body{{background:white;font-size:11pt}}main{{max-width:none;padding:0}}nav,.technical{{display:none}}section{{border:0;padding:12px 0}}h2{{break-after:avoid}}tr{{break-inside:avoid}}a{{color:inherit}}.table-wrap{{overflow:visible}}}}
</style></head><body><main>
<header class="report-brand"><a class="brand" href="https://www.expectedparrot.com/" aria-label="Expected Parrot">
<span class="brand-mark" aria-hidden="true">E[&#x1f99c;]</span><span><strong class="brand-name">Expected Parrot</strong><small class="brand-tagline">Open-source research tools</small></span></a><span class="brand-product">Vorhersage</span></header>
<p class="eyebrow">Forecast research report</p><h1>{title}</h1>
<nav aria-label="Contents">{''.join(toc)}</nav><article>{''.join(parts)}</article>
<details class="technical"><summary>Technical appendix — full research records, model inputs and provenance</summary>{appendix}
<details class="audit"><summary>Complete report input (JSON)</summary><pre>{audit}</pre></details></details>
<footer class="report-footer"><a href="https://www.expectedparrot.com/"><strong>Expected Parrot</strong></a> · Open-source research tools<br>Prepared with Vorhersage · Forecasting, research, and evidence.</footer>
</main></body></html>'''


def tex_escape(value):
    replacements = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&",
                    "#": r"\#", "%": r"\%", "_": r"\_", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return ''.join(replacements.get(c, c if ord(c) >= 32 or c == '\n' else ' ') for c in _scalar(value))


def _tex_text(value):
    # Add break opportunities to long tokens, including IDs inside prose.
    return ''.join(r"\hspace{0pt}".join(tex_escape(token[i:i+12]) for i in range(0, len(token), 12))
                   if len(token) > 28 and not token.isspace() else tex_escape(token)
                   for token in re.split(r"(\s+)", _scalar(value)))


def _tex_value(value):
    if isinstance(value, dict):
        return '\n'.join(r"\par\noindent\textbf{" + _tex_text(_label(k)) + r":} "
                         + (r"\par " if isinstance(v, (dict, list)) else "") + _tex_value(v)
                         for k, v in value.items()) if value else 'None recorded.\n'
    if isinstance(value, list):
        if value and all(isinstance(row, dict) for row in value) and all(
                not isinstance(v, (dict, list)) for row in value for v in row.values()):
            keys = list(dict.fromkeys(k for row in value for k in row))
            if 0 < len(keys) <= 6:
                width = .88 / len(keys)
                columns = (r">{\raggedright\arraybackslash}p{" + f"{width:.3f}" + r"\linewidth}") * len(keys)
                return (r"\begin{longtable}{" + columns + "}\n"
                        + " & ".join(_tex_text(_label(k)) for k in keys) + r" \\ \hline\endhead" + '\n'
                        + '\n'.join(' & '.join(_tex_value(row.get(k)).strip() for k in keys) + r" \\" for row in value)
                        + '\n' + r"\end{longtable}" + '\n')
        # Avoid deeply nested LaTeX lists (models can contain arbitrarily nested JSON).
        return '\n'.join(r"\par\noindent\textit{Item " + str(i + 1) + r".}\par " + _tex_value(v)
                         for i, v in enumerate(value)) if value else 'None recorded.\n'
    if _safe_url(value):
        return r"\href{" + tex_escape(value) + "}{" + _tex_text(value) + "}\n"
    return _tex_text(value) + '\n'


def _latex_flowchart(chart):
    colors = {"process": "white", "data": "blue!5", "judgment": "orange!12", "result": "green!8"}
    parts = [r"\begin{center}", r"\begin{tikzpicture}[node distance=5mm, every node/.style={font=\small}]"]
    for i, step in enumerate(chart["steps"]):
        position = "" if i == 0 else f",below=of flow{i-1}"
        body = r"\textbf{" + tex_escape(step["title"]) + r"}\\ " + tex_escape(step["text"])
        for item in step.get("inputs", []):
            kind = item.get("kind", "process")
            body += (r"\\{\footnotesize\colorbox{" + colors[kind] + r"}{\strut\textbf{" + FLOW_LABELS[kind]
                     + r"}} \textbf{" + tex_escape(item["title"]) + "} — " + tex_escape(item["text"]) + "}")
        parts.append(r"\node[draw=black!35,rounded corners,align=center,text width=13cm,inner sep=5pt,fill="
                     + colors[step.get("kind", "process")] + position + f"] (flow{i}) {{{body}}};")
        if i:
            parts.append(r"\draw[->,thick,draw=black!55] " + f"(flow{i-1}.south) -- (flow{i}.north);")
    parts += [r"\end{tikzpicture}", r"\end{center}", r"{\small " + _tex_text(chart["caption"]) + "}"]
    return '\n'.join(parts)


def render_latex(data):
    title = tex_escape(data.get("report_narrative", {}).get("title", data["question"]["specification"]["text"]))
    parts = [r"\documentclass[11pt]{article}", r"\usepackage[margin=1in]{geometry}",
             r"\usepackage{fontspec}", r"\usepackage{longtable,array}", r"\usepackage{xcolor}",
             r"\definecolor{epgreen}{HTML}{428A5F}", r"\definecolor{epdarkgreen}{HTML}{214D35}", r"\usepackage[hidelinks]{hyperref}",
             r"\setlength{\parindent}{0pt}", r"\setlength{\parskip}{5pt}", r"\emergencystretch=3em", r"\sloppy",
             r"\title{" + title + "}",
             r"\author{\href{https://www.expectedparrot.com/}{\textcolor{epgreen}{\textbf{Expected Parrot}}}\\{\small Open-source research tools}\\[4pt]{\small Vorhersage | Forecast research report}}",
             r"\date{" + tex_escape(data["report_metadata"]["generated_at"]) + "}",
             r"\begin{document}", r"\maketitle", r"{\color{epgreen}\hrule height 1.5pt}\vspace{8pt}"]
    reading = sections(data)
    if any(s.get("flowchart") for s in reading):
        parts.insert(1, r"\usepackage{tikz}\usetikzlibrary{positioning}")
    for i, section in enumerate(reading + audit_sections(data)):
        if i == len(reading):
            parts.extend([r"\clearpage", r"\appendix", r"\section{Technical appendix}",
                          "Complete records follow. These do not change the assessment above."])
        if section.get("flowchart"):
            parts.append(r"\clearpage")
        command = r"\section*{" if i < len(reading) else r"\subsection*{"
        parts.append(command + r"\textcolor{epdarkgreen}{" + _tex_text(section["title"]) + "}}")
        parts.extend(_tex_text(p) + '\n\n' for p in section["paragraphs"])
        if section.get("flowchart"):
            parts.append(_latex_flowchart(section["flowchart"]))
            parts.append(r"\clearpage")
        if section["table"]:
            headers, rows = section["table"]
            if i < len(reading) and rows:
                width = .85 / len(headers)
                columns = (r">{\raggedright\arraybackslash}p{" + f"{width:.3f}" + r"\linewidth}") * len(headers)
                parts.append(r"\begin{longtable}{" + columns + "}")
                parts.append(' & '.join(r"\textbf{" + _tex_text(h) + "}" for h in headers) + r" \\ \hline\endhead")
                parts.extend(' & '.join(_tex_text(v) for v in row) + r" \\" for row in rows)
                parts.append(r"\end{longtable}")
            else:
                for row in rows:
                    parts.append(r"\begin{longtable}{>{\raggedright\arraybackslash}p{.27\linewidth}>{\raggedright\arraybackslash}p{.65\linewidth}}")
                    parts.extend(_tex_text(h) + " & " + _tex_text(v) + r" \\" for h, v in zip(headers, row))
                    parts.append(r"\end{longtable}")
            if not rows:
                parts.append("No predictions recorded.")
        if section["value"] is not None:
            parts.append(_tex_value(section["value"]))
        for source in section.get("sources", []):
            label, url = _tex_text(source.get("title", "Source")), source.get("url", "")
            link = r"\href{" + tex_escape(url) + "}{" + label + "}" if _safe_url(url) else label
            parts.append(r"\par{\small Source: " + link + "}")
    parts.append(r"\end{document}")
    return '\n'.join(parts) + '\n'


def export(data, output, format=None, attachments=(), narrative=None):
    path = Path(output)
    format = format or {".html": "html", ".htm": "html", ".tex": "latex", ".latex": "latex", ".json": "json"}.get(path.suffix.lower())
    require(format in ("html", "latex", "json"), "Choose --format html, latex or json, or an output ending in .html, .tex or .json.")
    authored = None
    if narrative is not None:
        require(Path(narrative).resolve() != path.resolve(), "Report output cannot overwrite its narrative.")
        authored = json.loads(Path(narrative).read_bytes())
        _validate_narrative(authored, data)
    data = {**data, "report_metadata": {"schema_version": "vorhersage.report.v1", "generated_at": now(),
            "record_sha256": digest(data), "format": format, "latex_engine": "XeLaTeX or LuaLaTeX"},
            "report_attachments": []}
    if authored:
        data["report_narrative"] = authored
        data["report_metadata"]["narrative_sha256"] = digest(authored)
    for item in attachments:
        attachment = Path(item)
        require(attachment.resolve() != path.resolve(), "Report output cannot overwrite an attachment.")
        raw = attachment.read_bytes()
        content = json.loads(raw)
        data["report_attachments"].append({"name": attachment.name, "sha256": hashlib.sha256(raw).hexdigest(),
                                            "provenance": "report_time_attachment", "content": content})
    document = (render_html(data) if format == "html" else render_latex(data) if format == "latex"
                else json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")
    return {"output": str(path.resolve()), "format": format, "record_sha256": data["report_metadata"]["record_sha256"],
            "attachments": [{k: v for k, v in a.items() if k != "content"} for a in data["report_attachments"]]}
