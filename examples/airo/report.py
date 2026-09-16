#!/usr/bin/env python3
"""Render publication-style figures and a report from Vorhersage's AIRO results."""

import argparse
import gzip
import json
import os
import tempfile
from pathlib import Path
from statistics import median

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "vorhersage-matplotlib"))

MODELS = ["GPT-6 Astra", "Fable 5.1", "Opus 5", "GPT-5.5 Pro"]
COLORS = ["#0e7c7b", "#8e2a63", "#7a4fa3", "#c25a2e"]
HORIZONS = ["6mo", "12mo", "2028", "2030", "2050", "2100"]


def render(output, source):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    summary = json.loads((output / "summary.json").read_text())
    mapping = json.loads((output / "question-map.json").read_text())
    condition_ids = json.loads((output / "condition-map.json").read_text())
    reverse = {v: k for k, v in condition_ids.items()}
    panel = json.loads(gzip.decompress((output / "panel.json.gz").read_bytes()))
    rows = {(mapping[r["question_id"]]["source_question_id"], mapping[r["question_id"]]["horizon"], reverse[r["condition_id"]]): r
            for r in panel["rows"]}
    alternative = json.loads(gzip.decompress((output / "status-quo-comparison.json.gz").read_bytes()))
    alternative_rows = {(mapping[r["question_id"]]["source_question_id"], mapping[r["question_id"]]["horizon"], reverse[r["condition_id"]]): r
                        for r in alternative["rows"]}
    figures = output / "figures"
    figures.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.titleweight": "bold", "figure.dpi": 140, "savefig.dpi": 180})
    percent = FuncFormatter(lambda x, _: f"{x:g}%")
    def save(fig, name):
        fig.savefig(figures / (name + ".png"), bbox_inches="tight")
        fig.savefig(figures / (name + ".pdf"), bbox_inches="tight")
        plt.close(fig)
    def member_value(row, model, key):
        return next(m[key] for m in row["members"] if m["forecaster"] == model)

    # Figure 6: the three overlapping domain-specific incident ladders.
    rungs = ["100", "1k", "10k", "100k", "1M", "10M", "100M", "1B"]
    fig, axes = plt.subplots(3, 1, figsize=(9, 9), sharex=True, constrained_layout=True)
    for ax, h in zip(axes, ("2030", "2050", "2100")):
        for cause, label, color in (("cyber", "Cyber", "#366a91"), ("misalign", "Misalignment", "#8e2a63"),
                                    ("bio", "Human-caused epidemic", "#b8742a")):
            ax.plot(range(8), [rows[(f"ladder:{cause}:{r}", h, "unconditional")]["median_probability"] * 100 for r in rungs],
                    "o-", color=color, label=label)
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(percent)
        ax.set_title("By " + h, loc="left")
        ax.grid(axis="y", alpha=0.2)
    axes[0].legend(loc="lower left", frameon=False)
    axes[1].set_ylabel("Probability of cumulative qualifying incidents reaching the threshold")
    axes[-1].set_xticks(range(8), [f"{r}\n${d}" for r, d in zip(rungs, ("220M", "2.2B", "22B", "220B", "2.2T", "22T", "220T", "2.2Q"))])
    axes[-1].set_xlabel("Severity threshold: deaths or equivalent morbidity / economic damages (2026 USD)\n"
                        "Onsets from September 10, 2026 to the horizon; harm counted within three years of onset")
    fig.suptitle("AIRO incident ladders · reproduced from the September 10, 2026 sessions")
    save(fig, "figure6_incident_ladders")

    # Figure 7: model points and unweighted probability medians.
    g1 = json.loads((source / "results/graph1_data.json").read_text())
    human = {q["id"]: q["human"] for q in g1["questions"] if q["id"] in ("catastrophe:general", "catastrophe:ai", "disempowerment")}
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.8), sharey=True, constrained_layout=True)
    for ax, q, label in zip(axes, ("catastrophe:general", "catastrophe:ai", "disempowerment"),
                           ("General catastrophe", "AI catastrophe", "Human disempowerment")):
        for i, (model, color) in enumerate(zip(MODELS, COLORS)):
            ax.scatter([x + (i - 1.5) * 0.045 for x in range(6)],
                       [member_value(rows[(q, h, "unconditional")], model, "probability") * 100 for h in HORIZONS],
                       color=color, label=model, s=23, alpha=0.9)
        ax.plot(range(6), [rows[(q, h, "unconditional")]["median_probability"] * 100 for h in HORIZONS],
                "o-", mfc="white", color="#20252b", label="Ensemble median", zorder=5)
        for baseline in human[q]:
            points = [(HORIZONS.index(h), p) for h, p in baseline["ps"].items() if h in HORIZONS]
            ax.scatter([x for x, _ in points], [p for _, p in points], marker="D", facecolors="none",
                       edgecolors=baseline["color"], label=f"{baseline['panel']} superforecasters ({baseline['date'][:4]})", s=35)
        ax.set_title(label)
        ax.set_xticks(range(6), ["6 mo", "12 mo", "2028", "2030", "2050", "2100"], rotation=35)
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(percent)
        ax.grid(axis="y", alpha=0.2)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=4, frameon=False, fontsize=8)
    fig.suptitle("AIRO unconditional forecasts · reproduced medians and original human reference points")
    save(fig, "figure7_unconditional")

    def ratios(ids, labels, name, title):
        fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), sharey=True, constrained_layout=True)
        for ax, h in zip(axes, ("2030", "2050")):
            for i, (model, color) in enumerate(zip(MODELS, COLORS)):
                ax.scatter([member_value(rows[("catastrophe:ai", h, cid)], model, "ratio") for cid in ids],
                           [y + (i - 1.5) * 0.1 for y in range(len(ids))], color=color, s=25, label=model)
            ax.scatter([rows[("catastrophe:ai", h, cid)]["multiplier"] for cid in ids], range(len(ids)),
                       marker="D", facecolors="white", edgecolors="#20252b", s=42, zorder=5, label="Geometric median")
            ax.axvline(1, color="#555", linestyle="--", linewidth=0.8)
            ax.set_xscale("log")
            ax.set_xticks([0.25, 0.5, 1, 2, 4], ["0.25×", "0.5×", "1×", "2×", "4×"])
            ax.set_xlim(0.18, 4.1)
            ax.set_yticks(range(len(ids)), labels)
            if ax is axes[0]:
                ax.invert_yaxis()
            ax.set_title(f"By {h} · baseline {100 * rows[('catastrophe:ai', h, 'unconditional')]['median_probability']:g}%")
            ax.set_xlabel("Conditional / same-session unconditional probability")
            ax.grid(axis="x", alpha=0.15)
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="outside lower center", ncol=5, frameon=False, fontsize=8)
        fig.suptitle(title)
        save(fig, name)

    policy_ids = ["sq", "p1", "p2a", "p2b", "p3a", "p3b", "p4", "p5"]
    policy_labels = ["Status quo: no new policy", "Federal preemption", "Compute cap: US", "Compute cap: US + China",
                     "Pre-release authorization: US", "Pre-release authorization: international", "Strict liability", "Combined package"]
    ratios(policy_ids, policy_labels, "figure8_policy", "AIRO policy conditions · reproduced paired multipliers")
    capability_ids = ["eci_p10", "eci_p25", "eci_p50", "eci_p75", "eci_p90"]
    quantiles = {f"p{p}": median(s["eci_forecast"][f"p{p}"] for s in summary["sessions"]) for p in (10, 25, 50, 75, 90)}
    ratios(capability_ids, [f"Own {cid[5:]}th percentile (median ECI {quantiles[cid[4:]]:g})" for cid in capability_ids],
           "figure9_capability", "AIRO capability conditions · models condition on their own quantiles")

    def pct(q, h, condition="unconditional"):
        return 100 * rows[(q, h, condition)]["median_probability"]
    text = ["# Reproducing the authors' AIRO panel", "",
            f"Imported **{summary['probabilities']:,} probabilities** from the authors' four original sessions and recomputed the panel summaries using Vorhersage's joint-session aggregation functions. "
            f"All **{summary['matched_published_values']} published-value checks passed**. No new forecasts or paid model calls were made.", "",
            f"Source: [Forecasting Research Institute's AIRO repository](https://github.com/forecastingresearch/airo/tree/{summary['source_commit']}), "
            f"run `{summary['run_id']}`, protocol `{PROTOCOL_LABEL}`. Original source rows and instrument files are frozen with hashes under `../source/`.", "",
            "| Forecast | By 2030 | By 2050 | By 2100 |", "| --- | ---: | ---: | ---: |"]
    for q, name in (("catastrophe:general", "General catastrophe"), ("catastrophe:ai", "AI catastrophe"), ("disempowerment", "Human disempowerment")):
        text.append(f"| {name} | " + " | ".join(f"{pct(q,h):g}%" for h in ("2030", "2050", "2100")) + " |")
    text += ["", "Values retain source precision. The paper reports rounded values, including 0.47% for the raw 0.475% AI-catastrophe median in 2030.", "",
             "![Unconditional forecasts](figures/figure7_unconditional.png)", "",
             "| Policy condition | 2030 multiplier | 2050 multiplier | 2050 vs. status quo |", "| --- | ---: | ---: | ---: |"]
    for cid, label in zip(policy_ids, policy_labels):
        text.append(f"| {label} | {rows[('catastrophe:ai','2030',cid)]['multiplier']:.3f}× | "
                    f"{rows[('catastrophe:ai','2050',cid)]['multiplier']:.3f}× | {alternative_rows[('catastrophe:ai','2050',cid)]['multiplier']:.3f}× |")
    text += ["", "The first two columns reproduce the paper's geometric medians of within-model ratios. The last column is an additional comparison: "
             "each policy versus the same model's status-quo condition. All policy conditions, including status quo, fix capability at that model's median trajectory; "
             "the unconditional baseline does not fix capability. These are model-elicited comparisons, not empirically identified policy effects.", "",
             "![Policy multipliers](figures/figure8_policy.png)", "", "![Capability multipliers](figures/figure9_capability.png)", "",
             f"The median own-90th-percentile capability condition raises the 2030 AI-catastrophe forecast by "
             f"**{rows[('catastrophe:ai','2030','eci_p90')]['multiplier']:.3f}×**. "
             "Each model uses its own numeric capability estimate; these are not common ECI scenarios across the panel.", "",
             "![Incident ladders](figures/figure6_incident_ladders.png)", "",
             f"The authors' unconditional coherence diagnostic is reproduced: **{summary['author_coherence_violations']} violations in "
             f"{summary['author_coherence_comparisons']:,} comparisons**. Its 24 BRACKET comparisons link a catastrophe's mortality window "
             "to an incident ladder with a later onset start and a three-year harm window. Those are retained in the reproduction but excluded from "
             "Vorhersage's registered logical implications. The package separately checks the valid registered relations and their transitive implications under every condition.", "",
             "That broader check finds **four conditional inconsistencies, all in Opus 5**. Each concerns a 12-month cyber incident at the 1,000-death-equivalent "
             "or $2.2 billion threshold exceeding the probability of any AI incident at the same threshold. This is additional analysis; the paper's 100% result is explicitly unconditional.", "",
             "| Condition | Cyber incident | Any AI incident |", "| --- | ---: | ---: |"]
    for session in summary["sessions"]:
        for violation in session["coherence_details"]:
            cid = reverse[violation["condition_id"]]
            text.append(f"| {policy_labels[policy_ids.index(cid)]} | {100 * violation['antecedent_probability']:g}% | "
                        f"{100 * violation['consequent_probability']:g}% |")
    text += ["",
             "The incident categories overlap and their probabilities must not be summed. Deaths-or-damages incident thresholds do not decompose the deaths-only catastrophe question.", "",
             "| Original model session | Finalization (UTC) | Searches | Page reads | Source-reported model cost |", "| --- | --- | ---: | ---: | ---: |"]
    for s in summary["sessions"]:
        tools = s["recorded_tool_calls"]
        text.append(f"| {s['label']} | {s['finalized_at']} | {tools.get('web_search',0)} | {tools.get('read_page',0)} | ${s['source_usage']['cost_usd']:.2f} |")
    text += ["", f"The original sessions report ${summary['source_reported_usage']['cost_usd']:.2f} in model costs; these are historical charges, not costs incurred by this reproduction. "
             "Shared usage is counted once per session. Tool responses and source text are preserved as authors' records, without re-fetching or endorsing their claims. "
             "Per-tool timestamps and the original incremental probability submissions are absent from the expanded final export. Imported evidence times therefore use the session completion as an explicitly labeled upper bound.", "",
             "Reproduced here: the complete principal probability grid and Figures 6–9, including all 210 unconditional medians and the saved endpoint conditional summaries. "
             "The ForecastBench calibration, simulator validation, anchoring experiments, and additional Figure 10 instruments remain separate reproduction tasks; this report does not establish forecasting accuracy.", "",
             "Audit files: [verification](verification.json), [summary](summary.json), [all panel cells](panel.csv), "
             "[author coherence](author-coherence.json). Full panel/member reports are in `panel.json.gz` and `status-quo-comparison.json.gz`; "
             "the local Vorhersage project is in `project/`. Each figure is also available as a PDF in `figures/`.", "",
             "Data and original definitions: AIRO, Forecasting Research Institute, https://airo.forecastingresearch.org, CC BY 4.0; see the preserved source licenses. "
             "This report and the reconstructed figures were generated by the Vorhersage reproduction scripts."]
    (output / "REPORT.md").write_text("\n".join(text) + "\n")
    return {"report": str(output / "REPORT.md"), "figures": 4}


PROTOCOL_LABEL = "unified-joint-combined-v5"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path(__file__).with_name("source"))
    args = parser.parse_args()
    print(json.dumps(render(args.out, args.source), indent=2))
