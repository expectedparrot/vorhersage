"""Render all model outcomes, including failures, without selecting on forecasts."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import edsl_pilot as pilot

HERE = Path(__file__).resolve().parent
KEYS = ["astra", "opus", "fable", "gemini"]
NAMES = ["GPT-6 Astra", "Opus 5", "Fable 5.1", "Gemini 3.1 Pro Preview"]


def plot(out, data):
    import os
    import tempfile
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "vorhersage-matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    index = {tuple(r[:3]): r for r in data["rows"]}
    colors = ["#007c78", "#79549c", "#a95262", "#b47519"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.8), constrained_layout=True)
    for ax, q in zip(axes, ("catastrophe:general", "catastrophe:ai", "disempowerment")):
        rows = [index[q, h, "unconditional"] for h in data["horizons"]]
        for i, m in enumerate(data["models"]):
            if m["status"] == "complete":
                ax.plot(range(6), [100*r[6][i] for r in rows], "o-", color=colors[i], label=m["name"], markersize=4)
        ax.plot(range(6), [100*r[3] for r in rows], "--", color="#768486", label="Authors' median")
        ax.fill_between(range(6), [100*r[4] for r in rows], [100*r[5] for r in rows], color="#dce2dc", alpha=.55)
        if all(r[3] > 0 and all(p is None or p > 0 for p in r[6]) for r in rows):
            ax.set_yscale("log")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, pos: f"{v:g}%"))
        ax.set_xticks(range(6), data["horizons"], rotation=30)
        ax.set_title(data["questions"][q]["label"])
        ax.grid(axis="y", alpha=.2)
        ax.spines[["top", "right"]].set_visible(False)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=4)
    fig.suptitle("Expanded AIRO elicitation · completed models\nAuthors' range shaded; research and model settings differ", fontsize=12)
    fig.savefig(out / "comparison.png", dpi=180, bbox_inches="tight")
    fig.savefig(out / "comparison.pdf", bbox_inches="tight")
    plt.close(fig)


def build(out):
    mapping = pilot.load(HERE / "output/question-map.json")
    conditions = {v: k for k, v in pilot.load(HERE / "output/condition-map.json").items()}
    original = json.loads(gzip.decompress((HERE / "output/panel.json.gz").read_bytes()))
    authors = {(mapping[r["question_id"]]["source_question_id"], mapping[r["question_id"]]["horizon"], conditions[r["condition_id"]]): r for r in original["rows"]}
    first = pilot.load(HERE / "edsl_pilot_01/state.json")
    models, states = [], []
    for key, name in zip(KEYS, NAMES):
        reg, state = pilot.checked(out / key)
        states.append(state)
        receipts = pilot.research_receipts(out / key, state)
        detail = pilot.research_status(reg, receipts)
        summary = pilot.load(out / key / "summary.json") if (out / key / "summary.json").exists() else {}
        models.append({"key": key, "name": name, "status": "complete" if state["final"] else "refused" if state.get("terminal_failure") else "in progress",
                       "questions": len(state["cells"]), "cost": state["reported_cost_usd"], "turns": state["turn"],
                       "research": detail, "failed_tools": sum(not r["ok"] for r in receipts),
                       "quantiles": state["quantiles"], "violations": summary.get("coherence_violations"),
                       "comparisons": summary.get("coherence_comparisons"),
                       "settings": state.get("model_override", reg["model"]), "started": reg["created_at"],
                       "finalized": state.get("finalized_at"),
                       "failures": [pilot.load(out / key / e["path"]).get("transport_failure") for e in state["events"]
                                    if e["kind"] == "model" and pilot.load(out / key / e["path"]).get("transport_failure")]})
    questions = {}
    for q in mapping.values():
        src = q["source_question"]
        questions[src["id"]] = {"label": {"catastrophe:general": "General catastrophe", "catastrophe:ai": "AI catastrophe", "disempowerment": "Human disempowerment"}.get(src["id"], src.get("cause_label", "") + " · " + src.get("severity", {}).get("label", "")),
                               "text": src["text"], "criteria": src["criteria"]}
    rows, csv_rows = [], []
    for (q, h, c), original in authors.items():
        index = pilot.airo.HORIZONS.index(h)
        members = {m["forecaster"]: m for m in original["members"]}
        fresh = [s["cells"][q][c][index] if s["final"] else None for s in states]
        matched = [members[n]["probability"] for n in NAMES[:3]] + [first["cells"][q][c][index]]
        old = original["median_probability"]
        values = [m["probability"] for m in original["members"]]
        rows.append([q, h, c, old, min(values), max(values), fresh, matched])
        for i, m in enumerate(models):
            csv_rows.append({"model": m["name"], "status": m["status"], "question": q, "horizon": h, "condition": c,
                             "fresh_probability": fresh[i], "authors_panel_median": old,
                             "matched_baseline_probability": matched[i],
                             "matched_baseline": "Initial Gemini pilot" if i == 3 else "Original " + m["name"]})
    assert len(rows) == 2940 and len({tuple(r[:3]) for r in rows}) == 2940
    with (out / "comparison.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(csv_rows[0]))
        writer.writeheader()
        writer.writerows(csv_rows)
    data = {"models": models, "rows": rows, "questions": questions, "horizons": pilot.airo.HORIZONS,
            "generated_at": pilot.now(), "total_cost": sum(m["cost"] for m in models)}
    plot(out, data)
    pilot.write(out / "study-summary.json", {k: v for k, v in data.items() if k not in ("rows", "questions")})
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False, allow_nan=False).replace("<", "\\u003c").replace("&", "\\u0026")
    template = (HERE / "study_template.html").read_text()
    (out / "comparison.html").write_text(template.replace("__DATA__", payload))
    lines = ["# Expanded AIRO model study", "", "[Interactive comparison](comparison.html) · [Full CSV](comparison.csv) · [Replication protocol and gaps](../REPLICATION.md)", "",
             "All attempted models are reported. Failed or unfinished sessions have no final probability estimates in the comparison.", "",
             "| Model | Outcome | Questions accepted | Successful tools | Distinct pages | Failed tools | Reported model cost |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for m in models:
        counts = m["research"]["counts"]
        lines.append(f"| {m['name']} | {m['status']} | {m['questions']} | {counts['minimum_research_calls']} | {counts['minimum_unique_page_reads']} | {m['failed_tools']} | ${m['cost']:.5f} |")
    lines += ["", f"Total reported model cost: **${data['total_cost']:.5f}**, including failed calls; web costs are not included.", "",
              "The research provider was web.run, not the authors' Tavily. Expanded gates enforce recency, multiple distinct sources and later-turn follow-up searches. Page windows preserve the available provider extraction; that extraction can still be incomplete.", "",
              "Astra requested xhigh, but the local EDSL adapter drops the setting. Its effective remote effort is unverified. Opus required lowering adaptive effort from max to high after using all 20,000 tokens on thinking. Both Anthropic models required lowering the initial 64,000-token allowance because the EDSL adapter lacks streaming. Fable subsequently returned a provider refusal and its session ended. All changes and costs are recorded.", "",
              "## Headline forecasts by 2050", "", "| Model | General catastrophe | AI catastrophe | Disempowerment |", "| --- | ---: | ---: | ---: |"]
    for i, m in enumerate(models):
        values = [next(r[6][i] for r in rows if r[:3] == [q, "2050", "unconditional"]) for q in ["catastrophe:general", "catastrophe:ai", "disempowerment"]]
        lines.append("| " + m["name"] + " | " + " | ".join(f"{100*v:g}%" if v is not None else "—" for v in values) + " |")
    lines += ["| Authors' four-model median | 8.5% | 6% | 15.5% |", "", "![Completed model comparison](comparison.png)", "",
              "Compare Astra and Opus with their respective original model as well as with the four-model median. Compare the new Gemini with its original pilot. These single live-research sessions change several factors at once and cannot identify the effect of research depth or EDSL transport. A controlled experiment needs repeated runs with frozen evidence and verified provider settings.", "",
              "Instrument and original panel: AIRO, Forecasting Research Institute, CC BY 4.0 with third-party carve-outs; see ../source/LICENSE-DATA."]
    (out / "REPORT.md").write_text("\n".join(lines)+"\n")
    return {"html": str(out / "comparison.html"), "models": [{k: m[k] for k in ("name", "status", "cost", "questions")} for m in models]}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=HERE / "edsl_study_02")
    args = p.parse_args()
    print(json.dumps(build(args.out), indent=2))
