# Deep research mode

The single-question study interface uses `research_effort: "deep"` by
default. Deep mode is intended for forecasts where the agent should spend
substantial effort before issuing a probability.

The workflow now starts with two explicit tasks before the prior: **reference
class design** and **reference class analysis**. The prior task must then use an empirical reference class. The agent should
construct that class with [Flyvbjerg](../../flyvbjerg), preserving the target
population, inclusion rule, case evidence, outcome metric, maturity and
dependence decisions, and sensitivity analyses. A completed analysis task
must identify an exported `analysis.json`; Vorhersage validates its analysis
ID, frozen subject count, metric, and dependence clusters. Flyvbjerg performs no web
research itself: the agent searches with its available tools, then registers
the source identities and captures in Flyvbjerg.

If no defensible reference class exists, the analysis may be marked blocked and
the agent may use a judgmental prior only with a `reference_class_exception`.
That field must explain the searches
performed, the candidate classes rejected, why they were not comparable, and
which assumptions remain unsupported. The exception is retained with the
forecast so a later reviewer can target the missing work.

Low-level `Workflow.start` callers can select `research_effort: "standard"`
for compatibility with lightweight tests and ablation arms. Experiments can
therefore compare deep research against standard, minimal, or stage-ablated
methods explicitly.
