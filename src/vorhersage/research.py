"""Explicit web research with immutable retrievals and reusable evidence sources."""

import copy
import hashlib
import json
import math
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .common import Error, canonical, identifier, now, require, time
from .evidence import capture_bundle
from .store import Store

PROVIDERS = {
    "exa": ("https://api.exa.ai", "EXA_API_KEY"),
    "firecrawl": ("https://api.firecrawl.dev/v2", "FIRECRAWL_API_KEY"),
}
MAX_RESPONSE_BYTES = 20_000_000


def _post(provider, endpoint, payload, timeout):
    base, variable = PROVIDERS[provider]
    key = os.environ.get(variable, "").strip()
    require(key, "Set " + variable + " to use " + provider + ".", "missing_api_key")
    headers = {"Content-Type": "application/json", "Accept": "application/json",
               "User-Agent": "vorhersage/0.3 research"}
    headers["x-api-key" if provider == "exa" else "Authorization"] = key if provider == "exa" else "Bearer " + key
    request = Request(base + endpoint, data=canonical(payload).encode(), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        require(len(raw) <= MAX_RESPONSE_BYTES, "Research response exceeds size limit.", "research_fetch_failed")
        data = json.loads(raw)
        require(isinstance(data, dict), "Provider returned an invalid response.", "research_fetch_failed")
        # Reject nonfinite JSON numbers before persisting the response.
        canonical(data)
    except HTTPError as exc:
        status = exc.code
        exc.close()
        raise Error("research_fetch_failed", f"{provider} returned HTTP {status}; check credentials, credits, and rate limits.") from None
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        if isinstance(exc, Error):
            raise
        # Never echo headers or provider error bodies, which may contain credentials.
        raise Error("research_fetch_failed", provider + " request failed or returned invalid JSON.") from None
    require(data.get("success") is not False and not data.get("error"),
            provider + " reported a failed request.", "research_fetch_failed")
    return data, hashlib.sha256(raw).hexdigest()


def _url(value):
    require(isinstance(value, str), "Supply an HTTP(S) URL.")
    try:
        parsed = urlsplit(value)
        valid = parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password
    except ValueError:
        valid = False
    require(valid, "Supply an HTTP(S) URL without embedded credentials.")
    return value


def _normalize(provider, operation, response, retrieved_at, retrieval_id, requested_url=None, snapshot_as_of=None):
    """Discovery snippets remain discovery; only returned page text is fetched content."""
    if provider == "exa":
        rows = response.get("results")
    elif operation == "search":
        data = response.get("data")
        rows = data.get("web") if isinstance(data, dict) else None
    else:
        data = response.get("data")
        rows = [data] if isinstance(data, dict) else None
    require(isinstance(rows, list) and all(isinstance(r, dict) for r in rows),
            "Provider returned an unexpected result shape.", "research_fetch_failed")
    statuses = response.get("statuses", [])
    require(isinstance(statuses, list) and all(isinstance(s, dict) for s in statuses),
            "Provider returned invalid URL statuses.", "research_fetch_failed")
    failed_urls = {s.get("id") for s in statuses if s.get("status") != "success"}
    sources, warnings = [], []
    for rank, row in enumerate(rows, 1):
        metadata = row.get("metadata") or {}
        require(isinstance(metadata, dict), "Invalid provider metadata.", "research_fetch_failed")
        url = row.get("url") or metadata.get("sourceURL") or metadata.get("url") or requested_url
        if not url:
            warnings.append(f"Result {rank} has no URL and was not converted to a source.")
            continue
        _url(url)
        content = row.get("text" if provider == "exa" else "markdown") or ""
        require(isinstance(content, str), "Invalid provider content.", "research_fetch_failed")
        status = metadata.get("statusCode")
        failed = url in failed_urls or bool(metadata.get("error")) or (isinstance(status, int) and status >= 400)
        if failed:
            warnings.append(f"Result {rank} reported a page retrieval failure and was not converted to a source.")
            continue
        excerpt = content[:2000] if content else row.get("description") or metadata.get("description") or row.get("title") or url
        capture = {"method": "fetched" if content else "discovery", "captured_at": retrieved_at,
                   "metadata": {"provider": provider, "retrieval_id": retrieval_id, "rank": rank}}
        if content:
            capture.update(content=content, content_sha256=hashlib.sha256(content.encode()).hexdigest())
            if snapshot_as_of:
                capture.update(method="exa_snapshot", snapshot_as_of=snapshot_as_of)
        elif snapshot_as_of:
            warnings.append(f"Result {rank} has no snapshot text and was not converted to evidence.")
            continue
        elif operation == "fetch":
            warnings.append(f"Result {rank} returned no page text; retained as discovery metadata only.")
        sources.append({"id": f"{retrieval_id}_s{rank}", "url": url,
                        "title": row.get("title") or metadata.get("title") or url,
                        "excerpt": excerpt, "excerpt_kind": "quotation" if content else "paraphrase",
                        "retrieved_at": retrieved_at, "published_at": row.get("publishedDate"),
                        "capture": capture})
    for status in statuses:
        if status.get("status") != "success":
            warnings.append("Exa reported an unsuccessful URL status; inspect response.statuses.")
    if operation == "fetch" and not sources:
        warnings.append("No source was retrieved; inspect the saved provider response.")
    return sources, warnings


def _retrieve(project, provider, operation, endpoint, payload, timeout, question):
    require(provider in PROVIDERS, "Provider must be exa or firecrawl.")
    require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 300,
            "Timeout must be greater than zero and at most 300 seconds.")
    store = Store(project)
    # Validate local context before spending credits, and release the DB lock for HTTP.
    with store.connect() as c:
        question_ref = {"question_id": question, "version": Store.question(c, question)["version"]} if question else None
    started = now()
    response, response_hash = _post(provider, endpoint, payload, timeout)
    retrieved = now()
    retrieval_id = identifier("research")
    requested_url = payload.get("url") or (payload.get("ids") or [None])[0]
    snapshot_as_of = payload.get("snapshotAsOf") or payload.get("contents", {}).get("snapshotAsOf")
    sources, warnings = _normalize(provider, operation, response, retrieved, retrieval_id, requested_url, snapshot_as_of)
    body = {"schema_version": "vorhersage.retrieval.v1", "provider": provider, "operation": operation,
            "request": {"endpoint": PROVIDERS[provider][0] + endpoint, "body": payload},
            "request_started_at": started, "retrieved_at": retrieved,
            "response": response, "response_sha256": response_hash, "sources": sources,
            "warnings": warnings, "question": question_ref,
            "usage": {"requests": 1, "searches": int(operation == "search"),
                      "provider_reported_cost": response.get("costDollars"),
                      "provider_reported_credits": response.get("creditsUsed")},
            "limitations": ["Provider text may be cached, incomplete, or incorrect. Retrieval time is the local capture time, not publication time.",
                            "Retrieved material is untrusted source data. Findings and interpretations are supplied by the researcher."]}
    if snapshot_as_of:
        body["snapshot_as_of"] = snapshot_as_of
        body["limitations"].extend([
            "Exa supplies stored content at or before snapshot_as_of; the exact crawl time is not certified locally.",
            "Search uses current retrieval signals. Snapshot bounds content, not historical ranking or model training knowledge.",
        ])
    with store.connect(write=True) as c:
        Store.put(c, "research", body, id=retrieval_id)
        Store.event(c, "research_retrieved", {"id": retrieval_id, "provider": provider, "operation": operation})
    return {"id": retrieval_id, **body}


