"""Recorded, paginated research for EDSL: Tavily or externally captured web.run.

The Tavily request shapes match the pinned AIRO tools.py. A cached extraction
provides stable 7,000-character windows. No model-selected URL is fetched by
the local process directly: it goes to the selected research provider.
"""
import argparse
import json
import os
import urllib.request
from datetime import date, timedelta
from pathlib import Path
import edsl_pilot as pilot

PAGE_CHARS = 7000


def search_body(action, today):
    body = {"query": action["query"], "max_results": action.get("max_results", 5),
            "search_depth": "advanced", "include_answer": True}
    if action.get("recent_days"):
        days = min(action["recent_days"], 3650)
        body.update(topic="news", include_answer=False,
                    start_date=(today - timedelta(days=days)).isoformat(), end_date=today.isoformat())
    return body


def page_window(text, offset, url):
    pilot.require(type(offset) is int and offset >= 0, "Invalid page offset.")
    body = {"url": url, "offset": offset, "total_chars": len(text), "text": text[offset:offset + PAGE_CHARS]}
    if offset + PAGE_CHARS < len(text):
        body["next_offset"] = offset + PAGE_CHARS
    return body


def pending_action(out, index):
    reg, state = pilot.checked(out)
    p = state["pending"]
    pilot.require(p and p["kind"] == "tools" and index not in p["completed"] and 0 <= index < len(p["actions"]), "No such pending research action.")
    return reg, state, p["actions"][index], out / p["directory"]


def cached_page(out, action):
    return out / "page-cache" / (pilot.digest(action["url"]) + ".json")


def accept_capture(out, index, capture_path):
    reg, state, action, directory = pending_action(out, index)
    capture = pilot.load(capture_path)
    pilot.require(capture["action"] == action and capture["provider"] == reg["research_provider"], "Capture identity mismatch.")
    pilot.require(type(capture["ok"]) is bool, "Capture status required.")
    text = capture["text"]
    pilot.require(isinstance(text, str) and text, "Capture text required.")
    meta = {"capture_sha256": pilot.digest(capture), "capture_path": str(capture_path.resolve().relative_to(out.resolve()))}
    if action["tool"] == "web_search" and capture["provider"] == "web.run":
        text = json.dumps({"text": text[:7600], "provider_output_chars": len(text), "truncated": len(text) > 7600,
                           "note": "Search excerpt capped to approximately the authors' 8,000-character tool envelope. Full service response is retained. web.run recency is not Tavily's exact-date news filter; max_results is not available."}, ensure_ascii=False)
    if action["tool"] == "read_page" and capture["ok"]:
        cache = cached_page(out, action)
        if cache.exists():
            saved = pilot.load(cache)
            pilot.require(saved["text"] == text, "Page capture changed between windows.")
        else:
            pilot.write(cache, {"url": action["url"], "text": text, "retrieved_at": capture["retrieved_at"],
                                "provider": capture["provider"], **meta})
        window = page_window(text, action.get("offset", 0), action["url"])
        if not window["text"]:
            capture["ok"] = False
        window["extraction_note"] = capture.get("extraction_note", "total_chars describes the provider's extracted representation, not guaranteed full source coverage.")
        text = json.dumps(window, ensure_ascii=False)
    receipt_path = directory / f"receipt-{index}.json"
    pilot.write(receipt_path, {"action": action, "provider": capture["provider"], "ok": capture["ok"],
                              "retrieved_at": capture["retrieved_at"], "text": text, **meta})
    return pilot.receipt(out, index, receipt_path)


def tavily(out, index):
    reg, state, action, directory = pending_action(out, index)
    pilot.require(reg["research_provider"] == "tavily", "This run is not registered for Tavily.")
    key = os.environ.get("TAVILY_API_KEY")
    pilot.require(key, "Set TAVILY_API_KEY in the environment before executing Tavily research.")
    cache = cached_page(out, action) if action["tool"] == "read_page" else None
    if cache and cache.exists():
        saved = pilot.load(cache)
        capture = {"action": action, "provider": "tavily", "ok": True, "text": saved["text"],
                   "retrieved_at": pilot.now(), "cached_extraction_at": saved["retrieved_at"]}
    else:
        search = action["tool"] == "web_search"
        body = search_body(action, date.fromisoformat(reg["created_at"][:10])) if search else {"urls": [action["url"]], "extract_depth": "basic"}
        request = urllib.request.Request("https://api.tavily.com/" + ("search" if search else "extract"),
            data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
        # Let network failures surface so the caller can distinguish sandbox
        # restrictions from provider failures; do not fabricate a success receipt.
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = json.load(response)
        if search:
            result = {"query": action["query"], "answer": raw.get("answer"), "results": [
                {"title": r.get("title"), "url": r.get("url"), "content": (r.get("content") or "")[:1500],
                 **({"published": r["published_date"]} if r.get("published_date") else {})} for r in raw.get("results", [])]}
            if action.get("recent_days"):
                result["window"] = {"start": body["start_date"], "end": body["end_date"]}
            text = json.dumps(result, ensure_ascii=False)
            ok = not raw.get("error")
        else:
            text = next((r.get("raw_content", "") for r in raw.get("results", []) if r.get("raw_content")), "")
            ok = bool(text)
            if not ok:
                text = json.dumps({"error": "Page extraction failed", "failed_results": raw.get("failed_results", [])})
        capture = {"action": action, "provider": "tavily", "ok": ok, "text": text,
                   "retrieved_at": pilot.now(), "request": body, "raw_response": raw}
    path = directory / f"capture-{index}.json"
    pilot.write(path, capture)
    return accept_capture(out, index, path)


def pending_external(out):
    """Use frozen page caches where possible; return outstanding network work."""
    reg, state = pilot.checked(out)
    p = state["pending"]
    if not p or p["kind"] != "tools":
        return []
    pending = []
    for index, action in enumerate(p["actions"]):
        if index in p["completed"]:
            continue
        path = out / p["directory"] / f"capture-{index}.json"
        if path.exists():
            continue
        cache = cached_page(out, action) if action["tool"] == "read_page" else None
        if cache and cache.exists():
            saved = pilot.load(cache)
            pilot.write(path, {"action": action, "provider": reg["research_provider"], "ok": True,
                               "text": saved["text"], "retrieved_at": pilot.now(),
                               "cached_extraction_at": saved["retrieved_at"]})
        else:
            pending.append({"name": out.name, "index": index, "action": action,
                            "directory": p["directory"], "capture_path": str(path.resolve())})
    return pending


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["tavily", "ingest"])
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--index", type=int, required=True)
    p.add_argument("--capture", type=Path)
    args = p.parse_args()
    print(json.dumps(tavily(args.out, args.index) if args.command == "tavily" else accept_capture(args.out, args.index, args.capture)))
