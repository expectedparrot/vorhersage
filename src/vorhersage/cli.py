"""JSON-first CLI. Agents supply research and judgment through typed submissions."""

import argparse
import json
import sqlite3
import subprocess
import sys
import time as clock
from pathlib import Path

from . import __version__
from .common import Error, load, require
from .backtesting import prepare_halawi, start_case, evaluate_replay
from .evaluation import evaluate
from .evidence import Epiq, audit as audit_evidence, capture_bundle
from .scenarios import calculate as calculate_scenario
from .odds import calculate as calculate_odds
from .widget import export as export_widget
from . import timeline, timeline_reports, timeline_text
from .relations import add as add_relation, audit as audit_relations
from .monitoring import configure, configs, disable, tick
from .schemas import SCHEMAS
from .store import Store
from .workflow import Workflow
from .reference import add as add_reference, query as query_reference
from . import experiments, sessions, session_runtime, session_studies, session_reports
from . import market_data, workbench, reports

GUIDE = """Create a project, register a precise binary question, and start a run.
Repeat next --run ID, author the returned payload schema, then submit --run ID --from FILE.
Use Epiq to research facts; epiq search helps locate cells and epiq freeze imports a portable packet.
Packet record references go into evidence_refs. An unknown is valid when explained.
Questions and profiles are versioned/frozen; issued forecasts never change in place.
When monitoring is due, start a run with previous_forecast_id or resolve the exact question version.
Use simulation questions for fixtures and retrospective mode for hindsight work.
Evaluate selects the latest eligible forecast per forecaster and question at a fixed cutoff.
Use benchmark import-halawi/start/evaluate for explicit historical replay; it preserves actual issue times.
Declare research_status at run start; an after-research judgment is not a pre-research prior.
Use research capture and packet audit to preserve provenance and source relationships.
Use scenario for optional mixtures/sensitivity, relation for implications, coherence to audit.
Use odds-ledger for declared likelihood ratios and export-widget FORECAST_ID for an offline interactive audit.
Use timeline add/gaps/analyze/shift/compare/report for deadline models; NAME@VERSION selects a fixed model and --format text gives readable output.
Timeline shift records a duration sensitivity alternative; run workflow=timeline starts with structure and parameter research, without a prior.
Use reference add/query for reusable observed episodes with deadline-specific censoring.
Use watch add/tick/run for polling and optional configured research/agent subprocesses.
Use method add and experiment add/start/run/status/evaluate for frozen-packet methodology comparisons.
Use workbench browse/inspect/start/submit/reveal/report for one-question research against a hidden live market target.
Use report --question ID --format html|latex --output FILE for complete question, research, model and prediction reports.
Workbench targets require a separate evaluator project; plans precede research checkpoints and finish seals the trajectory.
Use condition add and session start/submit/finalize/import/aggregate for joint elicitation records.
Joint sessions preserve hypothetical conditions separately from ordinary scored forecasts.
Worker commands are explicit executable argv arrays, receive JSON on stdin, and return JSON.
Research/model usage is agent-reported. No web service or model is selected automatically.
Read schema NAME for the complete input shape. All timestamps must include a timezone.
"""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Error("invalid_arguments", message)


