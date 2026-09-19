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
DOMAINS = ("freddiemac.com", "census.gov", "cdc.gov", "nasa.gov", "weather.gov", "dunemovie.com", "noaa.gov")
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
    require("Failed to fetch" not in content and "not accessible via this tool" not in content and "Internal Error" not in content, "Cannot present failed access as a source capture.")
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
    mortgage = source('mortgage', 'Freddie Mac reports 30-year fixed mortgage rates of 6.95% on September 17, 6.76% on September 10, 6.71% on September 3, 6.66% on August 27, and 6.65% on August 20, 2026. These are prior weekly observations, not the September 24 result.',
                      {'30_year_FRM_percent': {'2026-09-17': 6.95, '2026-09-10': 6.76, '2026-09-03': 6.71, '2026-08-27': 6.66, '2026-08-20': 6.65}})
    housing = source('housing', 'The Census Bureau September 17 release reports August housing starts of 1.275 million at a seasonally adjusted annual rate, versus revised July 1.309 million. August permits were 1.394 million versus revised July 1.433 million. The August starts month-on-month change is -2.6% with reported sampling margin of +/-12.0 percentage points.',
                     {'starts_SAAR_millions': {'2026-08':1.275,'2026-07':1.309}, 'permits_SAAR_millions':{'2026-08':1.394,'2026-07':1.433}})
    packet('mortgage',[mortgage],['Five recent weekly observations, not a fitted rate-transition distribution. No bond-yield or lender-level evidence included.'])
    packet('housing',[housing,mortgage],['September starts have not been released; August estimates are preliminary and can be revised. A sampling interval for a past monthly change is not a predictive interval for the next release.'])
    disease = source('measles','CDC data updated September 18 report 3,471 confirmed U.S. measles cases as of September 17, 2026, including 17 international visitors. There are 39 new outbreaks; 95% of cases are outbreak-associated. Full-year 2025 had 2,289 cases. The current count is below 6,000.',
                     {'as_of':'2026-09-17','2026_US_cases':3471,'2026_new_outbreaks':39,'outbreak_associated_fraction':.95,'2025_US_cases':2289})
    packet('measles',[disease],['Confirmed, provisional CDC counts; reporting lags and revisions apply. CDC assigns cases to years by epidemiological week of rash onset. No weekly growth series or transmission model is supplied; cumulative totals alone do not establish the remaining-year incidence rate.'])
    heat = source('global_heat','NASA GISS LOTI anomalies relative to 1951-1980 for January-August 2026 are 1.09, 1.25, 1.32, 1.17, 1.13, 1.18, 1.25, and 1.40 degrees C. September-December and annual 2026 values are missing. The unsmoothed annual 2025 value is 1.19 C; annual 2024 is 1.29 C. The contract explicitly requires exceeding 1.28 C and the 2025 value.',
                  {'base_period':'1951-1980','2026_monthly_C':[1.09,1.25,1.32,1.17,1.13,1.18,1.25,1.40],'annual_2025_C':1.19,'annual_2024_C':1.29},
                  receipt='global_heat-tail.json',url='https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.txt')
    # Keep the legal threshold out of research evidence; it is supplied in the definition.
    heat[0]['excerpt'] = heat[0]['excerpt'].replace(' The contract explicitly requires exceeding 1.28 C and the 2025 value.','')
    packet('global_heat',[heat],['The annual target remains unknown, with four months missing. Use the stated contractual numerical threshold rather than silently replacing it with the revised historical record. No ENSO forecast or fitted annual-temperature predictive distribution is supplied.'])
    miami_url='https://forecast.weather.gov/MapClick.php?FcstType=text&TextType=2&lat=25.7939&lg=english&lon=-80.313&unit=0'
    miami=source('miami','An NWS search-index capture for Miami International Airport, updated September 18 at 4:06 pm EDT, forecasts Saturday September 19 high near 89 F, with an 80% precipitation chance and thunderstorms. This is a point forecast, not the probability of a two-degree temperature interval.',
                 {'target_date':'2026-09-19','point_high_F':89,'precipitation_probability':.8,'publication_time':'2026-09-18T16:06:00-04:00'},
                 receipt='miami-search.json',url=miami_url,search=True)
    packet('miami',[miami],['The current forecast is a search-index capture. Two direct coordinate pages were inaccessible; another direct open returned a September 13 forecast, so it was not treated as the September 18 forecast.','Settlement uses The Weather Company; NWS airport-point forecasts may differ in location, rounding, or final station maximum. No fitted forecast-error distribution is supplied.'])
    austin=source('austin','NWS Austin-Bergstrom airport forecast updated September 18 at 5:48 pm CDT gives Saturday September 19 sunny with high near 98 F, calm wind becoming southeast around 5 mph in the afternoon. Sunday high is near 99 F. These are point forecasts, not interval probabilities.',
                  {'target_date':'2026-09-19','Saturday_point_high_F':98,'Sunday_point_high_F':99,'publication_time':'2026-09-18T17:48:00-05:00'})
    packet('austin',[austin],['Settlement uses The Weather Company at Austin CLIAUS. NWS forecasts are outside evidence and can differ in rounding, grid location, or final station maximum. No fitted forecast-error distribution is supplied.'])
    dune=source('dune','The official Dune: Part Three site currently advertises North American theaters and IMAX release December 18, 2026, and international release beginning December 16. The page credits Warner Bros. and Legendary, names Denis Villeneuve as director, and lists early-access screenings December 14 and 15.',
                {'advertised_North_America_release':'2026-12-18','advertised_international_release':'2026-12-16'},
                receipt='dune-full.json',url='https://www.dunemovie.com/')
    packet('dune',[dune],['An advertised schedule is not proof of completed post-production or a guarantee against delay. Some character sections contain placeholder text. The ordinary Warner Bros. page yielded only an iframe; the dedicated official film site supplied the accessible schedule. No historical delay base rate was fitted.'])
    reasons={'mortgage':'Future September 24 survey; latest released observation is September 17.',
             'housing':'September construction month incomplete; release scheduled October 20.',
             'measles':'Full contract terms identify CDC U.S. cases; September 17 count 3471 is below 6000.',
             'global_heat':'NASA September-December and annual 2026 fields missing; future observations required.',
             'miami':'September 19 local day has not begun. All calls must be issued before September 19 04:00 UTC.',
             'austin':'September 19 local day has not begun. All calls must be issued before September 19 05:00 UTC.',
             'dune':'Current official film site continues to advertise the scheduled December 18 release; no present delay established.'}
    cases=load(OUT/'cases.json')
    eligibility={c['id']:{'eligible':True,'checked_at':now(),'rationale':reasons[c['id']]} for c in cases}
    from vorhersage.common import time
    for c in cases:
        require((time(c['question']['event_deadline'])-time(now())).total_seconds()>12*3600,'Insufficient horizon.')
    require(time(now())<time('2026-09-19T03:45:00Z'),'Weather forecast window passed.')
    write(OUT/'outcome-eligibility.json',eligibility)
    write(OUT/'definition-notes.json',{'measles':{'clarification':'The full MEASLES contract terms define the underlying as the number of measles cases in the United States in the specified year according to CDC. Revisions after expiration are not used. This is a definition clarification, not evidence for likelihood.',
                                              'terms_url':'https://assets.kalshi.com/contract_terms/MEASLES.pdf'}})
    print('Seven source packets frozen; all seven outcomes remain unknown.')

if __name__ == '__main__': build()
