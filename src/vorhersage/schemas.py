"""Published JSON Schemas and validation of the subset used by this package."""

import math

from .common import require, time

TEXT = {"type": "string", "minLength": 1}
TIME = {**TEXT, "format": "date-time"}
PROB = {"type": "number", "minimum": 0, "maximum": 1}
COUNT = {"type": "integer", "minimum": 0}


def array(items=TEXT, minimum=0):
    return {"type": "array", "items": items, "minItems": minimum}


def enum(*values):
    return {"enum": list(values)}


def obj(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required,
            "additionalProperties": False}


REF = obj({"packet_id": TEXT, "record_id": TEXT})
REFS = array(REF)
PROFILE = obj({"id": TEXT, "description": TEXT, "domains": array(TEXT, 1)})
QUESTION = obj({
    "id": TEXT, "text": TEXT, "yes": TEXT, "no": TEXT, "void": TEXT,
    "event_deadline": TIME, "resolve_after": TIME, "resolution_source": TEXT,
    "event_group": TEXT, "domain": TEXT, "profile": TEXT, "kind": enum("real", "simulation"),
})
RUN = obj({"question_id": TEXT, "question_version": {"type": "integer", "minimum": 1}, "forecaster": TEXT, "method": TEXT,
           "mode": enum("prospective", "retrospective", "simulation"), "information_as_of": TIME,
           "max_searches": COUNT, "max_extra_tasks": COUNT,
           "cutoff_policy": enum("live", "fixed"),
           "research_status": enum("not_started", "in_progress", "completed", "unspecified"),
           "coherence_policy": enum("warn", "strict"),
           "workflow": enum("standard", "timeline"),
           "research_contract": enum("structured_v1", "structured_v2"),
           "research_effort": enum("deep", "standard", "minimal"),
           "reference_policy": enum("legacy", "widening_v1"), "model_semantics_version": enum(0, 1),
           "previous_forecast_id": TEXT},
          ["question_id", "forecaster", "method", "mode", "information_as_of", "max_searches", "max_extra_tasks"])
REFERENCE_QUERY = obj({"tags": array(TEXT, 1), "horizon_days": {"type": "number", "minimum": 0.000001},
                       "known_as_of": TIME, "selection_rule": TEXT})
PRIOR = obj({"method": enum("judgment", "reference_class"), "rationale": TEXT,
             "research_status_at_estimate": enum("not_started", "in_progress", "completed", "unspecified"),
             "limitations": array(), "evidence_refs": REFS, "probability": PROB,
             "selection_rule": TEXT, "reference_query": REFERENCE_QUERY,
             "cases": array(obj({"id": TEXT, "outcome": enum(0, 1), "evidence_refs": array(REF, 1)}), 1),
             "reference_class_exception": TEXT},
             ["method", "rationale", "limitations", "evidence_refs"])
REFERENCE_CLASS_DESIGN = obj({"rationale": TEXT, "population": TEXT, "selection_rule": TEXT,
                              "metric": TEXT, "search_plan": array(TEXT, 1), "limitations": array(),
                              "evidence_refs": REFS})
REFERENCE_CLASS_ANALYSIS = obj({"status": enum("complete", "blocked"), "analysis_id": TEXT,
                                "case_count": {"type": "integer", "minimum": 0},
                                "independent_episode_count": {"type": "integer", "minimum": 0},
                                "estimator": TEXT, "result": TEXT, "limitations": array(),
                                "evidence_refs": REFS, "analysis_path": TEXT, "artifact_omission_reason": TEXT},
                               ["status", "analysis_id", "case_count", "independent_episode_count", "result", "limitations", "evidence_refs"])
# Optional on legacy records; required by the versioned widening workflow.
REFERENCE_CLASS = obj({"id": TEXT, "population": TEXT,
                       "distance": enum("close", "nearby", "mechanism"),
                       "selection_rule": TEXT, "target_input_ids": array(TEXT, 1),
                       "transfer_rationale": TEXT, "search_plan": array(TEXT, 1)})
REFERENCE_CANDIDATE = obj({"id": TEXT, "episode_id": TEXT, "description": TEXT,
                          "use": enum("base_rate", "input_analogy", "context_only", "excluded"),
                          "target_input_ids": array(TEXT), "similarities": TEXT, "differences": TEXT,
                          "outcome_status": enum("verified", "partial", "unknown"),
                          "rationale": TEXT, "evidence_refs": REFS})
