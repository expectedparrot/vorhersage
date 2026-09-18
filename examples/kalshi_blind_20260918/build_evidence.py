"""Transparent, deterministic extraction of the coordinator's selected source facts."""

import json
from datetime import datetime, timezone

from study import OUT, load, source_text, source_url, write
from vorhersage.evidence import capture_bundle


def direct(name, title, excerpt):
    receipt = load(OUT / "research" / (name + ".json"))
    assert receipt["accepted"]
    return source(name, receipt["final_url"], title, excerpt, receipt["text"], receipt["retrieved_at"], name + ".json")


def browser(name, receipt_name, url, title, excerpt, marker):
    receipt = load(OUT / "research" / (receipt_name + ".json"))
    parts = receipt["result"].split("-" * 80)
    body = next(p for p in parts if marker in p and url in p)
    stamp = datetime.strptime(receipt["retrieved_at"], "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc).isoformat()
    return source(name, url, title, excerpt, body, stamp, receipt_name + ".json")


def source(name, url, title, excerpt, content, stamp, receipt):
    source_url(url)
    source_text(content)
    source_text(excerpt)
    return {"id": name, "url": url, "title": title, "excerpt": excerpt, "excerpt_kind": "paraphrase",
            "retrieved_at": stamp, "capture": {"method": "fetched", "captured_at": stamp, "content": content,
                "metadata": {"retrieval_receipt": "research/" + receipt,
                             "note": "Direct HTTP or browser-extracted source text; excerpt is a coordinator paraphrase checked against the saved response."}}}


def packet(name, entries, limitations):
    sources, findings = [], []
    for s, value in entries:
        sources.append(s)
        findings.append({"id": s["id"], "claim": s["excerpt"], "claim_type": "reporting", "source_ids": [s["id"]], "value": value})
    bundle = {"sources": sources, "findings": findings, "limitations": limitations + [
        "Small coordinator-selected source packet; gaps remain and facts must not be confused with calibrated probabilities.",
        "Primary-source domain checks and lexical screening found no excluded content; these checks cannot establish complete absence of indirect influence."]}
    result = capture_bundle(bundle)
    source_text(json.dumps(result))
    write(OUT / "packets" / (name + ".json"), result)


def build():
    weather = json.loads(load(OUT / "research/weather_forecast.json")["text"])["properties"]
    packet("weather", [
        (direct("weather_forecast", "NWS forecast at LAX airport", "The NWS forecast updated September 18 gives Friday a high near 79 F, mostly sunny skies, and west-southwest wind of 0–15 mph."),
         {"updateTime": weather["updateTime"], "periods": weather["periods"][:4]}),
        (direct("weather_climate", "NWS CLILAX daily climate report", "CLILAX identifies Los Angeles International Airport. September 17's maximum was 78 F; the September 18 climate normal maximum is 76 F."),
         {"station": "Los Angeles International Airport", "previous_day_max_F": 78, "normal_today_max_F": 76}),
    ], ["The settlement source is a commercial weather product, while these observations and forecasts are NWS products.",
        "A deterministic high forecast does not supply a predictive distribution or measured forecast-error scale. No historical residual distribution was fitted.",
        "The current-day maximum is still unknown; the source climate report describes the previous day."])
    employment = browser("bls_august", "primary-web-followup", "https://www.bls.gov/news.release/archives/empsit_09042026.htm",
        "BLS August 2026 Employment Situation", "The September 4 BLS release reports unemployment of 4.1% in August and July, versus 4.2% in June. August nonfarm payroll growth was 162,000. September's release is scheduled for October 2 at 8:30 a.m. ET.", "Employment Situation")
    packet("employment", [(employment, {"unemployment_percent": {"2026-06": 4.2, "2026-07": 4.1, "2026-08": 4.1},
        "August_payroll_change": 162000, "June_revised_payroll_change": 31000, "July_revised_payroll_change": 21000,
        "September_release": "2026-10-02T12:30:00Z"})],
        ["Direct BLS requests and a FRED historical download failed; BLS facts were recovered using the browser tool.",
         "Three recent unemployment readings are not a full transition distribution. September survey results and relevant future shocks are unknown.",
         "Strictly above 4.4% means at least 4.5% at the published one-decimal precision."])
    projection = "September FOMC projections show a median end-2026 federal-funds midpoint of 4.1%, with a 3.9–4.4% participant range. Median end-2026 unemployment is 4.1%; PCE inflation 3.7%; core PCE inflation 3.4%. These are conditional policy judgments, not next-meeting probabilities."
    packet("fed", [
        (direct("fed_statement", "September 16, 2026 FOMC statement", "The September 16 statement reports a unanimous 12–0 decision to raise the target range by 25 basis points to 3.75–4.00%. It describes solid economic activity and elevated inflation."),
         {"decision": "hike", "basis_points": 25, "new_range_percent": [3.75, 4.00], "vote": "12-0"}),
        (direct("fed_projections", "September 2026 Summary of Economic Projections", projection),
         {"median_year_end_midpoint_percent": 4.1, "participant_year_end_range_percent": [3.9, 4.4],
          "median_2026_PCE_inflation_percent": 3.7, "median_2026_core_PCE_inflation_percent": 3.4}),
    ], ["Year-end dot projections do not identify which meeting will contain an adjustment; two scheduled meetings remain after September.",
        "New inflation and employment information before October 28 can change policy."])
    neutron = browser("neutron_q2", "final-primary-open",
        "https://investors.rocketlabcorp.com/news-releases/news-release-details/rocket-lab-announces-second-quarter-2026-financial-results-posts",
        "Rocket Lab Q2 2026 results, August 10", "Rocket Lab reported progress in first-flight hardware assembly, integration and testing. Stage 1 tank production was aligned with delivery of Neutron to the launch pad in Q4 2026. Delivery to the pad is a different milestone from launch.", "Release Details")
    packet("neutron", [(neutron, {"statement_date": "2026-08-10", "target": "vehicle delivery to launch pad in Q4 2026",
                                 "remaining_work": "first-flight hardware assembly, integration and testing"})],
        ["A company schedule is an interested-party forward-looking statement, not independently verified readiness.",
         "The reviewed statement provides no exact launch date or completed integrated-test sequence. The packet does not establish how much work was completed after August 10.",
         "A September 15 official company announcement still describes Neutron as upcoming in discovery; no confirmed launch was found in the inspected official results."])
    netflix = browser("netflix_us_week", "primary-web-open", "https://www.netflix.com/tudum/top10/united-states",
        "Netflix US weekly film ranking, September 7–13", "For September 7–13, the US film chart ranks Why Did I Get Married Again? first, Those Who Wish Me Dead second, and The Whisper Man third. This is the preceding week, not the contract's target week.", "Top 10 Movies in United States")
    packet("netflix", [(netflix, {"week_start": "2026-09-07", "week_end": "2026-09-13",
        "top_10": ["Why Did I Get Married Again?", "Those Who Wish Me Dead", "The Whisper Man", "Turning Point: Generation 9/11", "Contraband", "Untold Mr. T: I Pity The Fool", "The Angry Birds Movie 2", "Shark Tale", "The Secret Woman", "Ready or Not"],
        "target_week_ends": "2026-09-20", "target_chart_publication": "2026-09-22"})],
        ["Direct chart downloads failed; the browser tool recovered the official preceding-week US ranking.",
         "This packet lacks current-week US viewing counts, daily trajectory and a complete competing-release slate; persistence must remain an assumption."])
    schedule = json.loads(load(OUT / "research/baseball_schedule.json")["text"])["dates"][0]["games"][0]
    standings = json.loads(load(OUT / "research/baseball_standings.json")["text"])
    teams = []
    for group in standings["records"]:
        for t in group["teamRecords"]:
            if t["team"]["id"] in (158, 110):
                teams.append({**{k: t[k] for k in ("team", "wins", "losses", "runsScored", "runsAllowed", "runDifferential")},
                              "home_away": t["records"]["overallRecords"]})
    packet("baseball", [
        (direct("baseball_schedule", "MLB official September 20 schedule", "MLB lists Milwaukee at Baltimore on September 20 at 23:20 UTC, at Oriole Park. The game status is Scheduled. The response does not name probable starting pitchers."),
         {"gamePk": schedule["gamePk"], "gameDate": schedule["gameDate"], "status": schedule["status"], "away": "Milwaukee Brewers", "home": "Baltimore Orioles", "venue": schedule["venue"]}),
        (direct("baseball_standings", "MLB standings through September 17", "Milwaukee is 95–58 with a +197 run differential; Baltimore is 75–78 with a −26 differential. Milwaukee's road record is 43–32, while Baltimore's home record is 36–39."), teams),
    ], ["The future game's starting pitchers, final lineups, injuries and bullpen availability are not established in this packet.",
        "Season win rates and run differentials need an explicit transfer assumption for a single game against this opponent; home advantage and schedule strength can matter."])
    print("Built six outside-source packets; no target probabilities read.")


if __name__ == "__main__":
    build()
