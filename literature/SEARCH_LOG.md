# Search and extraction notes

Research cutoff: September 8, 2026.

## Scope and approach

The working question is: what empirical evidence and infrastructure would help
an agent-facing forecasting package produce, evaluate, and improve probabilistic
forecasts of real-world events?

The initial scope follows the preceding Vorhersage discussion. It emphasizes
event forecasting with LLMs and agents. Numerical forecasting appears where it
clarifies specialist baselines or the value of textual context. This is a
narrative review with targeted searches and citation following, not a registered
systematic review. Search-result counts, duplicate-removal counts, and a PRISMA
flow were not collected, so none are inferred after the fact.

The seed source was the user-supplied `forcasting.pdf`, *Evaluating Strategic
Reasoning in Forecasting Agents* (source 21). All 17 PDF pages were read. Searches
then followed its cited systems, relevant benchmarks, and methodological critiques.
The August 2026 survey by Xu et al. (29) provided a further discovery map; original
papers support the review's substantive technical claims.

Searches used general scholarly web discovery, arXiv, OpenReview, conference
proceedings, publisher pages, and author/institutional repositories. Third-party
indexes helped locate papers and versions; their summaries were not used as
the substantive basis for technical conclusions. The dated bibliography records
the source actually used, including explicit versions where inspected.

## Search families

The search progressed through the following themes. These are reproducible query
families, not a claim to preserve every query string or result ordering.

| Theme | Representative terms and follow-ups |
| --- | --- |
| Field map | AI forecasting literature review; LLM event forecasting survey; forecasting agents 2026 |
| Capability | Approaching Human-Level Forecasting; Wisdom of the Silicon Crowd; Superhuman Automated Forecasting; AIA Forecaster |
| Evaluation | ForecastBench; Autocast; ForecastQA; FutureX; MIRAI; FOReCAst; Prophet Arena |
| Historical controls | Pitfalls in Evaluating Language Model Forecasters; Bench to the Future; Hindcast; Agentic Time Machine |
| Research and reasoning | AutoCast++; strategic reasoning forecasting agents; sequential Bayesian updating linguistic beliefs |
| Aggregation | Diversity is the Strength of the AI Crowd; LLM forecasting deliberation; model ensemble dependence |
| Training | Outcome-based Reinforcement Learning to Predict the Future; Future-as-Label; forecasting reinforcement learning 2026 |
| Uncertainty | consistency checks forecasters; Beta-Bernoulli calibrator; forecasting calibration rationale faithfulness |
| Human foundations | Mellers forecasting tournament training; Chang CHAMPS KNOW |
| Human–AI systems | AI-Augmented Predictions; prospective venture tournament; human AI forecasting collaboration |
| Adjacent numerical work | Chronos; Chronos-2; Are Language Models Actually Useful for Time Series Forecasting; Context is Key; GenCast |

Exact-title, arXiv-ID, and DOI lookups followed discovery to verify metadata and
retrieve original sources. Publication dates were distinguished from search
engine crawl dates. Coverage includes recent work through August 2026; this is
not a claim that every paper published before the cutoff has been located.

## Inclusion and interpretation

Include research with direct relevance to forecast generation, evidence access,
aggregation, training, calibration, evaluation, or human–AI forecasting. Include
negative findings and methodological critiques. Clearly distinguish foundational
theory, experiments, technical reports, preprints, surveys, and announcements.
The CAIS announcement (10) is included as a historical claim, with the limited
access to its underlying report made explicit.

Exclude generic future-of-AI speculation, papers merely using the word
“prediction” for an unrelated classification task, and unsupported third-party
performance summaries. This pass does not comprehensively cover econometrics,
financial trading, demand forecasting, epidemiology, or weather. It also does
not establish the current rank of every model on a changing leaderboard.

For each included source, extract the task and evaluation design, source version,
reading depth, a supported finding, an important limitation, and a proposed
Vorhersage implication. A design implication is a synthesis, not an empirical
effect measured in the cited paper.

Reading depth has deliberately conservative labels:

- **Full supplied PDF:** all pages of the seed paper.
- **Selected full-text sections:** relevant methods, tables, or limitations were
  read; this does not imply a complete paper or supplement review.
- **Abstract/introduction/overview:** useful for mapping contributions; numerical
  conclusions are limited to what was directly checked.
- **Announcement:** a primary record of an author's or organization's claim,
  carrying less evidential weight than a verified evaluation report.

No study's code, dataset, forecast timestamps, or statistical results have been
independently reproduced in this pass. Access to a paper is not verification of
its raw data or leakage controls.