REFERENCE_SEARCH = obj({"class_id": TEXT,
                       "status": enum("searched", "unavailable", "budget_exhausted"),
                       "searches": array(obj({"query": TEXT, "retrieval_ids": array(TEXT),
                                              "evidence_refs": REFS, "finding": TEXT})),
                       "candidates": array(REFERENCE_CANDIDATE), "limitations": array(),
                       "next_action": TEXT})
REFERENCE_CLASS_DESIGN["properties"].update({
    "classes": array(REFERENCE_CLASS, 2),
    "search_allocation": obj({"discovery": COUNT, "verification": COUNT, "followup": COUNT}),
})
REFERENCE_CLASS_ANALYSIS["properties"]["status"] = enum(
    "complete", "blocked", "partial", "search_incomplete", "budget_exhausted",
    "outcomes_unavailable", "no_usable_cases_found", "continue_research")
REFERENCE_CLASS_ANALYSIS["properties"].update({
    "class_results": array(obj({"class_id": TEXT, "assessment": TEXT}), 2),
    "remaining_assumptions": array(TEXT),
    "followups": array(obj({"class_id": TEXT, "action": TEXT})),
    "additional_classes": array(REFERENCE_CLASS),
})
DRIVERS = obj({"drivers": array(obj({"name": TEXT, "mechanism": TEXT, "evidence_refs": REFS}), 1),
               "yes_path": TEXT, "no_path": TEXT, "unknowns": array()})
RESEARCH = obj({"disposition": enum("assessed", "unknown"), "interpretation": TEXT,
                "evidence_refs": REFS, "sources_checked": array(), "unknowns": array(),
                "conflicts": array(obj({"description": TEXT, "status": enum("resolved", "unresolved"), "decision": TEXT}))})
COMPONENT = obj({"id": TEXT, "conditional_on": {"type": ["string", "null"]},
                 "probability": PROB, "rationale": TEXT, "evidence_refs": REFS})
RANGE = array(PROB, 2)
SCENARIO_SEMANTICS = obj({"version": enum(1), "conditioning_event": TEXT,
    "target_relation": enum("entails_yes", "entails_no", "unresolved"),
    "residual_event": TEXT, "non_overlap_rationale": TEXT},
    ["version", "conditioning_event", "target_relation"])
SCENARIO = obj({"semantics": SCENARIO_SEMANTICS,"id": TEXT, "description": TEXT, "weight": PROB, "probability": PROB,
                "rationale": TEXT, "evidence_refs": REFS, "unknowns": array(),
                "weight_range": RANGE, "probability_range": RANGE},
               ["id", "description", "weight", "probability", "rationale", "evidence_refs", "unknowns"])
MIXTURE = obj({"scenarios": array(SCENARIO, 2), "partition_justification": TEXT})
INTAKE = obj({"rationale": TEXT,
              "inputs": array(obj({"id": TEXT, "target": TEXT}), 1),
              "unknowns": array(obj({"id": TEXT, "question": TEXT, "input_ids": array(TEXT, 1),
                                     "route": enum("ask_user", "search", "assumption", "unobservable"),
                                     "why_it_matters": TEXT, "action": TEXT}))})
INQUIRY = obj({"status": enum("answered", "unresolved"), "answer": TEXT, "evidence_refs": REFS,
               "coverage": array(obj({"domain": TEXT, "interpretation": TEXT}))},
              ["status", "answer", "evidence_refs"])
MODEL_MAP = obj({"version": {"type": "integer", "minimum": 1}, "previous_version": COUNT,
                 "rationale": TEXT,
                 "inputs": array(obj({"model_input": TEXT, "input_ids": array(TEXT, 1), "target": TEXT,
                                      "quantity": enum("scenario_weight", "conditional_probability", "probability",
                                                       "likelihood_ratio", "ensemble_weight", "timeline_input")}), 1)})
CONCERN = obj({"id": TEXT, "model_inputs": array(TEXT, 1), "question": TEXT,
               "disposition": enum("investigate", "await_evidence", "retain_assumption"),
               "rationale": TEXT, "action": TEXT})
CONCERN_RESOLUTION = obj({"concern_id": TEXT,
                          "disposition": enum("investigate", "await_evidence", "retain_assumption"),
                          "rationale": TEXT, "action": TEXT, "route": enum("search", "ask_user")},
                         ["concern_id", "disposition", "rationale", "action"])
