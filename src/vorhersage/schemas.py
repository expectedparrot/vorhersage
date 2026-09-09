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
RUN = obj({"question_id": TEXT, "forecaster": TEXT, "method": TEXT,
           "mode": enum("prospective", "retrospective", "simulation"), "information_as_of": TIME,
           "max_searches": COUNT, "max_extra_tasks": COUNT,
           "cutoff_policy": enum("live", "fixed"),
           "previous_forecast_id": TEXT},
          ["question_id", "forecaster", "method", "mode", "information_as_of", "max_searches", "max_extra_tasks"])
PRIOR = obj({"method": enum("judgment", "reference_class"), "rationale": TEXT,
             "limitations": array(), "evidence_refs": REFS, "probability": PROB,
             "selection_rule": TEXT,
             "cases": array(obj({"id": TEXT, "outcome": enum(0, 1), "evidence_refs": array(REF, 1)}), 1)},
            ["method", "rationale", "limitations", "evidence_refs"])
DRIVERS = obj({"drivers": array(obj({"name": TEXT, "mechanism": TEXT, "evidence_refs": REFS}), 1),
               "yes_path": TEXT, "no_path": TEXT, "unknowns": array()})
RESEARCH = obj({"disposition": enum("assessed", "unknown"), "interpretation": TEXT,
                "evidence_refs": REFS, "sources_checked": array(), "unknowns": array(),
                "conflicts": array(obj({"description": TEXT, "status": enum("resolved", "unresolved"), "decision": TEXT}))})
COMPONENT = obj({"id": TEXT, "conditional_on": {"type": ["string", "null"]},
                 "probability": PROB, "rationale": TEXT, "evidence_refs": REFS})
ASSESSMENT = obj({"method": enum("judgment", "conditional_path", "ensemble"),
                  "rationale": TEXT, "limitations": array(), "evidence_refs": REFS,
                  "probability": PROB, "components": array(COMPONENT, 1),
                  "nested_events_justification": TEXT, "members": array(TEXT, 1),
                  "weights": array({"type": "number", "minimum": 0}, 1)},
                 ["method", "rationale", "limitations", "evidence_refs"])
REVIEW = obj({"decision": enum("retain", "revise", "research"), "rationale": TEXT,
              "objections": array(obj({"direction": enum("too_high", "too_low"), "objection": TEXT, "response": TEXT}), 2),
              "evidence_refs": REFS, "probability": PROB,
              "research_tasks": array(obj({"domain": TEXT, "purpose": TEXT}), 1)},
             ["decision", "rationale", "objections", "evidence_refs"])
ISSUE = obj({"stopping_reason": TEXT, "review_at": TIME,
             "triggers": array(obj({"description": TEXT, "evidence_refs": REFS}), 1)})
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
SOURCE = obj({"id": TEXT, "url": TEXT, "title": TEXT, "excerpt": TEXT, "retrieved_at": TIME,
              "published_at": {"type": ["string", "null"]}, "origin_id": TEXT},
             ["id", "url", "title", "excerpt", "retrieved_at"])
RECORD = obj({"id": TEXT, "claim": TEXT, "value": {}, "entity_ids": array(),
              "observed_at": TIME, "sources": array(SOURCE, 1), "provenance": {"type": "object"}})
PACKET = obj({"schema_version": enum("vorhersage.evidence.v1"), "kind": enum("manual", "epiq"),
              "information_as_of": TIME, "created_at": TIME, "records": array(RECORD, 1),
              "limitations": array(), "epiq": {"type": "object"}, "sha256": TEXT},
             ["schema_version", "kind", "information_as_of", "created_at", "records", "limitations"])
SELECTION = obj({"cells": array(obj({"kind": TEXT, "subject": TEXT, "question": TEXT}), 1),
                 "information_as_of": TIME, "known_at": TIME}, ["cells", "information_as_of"])

SCHEMAS = {"question": QUESTION, "profile": PROFILE, "run": RUN, "submit": SUBMIT,
           "prior": PRIOR, "drivers": DRIVERS, "research": RESEARCH, "assessment": ASSESSMENT,
           "review": REVIEW, "issue": ISSUE, "resolution": RESOLUTION, "signal": SIGNAL,
           "evaluation": EVALUATION, "replay_evaluation": REPLAY_EVALUATION,
           "packet": PACKET, "epiq_selection": SELECTION}


def validate(value, schema, path="$"):
    if "enum" in schema:
        require(any(value == x and type(value) is type(x) for x in schema["enum"]), path + ": invalid enum value")
    kinds = schema.get("type", [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    predicates = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
                  "string": lambda x: isinstance(x, str), "null": lambda x: x is None,
                  "integer": lambda x: type(x) is int,
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


def check(value, name):
    validate(value, SCHEMAS[name])
    return value
