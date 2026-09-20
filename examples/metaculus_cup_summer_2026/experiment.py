"""Acquire, curate, and research the Cup; never submit predictions to Metaculus."""

import argparse
import json
import os
from datetime import timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from vorhersage import research
from vorhersage.backtesting import FORMAT, validate_cases
from vorhersage.common import Error, digest, load, now, require, time
from vorhersage.schemas import check
from vorhersage.store import Store
from vorhersage.workflow import Workflow

ROOT = Path(__file__).resolve().parent
SLUG = "metaculus-cup-summer-2026"
API = "https://www.metaculus.com/api/"


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as f:
        f.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def get(path):
    headers = {"Accept": "application/json", "User-Agent": "vorhersage-cup-replay/1"}
    token = (os.environ.get("METACULUS_API_TOKEN") or os.environ.get("METACULUS_API_KEY", "")).strip()
    require(token, "Set METACULUS_API_TOKEN from Metaculus account settings > API Access. "
            "All API requests require authentication.", "missing_api_key")
    headers["Authorization"] = "Token " + token
    try:
        with urlopen(Request(API + path, headers=headers), timeout=60) as response:
            return json.load(response)
    except HTTPError as exc:
        status = exc.code
        exc.close()
        raise Error("acquisition_failed", f"Metaculus HTTP {status}; no cohort was inferred or substituted.") from None
    except (URLError, TimeoutError, ValueError):
        raise Error("acquisition_failed", "Metaculus did not return usable JSON.") from None


def acquire(output, *, feed_only=False):
    require(not output.exists(), "Output exists; choose a fresh directory.")
    tournament = get(f"projects/tournaments/{SLUG}/")
    posts, seen, offset, pages = [], set(), 0, []
    while True:
        page = get("posts/?" + urlencode({"tournaments": SLUG, "limit": 100,
                                         "offset": offset, "with_cp": "false", "include_descriptions": "true",
                                         "order_by": "published_at"}))
        require(isinstance(page.get("results"), list), "Unexpected Metaculus pagination.")
        pages.append(page)
        rows = page["results"]
        if not rows:
            break
        for row in rows:
            require(row["id"] not in seen, "Repeated post across pages; refusing incomplete acquisition.")
            seen.add(row["id"])
            posts.append(row if feed_only else get(f"posts/{row['id']}/?with_cp=false"))
        offset += 100
    result = import_posts(posts, output, {"tournament": tournament, "acquired_at": now(),
                                         "method": "authenticated_api_feed" if feed_only else "authenticated_api_post_details"})
    save(output / "evaluator/feed_pages.json", pages)
    return result


def import_posts(posts, output, provenance=None):
    require(isinstance(posts, list) and posts, "Supply a nonempty array of Metaculus post details.")
    require(not output.exists(), "Output exists; choose a fresh directory.")
    rows, review, seen = [], {}, set()
    for post in posts:
        pid = post["id"]
        require(type(pid) is int and pid > 0 and pid not in seen, "Invalid or duplicate Metaculus post ID.")
        seen.add(pid)
        q = post.get("question") or {}
        kind = q.get("type") or ("group" if post.get("group_of_questions") else
                                 "conditional" if post.get("conditional") else
                                 "notebook" if post.get("notebook") else "other")
        row = {"post_id": pid, "url": f"https://www.metaculus.com/questions/{pid}/",
               "type": kind, "title": post.get("title"), "open_time": q.get("open_time") or post.get("open_time"),
               "scheduled_close_time": q.get("scheduled_close_time"),
               "current_criteria": q.get("resolution_criteria"),
               "current_fine_print": q.get("fine_print")}
        rows.append(row)
        review[str(pid)] = {"approved": False, "audit_note": "", "text": post.get("title"),
                           "yes": q.get("resolution_criteria"), "no": None, "void": None,
                           "event_deadline": None, "resolve_after": None,
                           "domain": "general", "event_group": f"metaculus_{pid}"}
    output.mkdir(parents=True)
    save(output / "evaluator/posts.json", posts)
    save(output / "inventory.json", {"created_at": now(), "posts_sha256": digest(posts),
                                     "provenance": provenance or {"method": "supplied_export_unverified_membership"},
                                     "rows": rows})
    save(output / "review.json", review)
    return {"inventory_posts": len(rows), "output": str(output), "status": "historical_review_required"}