MODEL_CHALLENGE = obj({"map_version": {"type": "integer", "minimum": 1},
                       "transfers": array(obj({"model_input": TEXT,
                                              "verdict": enum("supported", "assumption", "mismatch"),
                                              "reason": TEXT, "evidence_refs": REFS}), 1),
                       "boundary_cases": array(obj({"description": TEXT, "scenario_ids": array(TEXT),
                                                   "reason": TEXT, "concern_ids": array(TEXT)},
                                                  ["description", "scenario_ids", "reason"])),
                       "partition_review": TEXT, "concerns": array(CONCERN),
                       "event_alignment": obj({"target": TEXT, "matches_question": {"type": "boolean"},
                                               "rationale": TEXT, "concern_ids": array(TEXT)})},
                      ["map_version", "transfers", "boundary_cases", "partition_review", "concerns"])
PARAMETER_SUPPORT = obj({"input_id": TEXT, "model_input": TEXT, "value": {"type": ["number", "string"]},
                         "target": TEXT, "evidence_measures": TEXT,
                         "transfer_assumptions": TEXT,
                         "basis": enum("measured", "calculated", "extrapolated", "assumed"),
                         "plausible_range": array({"type": ["number", "string"]}, 2),
                         "evidence_refs": REFS})
LR = {"type": "number", "exclusiveMinimum": 0}
ODDS_TERM = {"lr": LR, "lr_range": array(LR, 2),
             "direction": enum("supports", "opposes", "neutral"), "rationale": TEXT}
ODDS_LEDGER = obj({
    "anchor": obj({"probability": PROB, "basis": enum("assumed", "empirical"),
                   "prior_artifact_id": TEXT, "rationale": TEXT},
                  ["probability", "basis", "rationale"]),
    "entries": array(obj({"finding_id": TEXT, "evidence_refs": array(REF, 1),
                          "dependence_group": TEXT, **ODDS_TERM},
                         ["finding_id", "evidence_refs", "dependence_group", "lr", "direction", "rationale"])),
    "joint_declarations": array(obj({"dependence_group": TEXT, "finding_ids": array(TEXT, 2), **ODDS_TERM},
                                    ["dependence_group", "finding_ids", "lr", "direction", "rationale"])),
    "independence_rationale": TEXT, "comparison_probability": PROB,
}, ["anchor", "entries", "joint_declarations", "independence_rationale"])
ASSESSMENT = obj({"method": enum("judgment", "conditional_path", "ensemble", "scenario_mixture", "odds_ledger", "timeline_model"),
                  "rationale": TEXT, "limitations": array(), "evidence_refs": REFS,
                  "probability": PROB, "components": array(COMPONENT, 1),
                  "nested_events_justification": TEXT, "members": array(TEXT, 1),
                  "weights": array({"type": "number", "minimum": 0}, 1),
                  "scenarios": array(SCENARIO, 2), "partition_justification": TEXT,
                  "odds_ledger": ODDS_LEDGER, "timeline_model_id": TEXT,
                  "parameter_support": array(PARAMETER_SUPPORT, 1), "model_map": MODEL_MAP},
                 ["method", "rationale", "limitations", "evidence_refs"])
REVIEW = obj({"concern_resolutions": array(CONCERN_RESOLUTION), "decision": enum("retain", "revise", "research"), "rationale": TEXT,
              "objections": array(obj({"direction": enum("too_high", "too_low"), "objection": TEXT, "response": TEXT}), 2),
              "evidence_refs": REFS, "probability": PROB,
              "sensitivity_review": obj({"interpretation": TEXT, "influential_inputs": array(TEXT, 1),
                                          "next_evidence": TEXT}),
              "parameter_support": array(PARAMETER_SUPPORT, 1),
              "research_tasks": array(obj({"domain": TEXT, "purpose": TEXT}), 1)},
             ["decision", "rationale", "objections", "evidence_refs"])
ISSUE = obj({"stopping_reason": TEXT, "review_at": TIME,
             "triggers": array(obj({"description": TEXT, "evidence_refs": REFS, "at": TIME}, ["description", "evidence_refs"]), 1)})
USAGE = obj({"searches": COUNT, "cost_usd": {"type": "number", "minimum": 0}, "model_calls": COUNT})
SUBMIT = obj({"task_id": TEXT, "expected_revision": COUNT, "idempotency_key": TEXT,
              "payload": {"type": "object"}, "usage": USAGE},
             ["task_id", "expected_revision", "idempotency_key", "payload"])
RESOLUTION = obj({"question_id": TEXT, "question_version": {"type": "integer", "minimum": 1},
                  "outcome": enum("yes", "no", "void", "disputed"), "reason": TEXT,
                  "known_at": TIME, "evidence_refs": array(REF, 1),
                  "previous_resolution_id": {"type": ["string", "null"]}, "idempotency_key": TEXT})
