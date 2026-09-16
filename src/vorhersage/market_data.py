"""Public GET-only market adapters. Discovery never returns numerical forecasts."""

import hashlib
import json
import math
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .common import Error, digest, now, probability, require, time

KALSHI = "https://external-api.kalshi.com/trade-api/v2"
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"


def get(url):
    started = now()
    try:
        request = Request(url, headers={"User-Agent": "vorhersage/0.3 market-workbench", "Accept": "application/json"})
        with urlopen(request, timeout=25) as response:
            raw = response.read(10_000_001)
        require(len(raw) <= 10_000_000, "Market response exceeds size limit.")
        data = json.loads(raw)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        # Do not echo response bodies: errors must not inadvertently reveal prices.
        raise Error("market_fetch_failed", "Public market GET failed for " + url) from exc
    return {"url": url, "request_started_at": started, "retrieved_at": now(),
            "response_sha256": hashlib.sha256(raw).hexdigest(), "data": data}


def _array(value):
    return json.loads(value) if isinstance(value, str) else value


def contract(venue, m):
    """Allowlisted terms only. Never forward arbitrary exchange metadata."""
    if venue == "kalshi":
        return {"venue": venue, "market_id": m["ticker"], "title": m.get("title", m["ticker"]),
                "yes_description": m.get("yes_sub_title", ""),
                "rules": "\n\n".join(s for s in (m.get("rules_primary"), m.get("rules_secondary")) if s),
                "scheduled_close": m.get("close_time"), "resolution_source": "See frozen Kalshi rules and series contract.",
                "event_group": m.get("event_ticker", m["ticker"])}
    require(venue == "polymarket", "Unsupported exchange.")
    return {"venue": venue, "market_id": str(m["id"]), "title": m["question"],
            "yes_description": "Yes", "rules": m.get("description", ""),
            "scheduled_close": m.get("endDate"), "resolution_source": m.get("resolutionSource", "See market rules."),
            "event_group": str((m.get("events") or [{}])[0].get("id", m.get("conditionId", m["id"])))}


def inspect(venue, market_id):
    base = KALSHI if venue == "kalshi" else GAMMA
    require(venue in ("kalshi", "polymarket"), "Unsupported exchange.")
    response = get(base + "/markets/" + quote(str(market_id), safe=""))
    m = response["data"]["market"] if venue == "kalshi" else response["data"]
    return contract(venue, m)


def browse(venue, query="", limit=10, pages=3, series=None):
    require(venue in ("kalshi", "polymarket"), "Unsupported exchange.")
    require(1 <= limit <= 50 and 1 <= pages <= 10, "Use limit 1..50 and pages 1..10.")
    require(not series or venue == "kalshi", "Series filtering is Kalshi-only.")
    matches, cursor, scanned = [], None, 0
    more = False
    for page in range(pages):
        if venue == "kalshi":
            params = {"status": "open", "limit": 100, "mve_filter": "exclude"}
            if cursor:
                params["cursor"] = cursor
            if series:
                params["series_ticker"] = series
            result = get(KALSHI + "/markets?" + urlencode(params))["data"]
            markets, cursor = result["markets"], result.get("cursor")
            more = bool(cursor)
        else:
            params = {"active": "true", "closed": "false", "limit": 100, "offset": page * 100,
                      "order": "volume24hr", "ascending": "false"}
            markets = get(GAMMA + "/markets?" + urlencode(params))["data"]
            more = len(markets) == 100
        for m in markets:
            scanned += 1
            if venue == "kalshi" and m.get("market_type", "binary") != "binary":
                continue
            if venue == "polymarket" and set(_array(m.get("outcomes", []))) != {"Yes", "No"}:
                continue
            item = contract(venue, m)
            if query.casefold() in (item["title"] + " " + item["rules"]).casefold():
                matches.append(item)
        if len(matches) >= limit or not more:
            break
    return {"candidates": matches[:limit], "scanned": scanned, "more_available": more or len(matches) > limit,
            "note": "Bounded discovery; no prices shown. Inspect terms, then start to check an active two-sided book. Scheduled close is not necessarily the event deadline."}