def prepare(cohort, output, protocol):
    require(not output.exists(), "Output exists; choose a fresh directory.")
    posts = load(cohort / "evaluator/posts.json")
    inventory, reviews = load(cohort / "inventory.json"), load(cohort / "review.json")
    require(digest(posts) == inventory["posts_sha256"], "Raw post export changed.")
    cases, labels, excluded = [], [], []
    days = protocol["cutoff"]["days"]
    require(type(days) is int and days > 0, "Cutoff days must be positive.")
    for post in posts:
        pid = post["id"]
        review = reviews[str(pid)]
        q = post.get("question") or {}
        try:
            require(q.get("type") == "binary", "unsupported_question_type")
            require(review["approved"] is True and review["audit_note"].strip(), "historical_review_pending")
            require(q.get("resolution") in ("yes", "no"), "missing_binary_resolution")
            cutoff = (time(q["open_time"]) + timedelta(days=days)).isoformat()
            resolved = time(q["actual_resolve_time"])
            require(time(cutoff) < resolved < time(now()), "resolution_outside_replay_window")
            # The existing scorer accepts date-only resolution labels and excludes
            # same-day cutoffs; retain that conservative rule explicitly.
            require(time(cutoff).date() < resolved.date(), "cutoff_on_resolution_day")
            if q.get("actual_close_time"):
                require(time(cutoff) < time(q["actual_close_time"]), "cutoff_after_actual_close")
            cid = f"metaculus_{pid}"
            question = {k: review[k] for k in ("text", "yes", "no", "void", "event_deadline", "resolve_after", "domain", "event_group")}
            question.update(id=cid, resolution_source=f"https://www.metaculus.com/questions/{pid}/",
                            profile="general", kind="real")
            check(question, "question")
            require(time(cutoff) < time(question["event_deadline"]), "cutoff_after_event_deadline")
            require(time(question["resolve_after"]) >= time(question["event_deadline"]), "invalid_resolve_after")
            cases.append({"id": cid, "question": question, "information_as_of": cutoff,
                          "criteria_available": True, "historical_wording_audit": "curator_reviewed",
                          "evidence_status": "snapshot_research_pending"})
            labels.append({"case_id": cid, "outcome": int(q["resolution"] == "yes"),
                           "resolution_date": resolved.date().isoformat(), "source_url": question["resolution_source"],
                           "crowd": None})
        except (Error, KeyError, TypeError, ValueError) as exc:
            excluded.append({"post_id": pid, "reason": str(exc), "audit_note": review.get("audit_note", "")})
    require(cases, "No eligible reviewed binary cases; inspect review.json and inventory.json.")
    bundle = {"schema_version": FORMAT, "source": {"tournament": SLUG, "posts_sha256": digest(posts)},
              "selection": {"days_after_open": days, "protocol_sha256": digest(protocol)},
              "limitations": ["Retrospective replay; model knowledge and current search ranking remain uncontrolled."],
              "cases": sorted(cases, key=lambda c: c["id"])}
    validate_cases(bundle)
    label_bundle = {"schema_version": FORMAT, "cases_sha256": digest(bundle), "labels": labels}
    manifest = {"schema_version": FORMAT, "created_at": now(), "cases_sha256": digest(bundle),
                "labels_sha256": digest(label_bundle), "review_sha256": digest(reviews),
                "source_rows": len(posts), "selected_rows": len(cases), "exclusions": excluded}
    save(output / "agent/cases.json", bundle)
    save(output / "evaluator/labels.json", label_bundle)
    save(output / "manifest.json", manifest)
    save(output / "evaluator/review.json", reviews)
    save(output / "protocol.json", protocol)
    return {"selected": len(cases), "excluded": len(excluded), "output": str(output)}


