"""Small, optional bridge for validating Flyvbjerg frozen analyses.

Flyvbjerg remains an external package and workspace. Vorhersage records the
analysis identity and validates a supplied exported ``analysis.json`` without
importing or executing Flyvbjerg.
"""

import json
from pathlib import Path

from .common import require


def validate_export(spec):
    path = spec.get("analysis_path")
    require(path, "A Flyvbjerg analysis needs analysis_path.")
    file = Path(path)
    require(file.is_file(), f"Flyvbjerg analysis export not found: {path}")
    try:
        analysis = json.loads(file.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        require(False, f"Invalid Flyvbjerg analysis export: {exc}")
    require(analysis.get("analysis_id") == spec["analysis_id"], "Flyvbjerg analysis_id does not match the submitted artifact.")
    require(analysis.get("n_subjects", 0) >= spec["case_count"], "Submitted case count exceeds the frozen Flyvbjerg analysis.")
    require(analysis.get("n_subjects", 0) >= spec["independent_episode_count"], "Submitted episode count exceeds the frozen Flyvbjerg analysis.")
    require(bool(analysis.get("metric")) and bool(analysis.get("subject_ids")), "Flyvbjerg analysis lacks a metric or frozen subjects.")
    return {"analysis_id": analysis["analysis_id"], "collection_id": analysis.get("collection_id"),
            "n_subjects": analysis.get("n_subjects", 0), "metric": analysis["metric"],
            "dependence_clusters": analysis.get("dependence_clusters", [])}