def _levels(rows, divisor=1, complement=False):
    out = []
    for row in rows or []:
        p, size = (row["price"], row["size"]) if isinstance(row, dict) else row
        p, size = float(p) / divisor, float(size)
        probability(p)
        require(math.isfinite(size) and size >= 0, "Invalid order size.")
        if size > 0:
            out.append([round(1 - p, 10) if complement else p, size])
    return out


def summarize_book(bids, asks):
    bids = sorted(bids, reverse=True)
    asks = sorted(asks)
    require(bids and asks, "Market needs nonempty bids and asks.", "unusable_market")
    bid, ask = bids[0][0], asks[0][0]
    require(0 < bid <= ask < 1, "Market needs an uncrossed, non-extreme two-sided book.", "unusable_market")
    return {"bid": bid, "ask": ask, "midpoint": (bid + ask) / 2, "spread": round(ask - bid, 10),
            "bid_size": bids[0][1], "ask_size": asks[0][1],
            "bid_contracts_within_2c": sum(s for p, s in bids if p >= bid - .02 - 1e-9),
            "ask_contracts_within_2c": sum(s for p, s in asks if p <= ask + .02 + 1e-9)}


def snapshot(venue, market_id):
    """Coordinator only: response includes hidden prices and original API bodies."""
    require(venue in ("kalshi", "polymarket"), "Unsupported exchange.")
    base = KALSHI if venue == "kalshi" else GAMMA
    response = get(base + "/markets/" + quote(str(market_id), safe=""))
    m = response["data"]["market"] if venue == "kalshi" else response["data"]
    if venue == "kalshi":
        require(m.get("market_type", "binary") == "binary" and m.get("status") in ("active", "open")
                and not m.get("result"), "Market is not an unresolved active binary contract.", "unusable_market")
        book_response = get(KALSHI + "/markets/" + quote(str(market_id), safe="") + "/orderbook?depth=100")
        book = book_response["data"]
        if "orderbook_fp" in book:
            book = book["orderbook_fp"]
            bids = _levels(book.get("yes_dollars"))
            asks = _levels(book.get("no_dollars"), complement=True)
        else:
            book = book["orderbook"]
            dollar = "yes_dollars" in book
            bids = _levels(book.get("yes_dollars" if dollar else "yes"), 1 if dollar else 100)
            asks = _levels(book.get("no_dollars" if dollar else "no"), 1 if dollar else 100, True)
    else:
        require(m.get("active") is True and not m.get("closed") and m.get("acceptingOrders") is True
                and m.get("enableOrderBook") is True,
                "Market is not active and accepting orders.", "unusable_market")
        outcomes, tokens = _array(m["outcomes"]), _array(m["clobTokenIds"])
        require(len(outcomes) == len(tokens) == 2 and set(outcomes) == {"Yes", "No"}, "Only binary Yes/No markets are supported.")
        token = tokens[outcomes.index("Yes")]
        book_response = get(CLOB + "/book?" + urlencode({"token_id": token}))
        book = book_response["data"]
        require(str(book.get("asset_id")) == str(token), "Order book outcome identity mismatch.")
        bids, asks = _levels(book.get("bids")), _levels(book.get("asks"))
    terms = contract(venue, m)
    require(terms["market_id"] == str(market_id), "Market identity mismatch.")
    require(terms["rules"], "Market has no resolution rules.")
    # Gamma endDate is often a date marker at midnight, not the actual trading
    # cutoff (e.g. an afternoon FOMC announcement). The reviewed question supplies
    # the event deadline; do not mistake Gamma's date marker for known resolution.
    if venue == "kalshi" and terms["scheduled_close"]:
        require(time(terms["scheduled_close"]) > time(now()), "Market close has passed.", "unusable_market")
    return {"venue": venue, "market_id": str(market_id), "captured_at": book_response["retrieved_at"],
            "contract": terms, "contract_sha256": digest(terms), "quote": summarize_book(bids, asks),
            "raw": [response, book_response]}