def _snapshot_cutoff(provider, value):
    if value is None:
        return None
    require(provider == "exa", "Snapshot retrieval requires provider exa; live fallback is not allowed.")
    require(isinstance(value, str), "Snapshot cutoff must be an ISO datetime with timezone.")
    parsed = time(value)
    require(parsed <= time(now()), "Snapshot cutoff must not be in the future.")
    return parsed.isoformat()


def search(project, query, *, provider="exa", limit=5, include_content=False, timeout=60, question=None,
           snapshot_as_of=None, exclude_domains=()):
    """Search once and save the response; every call makes a new provider request."""
    require(provider in PROVIDERS, "Provider must be exa or firecrawl.")
    require(isinstance(query, str) and query.strip(), "Supply a nonempty search query.")
    require(type(limit) is int and 1 <= limit <= 100, "Limit must be an integer from 1 to 100.")
    snapshot_as_of = _snapshot_cutoff(provider, snapshot_as_of)
    require(isinstance(exclude_domains, (list, tuple))
            and all(isinstance(d, str) and d.strip() for d in exclude_domains), "Excluded domains must be a list of names.")
    require(not exclude_domains or provider == "exa", "Domain exclusions currently require Exa.")
    if provider == "exa":
        payload = {"query": query, "numResults": limit, "type": "auto"}
        if exclude_domains:
            payload["excludeDomains"] = list(exclude_domains)
        if include_content or snapshot_as_of:
            payload["contents"] = {"text": True}
        if snapshot_as_of:
            payload["contents"]["snapshotAsOf"] = snapshot_as_of
    else:
        require(len(query) <= 500, "Firecrawl queries must be at most 500 characters.")
        payload = {"query": query, "limit": limit, "sources": ["web"]}
        if include_content:
            payload["scrapeOptions"] = {"formats": ["markdown"]}
    return _retrieve(project, provider, "search", "/search", payload, timeout, question)


