import hashlib
import json
import shutil
import subprocess
import sys

import pytest

from vorhersage import reports, workbench
from vorhersage.common import Error, digest
from vorhersage.workflow import Workflow
from vorhersage.store import Store
from test_workbench import case, initial, plan, checkpoint, finish, post
from test_workflow import question, packet, run_spec, finish as finish_run


@pytest.mark.parametrize("extension", ["html", "tex", "json"])
def test_full_report_preserves_hidden_target_and_journal(case, tmp_path, extension):
    w, _, cid, _ = case
    post(case, "initial", initial())
    post(case, "plan", plan())
    post(case, "checkpoint", checkpoint())
    output = tmp_path / ("report." + extension)
    result = workbench.report(w.store, cid, output)
    text = output.read_text()
    assert result["checkpoints"] == 2
    assert "City registry" in text
    assert "Opening requires authorization" in text
    assert "One prerequisite is complete" in text
    assert "Construction" in text
    assert "secret_price" not in text and "midpoint" not in text
    assert "70.0" not in text
    assert w.doctor()["ok"]
    if extension == "json":
        assert json.loads(text)["case_id"] == cid


def test_question_report_collects_regular_runs_models_evidence_and_versions(tmp_path):
    w = Workflow(tmp_path / "project")
    w.store.init("Reports")
    w.question(question())
    evidence = w.import_packet(packet())
    refs = [evidence["records"][0]["evidence_ref"]]
    run = w.start(run_spec())["run_id"]
    fid = finish_run(w, run, refs)
    amended = question()
    amended["text"] = "Changed event definition"
    w.question(amended, expected_version=1)
    data = reports.question_data(w.store, "factory")
    assert len(data["question_versions"]) == 2
    assert data["forecasts"][0]["id"] == fid
    assert data["forecasts"][0]["question_version"] == 1
    assert any(v["kind"] == "task_result" for v in data["artifacts"].values())
    for extension in ("html", "tex"):
        path = tmp_path / ("question." + extension)
        reports.export(data, path)
        text = path.read_text()
        assert "Synthetic unfitted judgment after research." in text
        assert "Fictional factory readiness and shipment record" in text
        assert "Remaining delays." in text
        assert "Question versions" in text


