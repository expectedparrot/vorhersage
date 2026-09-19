"""Frozen, primary-source evidence for the expanded experiment."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from vorhersage.common import load, now, require
from vorhersage.evidence import capture_bundle

HERE = Path(__file__).resolve().parent
OUT = HERE / "run"
DOMAINS = ("bea.gov", "bls.gov", "federalreserve.gov", "atlantafed.org", "nhc.noaa.gov",
           "noaa.gov", "nfl.com", "faa.gov", "spacex.com", "usgs.gov")
EXCLUDED = re.compile(r"kalshi|polymarket|predictit|manifold\.markets|prediction[ -]markets?|sportsbook|betting odds", re.I)


def check_url(url):
    p = urlparse(url)
    require(p.scheme == "https" and not p.username and not p.password, "Invalid source URL.")
    require(any(p.hostname == d or (p.hostname or "").endswith("." + d) for d in DOMAINS), "Outside primary-source allowlist.")
    check_text(url)


def check_text(value):
    require(not EXCLUDED.search(value), "Excluded source content; quarantine rather than pass to models.")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), "Frozen artifact already exists: " + str(path))
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def source(name, claim, value, *, receipt=None, url=None, search=False):
    filename = receipt or name + "-open.json"
    record = load(OUT / "research" / filename)
    content = record["result"]
    url = url or record["url"]
    if search:
        content = next(p for p in content.split("-" * 80) if "(" + url + ")" in p).strip()
    require("Failed to fetch" not in content, "Cannot present failed access as a source capture.")
    check_url(url)
    check_text(content)
    check_text(claim)
    stamp = datetime.strptime(record["retrieved_at"], "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc).isoformat()
    s = {"id": name, "url": url, "title": content.splitlines()[0], "excerpt": claim,
         "excerpt_kind": "paraphrase", "retrieved_at": stamp,
         "capture": {"method": "manual" if search else "fetched", "captured_at": stamp,
                     "content": content, "metadata": {"receipt": "research/" + filename,
                         "mechanism": "Search-index source excerpt; direct page access failed." if search else "Browser-extracted page text; not an original HTTP body.",
                         "interpretation": "Coordinator-selected paraphrase and deterministic table extraction; sources remain external assertions."}}}
    return s, value


def packet(cid, entries, limitations):
    bundle = {"sources": [s for s, _ in entries], "findings": [
        {"id": s["id"], "claim": s["excerpt"], "claim_type": "reporting", "source_ids": [s["id"]], "value": v}
        for s, v in entries], "limitations": limitations + [
            "Small coordinator-selected packet; no fitted probability model or complete research review.",
            "Different questions can share source information and economic drivers; do not treat their errors as independent."]}
    result = capture_bundle(bundle)
    check_text(json.dumps(result))
    path = OUT / "packets" / (cid + ".json")
    if path.exists():
        old = load(path)
        require(old["records"] == result["records"] and old["limitations"] == result["limitations"], "Packet content changed.")
        return
    write(path, result)


def clean(text):
    text = re.sub(r"cite[^†]+†([^]+)", r"\1", text)
    return re.sub(r"L\d+:\s*", "", text)


def build():
    gdp = source("gdp", "BEA's second estimate puts Q2 2026 real GDP growth at 1.5% annualized, following 2.1% in Q1. These are past quarters, not the target advance estimates.",
                 {"Q1_2026_real_GDP_SAAR_percent": 2.1, "Q2_2026_second_estimate_SAAR_percent": 1.5})
    gdpnow = source("gdpnow", "Atlanta Fed GDPNow estimates Q3 2026 real growth at 5.1% annualized on September 17, unchanged from September 16; September 10 was 4.4%. The next update is September 25.",
                    {"target_quarter": "2026 Q3", "SAAR_percent": 5.1, "estimate_date": "2026-09-17", "previous_September_10": 4.4})
    jobs = source("jobs", "BLS reports August payroll growth of 162,000 and unemployment of 4.1%. June payroll growth was revised to 31,000 and July to 21,000. September's release is scheduled for October 2.",
                  {"payroll_changes": {"2026-06": 31000, "2026-07": 21000, "2026-08": 162000},
                   "August_U3_percent": 4.1, "next_release": "2026-10-02T12:30:00Z"})
    cpi = source("cpi", "BLS reports August seasonally adjusted headline CPI growth of 0.4%, core growth of 0.3%, and gasoline growth of 3.9%. July headline growth was 0.1%. August twelve-month headline inflation was 3.4%.",
                 {"headline_monthly_percent": {"2026-02": .3, "2026-03": .9, "2026-04": .6,
                   "2026-05": .5, "2026-06": -.4, "2026-07": .1, "2026-08": .4},
                  "August_core_monthly_percent": .3, "August_gasoline_monthly_percent": 3.9, "August_headline_yearly_percent": 3.4})
    fed = source("fed", "On September 16 the FOMC unanimously raised its policy target by 25 basis points to 3.75–4.00%, citing solid growth and elevated inflation.",
                 {"decision": "hike", "basis_points": 25, "new_range_percent": [3.75, 4], "vote": "12-0"})
    projections = source("projections", "September FOMC projections give median end-2026 policy midpoint 4.1%, range 3.9–4.4%; Q4 unemployment median 4.1%; 2026 PCE inflation 3.7% and core PCE 3.4%; Q4/Q4 real GDP growth 2.3%.",
                         {"end_2026_policy_midpoint_median_percent": 4.1, "policy_range_percent": [3.9, 4.4],
                          "Q4_unemployment_median_percent": 4.1, "PCE_inflation_percent": 3.7,
                          "core_PCE_inflation_percent": 3.4, "Q4_over_Q4_GDP_growth_percent": 2.3})
    for n in (1, 2):
        packet(f"candidate-{n:02d}", [gdp, gdpnow, projections], [
            "GDPNow covers Q3 only, not Q4; it is a point nowcast, not a probability or a promise of the advance release.",
            "Annual Q4/Q4 growth differs from quarter-on-quarter annualized growth. No historical nowcast-error distribution has been fitted."])
    for n in (3, 4, 7):
        packet(f"candidate-{n:02d}", [jobs, projections], [
            "Only three recent payroll readings are included. September and October survey results are unknown.",
            "A Q4 unemployment projection is a quarterly average, not the October reading; payroll employment and unemployment come from different surveys."])
    for n in (5, 6):
        packet(f"candidate-{n:02d}", [cpi, projections], [
            "October and November price data are not observed. No current commodity-price forecast or complete CPI component model is supplied.",
            "PCE is a different index from CPI; annual inflation is not monthly inflation. Strict threshold and one-decimal rounding matter."])
    packet("candidate-08", [fed, projections, cpi, jobs], [
        "A year-end policy projection does not identify the December meeting's action; policy can change at the October meeting first.",
        "No meeting-specific probabilities are supplied. New releases and shocks can change policy."])
    hurricane = source("hurricane_summary", "NHC's 2026 Atlantic summary as of September 18 at 21 UTC lists five named storms, no hurricanes, and no major hurricanes; accumulated cyclone energy is 4.4.",
                       {"as_of": "2026-09-18T21:00:00Z", "named_storms": 5, "hurricanes": 0, "major_hurricanes": 0, "ACE": 4.4},
                       receipt="counts-search.json", url="https://www.nhc.noaa.gov/data/tcr/index.php", search=True)
    climate = source("hurricane_climatology", "NHC's 1991–2020 Atlantic climatology averages 14 named storms, seven hurricanes, and three major hurricanes per season. The Atlantic season runs June 1 through November 30.",
                     {"normal_period": "1991-2020", "annual_named_storms": 14, "annual_hurricanes": 7, "annual_major_hurricanes": 3},
                     receipt="counts-search.json", url="https://www.nhc.noaa.gov/climo/", search=True)
    packet("candidate-12", [hurricane, climate], [
        "Direct NHC page opens returned 403; these are saved primary-source search-index excerpts, not independently fetched full pages.",
        "The annual climatological mean is not a mean for the remaining season. No conditional late-season model or current basin forecast is included.",
        "The summary is dated September 18 at 21 UTC; later observations or retrospective classification revisions are not included."])
    standings = clean(load(OUT / "research/nfl_standings-open.json")["result"])
    injury_raw = load(OUT / "research/nfl_injuries-open.json")["result"]
    games = [
        (15, "Cincinnati Bengals", "Houston Texans", 99, 121, "2026-09-20T17:00:00Z"),
        (16, "Cleveland Browns", "Tampa Bay Buccaneers", 174, 196, "2026-09-20T17:00:00Z"),
        (17, "Jacksonville Jaguars", "Denver Broncos", 221, 245, "2026-09-20T20:05:00Z"),
        (18, "Las Vegas Raiders", "Los Angeles Chargers", 246, 271, "2026-09-20T20:05:00Z"),
        (19, "Miami Dolphins", "San Francisco 49ers", 320, 344, "2026-09-20T20:25:00Z"),
        (20, "Seattle Seahawks", "Arizona Cardinals", 272, 296, "2026-09-20T20:25:00Z"),
    ]
    for n, away, home, first, last, kickoff in games:
        teams = []
        for team in (away, home):
            row = next(line for line in standings.splitlines() if team in line and " | " in line)
            values = row.split(" | ")[1:8]
            teams.append(dict(zip(("wins", "losses", "ties", "win_fraction", "points_for", "points_against", "net_points"), values), team=team))
        record = source("nfl_standings", f"NFL's 2026 regular-season standings show the first-game records and scoring totals for {away} and {home}.", teams)
        selection = "\n".join(line for line in injury_raw.splitlines()
                              if (m := re.match(r"L(\d+):", line)) and first <= int(m[1]) <= last)
        detail = clean(selection)
        require(away in detail and home in detail, "Injury section does not match game.")
        injuries = source("nfl_injuries", f"NFL's September 18 Week 2 report schedules {away} at {home} for September 20 and lists the following player availability.",
                          {"away": away, "home": home, "kickoff": kickoff, "reported_availability": detail})
        packet(f"candidate-{n:02d}", [record, injuries], [
            "Only one regular-season game has been played by these teams; records and scoring totals are a very small sample.",
            "No opponent-adjusted strength model or final game-day inactive list is supplied. Injury designations can change before kickoff.",
            "Forecast the stated team's probability of winning. A tie is not a win; the contract's fractional tie settlement makes the evaluation price a payout proxy."])
    eligibility = {}
    for c in load(OUT / "cases.json"):
        cid = c["id"]
        if cid == "candidate-10":
            reason = "FAA's linked current launch-count dashboard returned 403; annual threshold crossing cannot be ruled out from the accessible sources."
        elif cid == "candidate-11":
            reason = "Supplied earthquake rules specify an end date but not an unambiguous event-window start; no forecasting against an assumed window."
        else:
            reason = None
        eligibility[cid] = {"eligible": reason is None, "checked_at": now(), "reason": reason or (
            "Official NFL Week 2 report schedules this game on September 20, after inference." if c["series"] == "KXNFLGAME" else
            "NHC's dated summary shows zero major hurricanes so far; target requires more than three before December 1." if cid == "candidate-12" else
            "Target economic period/release or policy meeting lies in the future; current official sources report earlier periods only."),
            "evidence_packet": "packets/" + cid + ".json" if reason is None else None}
    write(OUT / "outcome-eligibility.json", eligibility)
    print("Built 15 shared packets; two quote-eligible cases excluded before model calls.")


if __name__ == "__main__":
    build()