def run_case(args, protocol):
    bundle = load(args.cases)
    cases = validate_cases(bundle)
    require(args.case in cases, "Unknown case.")
    case = cases[args.case]
    require(bundle["selection"]["protocol_sha256"] == digest(protocol), "Protocol changed since cohort freeze.")
    registration = {"cases_sha256": digest(bundle), "protocol_sha256": digest(protocol)}
    lock = args.project / "experiment.json"
    if args.action == "start":
        if lock.exists():
            require(load(lock) == registration, "Project is registered to different cases or protocol.")
        else:
            require(not args.project.exists(), "Use a fresh project or one registered to this experiment.")
            Store(args.project).init("Metaculus Cup historical replay")
            save(lock, registration)
        w = Workflow(args.project)
        w.question(case["question"])
        return w.start({"question_id": case["id"], "forecaster": "agent:exa_snapshot", "method": "cup-snapshot-v1",
                        "mode": "retrospective", "information_as_of": case["information_as_of"], "cutoff_policy": "fixed",
                        "research_contract": "structured_v2", "research_effort": "deep",
                        "max_searches": protocol["research"]["max_searches_per_case"], "max_extra_tasks": 2})
    require(lock.exists() and load(lock) == registration, "Start this experiment project before researching.")
    policy = protocol["research"]
    if args.action == "fetch":
        host = (urlsplit(args.url).hostname or "").lower().rstrip(".")
        require(not any(host == d or host.endswith("." + d) for d in policy["exclude_domains"]),
                "Tournament pages are excluded from forecast research; use curated question inputs.")
        research._url(args.url)
    else:
        require(args.query.strip(), "Supply a nonempty query.")
    # Reserve attempts transactionally before HTTP; errors and timeouts consume
    # budget too. This wrapper is intended to be the worker's only network tool.
    with Store(args.project).connect(write=True) as c:
        Store.question(c, args.case)
        attempts = [a for a in Store.all(c, "snapshot_attempt") if a["case_id"] == args.case]
        require(len(attempts) < policy["max_requests_per_case"], "Case request budget exhausted.")
        if args.action == "search":
            require(sum(a["operation"] == "search" for a in attempts) < policy["max_searches_per_case"], "Case search budget exhausted.")
        Store.put(c, "snapshot_attempt", {"case_id": args.case, "operation": args.action,
                                         "snapshot_as_of": case["information_as_of"], "started_at": now()})
    kwargs = {"provider": "exa", "question": args.case, "snapshot_as_of": case["information_as_of"]}
    if args.action == "search":
        return research.search(args.project, args.query, limit=policy["search_limit_per_request"],
                               exclude_domains=policy["exclude_domains"], **kwargs)
    return research.fetch(args.project, args.url, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("acquire", "import", "prepare"):
        p = sub.add_parser(action)
        p.add_argument("--out", type=Path, required=True)
        if action == "acquire":
            p.add_argument("--feed-only", action="store_true", help="Save the feed with descriptions without individual detail requests")
        if action == "import":
            p.add_argument("--from", dest="source", type=Path, required=True)
        if action == "prepare":
            p.add_argument("--cohort", type=Path, required=True)
    for action in ("start", "search", "fetch"):
        p = sub.add_parser(action)
        p.add_argument("--cases", type=Path, required=True)
        p.add_argument("--case", required=True)
        p.add_argument("--project", type=Path, required=True)
        if action == "search":
            p.add_argument("--query", required=True)
        if action == "fetch":
            p.add_argument("--url", required=True)
    args = parser.parse_args()
    protocol = load(ROOT / "protocol.json")
    if args.action == "acquire":
        result = acquire(args.out, feed_only=args.feed_only)
    elif args.action == "import":
        result = import_posts(load(args.source), args.out)
    elif args.action == "prepare":
        result = prepare(args.cohort, args.out, protocol)
    else:
        result = run_case(args, protocol)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