def test_cli_question_report_includes_workbench_and_explicit_attachments(case, tmp_path):
    w, vault, cid, _ = case
    post(case, "initial", initial())
    post(case, "finish", finish())
    workbench.reveal(w.store, cid, vault, skip_refresh=True)
    attachment = tmp_path / "model.json"
    attachment.write_text(json.dumps({"assumption": "Independent trials", "probability": .5}))
    before = workbench.status(w.store, cid)
    for extension in ("html", "tex", "json"):
        output = tmp_path / ("question." + extension)
        proc = subprocess.run([sys.executable, "-m", "vorhersage", "--project", str(w.store.root),
            "report", "--question", "factory", "--output", str(output), "--attachment", str(attachment)],
            capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        receipt = json.loads(proc.stdout)["data"]
        assert receipt["attachments"][0]["sha256"] == hashlib.sha256(attachment.read_bytes()).hexdigest()
        text = output.read_text()
        assert "Independent trials" in text
        if extension != "json":
            assert "70.0" in text
            assert "Supplied at report generation" in text
            assert "not an outcome score" in text
        else:
            assert json.loads(text)["workbenches"][0]["comparison"]["target"]["midpoint"] == pytest.approx(.7)
    assert workbench.status(w.store, cid) == before


def test_untrusted_markup_is_data_in_both_formats(case, tmp_path):
    w, _, cid, _ = case
    payload = initial()
    payload["rationale"] = '<img src=x onerror=alert(1)> & 50% \\input{secrets} $x_2$ # ~ ^'
    payload["assumptions"] = ['javascript:alert(1)', 'https://example.org/a?x=1&y=2#anchor', 'https://[broken']
    post(case, "initial", payload)
    workbench.report(w.store, cid, tmp_path / "safe.html")
    workbench.report(w.store, cid, tmp_path / "safe.tex")
    h = (tmp_path / "safe.html").read_text()
    t = (tmp_path / "safe.tex").read_text()
    assert '<img' not in h and '&lt;img' in h
    assert 'href="javascript:' not in h
    assert 'href="https://example.org/' in h
    assert r'\input{secrets}' not in t
    assert r'\textbackslash{}input\{secrets\}' in t
    assert r'50\%' in t and r'\$x\_2\$' in t
    engine = shutil.which("xelatex")
    if engine:
        built = subprocess.run([engine, "-no-shell-escape", "-halt-on-error", "-interaction=nonstopmode",
                                "-output-directory", str(tmp_path), str(tmp_path / "safe.tex")],
                               capture_output=True, text=True, timeout=60)
        assert built.returncode == 0, built.stdout[-6000:]
        assert (tmp_path / "safe.pdf").is_file()


def test_report_formats_fail_clearly_and_do_not_overwrite_attachment(case, tmp_path):
    w, _, cid, _ = case
    attachment = tmp_path / "input.json"
    attachment.write_text('{"parameter": 3}')
    with pytest.raises(Error, match="cannot overwrite"):
        workbench.report(w.store, cid, attachment, attachments=[attachment])
    assert json.loads(attachment.read_text()) == {"parameter": 3}
    with pytest.raises(Error, match="Choose --format"):
        workbench.report(w.store, cid, tmp_path / "report.pdf")
    proc = subprocess.run([sys.executable, "-m", "vorhersage", "--project", str(w.store.root),
                           "report", "--question", "factory", "--format", "latex"], text=True, capture_output=True)
    assert proc.returncode == 1
    assert "require --output" in json.loads(proc.stderr)["errors"][0]["message"]


def test_linked_model_is_rendered_as_recorded_without_supplement(case, tmp_path):
    w, _, cid, _ = case
    with w.store.connect(True) as c:
        model_id = Store.put(c, "prior", {"method": "judgment", "probability": .5,
            "rationale": "Declared baseline model", "assumptions": ["Exchangeable factory openings"]})
    post(case, "initial", {**initial(), "model_artifact_ids": [model_id]})
    for ext in ("html", "tex"):
        path = tmp_path / ("model-report." + ext)
        workbench.report(w.store, cid, path)
        document = path.read_text()
        assert "Declared baseline model" in document
        assert "Exchangeable factory openings" in document
        assert "No structured model artifact" not in document


def test_reading_view_moves_database_fields_to_collapsed_appendix(case, tmp_path):
    w, _, cid, _ = case
    post(case, "initial", initial())
    output = tmp_path / "readable.html"
    workbench.report(w.store, cid, output)
    reading, appendix = output.read_text().split('<details class="technical">', 1)
    assert "50.0%" in reading and "Uncertain readiness" in reading
    assert cid not in reading and "record_sha256" not in reading
    assert cid in appendix
    assert '<details class="technical" open' not in output.read_text()


def test_narrative_is_bound_to_snapshot_and_does_not_replace_records(case, tmp_path):
    w, _, cid, _ = case
    post(case, "initial", initial())
    before = workbench.status(w.store, cid)
    content = {"record_sha256": digest(before), "title": "A factory-opening forecast",
               "summary": "An authored explanation of the uncertainty.",
               "sections": [{"heading": "How the model works", "paragraphs": ["Readiness remains uncertain."],
                             "table": {"headers": ["Assumption", "Basis"], "rows": [["Readiness", "Judgment"]]}}]}
    narrative = tmp_path / "narrative.json"
    narrative.write_text(json.dumps(content))
    for extension in ("html", "tex", "json"):
        output = tmp_path / ("authored." + extension)
        workbench.report(w.store, cid, output, narrative=narrative)
        text = output.read_text()
        assert "An authored explanation" in text
        assert "Uncertain readiness" in text  # original record retained
    assert workbench.status(w.store, cid) == before
    content["sections"][0]["finding_refs"] = ["missing:source"]
    narrative.write_text(json.dumps(content))
    with pytest.raises(Error, match="unknown finding"):
        workbench.report(w.store, cid, tmp_path / "invalid.html", narrative=narrative)
    content["sections"][0].pop("finding_refs")
    narrative.write_text(json.dumps(content))
    post(case, "plan", plan())
    with pytest.raises(Error, match="another report snapshot"):
        workbench.report(w.store, cid, tmp_path / "stale.html", narrative=narrative)


def test_flowchart_is_offline_escaped_and_exported_in_both_formats(case, tmp_path):
    w, _, cid, _ = case
    post(case, "initial", initial())
    chart = {"caption": "Estimate before reveal", "steps": [
        {"title": "Collect evidence", "text": "<script>alert(1)</script>", "kind": "data"},
        {"title": "Seal forecast", "text": "50% & uncertain", "kind": "result",
         "inputs": [{"title": "Assumption", "text": r"\input{secret}", "kind": "judgment"}]}]}
    narrative = tmp_path / "narrative.json"
    content = {"record_sha256": digest(workbench.status(w.store, cid)), "title": "Method",
               "summary": "A research process", "sections": [{"heading": "Flowchart", "paragraphs": [], "flowchart": chart}]}
    narrative.write_text(json.dumps(content))
    for ext in ("html", "tex"):
        workbench.report(w.store, cid, tmp_path / ("chart." + ext), narrative=narrative)
    h, t = [(tmp_path / ("chart." + ext)).read_text() for ext in ("html", "tex")]
    assert '<figure class="flowchart">' in h and 'flow-judgment' in h
    assert '<script>' not in h and '&lt;script&gt;' in h
    assert r'\begin{tikzpicture}' in t and r'\draw[->' in t
    assert r'\input{secret}' not in t and r'50\% \& uncertain' in t
    if shutil.which('xelatex'):
        p = subprocess.run(['xelatex', '-no-shell-escape', '-halt-on-error', '-interaction=nonstopmode',
                            '-output-directory', str(tmp_path), str(tmp_path/'chart.tex')], capture_output=True, text=True, timeout=60)
        assert p.returncode == 0, p.stdout[-5000:]
    chart['steps'][0]['kind'] = 'arbitrary-style'
    narrative.write_text(json.dumps(content))
    with pytest.raises(Error, match='Unknown flowchart node kind'):
        workbench.report(w.store, cid, tmp_path/'bad.html', narrative=narrative)
