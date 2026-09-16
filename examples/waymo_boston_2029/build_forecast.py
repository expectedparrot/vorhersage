"""Issue the September 15, 2026 researched forecast once, or re-export its history.

Research was performed by the assistant using web search/page retrieval before
this script was authored. Running this script does not refresh the evidence.
"""

import json
from pathlib import Path

from vorhersage.common import now
from vorhersage.evidence import audit
from vorhersage.odds import calculate
from vorhersage.store import Store
from vorhersage.widget import export
from vorhersage.workflow import Workflow

ROOT = Path(__file__).resolve().parent
QUESTION_ID = "waymo_boston_public_paid_driverless_before_2029"
CUTOFF = "2026-09-15T23:04:02Z"
DEADLINE = "2029-01-01T00:00:00-05:00"

# Concise manual paraphrases, not raw page captures. Unknown exact publication
# times remain null; date labels are retained separately in provenance.
SOURCES = {
    "boston_plan": ("https://waymo.com/blog/shorts/back-to-boston/", "Waymo: return to Boston", "2026-02-05",
        "Waymo announces a return to Boston to prepare future service, describes adaptation to local roads and winter conditions, and says state legalization is needed before fully autonomous rides."),
    "service_map": ("https://waymo.com/rides/", "Waymo service locations", None,
        "The retrieved service-location page puts Boston among upcoming cities, rather than cities currently serving riders."),
    "september_rollout": ("https://waymo.com/blog/2026/09/ride-in-denver-san-diego-tampa/", "Waymo September city launches", "2026-09-01",
        "Waymo announces initial public riders in Denver, San Diego and Tampa, bringing its count to 14 cities; access expands gradually rather than opening to everyone immediately."),
    "funding": ("https://waymo.com/blog/2026/02/waymo-raises-usd16-billion-investment-round/", "Waymo financing announcement", "2026-02-02",
        "Waymo reports raising $16 billion to support expansion, with Alphabet remaining its majority investor."),
    "access_history": ("https://support.google.com/waymo/announcements/12766613?hl=en", "Waymo rider announcements", None,
        "Waymo lists initial Dallas and Houston access on February 24, 2026, then access for everyone in Dallas on August 4 and Houston on August 20. Las Vegas begins adding riders on September 14."),
    "ma_testing": ("https://www.mass.gov/info-details/general-requirements-safe-testing-of-automated-driving-systems", "MassDOT automated-driving testing requirements", None,
        "MassDOT's indexed testing requirements specify a trained test driver inside the vehicle who can monitor and immediately take control. A direct page open failed; this observation uses the official search-index excerpt."),
    "house_enabling": ("https://malegislature.gov/Bills/194/H3634", "Massachusetts H.3634 history", None,
        "The enabling bill H.3634 accompanied study order H.5326 on April 6, 2026; its retrieved history does not show enactment."),
    "senate_enabling": ("https://malegislature.gov/Bills/194/S2379", "Massachusetts S.2379 history", None,
        "The enabling bill S.2379 accompanied study order S.3245 on July 31, 2026, after reporting extensions; its retrieved history does not show enactment."),
    "house_restrictive": ("https://malegislature.gov/Bills/194/H3669", "Massachusetts H.3669 history", None,
        "The competing autonomous-vehicle safety bill H.3669 accompanied study order H.5328 on April 9, 2026."),
    "senate_restrictive": ("https://malegislature.gov/Bills/194/S2393", "Massachusetts S.2393 history", None,
        "The competing autonomous-vehicle safety bill S.2393 accompanied study order S.3245 on July 31, 2026."),
    "city_docket": ("https://boston.legistar.com/LegislationDetail.aspx?GUID=311445A0-001C-4CA7-ADB2-714EBFC16391&ID=7504068&Options=&Search=", "Boston commercial AV ordinance docket", None,
        "Boston docket 2025-1432 records a commercial autonomous-vehicle ordinance and council proceedings. Its status is Filed, not an enacted ordinance."),
    "local_reporting": ("https://www.boston.com/news/business/2026/02/06/waymo-wants-to-expand-into-boston-massachusetts-law-isnt-ready/", "Boston.com on Waymo and local opposition", "2026-02-06",
        "Local reporting describes city concerns about street navigation and labor opposition, alongside legislative and accessibility support for Waymo."),
    "ballot_list": ("https://www.sec.state.ma.us/divisions/news/right-story.htm", "Massachusetts final ballot signature certification", "2026-07-17",
        "The Secretary of the Commonwealth lists eight qualifying initiative petitions plus the firearms referendum; no autonomous-vehicle restriction appears among them."),
}