SIGNAL = obj({"reason": TEXT, "idempotency_key": TEXT, "question_id": TEXT,
              "evidence_refs": REFS}, ["reason", "idempotency_key", "evidence_refs"])
COHORT = array(obj({"question_id": TEXT, "version": {"type": "integer", "minimum": 1}}), 1)
EVALUATION = obj({"question_versions": COHORT, "forecasters": array(TEXT, 1),
                  "cutoff": TIME, "resolution_as_of": TIME,
                  "mode": enum("prospective", "retrospective", "simulation")})
REPLAY_EVALUATION = obj({"forecast_ids": array(TEXT), "forecasters": array(TEXT, 1),
                         "experiment": TEXT, "contamination_assessment": TEXT})
SOURCE = obj({"kind": enum("public", "testimony", "private_document"), "access": enum("public", "private"),
              "attribution": TEXT, "message_ref": TEXT, "id": TEXT, "url": TEXT, "title": TEXT, "excerpt": TEXT, "retrieved_at": TIME,
              "published_at": {"type": ["string", "null"]}, "origin_id": TEXT,
              "excerpt_kind": enum("quotation", "paraphrase"),
              "capture": obj({"method": enum("manual", "discovery", "fetched", "epiq", "exa_snapshot"),
                              "snapshot_as_of": TIME,
                              "captured_at": TIME, "content": TEXT, "content_sha256": TEXT,
                              "metadata": {"type": "object"}}, ["method"])},
             ["id", "title", "excerpt", "retrieved_at"])
# A passage supports one finding; inference remains a declared reasoning step.
CLAIM_SUPPORT = obj({"source_id": TEXT, "passage": TEXT,
                     "relation": enum("direct", "inference"), "rationale": TEXT})
RECORD = obj({"claim_support": array(CLAIM_SUPPORT, 1), "inference_rationale": TEXT, "id": TEXT, "claim": TEXT, "value": {}, "entity_ids": array(),
              "observed_at": TIME, "sources": array(SOURCE, 1), "provenance": {"type": "object"},
              "claim_type": enum("reporting", "official_statement", "observation", "inference", "unknown")},
             ["id", "claim", "value", "entity_ids", "observed_at", "sources", "provenance"])
EVIDENCE_LINK = obj({"from_record": TEXT, "to_record": TEXT,
                     "relation": enum("repeats", "independently_confirms", "contradicts"), "rationale": TEXT})
PACKET = obj({"schema_version": enum("vorhersage.evidence.v1"), "kind": enum("manual", "epiq"),
              "information_as_of": TIME, "created_at": TIME, "records": array(RECORD, 1),
              "limitations": array(), "epiq": {"type": "object"}, "sha256": TEXT,
              "relationships": array(EVIDENCE_LINK)},
             ["schema_version", "kind", "information_as_of", "created_at", "records", "limitations"])
SELECTION = obj({"cells": array(obj({"kind": TEXT, "subject": TEXT, "question": TEXT}), 1),
                 "information_as_of": TIME, "known_at": TIME}, ["cells", "information_as_of"])
QUESTION_REF = obj({"question_id": TEXT, "version": {"type": "integer", "minimum": 1}})
RELATION = obj({"antecedent": QUESTION_REF, "consequent": QUESTION_REF, "rationale": TEXT})
WATCH = obj({"id": TEXT, "question_id": TEXT, "forecaster": TEXT,
             "interval_seconds": {"type": "integer", "minimum": 1},
             "research_command": array(TEXT, 1), "agent_command": array(TEXT, 1),
             "epiq_db": TEXT, "epiq_source": TEXT,
             "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 60},
             "max_tasks": {"type": "integer", "minimum": 1, "maximum": 100},
             "max_searches": COUNT, "max_extra_tasks": COUNT},
            ["id", "question_id", "forecaster", "interval_seconds"])
BUNDLE = obj({"sources": array(SOURCE, 1),
              "findings": array(obj({"claim_support": array(CLAIM_SUPPORT, 1), "inference_rationale": TEXT, "id": TEXT, "claim": TEXT, "source_ids": array(TEXT, 1),
                                     "claim_type": RECORD["properties"]["claim_type"], "value": {},
                                     "entity_ids": array()}, ["id", "claim", "source_ids", "claim_type"]), 1),
              "information_as_of": TIME, "limitations": array(), "relationships": array(EVIDENCE_LINK)},
             ["sources", "findings", "limitations"])
REFERENCE_CASE = obj({"episode_id": TEXT, "eligibility": TEXT, "id": TEXT, "description": TEXT, "tags": array(TEXT, 1),
                      "trigger_at": TIME, "event_at": {"type": ["string", "null"]},
                      "observed_until": TIME, "known_at": TIME, "evidence_refs": array(REF, 1)},
                     ["id", "description", "tags", "trigger_at", "event_at", "observed_until", "known_at", "evidence_refs"])

