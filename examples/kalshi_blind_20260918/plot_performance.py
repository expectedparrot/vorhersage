"""Rebuild report figures and tables from frozen results; makes no network calls."""

from pathlib import Path
import json
import math
import subprocess
from statistics import mean

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "figures"
OUT.mkdir(exist_ok=True)
data = json.loads((ROOT / "run/comparison.json").read_text())
rows = data["pairs"]
assert len(rows) == 6 and not data["exclusions"]

# Independently recompute the reported aggregate metrics before rendering.
for arm, expected in data["metrics"].items():
    gaps = [r[arm] - r["target"] for r in rows]
    outside = [max(r["bid"] - r[arm], r[arm] - r["ask"], 0) for r in rows]
    actual = {"mae_pp": 100 * mean(abs(gap) for gap in gaps),
              "rmse_pp": 100 * math.sqrt(mean(gap ** 2 for gap in gaps)),
              "mean_outside_spread_pp": 100 * mean(outside)}
    for key, value in actual.items():
        assert math.isclose(value, expected[key], abs_tol=1e-10), (arm, key)

# R owns the figure; this entry point also regenerates the LaTeX tables.
subprocess.run(["Rscript", str(ROOT / "plot_performance.R")], check=True)

# The exact-value tables are generated from the same frozen artifact as the plot.
names = [r"LAX high 74--75$^\circ$F (Sep.\ 18)",
         r"US unemployment $>4.4\%$ (Sep.)", r"Fed holds rates (Oct.\ 28)",
         r"Neutron launches before 2027", r"Netflix film ranks first\textsuperscript{a}",
         r"Milwaukee beats Baltimore (Sep.\ 20)"]
case_lines = []
for name, r in zip(names, rows):
    case_lines.append(f"{name} & {100*r['bid']:g}--{100*r['ask']:g} & "
                      f"{100*r['target']:g} & {100*r['question_only']:g} & "
                      f"{100*r['outside_research']:g} " + r"\\")
(OUT / "contract_rows.tex").write_text("\\newcommand{\\ContractRows}{%\n" + "\n".join(case_lines) + "\n}\n")
metric_lines = []
for label, key in [("Mean absolute gap", "mae_pp"), ("Root mean squared gap", "rmse_pp"),
                   ("Mean distance outside spread", "mean_outside_spread_pp")]:
    values = " & ".join(f"{data['metrics'][a][key]:.2f}" for a in
                        ("question_only", "outside_research", "constant_50"))
    metric_lines.append(f"{label} & {values} " + r"\\")
(OUT / "metric_rows.tex").write_text("\\newcommand{\\MetricRows}{%\n" + "\n".join(metric_lines) + "\n}\n")
print("Verified three metrics for all three baselines; wrote figure and LaTeX table rows.")