FINDINGS = [
    ("boston_intent", ["boston_plan"], "Waymo has publicly committed to preparing a future Boston service.", "delivery", 1.8, [1, 3]),
    ("boston_weather", ["boston_plan"], "Waymo describes local-road adaptation and winter validation; this is not a demonstrated Boston commercial winter service.", "delivery", 0.9, [0.6, 1.2]),
    ("boston_not_live", ["service_map"], "Boston is listed as upcoming on the checked Waymo service page.", "delivery", 1, [0.8, 1.1]),
    ("multi_city_execution", ["september_rollout"], "Waymo has recently extended initial rider access to three more cities, including Denver.", "delivery", 1.5, [1, 2]),
    ("expansion_capital", ["funding"], "Waymo reports substantial committed financing for expansion.", "delivery", 1.2, [1, 1.5]),
    ("public_access_lag", ["access_history"], "Recent Texas launches illustrate a months-long gap between selected-rider access and access for everyone.", "delivery", 0.9, [0.7, 1]),
    ("driver_requirement", ["ma_testing"], "The checked state testing framework requires an in-vehicle driver; testing permission does not establish permission for the forecasted service.", "permission", 0.65, [0.4, 0.9]),
    ("house_study_order", ["house_enabling"], "A principal House enabling proposal went to a study order in April 2026.", "permission", 0.8, [0.5, 1]),
    ("senate_study_order", ["senate_enabling"], "The Senate enabling proposal also went to a study order in July 2026.", "permission", 0.75, [0.5, 1]),
    ("local_acceptance", ["city_docket", "local_reporting"], "Boston has debated restrictions and faces local concerns; the checked docket does not establish an enacted city ban.", "permission", 0.8, [0.6, 1.1]),
    ("competing_bills_stalled", ["house_restrictive", "senate_restrictive"], "Competing safety proposals also went to study orders; the enabling bills' lack of enactment is not evidence that those competing proposals passed.", "permission", 1.05, [1, 1.2]),
    ("no_av_ballot_item", ["ballot_list"], "The checked final ballot-certification list contains no autonomous-vehicle restriction; this limited absence check does not settle future legislative policy.", "permission", 1.05, [1, 1.2]),
]

LIMITATIONS = [
    "One assistant's subjective assessment; anchor and likelihood ratios are assumed, not fitted or calibrated.",
    "Research preceded workflow creation. The anchor is an explanatory starting assumption, not a preregistered blind prior.",
    "No complete sampled reference class of announced-city launches; selected rollout examples are illustrative and subject to selection bias.",
    "Manual paraphrases from web retrieval and official search excerpts; full source pages were not archived. Exact publication times are unknown.",
    "The legal review covers named bills, testing guidance and selected city/ballot records, not an exhaustive legal opinion or comprehensive search of every possible authorization route.",
    "Company statements have promotional incentives; local opposition reporting is older and does not prove current vote counts.",
    "Cross-group dependence can remain. Evidence does not uniquely imply the declared ratios. Sensitivity bounds are not confidence intervals.",
    "No model panel or separately metered inference was run. Recorded zero cost/model calls excludes unmetered assistant and browsing costs.",
]