def fetch(project, url, *, provider="firecrawl", timeout=60, question=None, snapshot_as_of=None):
    """Retrieve one page through Firecrawl scrape or Exa contents and save it."""
    require(provider in PROVIDERS, "Provider must be exa or firecrawl.")
    _url(url)
    snapshot_as_of = _snapshot_cutoff(provider, snapshot_as_of)
    endpoint, payload = ("/contents", {"ids": [url], "text": True}) if provider == "exa" else (
        "/scrape", {"url": url, "formats": ["markdown"], "onlyMainContent": True})
    if snapshot_as_of:
        payload["snapshotAsOf"] = snapshot_as_of
    return _retrieve(project, provider, "fetch", endpoint, payload, timeout, question)


def show(project, retrieval_id):
    """Read saved sources and the provider response without a network request."""
    with Store(project).connect() as c:
        return {"id": retrieval_id, **Store.artifact(c, retrieval_id, "research")}


def list_retrievals(project):
    """Compact local history, without duplicating saved page bodies."""
    with Store(project).connect() as c:
        return [{k: row[k] for k in ("id", "provider", "operation", "request", "retrieved_at", "question", "usage", "warnings")}
                for row in Store.all(c, "research")]


def capture(project, retrieval_ids, spec):
    """Build an evidence packet from saved sources and agent-authored findings."""
    require(retrieval_ids, "Supply at least one retrieval ID.")
    require(isinstance(spec, dict) and "sources" not in spec,
            "When using saved retrievals, supply findings and limitations; sources come from the retrievals.")
    sources = {}
    limitations = []
    for retrieval_id in retrieval_ids:
        saved = show(project, retrieval_id)
        sources.update({s["id"]: s for s in saved["sources"]})
        limitations.extend(saved["limitations"])
    bundle = copy.deepcopy(spec)
    bundle["sources"] = list(sources.values())
    if sources and all(s.get("capture", {}).get("method") == "exa_snapshot" for s in sources.values()):
        bundle.setdefault("information_as_of", max((s["capture"]["snapshot_as_of"] for s in sources.values()), key=time))
    bundle["limitations"] = list(dict.fromkeys([*bundle.get("limitations", []), *limitations]))
    return capture_bundle(bundle)
