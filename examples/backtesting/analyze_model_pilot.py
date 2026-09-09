"""Summarize a completed pilot without changing forecasts or selecting new runs."""

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from edsl import Results
from vorhersage.common import digest


def read(path):
    return json.loads(path.read_text())


def mean(values):
    return math.fsum(values) / len(values) if values else None


def summarize(root):
    strict = read(root / "evaluation.json")["data"]
    posthoc = read(root / "posthoc_evaluation.json")["data"]
    imports = read(root / "project/import_report.json")
    diagnostics = read(root / "posthoc_project/import_report.json")
    cases = {c["id"]: c for c in read(root / "cases.json")["cases"]}
    models = [m["model"] for m in read(root / "registration.json")["models"]]
    cost_by_arm, finish_by_arm, versions = {}, {}, {}
    for result in Results.load(str(root / "results.ep")):
        r = result.to_dict()
        arm = r["model"]["model"] + ":" + r["scenario"]["condition"]
        raw = r["raw_model_response"]
        response = raw.get("forecast_raw_model_response", {})
        cost_by_arm.setdefault(arm, []).append(raw["forecast_cost"])
        finish_by_arm.setdefault(arm, Counter())[response.get("candidates", [{}])[0].get("finish_reason", "unknown")] += 1
        versions.setdefault(arm, set()).add(response.get("model_version", "unreported"))
    costs = {arm: math.fsum(values) for arm, values in cost_by_arm.items()}
    recognition = {}
    for row in diagnostics["imported"]:
        arm = row["model"] + ":" + row["condition"]
        recognition.setdefault(arm, {"parsed_n": 0, "recognized_n": 0})
        recognition[arm]["parsed_n"] += 1
        recognition[arm]["recognized_n"] += int(row["recognizes_outcome"])

    def pairs(evaluation, eligible=None):
        selected = {(r["case_id"], r["forecaster"]): r for r in evaluation["selected"]}
        output = []
        for model in models:
            arms = [model + ":plain", model + ":structured"]
            common = [cid for cid in cases if (eligible is None or cid in eligible)
                      and all((cid, arm) in selected for arm in arms)]
            values = [[selected[cid, arm]["brier"] for cid in common] for arm in arms]
            output.append({"model": model, "n": len(common), "case_ids": common,
                           "plain_brier": mean(values[0]), "structured_brier": mean(values[1]),
                           "structured_minus_plain": mean([b - a for a, b in zip(*values)])})
        return output

    criteria_cases = {cid for cid, c in cases.items() if c["criteria_available"]}
    review_effects = []
    for model in models:
        rows = []
        outcomes = {r["case_id"]: r["outcome"] for r in strict["selected"]}
        for row in imports["imported"]:
            if row["model"] != model or row["condition"] != "structured":
                continue
            record = read(root / "project/model_records" / (row["response_sha256"] + ".json"))
            from model_runs import parse_answer
            answer = parse_answer(record["answer"]["forecast"], "structured")
            before, after = answer["assessment"]["probability"], answer["review"]["probability"]
            y = outcomes[row["case_id"]]
            rows.append({"case_id": row["case_id"], "assessment": before, "review": after,
                         "brier_change": (after-y)**2 - (before-y)**2})
        review_effects.append({"model": model, "n": len(rows),
                               "changed_n": sum(r["assessment"] != r["review"] for r in rows),
                               "mean_brier_change": mean([r["brier_change"] for r in rows]), "rows": rows})
    summary = {"remote_job_uuid": read(root / "submission.json")["data"]["meta"]["remote_job"]["job_uuid"],
               "completed_interviews": 80, "strict_valid": imports["valid_forecasts"],
               "posthoc_valid": diagnostics["valid_forecasts"], "strict_failures": imports["failures"],
               "posthoc_failures": diagnostics["failures"], "strict_summaries": strict["summaries"],
               "posthoc_summaries": posthoc["summaries"], "strict_within_model_pairs": pairs(strict),
               "posthoc_within_model_pairs": pairs(posthoc),
               "strict_pairs_with_separate_criteria": pairs(strict, criteria_cases),
               "recognition_posthoc": recognition, "review_effects_strict": review_effects,
               "model_cost_usd_including_invalid": costs, "total_result_cost_usd": math.fsum(costs.values()),
               "server_billed_usd": read(root / "completion.json")["data"]["status"]["latest_job_run_details"]["cost_usd"],
               "finish_reasons": finish_by_arm, "provider_model_versions": {k: sorted(v) for k,v in versions.items()},
               "input_hashes": {name: digest(read(root / name)) for name in ("registration.json", "evaluation.json", "posthoc_evaluation.json")},
               "limitations": ["Small exposed historical development cohort; no skill or significance claim.",
                               "Most parsed outputs self-report outcome recognition; a negative self-report does not prove absence of leakage.",
                               "Question-only prompts; no archived research and five cases lack separate criteria.",
                               "Post-hoc parsing results are separate from the registered strict analysis.",
                               "Review fields are from one completion, not independently elicited forecast revisions.",
                               "Within-model matched sets can differ between models; do not rank those scores across models."]}
    (root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = ["# Model pilot 01 results", "", "Completed September 9, 2026: 80 model interviews, no remote execution exceptions. "
             f"Server charge: ${summary['server_billed_usd']:.4f}; sum of per-response costs: ${summary['total_result_cost_usd']:.6f}. "
             "Costs include malformed answers. No model completions were rerun.", "",
             "The clearest usable comparison is Gemini 3.1 Pro's complete 20-question pair. "
             "Its structured prompt scored better, but 37 of its 40 responses reported recognizing the outcome. "
             "These results exercise the forecasting pipeline and do not establish live forecasting skill.", "",
             "## Registered strict analysis", "", "| Model | Valid plain | Valid structured | Paired n | Plain Brier | Structured Brier |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for p in summary["strict_within_model_pairs"]:
        model = p["model"]
        lines.append(f"| {model} | {strict['summaries'][model+':plain']['available_n']}/20 | {strict['summaries'][model+':structured']['available_n']}/20 | {p['n']} | {p['plain_brier']:.4f} | {p['structured_brier']:.4f} |")
    lines += ["", "Lower Brier is better. Each row uses its own common questions; compare conditions within a row. "
              "The six-way common cohort (four model/prompt arms plus two baselines) has only four cases under strict parsing; "
              "its full scores are retained in [evaluation.json](evaluation.json).", "",
              "## Formatting diagnostic", "", "The registered parser accepted 64/80 outputs. "
              "A separate, post-hoc rule accepting exactly one fenced JSON block recovered five additional Flash plain responses. "
              "It did not repair broken JSON, infer probabilities from prose, or generate replacement answers. "
              "The diagnostic accepts 69/80 and has eight six-way matched cases. "
              "See [posthoc_evaluation.json](posthoc_evaluation.json) and the original [results.ep](results.ep).", "",
              "## Outcome recognition and costs", "", "| Arm | Recognized / parsed (diagnostic) | Cost, all 20 calls |", "| --- | ---: | ---: |"]
    for arm, values in recognition.items():
        lines.append(f"| {arm} | {values['recognized_n']}/{values['parsed_n']} | ${costs[arm]:.4f} |")
    lines += ["", "Recognition is a model self-report. Unparsed responses have unknown recognition status. "
              "Both conditions used the same output cap, but the structured prompts used more input and output tokens. "
              "One Flash plain response ended with MAX_TOKENS; the other 79 responses reported STOP.", "",
              "## Sensitivity and review", "", "Excluding the five cases without separate criteria, while retaining the original strict parsing:", ""]
    for p in summary["strict_pairs_with_separate_criteria"]:
        lines.append(f"- {p['model']}: n={p['n']}, plain {p['plain_brier']:.4f}, structured {p['structured_brier']:.4f}.")
    lines += ["", "Review diagnostics use assessment and review probabilities from the same structured completion:", ""]
    for r in review_effects:
        lines.append(f"- {r['model']}: {r['changed_n']}/{r['n']} probabilities changed; mean Brier change {r['mean_brier_change']:+.4f}.")
    lines += ["", "This cannot isolate a causal effect of review. "
              "The [machine-readable summary](summary.json) preserves cohort membership, failures, costs, model versions, and input hashes.", "",
              "Next experiment: audit original wording and criteria; assemble dated evidence; use cases and model versions with a defensible "
              "training-cutoff relationship or collect prospective predictions. Fix the response format contract before scaling. "
              "Keep this pilot unchanged as a recorded development experiment.", ""]
    (root / "RESULTS.md").write_text("\n".join(lines))
    print(json.dumps({k:summary[k] for k in ("strict_valid", "posthoc_valid", "strict_within_model_pairs", "recognition_posthoc", "total_result_cost_usd")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pilot", type=Path)
    summarize(parser.parse_args().pilot)
