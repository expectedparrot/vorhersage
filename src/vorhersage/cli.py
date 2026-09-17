"""Forecasting tools for people and agents, with explicit research and judgment."""

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
from .evidence import Epiq, audit as audit_evidence, capture_bundle, capture_finding
from .scenarios import calculate as calculate_scenario
from .odds import calculate as calculate_odds
from .widget import export as export_widget
from . import timeline, timeline_reports, timeline_text, timeline_plan, timeline_diagram
from .relations import add as add_relation, audit as audit_relations
from .monitoring import configure, configs, disable, tick
from .schemas import SCHEMAS
from .store import Store
from .workflow import Workflow
from .reference import add as add_reference, query as query_reference
from . import experiments, sessions, session_runtime, session_studies, session_reports
from . import market_data, workbench, reports, report_context, setup, study, study_text

GUIDE = """Vorhersage records research, computes declared models, and preserves issued forecasts and their revisions. You collect evidence and judge the inputs.
For one question, use start TEXT --project FOLDER. This saves an undefined question, without inventing a probability.
Supply --deadline TIME --yes CRITERIA --source SOURCE to start research immediately, or record them later with define --project FOLDER.
Agents should agree on the event definition with the user and supply --forecaster NAME for attribution. The default forecaster is user.
Define starts research automatically. Use --workflow timeline for a deadline model; declare --research-status in_progress or completed if research has already begun.
Use show --project FOLDER for readable progress, and next --project FOLDER --output task.json for the agent task and context.
Fill the task file's submission.payload according to payload_schema; add submission.usage for research/model usage. Preserve its run_id and submission bookkeeping.
Use submit --project FOLDER --from task.json, then next with a new output filename. Exact retries are safe; stale or altered retries fail.
Alternatively write just the payload to answer.json, then submit --project FOLDER --task task.json --answer answer.json [--usage usage.json]. The exported task retains all identifiers and retry guards.
New single-question studies begin with intake: name inputs and link unknowns to them. Each unknown specifies ask_user, search, assumption, or unobservable, its importance, and a concrete action. Subsequent inquiry tasks collect answers or explicit unresolved reasons before any initial estimate.
When several influential unknowns are facts the human user knows, offer to design a short survey for that user if ep is available. Explain which model inputs their answers could inform. A few questions can also be answered in chat; the survey is optional and can be offered during intake or a later revision.
For a chosen survey, inspect ep humanize create --help, author an EDSL survey saved as intake-survey.json, and run ep humanize create --survey intake-survey.json --name "Forecast follow-up". Save the returned survey UUID and give the user the respondent link. Link each question name to the intake unknown and input_ids; ask neutral factual questions, allow unknown/not applicable, and avoid showing the current forecast before eliciting facts.
After the user completes it, fetch ep humanize responses SURVEY_UUID --output intake-responses.json and inspect answers with ep results columns --file intake-responses.json and ep results export intake-responses.json --format json --output intake-answers.json. Preserve original answers and timestamps; capture each relevant self-reported finding with evidence add, citing the survey and question. Answers inform declared judgments; they do not automatically determine scenario weights or establish a population base rate.
Use the resulting evidence_refs in the active inquiry tasks. If a forecast has already issued, use revise with those references, update the affected parameter_support and scenario assumptions, then complete assessment/review/issue and regenerate the report. Explain which answers changed which inputs, what remained uncertain, and whether the forecast moved. If ep is unavailable, collect the same facts in chat.
Use evidence add CLAIM --project FOLDER --url URL --title TITLE --excerpt TEXT --claim-type observation to capture a user answer or source finding. This records the current capture time and returns evidence_refs. Keep observations separate from inferences. Never backdate evidence to satisfy a cutoff.
In the prior payload declare research_status_at_estimate. Searches already performed are research, even when the run began with research_status not_started. Report only newly performed searches in usage; reusing a source does not repeat its cost. Never reduce true usage just to pass a budget check.
Structured assessments require parameter_support for every supplied model input. Separate scenario weight from conditional probability. Each record links input_id from intake, model_input path, value, target, evidence_measures, transfer_assumptions, basis, plausible_range, and evidence_refs. Basis is measured, calculated, extrapolated, or assumed. Unsupported judgments remain assumed.
New studies use structured_v2. Every assessment supplies model_map {version, previous_version, rationale, inputs:[{model_input, input_ids, target, quantity}]}. Start at version 1 / previous_version 0; subsequent passes increment context.model_map.version. Targets must match parameter_support. Quantity is scenario_weight, conditional_probability, probability, likelihood_ratio, ensemble_weight, or timeline_input. Map each actual input exactly once and explain changes to the research/model mapping.
A model_challenge task follows each assessment. Inspect every evidence transfer (supported, assumption, mismatch), with reasons and evidence_refs; use actual source passages, not just citations. Scenario models need at least two concrete boundary trajectories, including a spike then reversal before the deadline. Record matching scenario_ids, including none or several where the partition fails. Each mismatch or partition gap needs a concern linked to model_inputs; boundary gaps name concern_ids. Read schema model_challenge for the exact shape.
Review resolves each concern through concern_resolutions [{concern_id, disposition, rationale, action}]. Dispositions: investigate (research now), await_evidence (name an observable trigger), retain_assumption (explain unresolved uncertainty). Investigate with decision research creates linked inquiry tasks then assessment/challenge/review; optional route ask_user elicits a user fact, otherwise search. Use decision revise to repair the model without new research; timeline revisions revisit structure and parameters. Concern investigations consume max_extra_tasks. Forms and source links cannot establish substantive correctness.
Inquiry answers can include coverage [{domain, interpretation}] for profile domains already addressed. Answers with evidence satisfy those domains directly; explicitly unresolved answers preserve gaps. Their duplicate generic research tasks are removed. Use only domains substantively addressed by that answer; timeline parameter assessments remain separate.
Capture one claim per finding. evidence add creates claim_support linking its passage. For inference use --claim-type inference --inference-rationale TEXT. Research bundles may attach claim_support [{source_id, passage, relation: direct|inference, rationale}] to each finding, and inference_rationale to inferences. Passage matching checks supplied text only; old packets remain usable with provenance gaps reported.
For an empirical prior, use reference add --from CASE.json to register dated cases with episode_id and eligibility, then reference query --from QUERY.json. Query fields: tags, horizon_days, known_as_of, selection_rule. Use its prior_payload plus research_status_at_estimate. Unresolved episodes are censored, not failures; shared episode IDs prevent multiple proposals being counted as separate trials. New empirical priors require reference_query matching the registered cases, not a prose zero-base-rate claim. Use a judgment prior when no defensible denominator exists.
Model input paths are probability for judgment, scenarios/ID/weight and scenarios/ID/probability for mixtures, components/ID/probability for paths, anchor/probability and entries/ID/lr or joint/GROUP/lr for odds, scenarios/ID/weight and scenarios/ID/inputs/PARAMETER for timelines, members/ID/weight for ensembles.
Review must include sensitivity_review with interpretation, influential_inputs (actual model_input paths), and next_evidence. Inspect context.sensitivity: its bounds vary assumptions and are not confidence intervals. In new studies, review decision revise returns to assessment and model challenge; do not supply an inline replacement probability. Existing structured_v1 studies retain their original review contract.
After new evidence arrives, use revise --project FOLDER --reason REASON --evidence PACKET:RECORD (repeat evidence as needed), then next/submit/report. This starts a linked revision with a fresh cutoff and carries prior evidence/model records. show distinguishes the previous issued forecast from the working revision. A signal alone never changes a probability.
The forecaster does the research and judgment, directly or with an agent; these commands do not call a model or browse automatically.
For an agent-authored report, use report context --project FOLDER --output analysis/forecast-report-context.json. Read that bounded evidence and writing handoff; a hash-bound full-material JSON file is saved beside it. Select --run RUN for a portfolio or --case CASE for a workbench; ambiguous runs are rejected. reportability distinguishes a completed forecast from a draft; readiness is not a quality certification. Preserve probabilities, evidence links, assumptions, challenges, and hidden-market boundaries; consult full material for omitted details.
The calling agent authors the explanation. In ep-agent, load skill:report-authoring, write writeup/report.md, and follow its branding, optional-review, compilation, and checking workflow to produce writeup/report.html. This package does not call another model to narrate results. Its legacy report --project FOLDER HTML/LaTeX exports remain inspection views, not the agent's final narrative.
The commands below support portfolios and explicit low-level control.
Create a project, register a precise binary question, and start a run.
Use init PROJECT --question TEXT --deadline TIME --yes CRITERIA --source SOURCE to create a project and question together.
Use question add TEXT --deadline TIME --yes CRITERIA --source SOURCE for another question; the general research profile is the default.
Use run start QUESTION_ID to begin research with standard defaults, or --from FILE for fully specified agent inputs.
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
Build an unresolved timeline with timeline new FILE.toml, then timeline step FILE.toml NAME DESCRIPTION [--date | --after STEPS] [--target].
Use timeline show FILE.toml to read the working plan and timeline save FILE.toml to validate and register an immutable model.
Use timeline edit FILE.toml STEP --after PREREQUISITES --rationale REASON to change dependencies; --rename updates references too.
Use timeline scenario FILE.toml NAME DESCRIPTION --probability 22% --rationale REASON to assign a scenario probability.
Use timeline estimate FILE.toml SCENARIO STEP --days N or --date TIME with --rationale; default basis is assumed. Estimated/observed inputs require --evidence PACKET:RECORD.
Scenario sets may be incomplete while editing. Calculating or saving requires all weights or none, total 100% when weighted, and a --partition explanation supplied to scenario.
Use timeline diagram FILE.toml --output diagram.svg for an offline dependency diagram, or omit --output for Mermaid source.
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


def question_options(parser, *, initializing=False, default_id_help=None):
    if initializing:
        source = parser.add_mutually_exclusive_group()
        source.add_argument("--question", help="Forecasting question to register")
        source.add_argument("--from", dest="input", help="Complete question JSON instead of inline options")
    else:
        parser.add_argument("question", nargs="?", help="Forecasting question")
        parser.add_argument("--from", dest="input", help="Complete question JSON instead of inline options")
    parser.add_argument("--id", dest="question_id", help="Question ID (default: " +
                        (default_id_help or "project directory for init, otherwise derived from the question") + ")")
    parser.add_argument("--deadline", help="Event deadline; YYYY-MM-DD means midnight UTC, or supply a timestamp with timezone")
    parser.add_argument("--yes", help="Criteria for a YES outcome (required for inline questions)")
    parser.add_argument("--source", help="Resolution source or policy (required for inline questions)")
    parser.add_argument("--no", help="NO rule (default: YES criteria not met by the deadline)")
    parser.add_argument("--void", help="Void rule (default: defective criteria or resolution evidence)")
    parser.add_argument("--resolve-after", help="Earliest resolution check (default: deadline)")
    parser.add_argument("--profile", help="Existing research profile (default: general)")
    parser.add_argument("--domain", help="Question domain (default: general)")
    parser.add_argument("--event-group", help="Group related events for evaluation (default: question ID)")
    parser.add_argument("--kind", choices=("real", "simulation"), help="Question kind (default: real)")


def run_options(parser):
    parser.add_argument("question_id", nargs="?", help="Registered question ID")
    parser.add_argument("--from", dest="input", help="Complete run JSON instead of inline options")
    parser.add_argument("--forecaster", help="Forecaster attribution (default: agent)")
    parser.add_argument("--method", help="Method description (default: agent judgment)")
    parser.add_argument("--mode", choices=("prospective", "retrospective", "simulation"), help="Default: prospective for real questions, simulation for fixtures")
    parser.add_argument("--as-of", dest="information_as_of", help="Information cutoff (default: now)")
    parser.add_argument("--workflow", choices=("standard", "timeline"), help="Research workflow (default: standard)")
    parser.add_argument("--research-status", choices=("not_started", "in_progress", "completed", "unspecified"), help="Prior research state (default: not_started)")
    parser.add_argument("--max-searches", type=int, help="Reported search budget (default: 20)")
    parser.add_argument("--max-extra-tasks", type=int, help="Additional review tasks (default: 2)")


def study_options(parser):
    """Ordinary run settings, without exposing identifiers or internal state."""
    parser.add_argument("--forecaster", default="user", help="Who supplies the judgments (default: user)")
    parser.add_argument("--method", help="Method description (default: declared judgment or declared timeline)")
    parser.add_argument("--research-status", choices=("not_started", "in_progress", "completed", "unspecified"), default="not_started")
    parser.add_argument("--workflow", choices=("standard", "timeline"), default="standard")
    parser.add_argument("--max-searches", type=int, default=20)
    parser.add_argument("--max-extra-tasks", type=int, default=2)


def study_settings(args):
    return {"forecaster": args.forecaster,
            "method": args.method or ("declared timeline" if args.workflow == "timeline" else "declared judgment"),
            "research_status": args.research_status, "workflow_name": args.workflow,
            "max_searches": args.max_searches, "max_extra_tasks": args.max_extra_tasks}


def human_output(args):
    if getattr(args, "json", False):
        return False
    if args.command in ("start", "define", "show", "revise"):
        return True
    if args.command in ("next", "submit"):
        return args.run is None
    return args.command == "report" and args.report_action != "context" and not args.question and args.format not in ("json", "markdown")


def parser():
    p = Parser(description=__doc__)
    p.add_argument("--project", type=Path, default=Path.cwd())
    commands = p.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start", help="Start a forecast from a question")
    question_options(start, default_id_help="question")
    define = commands.add_parser("define", help="Set the outcome rules and begin research")
    question_options(define, initializing=True, default_id_help="question")
    for ap in (start, define):
        study_options(ap)
    show = commands.add_parser("show", help="Read the forecast and research progress")
    revise = commands.add_parser("revise", help="Begin a linked revision after new evidence")
    revise.add_argument("--reason", required=True)
    revise.add_argument("--evidence", action="append", default=[], help="PACKET:RECORD; repeat for multiple findings")
    revise.add_argument("--expected-forecast", help="Reject if the issued forecast differs from this ID")
    for ap in (start, define, show, revise):
        ap.add_argument("--project", type=Path, default=argparse.SUPPRESS)
        ap.add_argument("--json", action="store_true", help="Machine-readable output")
    init = commands.add_parser("init")
    init.add_argument("path", nargs="?", type=Path)
    init.add_argument("--name", help="Project name (default: Forecast portfolio)")
    question_options(init, initializing=True)
    for name in ("version", "guide", "status", "monitor", "doctor", "coherence"):
        commands.add_parser(name)
    scenario = commands.add_parser("scenario")
    scenario.add_argument("--from", dest="input", required=True)
    odds = commands.add_parser("odds-ledger")
    odds.add_argument("--from", dest="input", required=True)
    evidence = commands.add_parser("evidence", help="Capture a finding with tool-recorded timestamps")
    sub = evidence.add_subparsers(dest="action", required=True)
    add = sub.add_parser("add")
    add.add_argument("claim")
    for name in ("url", "title", "excerpt"):
        add.add_argument("--" + name, required=True)
    add.add_argument("--claim-type", choices=("reporting", "official_statement", "observation", "inference", "unknown"), default="reporting")
    add.add_argument("--observed-at", help="Historical observation date; capture/retrieval time is always recorded now")
    add.add_argument("--inference-rationale", help="Required for inference: explain the step from source passage to this claim")
    widget = commands.add_parser("export-widget")
    widget.add_argument("id")
    widget.add_argument("--output", type=Path)
    tl = commands.add_parser("timeline")
    sub = tl.add_subparsers(dest="action", required=True)
    ap = sub.add_parser("new", help="Create an editable timeline plan")
    ap.add_argument("file", type=Path)
    ap.add_argument("--question", help="Default: the project's only question")
    ap.add_argument("--name", help="Saved model name (default: filename without .toml)")
    ap.add_argument("--as-of", help="Information cutoff (default: now)")
    ap.add_argument("--description")
    ap.add_argument("--deadline-rule", choices=("before", "on_or_before"), default="before")
    ap = sub.add_parser("step", help="Add a milestone and its prerequisites to a plan")
    ap.add_argument("file", type=Path)
    ap.add_argument("name", help="Short name used in --after")
    ap.add_argument("description", help="What must happen to complete this step")
    ap.add_argument("--date", action="store_true", help="Unknown calendar date; default is an unknown duration")
    ap.add_argument("--after", nargs="+", default=[], help="Steps that must finish before this one begins")
    ap.add_argument("--target", action="store_true", help="Completing this step satisfies the forecasting question")
    ap.add_argument("--rationale", help="Why these prerequisites apply (default: provisional, needs research)")
    ap = sub.add_parser("edit", help="Change a working step and explain the modeling decision")
    ap.add_argument("file", type=Path)
    ap.add_argument("name", help="Existing step name")
    ap.add_argument("--rename", help="New name; updates prerequisites and target references")
    ap.add_argument("--description")
    ap.add_argument("--after", nargs="*", help="Replace all prerequisites; use --after alone to clear them")
    ap.add_argument("--kind", choices=("date", "duration"))
    ap.add_argument("--target", action="store_true")
    ap.add_argument("--rationale", required=True, help="Reason for the changed definition or dependency")
    ap = sub.add_parser("scenario", help="Describe a possible future and assign its probability")
    ap.add_argument("file", type=Path)
    ap.add_argument("name")
    ap.add_argument("description")
    ap.add_argument("--probability", type=timeline_plan.probability_input, help="Scenario probability, such as 22% or 0.22")
    ap.add_argument("--rationale", required=True)
    ap.add_argument("--copy-from", help="Copy another scenario's inputs into a new scenario")
    ap.add_argument("--partition", help="Explain how the whole scenario set covers mutually exclusive possible outcomes")
    ap = sub.add_parser("estimate", help="Set a date or duration in one scenario")
    ap.add_argument("file", type=Path)
    ap.add_argument("scenario")
    ap.add_argument("step")
    value = ap.add_mutually_exclusive_group(required=True)
    value.add_argument("--date", help="Date with timezone; YYYY-MM-DD means midnight UTC")
    value.add_argument("--days", type=float, help="Duration in elapsed days")
    value.add_argument("--never", action="store_true", help="This step never completes in this scenario")
    value.add_argument("--unknown", action="store_true", help="Remove an estimate and leave the input unresolved")
    ap.add_argument("--basis", choices=("assumed", "estimated", "observed"), default="assumed")
    ap.add_argument("--rationale", required=True)
    ap.add_argument("--evidence", action="append", default=[], help="Evidence reference PACKET:RECORD; repeat for multiple findings")
    ap = sub.add_parser("diagram", help="Draw dependencies from a plan or saved model")
    ap.add_argument("id", help="Working .toml plan or immutable NAME@VERSION")
    ap.add_argument("--output", type=Path, help="Offline .svg image, .mmd source, or Mermaid .md file; default: source on stdout")
    ap = sub.add_parser("save", help="Validate a working plan and save an immutable model")
    ap.add_argument("file", type=Path)
    ap.add_argument("--name", help="Save under a new model name without changing the working file")
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
        ap.add_argument("id", help="Timeline artifact ID or NAME@VERSION; show/gaps/analyze also accept a .toml plan")
        if action == "analyze":
            ap.add_argument("--sensitivity", action="store_true")
        if action == "compare":
            ap.add_argument("other_id")
        if action == "report":
            ap.add_argument("--compare", dest="other_id")
            ap.add_argument("--output", type=Path, required=True)
    for ap in sub.choices.values():
        ap.add_argument("--project", type=Path, default=argparse.SUPPRESS)
        ap.add_argument("--format", choices=("json", "text"), help="Default: text for working plans, JSON for saved models")
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
            if name == "question" and action == "add":
                question_options(ap)
            elif name == "run" and action == "start":
                run_options(ap)
            elif action in ("add", "revise", "start", "import"):
                ap.add_argument("--from", dest="input", required=True)
            if action == "revise":
                ap.add_argument("--expected-version", type=int, required=True)
            if action in ("show", "audit"):
                ap.add_argument("id")
    nxt = commands.add_parser("next")
    nxt.add_argument("--run", help="Explicit run for a portfolio; omit for a single-question study")
    nxt.add_argument("--output", type=Path, help="Write a new agent task file with an answer template")
    submit = commands.add_parser("submit")
    submit.add_argument("--run", help="Explicit run for a portfolio; omit when submitting a study task file")
    source = submit.add_mutually_exclusive_group(required=True)
    source.add_argument("--from", dest="input")
    source.add_argument("--task", type=Path, help="Original exported task; supply its answer separately")
    submit.add_argument("--answer", type=Path, help="JSON payload only, with --task")
    submit.add_argument("--usage", type=Path, help="JSON usage record, with --task")
    for ap in (nxt, submit):
        ap.add_argument("--project", type=Path, default=argparse.SUPPRESS)
        ap.add_argument("--json", action="store_true")
    for name in ("resolve", "evaluate", "signal"):
        ap = commands.add_parser(name)
        ap.add_argument("--from", dest="input", required=True)
    report = commands.add_parser("report")
    report.add_argument("report_action", nargs="?", choices=["context"], help="Export evidence and writing guidance for an agent-authored report")
    selection = report.add_mutually_exclusive_group()
    selection.add_argument("--run", help="Run to use for report context; defaults to the active single-question study")
    selection.add_argument("--case", help="Workbench case to use for report context; preserves hidden targets")
    report.add_argument("--question", help="Explicit question for a portfolio; omit for a single-question study")
    report.add_argument("--project", type=Path, default=argparse.SUPPRESS)
    report.add_argument("--json", action="store_true")
    report.add_argument("--format", choices=["json", "markdown", "html", "latex"], help="Inspection export: HTML for a study, JSON with --question; agent writing uses report context")
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
    def project_options(ap):
        if "--project" not in ap._option_string_actions:
            ap.add_argument("--project", type=Path, default=argparse.SUPPRESS)
        for action in ap._actions:
            if isinstance(action, argparse._SubParsersAction):
                for child in action.choices.values():
                    project_options(child)
    project_options(p)
    return p


def evidence_references(values):
    refs = []
    for value in values:
        packet, separator, record = value.partition(":")
        require(packet and separator and record, "Evidence references use PACKET:RECORD.")
        refs.append({"packet_id": packet, "record_id": record})
    return refs


def dispatch(args):
    w = Workflow(args.project)
    s = w.store
    command = args.command
    if command == "start":
        if args.input or any(getattr(args, key) is not None for key in setup.QUESTION_OPTIONS):
            question = setup.question_input(args, default_id="question")
            return study.start(args.project, question["text"], question, **study_settings(args))
        require(args.question and args.question.strip(), "Enter the question you want to forecast.")
        require(study_settings(args) == {"forecaster": "user", "method": "declared judgment", "research_status": "not_started",
                                        "workflow_name": "standard", "max_searches": 20, "max_extra_tasks": 2},
                "Supply outcome rules to use research settings now, or pass the settings to define later.")
        return study.start(args.project, args.question)
    if command == "define":
        with s.connect() as c:
            brief = study.brief(c)
        if not args.input:
            require(args.question in (None, brief["question"]), "Definition must retain the original question.")
            args.question = brief["question"]
        question = setup.question_input(args, default_id="question")
        return study.define(w, question, **study_settings(args))
    if command == "show":
        return study.show(s)
    if command == "revise":
        return study.revise(w, reason=args.reason, refs=evidence_references(args.evidence), expected_forecast=args.expected_forecast)
    if command == "evidence":
        return w.import_packet(capture_finding(args.claim, url=args.url, title=args.title, excerpt=args.excerpt,
                                              claim_type=args.claim_type,
                                              inference_rationale=args.inference_rationale,
                                              observed_at=setup.timestamp(args.observed_at) if args.observed_at else None))
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
        working_file = args.action in ("show", "gaps", "analyze") and args.id.endswith(".toml")
        args.format = args.format or ("text" if working_file or args.action in ("new", "step", "edit", "scenario", "estimate", "diagram", "save") else "json")
        if args.action == "new":
            return timeline_plan.new(s, args.file, question_id=args.question, name=args.name,
                                     as_of=setup.timestamp(args.as_of) if args.as_of else None,
                                     description=args.description, deadline_rule=args.deadline_rule)
        if args.action == "step":
            return timeline_plan.step(args.file, args.name, args.description, after=args.after, date=args.date,
                                      target=args.target, rationale=args.rationale)
        if args.action == "edit":
            return timeline_plan.edit(args.file, args.name, rename=args.rename, description=args.description,
                                      after=args.after, kind=args.kind, target=args.target, rationale=args.rationale)
        if args.action == "diagram":
            return timeline_diagram.export(s, args.id, args.output)
        if args.action == "scenario":
            return timeline_plan.scenario(args.file, args.name, args.description, weight=args.probability,
                                          rationale=args.rationale, copy_from=args.copy_from, partition=args.partition)
        if args.action == "estimate":
            refs = []
            for reference in args.evidence:
                packet, separator, record = reference.partition(":")
                require(packet and separator and record, "Evidence references use PACKET:RECORD.")
                refs.append({"packet_id": packet, "record_id": record})
            kind, value = ("date", setup.timestamp(args.date)) if args.date is not None else (
                ("duration", args.days) if args.days is not None else ("never" if args.never else "unknown", None))
            return timeline_plan.estimate(args.file, args.scenario, args.step, value=value, value_kind=kind,
                                          basis=args.basis, rationale=args.rationale, evidence_refs=refs)
        if args.action == "save":
            return timeline_plan.save(s, args.file, args.name)
        if working_file:
            plan = timeline_plan.read(args.id)
            if args.action == "show":
                return {"path": args.id, "plan": plan}
            spec = timeline_plan.compile(plan)
            if args.action == "gaps":
                return timeline.gaps(spec)
            result = timeline.analyze(spec)
            if args.sensitivity:
                result["sensitivity"] = timeline.sensitivity(spec)
            return result
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
        if args.question is not None or args.input is not None or any(getattr(args, key) is not None for key in setup.QUESTION_OPTIONS):
            project = args.path or args.project
            default_id = setup.slug(project.resolve().name) if args.question and not args.question_id else None
            question = setup.question_input(args, default_id=default_id)
            return setup.initialize(project, args.name or "Forecast portfolio", question)
        return Store(args.path or args.project).init(args.name or "Forecast portfolio")
    if command in ("status", "monitor", "doctor"):
        return getattr(w, command)()
    if command == "next":
        require(not (args.run and args.output), "Task file export is for single-question studies; omit --run.")
        if args.run:
            return w.next(args.run)
        with s.connect() as c:
            defined = c.execute("SELECT 1 FROM artifacts WHERE id=?", (study.BINDING,)).fetchone()
        if not defined:
            require(not args.output, "Define the question before exporting a research task.")
            return study.show(s)
        return study.next_task(w, args.output)
    if command == "submit":
        require(bool(args.task) == bool(args.answer), "Use --task TASK.json together with --answer ANSWER.json.")
        require(args.usage is None or args.task is not None, "--usage accompanies --task and --answer.")
        if args.task:
            require(args.run is None, "--task uses the single-question study binding; omit --run.")
            return study.submit(w, load(args.task), load(args.answer), load(args.usage) if args.usage else None)
        return w.submit(args.run, load(args.input)) if args.run else study.submit(w, load(args.input))
    if command == "profile":
        if args.action == "add":
            return w.add_profile(load(args.input))
        with s.connect() as c:
            return [json.loads(r[0]) for r in c.execute("SELECT body FROM profiles ORDER BY id")]
    if command == "question":
        if args.action == "list":
            return w.status()["questions"]
        if args.action == "add":
            return w.question(setup.question_input(args))
        return w.question(load(args.input), args.expected_version)
    if command == "run":
        return w.start(setup.run_input(args, w)) if args.action == "start" else w.status()["runs"]
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
        spec = load(args.input)
        with s.connect() as c:
            if "question_id" not in spec and c.execute("SELECT 1 FROM artifacts WHERE id=?", (study.BINDING,)).fetchone():
                spec["question_id"] = study.active_binding(c)["question_id"]
        return w.signal(spec)
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
        if args.report_action == "context":
            require(not args.format and not args.attachment and not args.narrative,
                    "Report context exports JSON evidence; formatting and narrative belong to the author.")
            return report_context.export(s, output=args.output, question_id=args.question, run_id=args.run, case_id=args.case)
        require(not args.run and not args.case, "--run and --case select report context; use report context.")
        question = args.question or study.binding(s)["question_id"]
        if args.json and args.format is None and not args.output:
            args.format = "json"
        if not args.question and not args.output and args.format not in ("json", "markdown"):
            args.output = s.root / ("report.tex" if args.format == "latex" else "report.html")
        if args.output:
            require(args.format != "markdown", "Markdown reports use stdout; omit --output.")
            return reports.export(reports.question_data(s, question), args.output, args.format, args.attachment, args.narrative)
        require(args.format in (None, "json", "markdown"), "HTML and LaTeX reports require --output.")
        require(not args.attachment, "Report attachments require --output.")
        require(not args.narrative, "Report narratives require --output.")
        return w.report(question)
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
    args = None
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
        if human_output(args):
            if args.command == "report":
                print("Report saved to " + str(args.output.resolve()))
            else:
                print(study_text.render(data if args.command in ("start", "define", "show", "revise") else study.show(Store(args.project))))
                if args.command == "next" and args.output:
                    print("\nTask saved to " + str(args.output.resolve()) +
                          ". Fill submission.payload, then submit --from this file.")
            return
        if args.command == "timeline" and args.format == "text":
            if args.action == "diagram":
                if "diagram" in data:
                    print(data["diagram"], end="")
                else:
                    print("Diagram: " + data["path"])
            elif "plan" in data:
                print(timeline_plan.render(args.action, data))
            else:
                print(timeline_text.render("add" if args.action == "save" else args.action, data))
            return
        if args.command == "report" and args.format == "markdown" and not args.output:
            print("# " + data["question"]["specification"]["text"] + "\n")
            for f in data["forecasts"]:
                print(f"- {f['issued_at']}: **{f['probability']:.2%}**, {f['forecaster']} ({f['mode']}); `{f['id']}`")
            print("\nResolutions: " + json.dumps(data["resolutions"]))
            return
        actions = []
        if args.command == "init" and data.get("question_id"):
            actions.append({"argv": ["vorhersage", "--project", data["project"], "run", "start", data["question_id"]],
                            "mutates": True, "network": False})
        if isinstance(data, dict) and data.get("run_id") and (args.command in ("submit", "run")
                or (args.command == "benchmark" and args.action == "start")):
            actions.append({"argv": ["vorhersage", "--project", str(args.project.resolve()), "next", "--run", data["run_id"]], "mutates": False, "network": False})
        print(json.dumps({"schema_version": "1", "status": "ok", "command": args.command,
                          "data": data, "warnings": [], "errors": [], "next_actions": actions}, indent=2, allow_nan=False))
    except (Error, OSError, ValueError, KeyError, TypeError, sqlite3.Error, subprocess.SubprocessError) as exc:
        if args is not None and human_output(args):
            print("Error: " + str(exc), file=sys.stderr)
            raise SystemExit(1)
        print(json.dumps({"schema_version": "1", "status": "error", "data": None,
                          "errors": [{"code": getattr(exc, "code", "operation_failed"), "message": str(exc)}],
                          "warnings": [], "next_actions": []}), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