TIMELINE_PARAMETER = obj({"id": TEXT, "kind": enum("date", "duration_days"), "description": TEXT})
TIMELINE_VALUE = obj({"parameter_id": TEXT, "basis": enum("observed", "estimated", "assumed", "unresolved"),
                      "value": {"type": ["string", "number"]}, "rationale": TEXT, "evidence_refs": REFS},
                     ["parameter_id", "basis", "rationale", "evidence_refs"])
TIMELINE_NODE = obj({"id": TEXT, "kind": enum("event", "task", "all", "any"),
                     "completion_condition": TEXT, "parents": array(), "parameter_id": TEXT,
                     "state": enum("pending", "in_progress", "completed"), "not_before": TIME,
                     "started_at": TIME, "completed_at": TIME, "rationale": TEXT, "evidence_refs": REFS},
                    ["id", "kind", "completion_condition", "parents", "state", "rationale", "evidence_refs"])
TIMELINE_SCENARIO = obj({"id": TEXT, "description": TEXT, "assessments": array(TIMELINE_VALUE),
                         "weight": PROB, "weight_rationale": TEXT, "evidence_refs": REFS},
                        ["id", "description", "assessments", "evidence_refs"])
TIMELINE_MODEL = obj({"id": TEXT, "version": {"type": "integer", "minimum": 1}, "schedule_as_of": TIME,
                      "question": QUESTION_REF, "information_as_of": TIME, "deadline": TIME,
                      "deadline_rule": enum("before", "on_or_before"), "description": TEXT,
                      "target": TEXT, "parameters": array(TIMELINE_PARAMETER), "nodes": array(TIMELINE_NODE, 1),
                      "scenarios": array(TIMELINE_SCENARIO, 1), "partition_justification": TEXT,
                      "limitations": array(), "previous_model_id": TEXT, "derived_from_model_id": TEXT},
                     ["id", "version", "question", "information_as_of", "deadline", "deadline_rule", "description",
                      "target", "parameters", "nodes", "scenarios", "limitations"])
TIMELINE_STRUCTURE = obj({"timeline_model_id": TEXT, "rationale": TEXT})
TIMELINE_RESEARCH = obj({"assessments": array(obj({"scenario_id": TEXT, "assessment": TIMELINE_VALUE}), 1),
                         "rationale": TEXT})