def parser():
    p = Parser(description=__doc__)
    p.add_argument("--project", type=Path, default=Path.cwd())
    commands = p.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("path", nargs="?", type=Path)
    init.add_argument("--name", default="Forecast portfolio")
    for name in ("version", "guide", "status", "monitor", "doctor", "coherence"):
        commands.add_parser(name)
    scenario = commands.add_parser("scenario")
    scenario.add_argument("--from", dest="input", required=True)
    odds = commands.add_parser("odds-ledger")
    odds.add_argument("--from", dest="input", required=True)
    widget = commands.add_parser("export-widget")
    widget.add_argument("id")
    widget.add_argument("--output", type=Path)
    tl = commands.add_parser("timeline")
    sub = tl.add_subparsers(dest="action", required=True)
    ap = sub.add_parser("add")
    ap.add_argument("--from", dest="input", required=True)
    sub.add_parser("list")
    ap = sub.add_parser("shift", help="Save a duration sensitivity alternative")
    ap.add_argument("id", help="Timeline artifact ID or NAME@VERSION")
    ap.add_argument("--parameter", required=True, help="Duration parameter to change in every scenario")
    ap.add_argument("--days", type=float, required=True, help="Elapsed days to add (negative to shorten)")
    ap.add_argument("--name", required=True, help="New model name; starts at version 1")
    ap.add_argument("--rationale", required=True, help="Reason for this sensitivity assumption")
    for action in ("show", "gaps", "analyze", "report", "compare"):
        ap = sub.add_parser(action)
        ap.add_argument("id", help="Timeline artifact ID or NAME@VERSION")
        if action == "analyze":
            ap.add_argument("--sensitivity", action="store_true")
        if action == "compare":
            ap.add_argument("other_id")
        if action == "report":
            ap.add_argument("--compare", dest="other_id")
            ap.add_argument("--output", type=Path, required=True)
    for ap in sub.choices.values():
        ap.add_argument("--format", choices=("json", "text"), default="json", help="Terminal output format (default: json)")
    relation = commands.add_parser("relation")
    relation.add_argument("--from", dest="input", required=True)
    research = commands.add_parser("research")
    sub = research.add_subparsers(dest="action", required=True)
    ap = sub.add_parser("capture")
    ap.add_argument("--from", dest="input", required=True)
    reference = commands.add_parser("reference")
    sub = reference.add_subparsers(dest="action", required=True)
    for action in ("add", "query"):
        ap = sub.add_parser(action)
        ap.add_argument("--from", dest="input", required=True)
    watch = commands.add_parser("watch")
    sub = watch.add_subparsers(dest="action", required=True)
    ap = sub.add_parser("add")
    ap.add_argument("--from", dest="input", required=True)
    sub.add_parser("list")
    ap = sub.add_parser("disable")
    ap.add_argument("id")
    for action in ("tick", "run"):
        ap = sub.add_parser(action)
        ap.add_argument("--id")
        if action == "tick":
            ap.add_argument("--force", action="store_true")
        else:
            ap.add_argument("--interval", type=int, default=30)
            ap.add_argument("--cycles", type=int, default=0, help="0 runs until interrupted")
    schema = commands.add_parser("schema")
    schema.add_argument("name", nargs="?", choices=list(SCHEMAS))
    wb = commands.add_parser("workbench")
    sub = wb.add_subparsers(dest="action", required=True)
    for action in ("browse", "inspect"):
        ap = sub.add_parser(action)
        ap.add_argument("--venue", required=True, choices=["kalshi", "polymarket"])
        if action == "inspect":
            ap.add_argument("--market", required=True)
        else:
            ap.add_argument("--query", default="")
            ap.add_argument("--series")
            ap.add_argument("--limit", type=int, default=10)
            ap.add_argument("--pages", type=int, default=3)
    sub.add_parser("list")
    for action in ("start", "show", "submit", "export", "reveal", "report"):
        ap = sub.add_parser(action)
        if action != "start":
            ap.add_argument("id")
        if action in ("start", "submit"):
            ap.add_argument("--from", dest="input", required=True)
        if action in ("start", "reveal"):
            ap.add_argument("--vault", type=Path, required=True, help="Separate evaluator project, not accessible to the researcher")
            ap.add_argument("--snapshot", help="Fictional simulation fixture only; prospective runs fetch live data")
        if action in ("export", "report"):
            ap.add_argument("--output", type=Path, required=True)
        if action == "report":
            ap.add_argument("--format", choices=["html", "latex", "json"], help="Default: infer from output extension")
            ap.add_argument("--attachment", type=Path, action="append", default=[], help="Supplemental JSON model/research file; labeled as a report-time attachment")
            ap.add_argument("--narrative", type=Path, help="Authored explanation JSON tied to the current report snapshot")
        if action == "reveal":
            ap.add_argument("--skip-refresh", action="store_true", help="Reveal original target without a later quote")
    session = commands.add_parser("session")
    sub = session.add_subparsers(dest="action", required=True)
    for action in ("start", "import", "aggregate", "submit", "finalize", "show", "coherence", "list", "event", "audit", "run", "report", "evaluate"):
        ap = sub.add_parser(action)
        if action in ("submit", "finalize", "show", "coherence", "event", "audit", "run"):
            ap.add_argument("id")
        if action in ("start", "import", "aggregate", "submit", "finalize", "event", "report", "evaluate"):
            ap.add_argument("--from", dest="input", required=True)
        if action == "run":
            ap.add_argument("--max-steps", type=int, default=1)
        if action == "report":
            ap.add_argument("--output", required=True)
    study = commands.add_parser("session-study")
    sub = study.add_subparsers(dest="action", required=True)
    for action in ("add", "status", "run", "report", "evaluate"):
        ap = sub.add_parser(action)
        if action == "add":
            ap.add_argument("--from", dest="input", required=True)
        else:
            ap.add_argument("id")
        if action == "run":
            ap.add_argument("--max-steps", type=int, default=20)
        if action == "report":
            ap.add_argument("--output", required=True)
        if action == "evaluate":
            ap.add_argument("--cutoff", required=True)
            ap.add_argument("--resolution-as-of", required=True)
    distribution = commands.add_parser("distribution-score")
    distribution.add_argument("--from", dest="input", required=True)
    experiment = commands.add_parser("experiment")
    sub = experiment.add_subparsers(dest="action", required=True)
    ap = sub.add_parser("add")
    ap.add_argument("--from", dest="input", required=True)
    sub.add_parser("list")
    for action in ("show", "start", "status", "run", "evaluate"):
        ap = sub.add_parser(action)
        ap.add_argument("id")
        if action == "run":
            ap.add_argument("--max-tasks", type=int, default=20)
        if action == "evaluate":
            ap.add_argument("--resolution-as-of", required=True)
    for name, actions in (("profile", ["add", "list"]), ("question", ["add", "revise", "list"]),
                          ("method", ["add", "show", "list"]), ("condition", ["add", "show", "list"]),
                          ("session_aggregation", ["show", "list"]),
                          ("run", ["start", "list"]), ("packet", ["import", "show", "list", "audit"]),
                          ("forecast", ["show", "list"]), ("evaluation", ["show", "list"]),
                          ("replay_evaluation", ["show", "list"])):
        group = commands.add_parser(name)
        sub = group.add_subparsers(dest="action", required=True)
        for action in actions:
            ap = sub.add_parser(action)
            if action in ("add", "revise", "start", "import"):
                ap.add_argument("--from", dest="input", required=True)
            if action == "revise":
                ap.add_argument("--expected-version", type=int, required=True)
            if action in ("show", "audit"):
                ap.add_argument("id")
    nxt = commands.add_parser("next")
    nxt.add_argument("--run", required=True)
    submit = commands.add_parser("submit")
    submit.add_argument("--run", required=True)
    submit.add_argument("--from", dest="input", required=True)
    for name in ("resolve", "evaluate", "signal"):
        ap = commands.add_parser(name)
        ap.add_argument("--from", dest="input", required=True)
    report = commands.add_parser("report")
    report.add_argument("--question", required=True)
    report.add_argument("--format", choices=["json", "markdown", "html", "latex"], help="Default: JSON on stdout, otherwise infer from output extension")
    report.add_argument("--output", type=Path)
    report.add_argument("--attachment", type=Path, action="append", default=[], help="Supplemental JSON model/research file; does not alter recorded evidence")
    report.add_argument("--narrative", type=Path, help="Authored explanation JSON tied to the current report snapshot")
    epiq = commands.add_parser("epiq")
    sub = epiq.add_subparsers(dest="action", required=True)
    for action in ("search", "freeze", "check"):
        ap = sub.add_parser(action)
        ap.add_argument("--db", type=Path, required=True)
        ap.add_argument("--epiq-source", type=Path)
        if action == "search":
            ap.add_argument("--kind", required=True)
            ap.add_argument("--text", default="")
            ap.add_argument("--subject")
            ap.add_argument("--question")
        elif action == "freeze":
            ap.add_argument("--from", dest="input", required=True)
        else:
            ap.add_argument("--packet", required=True)
    benchmark = commands.add_parser("benchmark")
    sub = benchmark.add_subparsers(dest="action", required=True)
    imp = sub.add_parser("import-halawi")
    imp.add_argument("--from", dest="input", required=True)
    imp.add_argument("--out", type=Path, required=True)
    imp.add_argument("--revision", required=True)
    imp.add_argument("--split", choices=["train", "validation", "test"], required=True)
    imp.add_argument("--limit", type=int, default=20)
    imp.add_argument("--seed", default="vorhersage-1")
    imp.add_argument("--days-after-open", type=int, default=7)
    imp.add_argument("--category", action="append", default=[])
    start = sub.add_parser("start")
    start.add_argument("--cases", required=True)
    start.add_argument("--case", required=True)
    start.add_argument("--forecaster", required=True)
    start.add_argument("--method", required=True)
    score = sub.add_parser("evaluate")
    for name in ("cases", "labels", "manifest"):
        score.add_argument("--" + name, required=True)
    score.add_argument("--from", dest="input", required=True)
    return p


