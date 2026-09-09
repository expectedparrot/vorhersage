"""JSON-first CLI. Agents supply research and judgment through typed submissions."""

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from . import __version__
from .common import Error, load, require
from .backtesting import prepare_halawi, start_case, evaluate_replay
from .evaluation import evaluate
from .evidence import Epiq
from .schemas import SCHEMAS
from .store import Store
from .workflow import Workflow

GUIDE = """Create a project, register a precise binary question, and start a run.
Repeat next --run ID, author the returned payload schema, then submit --run ID --from FILE.
Use Epiq to research facts; epiq search helps locate cells and epiq freeze imports a portable packet.
Packet record references go into evidence_refs. An unknown is valid when explained.
Questions and profiles are versioned/frozen; issued forecasts never change in place.
When monitoring is due, start a run with previous_forecast_id or resolve the exact question version.
Use simulation questions for fixtures and retrospective mode for hindsight work.
Evaluate selects the latest eligible forecast per forecaster and question at a fixed cutoff.
Use benchmark import-halawi/start/evaluate for explicit historical replay; it preserves actual issue times.
Research/model usage is agent-reported. This CLI does not browse or call a model.
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
    for name in ("version", "guide", "status", "monitor", "doctor"):
        commands.add_parser(name)
    schema = commands.add_parser("schema")
    schema.add_argument("name", nargs="?", choices=list(SCHEMAS))
    for name, actions in (("profile", ["add", "list"]), ("question", ["add", "revise", "list"]),
                          ("run", ["start", "list"]), ("packet", ["import", "show", "list"]),
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
            if action == "show":
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
    report.add_argument("--format", choices=["json", "markdown"], default="json")
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
        data = dispatch(args)
        if args.command == "report" and args.format == "markdown":
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