## Specific extraction issues

| Sources | Issue and treatment |
| --- | --- |
| 4: ForecastQA | Preprint and published baseline accuracy differ. Use the published ACL version; omit the unnecessary baseline percentage. |
| 8: Halawi et al. | Use the NeurIPS PDF. Its multiple retrieval dates are first averaged within questions; record the 914-question test cohort rather than treating dates as independent questions. |
| 9: Silicon Crowd | Verify the published November 2024 version and author list; 31 questions limit generality despite a much larger human sample. |
| 10: CAIS | The primary announcement was read; the linked technical report was not retrieved. Keep the claim separate from stronger evidence. |
| 11 and 18: ForecastBench/AIA | Original ForecastBench source-category weighting and expert reference scores differ from AIA's presentation. Do not merge scores without reconciling policies and cohorts. |
| 18: AIA | Separate the 64 resolved live markets from 1,750 open markets compared with market prices. Only the former provide the cited direct live outcome result. |
| 19: Prophet Arena | Distinguish underlying events from contracts. A reported relative advantage in gross return does not establish profitable trading after costs. |
| 20: Question generation | Section 5.3 reports counts that do not reconcile. Do not use those counts as verified statistics. The separate 100-question resolution audit is reported as such. |
| 21: BTF-2 | The full evaluation has 1,417 questions; the combined-system comparison uses a common 1,367-question subset. Rationale rankings may be affected by answer format. |
| 22: Linguistic beliefs | Brier Index points are not raw Brier-loss differences. The headline cohort and expanded ablation cohort differ. The method retains history, so do not describe it as a compressed state replacing all history. |
| 23–25: Outcome training | Published, arXiv, and workshop versions can use different model details and evaluation sets. Keep claims attached to the accessed version. |
| 29: Survey | The PDF's journal template is not proof of journal publication. Treat it as the August 2026 arXiv survey preprint. |
| 35: Hindcast | Selection uses a probe's evidence assessment against the resolved side. Outcome-conditioned selection is a review concern inferred from the stated procedure. |
| 36: Agentic Time Machine | The offline/live correlation has 11 points including repeated runs and related ensembles; it is not validation across 11 independent architectures. |
| 37: AI augmentation | Use the published institutional-repository PDF. The study has 991 people but only six questions, and the control differs in capability and forecasting support. |
| 39: Venture tournament | There are 30 underlying ventures. The 870 pairwise comparisons are not independent venture outcomes; the principal reported metric is rank correlation. |

## Priorities for the next pass

1. **Audit the central empirical comparisons end to end.** Extract all relevant
   sample exclusions, exact forecast dates, uncertainty estimates, scoring
   formulas, and human/market information conditions for Halawi, ForecastBench,
   AIA, Prophet Arena, BTF-2, and the linguistic-belief forecaster. Build a
   machine-readable comparison matrix before any quantitative synthesis.
2. **Review calibration and training in depth.** Read the full protocols for
   outcome RL, Future-as-Label, the Beta-Bernoulli Calibrator, and consistency
   checks. Identify where temporal splits, model selection, or human targets
   change the interpretation of reported improvements.
3. **Audit replay data construction.** Follow question selection, archive
   capture, document filtering, and eligibility for newer models in BTF,
   Hindcast, and Agentic Time Machine. Check whether label-dependent processing
   changes task difficulty without exposing the literal answer.
4. **Extend aggregation and human–AI evidence.** Read the full deliberation and
   venture studies; examine dependence, multiple comparisons, and budget
   matching. Follow earlier SAGE and Human Forest work cited in source 37 to
   connect reference classes and hybrid forecasting before LLMs.
5. **Broaden domains deliberately.** Screen prospective sports studies such as
   [WorldCup Arena](https://arxiv.org/abs/2608.04008), then add macroeconomic,
   scientific, and organizational forecasting evidence. That sports candidate
   is a discovery lead, not an included or verified result. Extend numerical
   forecasting only as needed for the package's intended tasks.
6. **Turn findings into reproducible experiments.** Inventory code/data access
   and licenses; select a small public cohort; reproduce a simple forecast and
   equal-weight aggregate before more elaborate interventions. Keep this
   empirical phase separate from the present literature review.

Priority questions include whether a method helps at fixed cost, whether gains
survive a new period and domain, what fraction comes from imported human or
market information, and how much uncertainty remains after grouping forecasts
by underlying event. Long-horizon, conditional, and privately specified forecasts
remain important gaps in this collection.