def dispatch(args):
    w = Workflow(args.project)
    s = w.store
    command = args.command
    if command == "version":
        return {"version": __version__, "schema_version": "1", "runtime_dependencies": []}
    if command == "guide":
        return {"guide": GUIDE, "schemas": list(SCHEMAS), "command_help": "Use --help on any command.",
                "workflow": ["question add", "run start", "next", "submit", "monitor", "resolve", "evaluate"]}
    if command == "schema":
        return {"$schema": "https://json-schema.org/draft/2020-12/schema", **SCHEMAS[args.name]} if args.name else {"schemas": list(SCHEMAS)}
    if command == "workbench":
        if args.action == "browse":
            return market_data.browse(args.venue, args.query, args.limit, args.pages, args.series)
        if args.action == "inspect":
            return market_data.inspect(args.venue, args.market)
        if args.action == "start":
            return workbench.start(s, load(args.input), args.vault, load(args.snapshot) if args.snapshot else None)
        if args.action == "submit":
            return workbench.submit(s, args.id, load(args.input))
        if args.action == "show":
            return workbench.status(s, args.id)
        if args.action == "list":
            with s.connect() as c:
                return [{"case_id": x["id"], "question": x["question"]["specification"]["text"],
                         "created_at": x["created_at"]} for x in Store.all(c, "workbench")]
        if args.action == "export":
            return workbench.export_case(s, args.id, args.output)
        if args.action == "report":
            return workbench.report(s, args.id, args.output, args.format, args.attachment, args.narrative)
        if args.action == "reveal":
            return workbench.reveal(s, args.id, args.vault, load(args.snapshot) if args.snapshot else None, args.skip_refresh)
    if command == "scenario":
        return calculate_scenario(load(args.input))
    if command == "odds-ledger":
        return calculate_odds(load(args.input))
    if command == "export-widget":
        return export_widget(s, args.id, args.output or Path(args.id + ".html"))
    if command == "timeline":
        if args.action == "add":
            return timeline.add(s, load(args.input))
        if args.action == "list":
            with s.connect() as c:
                return Store.all(c, "timeline_model")
        if args.action == "shift":
            return timeline.shift(s, args.id, args.parameter, args.days, args.name, args.rationale)
        with s.connect() as c:
            model_id = timeline.resolve(c, args.id)
            other_id = timeline.resolve(c, args.other_id) if getattr(args, "other_id", None) else None
        if args.action == "compare":
            return timeline.compare(s, model_id, other_id)
        if args.action == "report":
            return timeline_reports.export(s, model_id, args.output, other_id)
        with s.connect() as c:
            body = timeline.read(c, model_id)
        if args.action == "show":
            return {"timeline_model_id": model_id, **body}
        spec = body["specification"]
        if args.action == "gaps":
            return timeline.gaps(spec)
        result = timeline.analyze(spec)
        if args.sensitivity:
            result["sensitivity"] = timeline.sensitivity(spec)
        return result
    if command == "condition":
        if args.action == "add":
            return sessions.add_condition(s, load(args.input))
        with s.connect() as c:
            return Store.artifact(c, args.id, "condition") if args.action == "show" else Store.all(c, "condition")
    if command == "session":
        if args.action == "event":
            return session_runtime.record(s, args.id, load(args.input))
        if args.action == "audit":
            return session_runtime.audit(s, args.id)
        if args.action == "run":
            return session_runtime.execute(s, args.id, args.max_steps)
        if args.action == "report":
            return session_reports.render(s, load(args.input)["session_ids"], args.output)
        if args.action == "evaluate":
            return session_reports.evaluate(s, load(args.input))
        if args.action == "list":
            with s.connect() as c:
                return Store.all(c, "joint_session")
        if args.action in ("show", "coherence"):
            return (sessions.status if args.action == "show" else sessions.coherence)(s, args.id)
        if args.action in ("submit", "finalize"):
            return getattr(sessions, args.action)(s, args.id, load(args.input))
        action = sessions.import_session if args.action == "import" else getattr(sessions, args.action)
        return action(s, load(args.input))
    if command == "session-study":
        if args.action == "add":
            return session_studies.add(s, load(args.input))
        if args.action == "run":
            return session_studies.run(s, args.id, args.max_steps)
        progress = session_studies.status(s, args.id)
        ids = [t["session_id"] for t in progress["trials"]]
        if args.action == "report":
            return session_reports.render(s, ids, args.output)
        if args.action == "evaluate":
            return session_reports.evaluate(s, {"session_ids": ids, "cutoff": args.cutoff,
                                           "resolution_as_of": args.resolution_as_of, "allow_source_reported": False})
        return progress
    if command == "distribution-score":
        return session_reports.distribution_score(load(args.input))
    if command == "session_aggregation":
        with s.connect() as c:
            return Store.artifact(c, args.id, "joint_aggregation") if args.action == "show" else Store.all(c, "joint_aggregation")
    if command == "method":
        if args.action == "add":
            return experiments.add_method(s, load(args.input))
        with s.connect() as c:
            return Store.artifact(c, args.id, "method") if args.action == "show" else Store.all(c, "method")
    if command == "experiment":
        if args.action == "add":
            return experiments.add_experiment(s, load(args.input))
        if args.action in ("show", "list"):
            with s.connect() as c:
                return Store.artifact(c, args.id, "experiment") if args.action == "show" else Store.all(c, "experiment")
        if args.action == "run":
            return experiments.execute(args.project, args.id, args.max_tasks)
        if args.action == "evaluate":
            return experiments.score(args.project, args.id, args.resolution_as_of)
        return getattr(experiments, args.action)(args.project, args.id)
    if command == "research":
        return w.import_packet(capture_bundle(load(args.input)))
    if command == "reference":
        return (add_reference if args.action == "add" else query_reference)(s, load(args.input))
    if command == "relation":
        return add_relation(s, load(args.input))
    if command == "coherence":
        with s.connect() as c:
            return audit_relations(c)
    if command == "watch":
        if args.action == "add":
            return configure(s, load(args.input))
        if args.action == "list":
            return configs(s)
        if args.action == "disable":
            return disable(s, args.id)
        if args.action == "tick":
            return tick(args.project, args.id, args.force)
    if command == "init":
        return Store(args.path or args.project).init(args.name)
    if command in ("status", "monitor", "doctor"):
        return getattr(w, command)()
    if command == "next":
        return w.next(args.run)
    if command == "submit":
        return w.submit(args.run, load(args.input))
    if command == "profile":
        if args.action == "add":
            return w.add_profile(load(args.input))
        with s.connect() as c:
            return [json.loads(r[0]) for r in c.execute("SELECT body FROM profiles ORDER BY id")]
    if command == "question":
        if args.action == "list":
            return w.status()["questions"]
        return w.question(load(args.input), args.expected_version if args.action == "revise" else None)
    if command == "run":
        return w.start(load(args.input)) if args.action == "start" else w.status()["runs"]
    if command == "packet" and args.action == "import":
        return w.import_packet(load(args.input))
    if command == "packet" and args.action == "audit":
        with s.connect() as c:
            return audit_evidence(Store.artifact(c, args.id, "packet"))
    if command in ("packet", "forecast", "evaluation", "replay_evaluation"):
        with s.connect() as c:
            return Store.artifact(c, args.id, command) if args.action == "show" else Store.all(c, command)
    if command == "resolve":
        return w.resolve(load(args.input))
    if command == "signal":
        return w.signal(load(args.input))
    if command == "evaluate":
        return evaluate(s, load(args.input))
    if command == "benchmark":
        if args.action == "import-halawi":
            return prepare_halawi(args.input, args.out, revision=args.revision, split=args.split,
                                  limit=args.limit, seed=args.seed, days_after_open=args.days_after_open,
                                  categories=args.category)
        if args.action == "start":
            return start_case(args.project, load(args.cases), args.case, args.forecaster, args.method)
        return evaluate_replay(s, load(args.cases), load(args.labels), load(args.manifest), load(args.input))
    if command == "report":
        if args.output:
            require(args.format != "markdown", "Markdown reports use stdout; omit --output.")
            return reports.export(reports.question_data(s, args.question), args.output, args.format, args.attachment, args.narrative)
        require(args.format in (None, "json", "markdown"), "HTML and LaTeX reports require --output.")
        require(not args.attachment, "Report attachments require --output.")
        require(not args.narrative, "Report narratives require --output.")
        return w.report(args.question)
    if command == "epiq":
        client = Epiq(args.db, args.epiq_source)
        if args.action == "search":
            return client.search(args.kind, args.text, args.subject, args.question)
        if args.action == "freeze":
            return w.import_packet(client.freeze(load(args.input)))
        with s.connect() as c:
            packet = Store.artifact(c, args.packet, "packet")
        changes = client.changes(packet)
        changes["suggested_signal"] = {"reason": "Selected Epiq evidence changed; reassess this forecast.",
                                       "idempotency_key": "epiq-check-" + args.packet + "-" + changes["checked_at"],
                                       "evidence_refs": [{"packet_id": args.packet, "record_id": r["record_id"]} for r in changes["changes"]]} if changes["changes"] else None
        return changes
    raise Error("unknown_command", "Unknown command.")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        args = parser().parse_args(argv)
        if args.command == "watch" and args.action == "run":
            require(1 <= args.interval <= 60 and args.cycles >= 0, "Polling interval must be 1..60 seconds and cycles nonnegative.")
            cycle = 0
            try:
                while args.cycles == 0 or cycle < args.cycles:
                    print(json.dumps({"schema_version": "1", "status": "ok", "command": "watch",
                                      "data": tick(args.project, args.id), "warnings": [], "errors": [],
                                      "next_actions": []}, allow_nan=False), flush=True)
                    cycle += 1
                    if args.cycles == 0 or cycle < args.cycles:
                        clock.sleep(args.interval)
            except KeyboardInterrupt:
                pass
            return
        data = dispatch(args)
        if args.command == "timeline" and args.format == "text":
            print(timeline_text.render(args.action, data))
            return
        if args.command == "report" and args.format == "markdown" and not args.output:
            print("# " + data["question"]["specification"]["text"] + "\n")
            for f in data["forecasts"]:
                print(f"- {f['issued_at']}: **{f['probability']:.2%}**, {f['forecaster']} ({f['mode']}); `{f['id']}`")
            print("\nResolutions: " + json.dumps(data["resolutions"]))
            return
        actions = []
        if isinstance(data, dict) and data.get("run_id") and (args.command in ("submit", "run")
                or (args.command == "benchmark" and args.action == "start")):
            actions.append({"argv": ["vorhersage", "--project", str(args.project.resolve()), "next", "--run", data["run_id"]], "mutates": False, "network": False})
        print(json.dumps({"schema_version": "1", "status": "ok", "command": args.command,
                          "data": data, "warnings": [], "errors": [], "next_actions": actions}, indent=2, allow_nan=False))
    except (Error, OSError, ValueError, KeyError, TypeError, sqlite3.Error, subprocess.SubprocessError) as exc:
        print(json.dumps({"schema_version": "1", "status": "error", "data": None,
                          "errors": [{"code": getattr(exc, "code", "operation_failed"), "message": str(exc)}],
                          "warnings": [], "next_actions": []}), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