def write(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def evidence():
    records = []
    for id, source_ids, claim, *_ in FINDINGS:
        sources = []
        for sid in source_ids:
            url, title, date_label, excerpt = SOURCES[sid]
            sources.append({"id": sid, "url": url, "title": title, "excerpt": excerpt,
                            "excerpt_kind": "paraphrase", "published_at": None,
                            "retrieved_at": CUTOFF, "origin_id": sid,
                            "capture": {"method": "manual", "metadata": {
                                "date_label": date_label, "access": "search_index_excerpt" if sid == "ma_testing" else "web_reader",
                                "timestamp_note": "Research snapshot completion time; individual request times were not recorded."}}})
        records.append({"id": id, "claim": claim, "claim_type": "observation" if id in ("boston_not_live", "no_av_ballot_item") else "reporting",
                        "value": None, "entity_ids": ["Waymo", "Boston", "Massachusetts"], "observed_at": CUTOFF,
                        "sources": sources, "provenance": {"researcher": "assistant", "snapshot_date": "2026-09-15",
                        "qualification": "An attributed finding, not independent evidence or a validated numerical adjustment."}})
    return {"schema_version": "vorhersage.evidence.v1", "kind": "manual", "information_as_of": CUTOFF,
            "created_at": now(), "records": records, "limitations": LIMITATIONS}


def build():
    w = Workflow(ROOT / "project")
    if not (ROOT / "project/.vorhersage/state.sqlite").exists():
        w.store.init("Waymo Boston before 2029")
    existing = w.report(QUESTION_ID) if w.status()["questions"] else None
    if existing and existing["forecasts"]:
        return export_outputs(w, existing["forecasts"][-1]["id"])
    # An interrupted build should be resumed explicitly rather than duplicating a run.
    if existing:
        raise RuntimeError("An unfinished run exists; resume it using next/submit.")
    domains = ["company_commitment_and_resources", "state_permission", "local_acceptance",
               "technical_and_weather_readiness", "public_access_and_launch_timing"]
    w.add_profile({"id": "robotaxi_launch", "description": "Permission, deployment capability and public commercial access.", "domains": domains})
    q = {"id": QUESTION_ID, "text": "Will paid, publicly accessible driverless Waymo service launch within Boston before January 1, 2029?",
         "yes": "Before 2029-01-01 00:00:00 America/New_York, a Waymo Driver passenger ride-hailing service must have opened to the general public, charged fares, and actually carried passengers without an in-vehicle safety driver on public-road trips with pickup and dropoff inside Boston municipal boundaries. Normal account/payment/age requirements and capacity limits are allowed; invite-only access, a launch waitlist, employee-only rides, free-only trials, mapping, safety-driver testing and announcements without service do not qualify. A limited neighborhood geofence or operating hours qualifies. A partner booking platform qualifies. A qualifying launch counts even if subsequently suspended. No airport access, citywide coverage, or operation through every snowstorm is required.",
         "no": "No service satisfying every YES criterion launched before the cutoff. Cambridge, Somerville or other Greater Boston service alone does not qualify. A later launch is NO for this deadline.",
         "void": "Only if the recorded criteria cannot be interpreted or verified because the question is materially defective; corporate withdrawal, prohibition, delay, or failure to launch is NO, not void. Use disputed while genuine evidentiary disagreement remains.",
         "event_deadline": DEADLINE, "resolve_after": "2029-01-02T12:00:00-05:00",
         "resolution_source": "Prefer dated Waymo or operating-partner launch announcements, service maps, fare/access terms, and relevant state/city permits; corroborate actual public passenger operations with reputable contemporaneous reporting. Later evidence can establish an earlier launch, but a later launch cannot satisfy the cutoff.",
         "event_group": "waymo_massachusetts_deployment", "domain": "autonomous_mobility", "profile": "robotaxi_launch", "kind": "real"}
    w.question(q)
    packet = evidence()
    write("evidence.json", packet)
    imported = w.import_packet(packet)
    refs = {r["record_id"]: r["evidence_ref"] for r in imported["records"]}
    all_refs = list(refs.values())
    ledger = {"anchor": {"probability": 0.5, "basis": "assumed",
                         "rationale": "A deliberately uninformative-looking but still subjective 50% starting convention for this roughly 27.5-month horizon. It is not a measured city-launch base rate."},
              "entries": [{"finding_id": id, "evidence_refs": [refs[id]], "dependence_group": group,
                           "lr": lr, "lr_range": bounds, "direction": "supports" if lr > 1 else "opposes" if lr < 1 else "neutral",
                           "rationale": "Subjective standalone annotation; superseded by its group's joint ratio. " + claim}
                          for id, _, claim, group, lr, bounds in FINDINGS],
              "joint_declarations": [
                  {"dependence_group": "delivery", "finding_ids": [f[0] for f in FINDINGS if f[3] == "delivery"],
                   "lr": 2.5, "lr_range": [1.5, 4], "direction": "supports",
                   "rationale": "Jointly, explicit Boston preparation, financing and demonstrated multi-city execution support delivery within the horizon. Discount for corporate promotion, unfinished Boston validation, competing cities and time to remove a waitlist. Shared corporate evidence is counted once."},
                  {"dependence_group": "permission", "finding_ids": [f[0] for f in FINDINGS if f[3] == "permission"],
                   "lr": 0.5, "lr_range": [0.2, 1], "direction": "opposes",
                   "rationale": "Jointly, the present driver-based testing framework, study-order outcomes for enabling legislation and local friction halve the odds. Counterweights are the remaining 2027-28 window, stalled competing proposals and absence of an AV restriction on the checked 2026 ballot list. These connected political observations are not multiplied separately."}],
              "independence_rationale": "Treat commercial/technical delivery and the permission process as separable evidence blocks for this judgmental approximation. Residual dependence remains: corporate deployment changes political support, and expected policy affects investment. Joint ratios are subjective net weights, not empirically established likelihoods.",
              "comparison_probability": 0.5}
    run = w.start({"question_id": QUESTION_ID, "forecaster": "assistant:researched-odds-ledger",
                   "method": "declared_odds_ledger_v1; source review 2026-09-15",
                   "mode": "prospective", "information_as_of": CUTOFF, "cutoff_policy": "fixed",
                   "research_status": "completed", "max_searches": 16, "max_extra_tasks": 0})["run_id"]
    research = {
        domains[0]: (["boston_intent", "expansion_capital", "multi_city_execution"], "Preparation plus funded execution makes lack of intent/capital less concerning than permission.", ["No verified Boston fleet size, depot commissioning date or binding launch date."]),
        domains[1]: (["driver_requirement", "house_study_order", "senate_study_order", "competing_bills_stalled", "no_av_ballot_item"], "The named enabling routes have not produced enactment in their retrieved histories. Study orders are a delay signal, not proof that every future route is closed.", ["No verified leadership vote count, governor commitment or complete search of all authorization alternatives."]),
        domains[2]: (["local_acceptance", "boston_intent"], "Local labor and operational concerns can delay service; accessibility support cuts the other way. A proposed ordinance is not an enacted ban.", ["Current city coalition, final state preemption rules and conditions of any local approval."]),
        domains[3]: (["boston_weather", "multi_city_execution"], "Denver expansion is encouraging but does not establish Boston winter readiness. The event permits weather pauses and a limited geofence.", ["No independent Boston-specific operating validation or winter service reliability data."]),
        domains[4]: (["public_access_lag", "boston_not_live"], "All-comer paid service is a stricter milestone than invited first riders. Recent staged rollouts warrant time for public access after permission.", ["Boston launch sequence and whether fare collection/public access will be delayed."]),
    }
    submissions = []
    while (step := w.next(run))["disposition"] == "actionable":
        kind = step["task"]["kind"]
        if kind == "prior":
            payload = {"method": "judgment", "probability": 0.5, "rationale": ledger["anchor"]["rationale"],
                       "evidence_refs": [], "limitations": LIMITATIONS[:3]}
        elif kind == "drivers":
            payload = {"drivers": [
                {"name": "Permission with time to implement", "mechanism": "A lawful path must permit driverless commercial rides and leave enough time for operational rollout.", "evidence_refs": [refs["house_study_order"], refs["senate_study_order"]]},
                {"name": "Delivery and public access", "mechanism": "Waymo must validate Boston operations, deploy capacity, charge fares and remove invitation-only access before the deadline.", "evidence_refs": [refs["boston_intent"], refs["public_access_lag"]]}],
                "yes_path": "A workable permission framework arrives with sufficient lead time; Waymo completes staged rollout and opens paid public service in a Boston geofence.",
                "no_path": "Policy stays blocked or arrives too late, or technical/commercial rollout remains testing or invitation-only at the deadline.",
                "unknowns": ["Timing of reform", "Implementation lag", "Boston winter and street validation", "Corporate deployment priorities"]}
        elif kind == "research":
            ids, interpretation, gaps = research[step["task"]["domain"]]
            payload = {"disposition": "assessed", "interpretation": interpretation, "evidence_refs": [refs[id] for id in ids],
                       "sources_checked": sorted({SOURCES[s][0] for f in FINDINGS if f[0] in ids for s in f[1]}),
                       "unknowns": gaps, "conflicts": []}
        elif kind == "assessment":
            payload = {"method": "odds_ledger", "odds_ledger": ledger,
                       "rationale": "Slightly more likely than not. Delivery strength is offset by permission and implementation timing. As a non-independent explanatory cross-check, 65% for a workable permission path with sufficient lead time times 85% for qualifying rollout conditional on that path gives 55.25%, close to the ledger's 55.56%. Both inputs are subjective judgments, not measured frequencies.",
                       "evidence_refs": all_refs, "limitations": LIMITATIONS}
        elif kind == "review":
            payload = {"decision": "retain", "rationale": "Retain 55.56%, communicated as about 55%. The apparent numerical precision is arithmetic, not epistemic precision.", "evidence_refs": all_refs,
                       "objections": [
                           {"direction": "too_high", "objection": "Both enabling bills have been put into study orders. Reform could consume most of the remaining horizon, and an invite-only opening would still fail this event.",
                            "response": "Agreed; permission is the largest swing assumption. Lowering its joint ratio from 0.5 to 0.2 takes the estimate to 33.33%. No extrapolation from permissive states guarantees Massachusetts reform."},
                           {"direction": "too_low", "objection": "With more than two years, explicit preparation and operational scale, a small public Boston geofence may be straightforward once approval arrives.",
                            "response": "Agreed; early workable authorization would substantially raise the estimate. Removing the current permission discount yields 71.43% at the same delivery weight; subsequent reassessment should update the underlying assumptions too."}]}
        else:
            payload = {"stopping_reason": "Completed five substantive domains, distinguished staged access from the event, checked both enabling and competing proposals, and documented unresolved political and operational inputs. Further unstructured searches have low expected value relative to waiting for concrete policy changes.",
                       "review_at": "2027-02-01T09:00:00-05:00", "triggers": [
                           {"description": "Enacted Massachusetts authorization, a new enabling bill advancing, or a binding restrictive requirement.", "evidence_refs": [refs["house_study_order"], refs["senate_study_order"]]},
                           {"description": "Waymo announces Boston driverless passenger testing, public paid access, a firm schedule, or withdrawal.", "evidence_refs": [refs["boston_intent"], refs["boston_not_live"]]},
                           {"description": "Material Boston permit decision, major fleet safety restriction or operational evidence that changes winter readiness.", "evidence_refs": [refs["local_acceptance"], refs["boston_weather"]]},
                           {"description": "Reassess time remaining if a workable permission path is still absent at the start of 2028.", "evidence_refs": [], "at": "2028-01-01T09:00:00-05:00"}]}
        req = {"task_id": step["task"]["id"], "expected_revision": step["revision"], "idempotency_key": step["task"]["id"],
               "payload": payload, "usage": {"searches": 16 if kind == "prior" else 0, "cost_usd": 0, "model_calls": 0}}
        receipt = w.submit(run, req)
        submissions.append({"request": req, "receipt": receipt})
        if kind == "prior":
            ledger["anchor"]["prior_artifact_id"] = receipt["artifact_id"]
        write("submissions.json", submissions)
    write("question.json", q)
    write("ledger.json", ledger)
    write("calculation.json", calculate(ledger))
    return export_outputs(w, step["forecast_id"])


def export_outputs(w, fid):
    widget = export(w.store, fid, ROOT / "forecast.html")
    write("report.json", w.report(QUESTION_ID))
    write("verification.json", {"doctor": w.doctor(), "widget": widget, "status": w.status(),
                                "note": "No resolution or autonomous monitoring job has been created."})
    with w.store.connect() as c:
        write("artifacts.json", [{"id": r["id"], "kind": r["kind"], "body": Store.artifact(c, r["id"])}
                                 for r in c.execute("SELECT id,kind FROM artifacts ORDER BY created_at,id")])
        write("events.json", [dict(r) for r in c.execute("SELECT * FROM events ORDER BY rowid")])
        packet_id = c.execute("SELECT id FROM artifacts WHERE kind='packet'").fetchone()[0]
        write("evidence_audit.json", audit(Store.artifact(c, packet_id, "packet")))
    print(json.dumps(widget, indent=2))
    return widget


if __name__ == "__main__":
    build()