METHOD = obj({
    "id": TEXT, "version": {"type": "integer", "minimum": 1}, "description": TEXT,
    "instructions": TEXT,
    "task_instructions": obj({kind: TEXT for kind in ("intake", "inquiry", "model_challenge", "prior", "drivers", "research", "assessment", "review", "issue", "timeline_structure", "timeline_research")}, []),
    "stages": array(enum("prior", "drivers", "research", "assessment", "review", "issue"), 2),
    "research_contract": enum("structured_v1", "structured_v2"),
    "prior_method": enum("judgment", "reference_class", "none"),
    "assessment_method": enum("judgment", "conditional_path", "scenario_mixture", "odds_ledger", "timeline_model"),
    "research_domains": array(TEXT),
    "worker": obj({"command": array(TEXT, 1), "config": {"type": "object"},
                   "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 60}}),
    "budget": obj({"max_searches": COUNT, "max_extra_tasks": COUNT,
                   "max_model_calls": {"type": "integer", "minimum": 1},
                   "max_cost_usd": {"type": "number", "minimum": 0}}),
}, ["id", "version", "description", "instructions", "task_instructions", "prior_method", "assessment_method", "research_domains", "worker", "budget"])
ARM = obj({
    "id": TEXT, "version": {"type": "integer", "minimum": 1}, "description": TEXT,
    "method_id": TEXT,
    "model": obj({"provider": TEXT, "name": TEXT, "parameters": {"type": "object"}}),
    "data": obj({"label": TEXT, "questions": array(obj({"question_id": TEXT,
                 "version": {"type": "integer", "minimum": 1}, "packet_ids": array(TEXT)}), 1)}),
})
EXPERIMENT = obj({
    "id": TEXT, "version": {"type": "integer", "minimum": 1}, "description": TEXT,
    "questions": array(obj({"question_id": TEXT, "version": {"type": "integer", "minimum": 1},
                            "packet_ids": array(TEXT)}, ["question_id", "version"]), 1),
    "method_ids": array(TEXT, 1), "arm_ids": array(TEXT, 1),
    "repetitions": {"type": "integer", "minimum": 1, "maximum": 100},
    "mode": enum("prospective", "retrospective", "simulation"),
    "information_as_of": TIME, "forecast_cutoff": TIME,
    "evidence_policy": enum("frozen_packets"), "order_seed": TEXT,
}, ["id", "version", "description", "questions", "repetitions", "mode", "information_as_of", "forecast_cutoff", "evidence_policy", "order_seed"])

# Joint sessions are separate from ordinary workflow forecasts and evaluations.
NUMBER = {"type": "number"}
BINDING = obj({"variable": TEXT, "unit": TEXT, "target_at": TIME, "vintage": TEXT,
               "quantile": PROB, "tolerance": {"type": "number", "minimum": 0}})
CONDITION = obj({"id": TEXT, "version": {"type": "integer", "minimum": 1},
                 "kind": enum("unconditional", "intervention", "information"),
                 "description": TEXT, "binding": BINDING},
                ["id", "version", "kind", "description"])
NUMERIC_FORECAST = obj({"variable": TEXT, "unit": TEXT, "target_at": TIME, "vintage": TEXT,
                        "quantiles": array(obj({"level": PROB, "value": NUMBER}), 1)})
JOINT_SESSION = obj({
    "id": TEXT, "wave": TEXT, "forecaster": TEXT, "protocol": TEXT,
    "repetition": {"type": "integer", "minimum": 1},
    "mode": enum("prospective", "retrospective", "simulation"), "information_as_of": TIME,
    "questions": COHORT, "condition_ids": array(TEXT, 1), "packet_ids": array(TEXT),
    "relation_ids": array(TEXT), "numeric_forecasts": array(NUMERIC_FORECAST),
    "bindings": array(obj({"condition_id": TEXT, "value": NUMBER})),
    "provenance": obj({"kind": enum("native", "external"), "source": TEXT}),
    "configuration": {"type": "object"},
})
JOINT_CELL = obj({"question_id": TEXT, "version": {"type": "integer", "minimum": 1},
                  "condition_id": TEXT, "probability": PROB, "evidence_refs": REFS})
JOINT_SUBMIT = obj({"expected_revision": COUNT, "idempotency_key": TEXT,
                    "cells": array(JOINT_CELL, 1), "usage": USAGE, "raw_record": {"type": "object"}})
JOINT_FINALIZE = obj({"expected_revision": COUNT, "idempotency_key": TEXT, "rationale": TEXT})
JOINT_IMPORT = obj({"session": JOINT_SESSION,
                    "submissions": array(obj({"submitted_at": TIME, "cells": array(JOINT_CELL, 1),
                                               "usage": USAGE, "raw_record": {"type": "object"}}), 1),
                    "finalized_at": TIME, "rationale": TEXT})
JOINT_AGGREGATION = obj({"session_ids": array(TEXT, 1), "expected_forecasters": array(TEXT, 1),
                         "baseline_condition_id": TEXT}, ["session_ids", "expected_forecasters"])

SESSION_WORKER = obj({"command": array(TEXT, 1), "config": {"type": "object"},
                      "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 60}})
SESSION_BUDGET = obj({"max_model_calls": COUNT, "max_searches": COUNT,
                      "max_cost_usd": {"type": "number", "minimum": 0}})
SESSION_RESEARCH = obj({"minimum_successful_tools": COUNT, "minimum_unique_pages": COUNT,
                        "domains": array(TEXT), "minimum_unique_searches": COUNT,
                        "minimum_recent_searches": COUNT, "minimum_followup_searches": COUNT},
                       ["minimum_successful_tools", "minimum_unique_pages", "domains"])
SESSION_EXECUTION = obj({"evidence_policy": enum("fixed", "live"), "defer_bindings": {"type": "boolean"},
                         "budget": SESSION_BUDGET, "research": SESSION_RESEARCH,
                         "requirements": array(obj({"id": TEXT, "description": TEXT, "expected": {"type": "object"}})),
                         "worker": SESSION_WORKER, "tool_worker": SESSION_WORKER},
                        ["evidence_policy", "defer_bindings", "budget", "research", "requirements"])
# Optional and opt-in: old session specifications and hashes retain their identity.
JOINT_SESSION["properties"]["execution"] = SESSION_EXECUTION
SESSION_PAYLOADS = {
    "tool_request": obj({"request_id": TEXT, "tool": TEXT, "arguments": {"type": "object"}}),
    "evidence": obj({"packet_ids": array(TEXT, 1), "information_as_of": TIME}),
    "bindings": obj({"numeric_forecasts": array(NUMERIC_FORECAST),
                      "bindings": array(obj({"condition_id": TEXT, "value": NUMBER}))}),
    "attempt_start": obj({"attempt_id": TEXT, "kind": enum("model", "tool"), "request": {"type": "object"}}),
    "attempt_result": obj({"attempt_id": TEXT,
                            "status": enum("waiting", "completed", "truncated", "refused", "error"),
                            "usage": {"type": ["object", "null"]}, "continuation": {"type": "object"},
                            "raw_record": {"type": "object"}}),
    "usage": obj({"attempt_id": TEXT, "usage": USAGE, "reason": TEXT}),
    "research": obj({"attempt_id": TEXT, "tool": TEXT, "ok": {"type": "boolean"},
                      "url": TEXT, "evidence_refs": REFS, "note": TEXT, "query": TEXT,
                      "recent_days": {"type": "integer", "minimum": 1}},
                     ["attempt_id", "tool", "ok", "evidence_refs", "note"]),
    "assessment": obj({"domain": TEXT, "disposition": enum("assessed", "unknown"),
                        "rationale": TEXT, "evidence_refs": REFS}),
    "observation": obj({"requirement_id": TEXT, "actual": {"type": ["object", "null"]},
                         "basis": enum("worker_reported", "provider_reported", "external_audit"),
                         "failed": {"type": "boolean"}, "note": TEXT, "evidence_refs": REFS}),
    "amendment": obj({"reason": TEXT, "budget": SESSION_BUDGET, "research": SESSION_RESEARCH,
                       "configuration": {"type": "object"}}, ["reason"]),
    "transition": obj({"status": enum("open", "failed", "refused", "budget_exhausted"), "reason": TEXT}),
}
SESSION_EVENT = obj({"expected_revision": COUNT, "idempotency_key": TEXT,
                     "kind": enum(*SESSION_PAYLOADS), "payload": {"type": "object"}})
SESSION_STUDY = obj({"id": TEXT, "version": {"type": "integer", "minimum": 1}, "description": TEXT,
                     "session_template": JOINT_SESSION, "repetitions": {"type": "integer", "minimum": 1, "maximum": 100},
                     "arms": array(obj({"id": TEXT, "configuration": {"type": "object"}, "execution": SESSION_EXECUTION}), 2),
                     "order_seed": TEXT, "evidence_policy": enum("frozen", "independent_live")})
SESSION_EVALUATION = obj({"session_ids": array(TEXT, 1), "cutoff": TIME, "resolution_as_of": TIME,
                          "allow_source_reported": {"type": "boolean"}})

WORKBENCH_START = obj({
    "question": QUESTION_REF, "venue": enum("kalshi", "polymarket"), "market_id": TEXT,
    "mode": enum("prospective", "simulation"), "method": TEXT,
    "eligibility_rationale": TEXT, "contract_match_rationale": TEXT,
    "max_spread": PROB, "min_contracts_each_side": {"type": "number", "exclusiveMinimum": 0},
}, ["question", "venue", "market_id", "mode", "method", "eligibility_rationale", "contract_match_rationale"])
WORKBENCH_INITIAL = obj({"probability": PROB, "rationale": TEXT, "assumptions": array(TEXT, 1),
                         "uncertainties": array(TEXT, 1),
                         "research_status": enum("not_started", "in_progress", "completed"),
                         "evidence_refs": REFS, "model_artifact_ids": array()},
                        ["probability", "rationale", "assumptions", "uncertainties", "research_status", "evidence_refs"])
WORKBENCH_PLAN = obj({"uncertainty": TEXT, "why_it_matters": TEXT, "higher_if": TEXT,
                      "lower_if": TEXT, "search_plan": TEXT, "stopping_rule": TEXT})
WORKBENCH_CHECKPOINT = obj({"probability": PROB, "rationale": TEXT, "findings": TEXT,
                            "changed_assumptions": array(), "remaining_uncertainties": array(),
                            "sources_checked": array(), "evidence_refs": REFS, "limitations": array(),
                            "model_artifact_ids": array(), "usage": USAGE},
                           ["probability", "rationale", "findings", "changed_assumptions", "remaining_uncertainties",
                            "sources_checked", "evidence_refs", "limitations"])
WORKBENCH_FINISH = obj({"stopping_reason": TEXT, "outcome_status": enum("unresolved", "known", "uncertain"),
                        "market_exposure": enum("none", "possible", "observed"), "exposure_notes": TEXT})
WORKBENCH_EXPOSURE = obj({"kind": enum("market_probability", "outcome"), "description": TEXT, "occurred_at": TIME})
WORKBENCH_REFLECTION = obj({"what_helped": TEXT, "what_did_not": TEXT, "next_method_change": TEXT})
WORKBENCH_SUBMIT = obj({"kind": enum("initial", "plan", "checkpoint", "finish", "exposure", "reflection"),
                        "expected_revision": COUNT, "idempotency_key": TEXT, "payload": {"type": "object"}})

SCHEMAS = {"question": QUESTION, "profile": PROFILE, "run": RUN, "submit": SUBMIT,
           "reference_class_search": REFERENCE_SEARCH,
           "reference_class_design": REFERENCE_CLASS_DESIGN, "reference_class_analysis": REFERENCE_CLASS_ANALYSIS,
           "model_map": MODEL_MAP, "model_challenge": MODEL_CHALLENGE,
           "intake": INTAKE, "inquiry": INQUIRY, "parameter_support": PARAMETER_SUPPORT,
           "prior": PRIOR, "drivers": DRIVERS, "research": RESEARCH, "assessment": ASSESSMENT,
           "review": REVIEW, "issue": ISSUE, "resolution": RESOLUTION, "signal": SIGNAL,
           "evaluation": EVALUATION, "replay_evaluation": REPLAY_EVALUATION,
           "packet": PACKET, "epiq_selection": SELECTION, "scenario_mixture": MIXTURE,
           "odds_ledger": ODDS_LEDGER, "timeline_model": TIMELINE_MODEL,
           "timeline_structure": TIMELINE_STRUCTURE, "timeline_research": TIMELINE_RESEARCH,
           "relation": RELATION, "watch": WATCH, "research_bundle": BUNDLE,
           "reference_case": REFERENCE_CASE, "reference_query": REFERENCE_QUERY,
           "method": METHOD, "arm": ARM, "experiment": EXPERIMENT, "condition": CONDITION,
           "session": JOINT_SESSION, "session_submit": JOINT_SUBMIT,
           "session_finalize": JOINT_FINALIZE, "session_import": JOINT_IMPORT,
           "session_aggregation": JOINT_AGGREGATION, "session_event": SESSION_EVENT,
           "session_execution": SESSION_EXECUTION, "session_study": SESSION_STUDY,
           "session_evaluation": SESSION_EVALUATION,
           "workbench_start": WORKBENCH_START, "workbench_submit": WORKBENCH_SUBMIT,
           "workbench_initial": WORKBENCH_INITIAL, "workbench_plan": WORKBENCH_PLAN,
           "workbench_checkpoint": WORKBENCH_CHECKPOINT, "workbench_finish": WORKBENCH_FINISH,
           "workbench_exposure": WORKBENCH_EXPOSURE, "workbench_reflection": WORKBENCH_REFLECTION,
           **{"session_" + k: v for k, v in SESSION_PAYLOADS.items()}}


def validate(value, schema, path="$"):
    if "enum" in schema:
        require(any(value == x and type(value) is type(x) for x in schema["enum"]), path + ": invalid enum value")
    kinds = schema.get("type", [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    predicates = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
                  "string": lambda x: isinstance(x, str), "null": lambda x: x is None,
                  "integer": lambda x: type(x) is int, "boolean": lambda x: type(x) is bool,
                  "number": lambda x: type(x) in (int, float) and math.isfinite(x)}
    if kinds:
        require(any(predicates[k](value) for k in kinds), path + ": expected " + "/".join(kinds))
    if isinstance(value, dict):
        require(all(k in value for k in schema.get("required", [])), path + ": missing required fields " + str(schema.get("required", [])))
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            require(not set(value) - set(props), path + ": unexpected fields " + str(set(value) - set(props)))
        for key, item in value.items():
            if key in props:
                validate(item, props[key], path + "." + key)
    if isinstance(value, list):
        require(len(value) >= schema.get("minItems", 0), path + ": too few items")
        for index, item in enumerate(value):
            validate(item, schema.get("items", {}), f"{path}[{index}]")
    if isinstance(value, str):
        require(len(value.strip()) >= schema.get("minLength", 0), path + ": text is empty")
        if schema.get("format") == "date-time":
            time(value)
    if type(value) in (int, float):
        require(math.isfinite(value), path + ": number must be finite")
        require(value >= schema.get("minimum", -math.inf) and value <= schema.get("maximum", math.inf), path + ": number out of bounds")
        require(value > schema.get("exclusiveMinimum", -math.inf), path + ": number must exceed exclusive minimum")


def check(value, name):
    validate(value, SCHEMAS[name])
    return value
