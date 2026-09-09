# AI Forecasting: Evidence, Methods, and Evaluation

## Overview

AI forecasting of real-world events has developed from temporal question answering
into systems that search for evidence, maintain probability estimates, combine
forecasts, and learn from resolved outcomes. The strongest results concern
particular systems under particular evaluation conditions. The literature supports
substantial progress, but a general claim that AI has surpassed expert human
forecasters would erase important differences in questions, information access,
forecast horizons, and scoring. Early prospective results, later ensemble studies,
and more recent agent systems measure different capabilities.[^7][^9][^18]

For an agent-facing forecasting package, the most defensible priorities are
reproducible evaluation, evidence provenance, independent forecast aggregation,
explicit belief updates, and calibration assessed on held-out data. Strategic
review is a promising experimental capability. A fluent rationale or completed
checklist should not itself count as evidence of forecasting skill. Recent work
also motivates outcome-based training, although the infrastructure needed to
produce trustworthy training examples overlaps heavily with the infrastructure
needed for trustworthy evaluation.[^21][^22][^23]

This review distinguishes empirical findings, authors' claims, and proposed
engineering implications. It covers literature identified through September 8,
2026, with primary emphasis on probabilistic event forecasting and selected
connections to numerical forecasting. It is a substantial initial narrative
review, not an exhaustive systematic review or a pooled meta-analysis. Some
recent studies remain preprints, and the accompanying bibliography identifies
which sources have only been screened at abstract level.

## 1. The scope of AI forecasting

Three task families should remain distinct. **Event forecasting** estimates the
probability of a specified event under a deadline and resolution rule. **Numerical
forecasting** predicts a future quantity or distribution from historical data and
possibly other information. **Structured event prediction** predicts relations,
entities, or event types in a temporal database. Systems may share components,
but their outputs and evaluation criteria differ.[^4][^14][^30]

| Task | Typical output | Appropriate comparison |
| --- | --- | --- |
| Binary event | Probability of a qualifying event by a deadline | Brier/log loss against outcomes; matched human or market estimates |
| Categorical event | Distribution over mutually exclusive outcomes | Multiclass proper score with a declared convention |
| Event timing | Distribution over dates or a cumulative event probability | Timing-sensitive evaluation with censoring handled explicitly |
| Numerical target | Quantiles, samples, or a predictive distribution | CRPS or other suitable distributional scores; specialist baselines |
| Relational event | Predicted actors, relations, or event sets | Task-specific retrieval/classification metrics; probability scoring if available |

The distinction matters for interpreting apparently contradictory results.
Language may contribute valuable knowledge about an unusual institutional change
while contributing little to a numerical series whose relevant structure is
already observable. The useful question is the incremental value of the language
component under the information actually required by the task.[^31][^34]

## 2. Foundations and early evidence

Proper scoring rules reward accurate probability distributions in expectation.
For binary outcomes, this review uses the Brier loss convention
`BS = mean((p - y)^2)`, with smaller values better. A constant 50% forecast scores
0.25, but an informative base-rate baseline can perform substantially better.
Probability accuracy, calibration, and decision value are related but distinct
properties. Numerical targets require distributional evaluation rather than
silently substituting point accuracy.[^1]

Human forecasting research provides a methodological foundation rather than a
guarantee about AI. Mellers and colleagues found benefits from probability
training, collaboration, and performance tracking. Chang and colleagues reported
6–11% improvements in Brier scores from brief forecasting training. These findings
motivate controlled tests of analogous agent workflows; they do not supply effect
sizes for an LLM implementation.[^2][^3]

ForecastQA formalized forecasting from time-restricted text as a question-answering
challenge. Autocast subsequently connected forecasting-platform questions with
dated news and included numerical uncertainty through IntervalQA. These studies
established useful task definitions and exposed substantial room for improvement.
They also illustrate why benchmark versions matter: a historical collection that
was appropriate for an early model can later become a test of remembered
outcomes.[^4][^5]

Schoenegger and Park's 2023 prospective tournament provides an important negative
baseline: the tested GPT-4 setup underperformed the human crowd and was not
significantly different from assigning 50% throughout. That finding should be
preserved as evidence about its model and protocol, rather than extrapolated to
all subsequent forecasting systems.[^7]

## 3. The benchmark landscape

Live evaluation, historical replay, and logical diagnostics answer different
questions. Live forecasts provide the strongest direct check on future-outcome
prediction, but feedback arrives slowly. Replay enables rapid development while
requiring explicit controls on information. Logical checks provide immediate
feedback about consistency, without replacing outcome evaluation.

| Benchmark or approach | Main contribution | Interpretation requirement |
| --- | --- | --- |
| ForecastQA / Autocast | Early temporal-text and tournament-question tasks | Preserve task type and historical model eligibility.[^4][^5] |
| MIRAI | Structured event history and news accessible through agent tools | Relational prediction is a different target from a binary tournament.[^14] |
| FOReCAst | Boolean, timeframe, and quantity questions | Retain target-specific confidence and scoring semantics.[^15] |
| ForecastBench | Repeated prospective evaluation with human comparisons | Inspect source weighting, multiple horizons, and unresolved-market proxies.[^11] |
| FutureX | Live, frequently refreshed future-prediction tasks | Inspect question mix and scoring before comparing leaderboard positions.[^16] |
| Prophet Arena | Live market events and stage-specific analysis | Separate market contracts, underlying events, and lead-time groups.[^19] |
| BTF / BTF-2 | Frozen evidence environments for repeatable research | Archived evidence does not certify the model's training history.[^17][^21] |
| Consistency checks | Tests on logically related probabilities | Consistency can diagnose errors without proving accuracy.[^12] |
| Hindcast | Frozen social evidence and historical market comparisons | Corpus coverage and model eligibility need separate checks.[^35] |
| Agentic Time Machine | Filtered replay and comparison with live performance | Approximate historical reconstruction remains a measurement assumption.[^36] |

Hindcast reports that retrieval helps where its Reddit archive contains useful
prior discussion and can hurt where it contains speculation. Agentic Time
Machine reports agreement between offline and live rankings for its tested
systems. These are useful extensions of the evaluation literature, but their
controls should be independently audited before treating replay as equivalent
to prospective evaluation. Hindcast selects markets using evidence judged against
the resolved side; this creates an outcome-conditioned selection concern even
when retrieved documents predate the outcome. That concern is an inference from
its sampling procedure. Agentic Time Machine's live/replay correlation uses 11
points that include repeated runs and related ensembles, limiting the breadth
of that validation.[^35][^36]

## 4. What human-level performance claims establish

The following comparisons are within-study observations, not a ranking across
studies. Raw Brier values should not be ordered across rows: outcome base rates,
question difficulty, horizons, and score aggregation differ.

| Study | Reported comparison | Appropriate reading |
| --- | --- | --- |
| Halawi et al. | Retrieval-augmented system approaches crowd performance; 914 held-out test questions | Evidence for a combined system under historical evaluation.[^8] |
| Wisdom of the Silicon Crowd | Twelve-model aggregate versus 925 humans on 31 binary questions | Encouraging prospective ensemble evidence with a small question sample.[^9] |
| ForecastBench v5, Table 2 | Superforecaster aggregate 0.096; leading listed LLM 0.122 | Historical benchmark result; source-balanced score includes proxy treatment for unresolved markets.[^11] |
| AIA, Table 2 | FB-7-21: AIA 0.1076, experts 0.1110; MarketLiquid: AIA 0.1258, market 0.1106 | Expert comparability and market superiority are different tests.[^18] |
| AIA, Table 8 | On 64 resolved live markets: AIA 0.1002, market 0.1111 | Authors cannot statistically distinguish the two estimates.[^18] |
| BTF-2, Table 6 | Combined system 0.119; Opus 4.6 0.130 on 1,367 common questions | A matched system improvement in a frozen historical environment.[^21] |

ForecastBench's Table 2 averages its dataset and market category means equally.
Its human score is therefore not the pooled mean over all forecast records.
AIA reports a different expert reference score for its ForecastBench comparison;
the two tables should not be joined as a common leaderboard without reconciling
their evaluation policies.[^11][^18]

Two recurring inferential errors deserve attention. First, a statistically
insignificant difference does not generally establish equivalence; an equivalence
claim needs a stated tolerance and appropriate analysis. Second, a system using
market or crowd forecasts as inputs should be assessed for what it adds to those
forecasts. Such an input can be entirely appropriate for deployment while changing
the meaning of a human-versus-AI comparison.

The CAIS announcement of FiveThirtyNine is historically relevant because of its
strong “superhuman” framing. Its stated evaluation assumptions include a model
cutoff and date-restricted search. Later methodological criticism makes those
assumptions material rather than sufficient assurances. The announcement is
included as a primary record of the claim; it is not treated as conclusive
evidence of general superhuman forecasting.[^10][^13]

## 5. Evidence retrieval and information synthesis

Halawi et al. make research, reasoning, and aggregation explicit system
components. AutoCast++ focuses more narrowly on retrieving concise, relevant,
recent evidence and summarizing it. Together these approaches motivate evaluating
the evidence-selection stage separately from the final probability estimate.
Better search results and better judgment over those results are different
interventions.[^8][^6]

AIA reports a particularly large search benefit in its small resolved live
sample: Brier loss was 0.1002 with search and 0.3609 without. Its larger set of
1,750 unresolved markets instead measures agreement with market prices. That is
a useful comparison signal but should not be described as 1,750 resolved
forecasting outcomes.[^18]

The practical synthesis is conditional. A package should record whether new
research supplies timely, independent, target-relevant information. More pages
or more queries are activity measures. A proposed evaluation should compare
research policies on matched questions at fixed budgets, retain failures and
empty results, and test whether source overlap explains apparent diversity.

For Vorhersage, an evidence item should have source identity, excerpt or locator,
capture hash, publication and retrieval times, and a statement of its relevance.
The agent should distinguish observations from interpretations and explicitly
record unresolved disputes. This is an engineering proposal for making research
effects measurable, rather than a claim that the record structure itself improves
accuracy.

## 6. Aggregation and complementary errors

The Silicon Crowd study is a useful starting point for simple aggregation. Its
prospective result makes an inexpensive equal-weight ensemble a serious baseline,
while the limited number of questions constrains generalization. The same study
also examines human information as an input, supporting a distinction between
independent forecasts and human-assisted estimates.[^9]

Aitchison et al. study allocation of a fixed forecast-sample budget. A model's
individual accuracy did not fully predict its marginal contribution to an
ensemble; diversity mattered. Their limitations include 113 binary questions
from one tournament and omitted differences in per-sample cost. The direction is
promising, but selecting weights or model combinations on the scored questions
requires a later independent test.[^26]

The proposed package behavior is therefore conservative about selection: keep
every individual forecast, identify shared models and evidence, and preserve the
exact ensemble membership and weights. Compare equal weighting with learned
weighting before adding complexity. Use a training period for selection and a
later period for evaluation. Count the latest eligible submission once per
member, so repeated revisions do not accidentally create extra voting weight.

Deliberation deserves a separate treatment from averaging. Schneider and Schramm
test 202 resolved questions and report a roughly 4% log-loss reduction when
different models review each other's forecasts with shared information. They find
no benefit for homogeneous groups under the same process. This is conditional
evidence for a particular intervention, with historical evaluation and several
experimental conditions; it does not establish that discussion reliably improves
every ensemble.[^38]

### Human–AI collaboration

Schoenegger et al.'s preregistered study assigns 991 people to forecasting
assistants on six questions. Both frontier-model assistants improve performance
relative to a weaker-model control, including an assistant prompted to provide
noisy advice. The small question set and sensitivity to one item limit transfer,
and the control does not isolate prompting from model capability.[^37]

A prospective venture tournament supplies a different result. Csaszar, Peterson,
and Wilde compare forecasts of 30 live crowdfunding ventures and find strong
performance from the best individual LLM, without further gains from ensembles
or human–AI teams. Its target is a ranking of fundraising success, not a calibrated
event probability; 870 pairwise comparisons also share only 30 underlying
ventures. Together these studies motivate measuring the incremental benefit of
collaboration against both constituent forecasters.[^39]

## 7. Belief states, strategic reasoning, and rationales

Murphy's Bayesian Linguistic Forecaster supplies a concrete implementation idea:
maintain a probability, evidence for and against the event, and open research
questions throughout tool use. A retrospective ablation reports a 5.1-point
decrease in Brier Index after removing the belief state. This is not a 0.051
decrease in raw Brier loss. The ablation uses an expanded cohort, and the work
acknowledges limited live validation and concentration on one base model. Some
configurations also use market priors.[^22]

The supplied BTF-2 paper combines performance measurement with trace analysis.
Its improved system emphasizes pre-mortems, alternative perspectives, and
wildcards more often than individual agents. Expert review identifies failures
in interpreting actors' incentives and institutional processes. These findings
motivate explicit review tasks, but the authors acknowledge that rationale
formatting can influence their rankings and that their stronger system may be
overfit to the benchmark.[^21]

The two case studies help specify useful interventions. For the Nigerian strike
question, the review should distinguish public escalation rhetoric from a
conditional bargaining position and assess actual negotiation progress. For the
Brazilian legislation question, it should ask whether an approaching political
deadline changes the relevance of the historical pattern of delay. A good review
task identifies a mechanism that could change the probability, rather than
merely asking the agent to sound more cautious.[^21]

There is direct reason to avoid equating elaborate reasoning prompts with
improved forecasts. Prophet Arena reports no statistically significant benefit
from its tested reasoning-scaffold prompt. Sarfati et al.'s recent preprint also
finds that evidence interventions can change a model's probability without a
corresponding change in its written reasoning; activation probes provide a
different diagnostic in the tested open models.[^19][^28]

The resulting research agenda is behavioral: save probabilities before and after
review, vary evidence or remove a source, and measure the effect on held-out
scores. Keep human or LLM rubric assessments as secondary diagnostics. Treat
“incentives considered,” “pre-mortem completed,” and “sources cited” as workflow
observations until experiments show their value.

## 8. Training on real-world outcomes

Outcome-based reinforcement learning extends the training target beyond matching
an existing answer or imitating a rationale. Turtel et al.'s TMLR paper reports
that a compact forecasting model can become competitive with larger baselines
and improve calibration. Its training and evaluation are still tied to particular
question-generation and historical-data procedures.[^23]

Future-as-Label develops the idea of obtaining supervision as events resolve,
using temporally masked inputs and proper-score rewards. Jeen et al.'s workshop
paper reports improved gpt-oss-120b performance after training on roughly 10,000
binary questions. These studies justify evaluating forecasting-specific
optimization. They do not establish that any historical question/outcome pair is
a clean training example or that a larger training set removes temporal
dependence.[^24][^25]

An outcome is a noisy realization of a forecasting problem. Training should be
assessed for calibrated generalization across events, rather than rewarding the
appearance of certainty about every realized label. A deployable learning loop
also needs correction handling when an outcome was misresolved or the question
was invalid. For Vorhersage, exporting a well-defined training set is a later
capability that depends on earlier work on provenance, resolution, and splits.

## 9. Calibration and uncertainty

Calibration should be evaluated alongside proper-score accuracy and informative
variation between forecasts. An estimate that repeats a population base rate may
be calibrated yet provide little discrimination. A model can also improve a
particular calibration diagnostic while worsening a different loss. Calibration
plots need counts and uncertainty, and conclusions depend on the questions and
bins being evaluated.[^1][^21]

The Beta-Bernoulli Calibrator learns from both outcomes and human forecasts,
producing a distribution over event likelihood. Its reported advantage makes
learned calibration an important comparator to expensive forecasting fine-tuning.
The paper also notes that its approach does not incorporate information updates
and may inherit the domain composition of prediction-platform training data.
Second-order uncertainty from such a model is an estimate with assumptions, not
an observed ground-truth probability distribution.[^27]

A package should distinguish the issued probability, a calibrated probability,
and any confidence or second-order distribution. Preserve calibration parameters,
training data identifiers, and the original forecast. Assess transformations on
held-out periods and compare them with a simple uncalibrated baseline. Similar
discipline applies to learned ensemble weights.

## 10. Evaluation failures and resolution quality

Paleka et al.'s critique identifies several ways a historical forecasting test
can reward information unavailable at the forecast date: question selection can
reveal which outcomes resolved early, current search can prioritize historically
irrelevant documents, pages can change without updated dates, and model cutoff
claims may not bound all information channels. Copying human forecasts and
correlated risks across questions further complicate capability claims.[^13]

Question resolution also needs measurement. Bosse et al. generate 1,499 questions
and audit automated resolution. A human check finds four errors in 100 cases,
including missed annulments. The paper's small automated annulment count should
therefore not be interpreted as near-perfect question quality. Generation,
forecasting, and resolution are separate stages with separate error rates.[^20]

The following are proposed evaluation requirements for Vorhersage:

- **Freeze the question and scoring policy.** Preserve wording, criteria,
  eligible forecast cutoff, source weighting, and treatment of void outcomes.
- **Separate information times.** Record when a forecast was issued, when data
  became available, when an event occurred, and when it was formally resolved.
- **Separate proxy and outcome scores.** Crowd agreement can be reported as such;
  it should never silently join an outcome-based mean.
- **Match comparisons.** Use common questions and comparable horizons; expose
  missing submissions and failed research rather than dropping them silently.
- **Account for dependence.** Group related thresholds, contracts, and questions
  about the same underlying event in splits and uncertainty estimates.
- **Preserve resolution history.** Support disputes, annulments, and corrections,
  with sensitivity analyses for questionable labels.
- **Maintain prospective validation.** Historical evaluation supports iteration;
  later live questions test whether those improvements transfer.

These requirements define an auditable measurement system. Their implementation
would not certify that all leakage has been removed, especially for proprietary
models or externally controlled search services.

## 11. Adjacent numerical and contextual forecasting

Chronos demonstrates transferable probabilistic forecasting through a transformer
trained on numerical sequences; Chronos-2 extends that direction to multivariate
and covariate-informed tasks. These are natural specialist components for an
agent facing a numerical question. They should not be confused with asking a
general-purpose chat model to reason from prose.[^30][^33]

Tan et al. find that several tested LLM-based time-series methods retain or
improve performance when the language-model component is removed or simplified.
Context is Key provides a useful counterpoint: its tasks deliberately require
textual information alongside numbers, and a prompting method performs strongly
there. The distinction is the information required by the task, not a universal
verdict for or against LLM forecasting.[^31][^34]

GenCast shows what specialized probabilistic AI can accomplish in weather
forecasting, with dense domain data and domain-specific verification. For an
event-forecasting package, its main lesson is architectural: when a credible
specialist distribution exists, treat it as a candidate input or baseline and
evaluate the agent's incremental contribution.[^32]

The broader 2026 survey by Xu et al. is a useful map of standalone, tool-augmented,
and hybrid approaches. It also locates many emerging benchmarks and application
areas beyond this review's event-centered scope. Its taxonomy is useful for
discovery; substantive capability claims should continue to be checked against
the original studies.[^29]

## 12. Implications for Vorhersage

The literature suggests that the package's first contribution should be making
forecasting methods comparable and improvable. The following proposals build on
the evidence above, but the expected benefits of the package itself remain to be
tested.

### Core objects

Define a question version, an evidence snapshot, an intermediate belief, an
issued forecast, a review, a resolution, and an evaluation policy. Store model
and method identifiers on forecasts rather than relying on a human-readable
label. Keep intermediate belief updates distinct from externally issued
submissions. A revision should append history and name the evidence or
assumption that changed.

An evidence snapshot should identify the actual supplied content. An ordinary
file hash establishes content identity, not that the content was publicly
available at the claimed time. Record the basis for availability claims, and
allow an evaluator to mark uncertain or disallowed evidence explicitly.

### A minimum comparative experiment

Choose a declared cohort of binary questions and establish an initial estimate
under a fixed evidence packet. Compare four conditions: a simple forecast, a
forecast with explicit belief updates, independent repeated forecasts combined
by arithmetic mean, and a structured strategic review. Hold the model and
resource budget comparable where possible, and report cost when they differ.

For review, preserve the initial probability and require a concrete objection:
contrary evidence, an omitted actor, an institutional prerequisite, or a reason
the reference class no longer applies. Permit no change after review. The
evaluation target is subsequent accuracy, not the size or frequency of revisions.

Use separate questions or time periods for designing prompts and scoring their
final performance. If sample size is initially small, report effect estimates
and uncertainty rather than choosing a winner from minor differences. Validate
the chosen method prospectively before advertising a persistent advantage.

### Integrations and boundaries

Flyvbjerg can supply auditable reference-class artifacts; Epiq suggests a useful
evidence and provenance model; Premortem can inform challenge prompts; Raiffa can
consume probabilities in a decision model. These are local design opportunities,
not dependencies established by the research literature. Simple file contracts
would allow testing before committing to tightly coupled packages.

Numerical providers should expose their forecast distribution, horizon, data
vintage, and covariates. Agent-generated interpretations should remain separate
from provider output. A downstream decision module additionally needs utilities,
actions, and assumptions about how actions affect outcomes: an unconditional
forecast is not automatically a causal forecast under intervention.

### Features to postpone until evaluation supports them

Complex learned ensemble weights, automatic probability corrections, continual
fine-tuning, and adaptive research-budget allocation all need a sufficiently
rich resolved record. Early versions should make these methods pluggable and
preserve their inputs. They should not encode the assumption that a longer
reasoning trace, more model calls, or more elaborate workflow improves accuracy.

## 13. Open questions

The most important unresolved question is how reliably improvements transfer
across domains, horizons, model releases, and information environments. A method
that helps with near-term political events may do little for product demand,
scientific milestones, or sparse private-company questions. Long-horizon and
conditional forecasts also provide slower and less complete feedback.

Other priorities are quantifying the value of research, understanding when
independent forecasts contribute new information, checking rationale faithfulness,
and measuring how resolution error affects model selection. Human-assisted and
market-assisted forecasting deserve their own comparisons. Their practical value
depends on the accuracy added by the combined system, not on maintaining an
artificial boundary between human and machine information.

A useful next research phase would reproduce a small set of these comparisons
with common question cohorts and controlled evidence. The current evidence is
strongest as a guide to such experiments. It does not justify predicting the
accuracy of a new Vorhersage implementation before those experiments exist.

## Sources

The numbered source notes identify the versions supporting this review. The
[annotated bibliography](BIBLIOGRAPHY.md) records findings, caveats, and reading
depth for each source. Structured records are available in
[JSON](sources.json) and [CSV](sources.csv).

[^1]: Tilmann Gneiting; Adrian E. Raftery (2007). [Strictly Proper Scoring Rules, Prediction, and Estimation](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf). Journal of the American Statistical Association 102(477):359–378. p. 359; DOI 10.1198/016214506000001437.

[^2]: Barbara Mellers et al. (2014). [Psychological Strategies for Winning a Geopolitical Forecasting Tournament](https://www.psychologicalscience.org/journals/psychological-science/0956797614524255/). Psychological Science 25(5). Abstract; DOI 10.1177/0956797614524255.

[^3]: Welton Chang; Eva Chen; Barbara Mellers; Philip Tetlock (2016). [Developing expert political judgment: The impact of training and practice on judgmental accuracy in geopolitical forecasting tournaments](https://sjdm.org/~baron/journal/16/16511/jdm16511.html). Judgment and Decision Making 11(5):509–526. Abstract.

[^4]: Woojeong Jin et al. (2021). [ForecastQA: A Question Answering Challenge for Event Forecasting with Temporal Text Data](https://aclanthology.org/2021.acl-long.357.pdf). ACL-IJCNLP 2021. p. 4636; arXiv first submission 2020.

[^5]: Andy Zou et al. (2022). [Forecasting Future World Events with Neural Networks](https://arxiv.org/abs/2206.15474). NeurIPS 2022 Datasets and Benchmarks. Abstract; Autocast and IntervalQA.

[^6]: Qi Yan; Raihan Seraj; Jiawei He; Lili Meng; Tristan Sylvain (2023). [AutoCast++: Enhancing World Event Prediction with Zero-shot Ranking-based Context Retrieval](https://arxiv.org/abs/2310.01880). arXiv preprint. Abstract.

[^7]: Philipp Schoenegger; Peter S. Park (2023). [Large Language Model Prediction Capabilities: Evidence from a Real-World Forecasting Tournament](https://arxiv.org/abs/2310.13014). arXiv preprint. Abstract; July–October 2023 tournament.

[^8]: Danny Halawi; Fred Zhang; Yueh-Han Chen; Jacob Steinhardt (2024). [Approaching Human-Level Forecasting with Language Models](https://proceedings.neurips.cc/paper_files/paper/2024/file/5a5acfd0876c940d81619c1dc60e7748-Paper-Conference.pdf). NeurIPS 2024. Abstract; §3; Table 2.

[^9]: Philipp Schoenegger; Indre Tuminauskaite; Peter S. Park; Rafael Valdece Sousa Bastos; Philip E. Tetlock (2024). [Wisdom of the Silicon Crowd: LLM Ensemble Prediction Capabilities Rival Human Crowd Accuracy](https://researchonline.lse.ac.uk/id/eprint/125626/1/sciadv.adp1528.pdf). Science Advances 10(45):eadp1528, November 2024. Study 1 and Study 2 abstracts; published DOI 10.1126/sciadv.adp1528.

[^10]: Center for AI Safety; accompanying report by Long Phan et al. (2024). [Superhuman Automated Forecasting](https://safe.ai/blog/forecasting). CAIS research announcement. Evaluation and technical-report link.

[^11]: Ezra Karger; Houtan Bastani; Yueh-Han Chen; Zachary Jacobs; Danny Halawi; Fred Zhang; Philip E. Tetlock (2025). [ForecastBench: A Dynamic Benchmark of AI Forecasting Capabilities](https://arxiv.org/html/2409.19839v5). arXiv v5; first submitted 2024. §5.2; Table 2 and its notes.

[^12]: Daniel Paleka; Abhimanyu Pallavi Sudhir; Alejandro Alvarez; Vineeth Bhat; Adam Shen; Evan Wang; Florian Tramèr (2025). [Consistency Checks for Language Model Forecasters](https://arxiv.org/abs/2412.18544). ICLR 2025; arXiv first submitted 2024. Abstract; ICLR OpenReview r5IXBlTCGc.

[^13]: Daniel Paleka; Shashwat Goel; Jonas Geiping; Florian Tramèr (2025). [Pitfalls in Evaluating Language Model Forecasters](https://arxiv.org/html/2506.00723v1). arXiv preprint. §§2–3.

[^14]: Chenchen Ye et al. (2024). [MIRAI: Evaluating LLM Agents for Event Forecasting](https://arxiv.org/abs/2407.01231). arXiv paper. Abstract; https://mirai-llm.github.io/.

[^15]: Zhangdie Yuan; Zifeng Ding; Andreas Vlachos (2025). [FOReCAst: The Future Outcome Reasoning and Confidence Assessment Benchmark](https://arxiv.org/abs/2502.19676v4). arXiv v4. Abstract.

[^16]: Zhiyuan Zeng et al. (2025). [FutureX: An Advanced Live Benchmark for LLM Agents in Future Prediction](https://arxiv.org/abs/2508.11987v3). arXiv v3. Abstract.

[^17]: Jack Wildman; Nikos I. Bosse; Daniel Hnyk; Peter Mühlbacher; Finn Hambly; Jon Evans; Dan Schwarz; Lawrence Phillips (2025). [Bench to the Future: A Pastcasting Benchmark for Forecasting Agents](https://arxiv.org/abs/2506.21558). arXiv preprint. Abstract.

[^18]: Rohan Alur; Bradly C. Stadie; Daniel Kang et al. (2025). [AIA Forecaster: Technical Report](https://arxiv.org/html/2511.07678v1). Bridgewater AIA Labs technical report. Tables 1, 2, 8; §§4–7.

[^19]: Qingchuan Yang; Simon Mahns; Sida Li; Anri Gu; Jibang Wu; Haifeng Xu (2026). [LLM-as-a-Prophet: Understanding Predictive Intelligence with Prophet Arena](https://arxiv.org/html/2510.17638v1). ICLR 2026; arXiv v1 dated 2025. §3.2; Tables 2, 10; Appendix C.6.1.

[^20]: Nikos I. Bosse; Peter Mühlbacher; Jack Wildman; Lawrence Phillips; Dan Schwarz (2026). [Automating Forecasting Question Generation and Resolution for AI Evaluation](https://arxiv.org/html/2601.22444v2). ICLR 2026 workshop; arXiv v2. §§4–5; human verification.

[^21]: Tom Liptay; Dan Schwarz; Rafael Poyiadzi; Jack Wildman; Nikos I. Bosse (2026). [Evaluating Strategic Reasoning in Forecasting Agents](https://arxiv.org/abs/2604.26106v1). arXiv v1; supplied PDF. Supplied forcasting.pdf, pp. 2–9, Tables 3–7.

[^22]: Kevin Murphy (2026). [Agentic Forecasting using Sequential Bayesian Updating of Linguistic Beliefs](https://arxiv.org/html/2604.18576v1). arXiv v1. §4 Table 3; §6; Appendix B.1.

[^23]: Benjamin Turtel; Danny Franklin; Kris Skotheim; Luke Hewitt; Philipp Schoenegger (2025). [Outcome-based Reinforcement Learning to Predict the Future](https://openreview.net/pdf?id=bbhdeL8EUX). Transactions on Machine Learning Research, November 2025. Published abstract; arXiv 2505.17989.

[^24]: Benjamin Turtel; Paul Wilczewski; Danny Franklin; Kris Skothiem (2026). [Future-as-Label: Scalable Supervision from Real-World Outcomes](https://arxiv.org/html/2601.06336v1). arXiv v1. Abstract; method.

[^25]: Scott Jeen; Matthew Aitchison; Maximilian Anthony Hugh Clark; Toby Shevlane; Ben Day (2026). [Reaching the frontier of AI forecasting with reinforcement learning](https://www.mantic.com/publications/153005). ICML 2026 forecasting workshop. https://openreview.net/pdf?id=lbpDR9pj5F; July 2026 author page.

[^26]: Matthew Aitchison; Scott Jeen; Toby Shevlane; Ben Day (2026). [Diversity is the Strength of the AI Crowd](https://arxiv.org/abs/2606.29661). arXiv preprint; ICML forecasting workshop. OpenReview JAYM7AGe50; §7.

[^27]: Hui Dai; Ryan Teehan; Parsa Torabian; Mengye Ren (2026). [Aligning LLMs with Human Uncertainty: A Beta-Bernoulli Calibrator for LLM Forecasting](https://arxiv.org/html/2605.27668v1). arXiv preprint. Abstract; Appendix A.

[^28]: Raphaël Sarfati; Pratyush Ranjan Tiwari; Siddharth Boppana; Christopher J. Earls; Srikar Varadaraj; Eric Ho (2026). [What LLM Forecasters Know but Don't Say: Probing Internal Representations for Calibration and Faithfulness](https://arxiv.org/abs/2607.08046v1). arXiv preprint. Abstract.

[^29]: Xiaogang Xu et al. (2026). [LLM-based Agents for Forecasting and Prediction: Methods, Training, Evaluation, and Applications](https://arxiv.org/pdf/2608.23058). arXiv survey preprint. §§5–7; references.

[^30]: Abdul Fatir Ansari et al. (2024). [Chronos: Learning the Language of Time Series](https://arxiv.org/abs/2403.07815). Transactions on Machine Learning Research, October 2024. Abstract; published OpenReview gerNCVqqtR.

[^31]: Mingtian Tan; Mike A. Merrill; Vinayak Gupta; Tim Althoff; Thomas Hartvigsen (2024). [Are Language Models Actually Useful for Time Series Forecasting?](https://arxiv.org/abs/2406.16964). NeurIPS 2024. Abstract.

[^32]: Ilan Price et al. (2024). [Probabilistic weather forecasting with machine learning](https://doi.org/10.1038/s41586-024-08252-9). Nature; GenCast. Published article; arXiv 2312.15796.

[^33]: Abdul Fatir Ansari et al. (2025). [Chronos-2: From Univariate to Universal Forecasting](https://arxiv.org/abs/2510.15821). arXiv preprint. Abstract.

[^34]: Andrew R. Williams et al. (2025). [Context is Key: A Benchmark for Forecasting with Essential Textual Information](https://proceedings.mlr.press/v267/williams25a.html). ICML 2025; first submitted 2024. Abstract; PMLR 267.

[^35]: Xiao Ye; Jacob Dineen; Evan Zhu; Shijie Lu; Kevin Song; Ben Zhou (2026). [Hindcast: Replaying Prediction Markets to Evaluate LLM Forecasters](https://arxiv.org/html/2607.14051v1). arXiv preprint. Abstract; §§3.3–4.1.

[^36]: Jingyi Chai; Bingyang Zheng; Xiangrui Liu; Hao Lu; Zihang Zhou; Tianchen Wang; Kemeng Zhang; Siheng Chen (2026). [Agentic Time Machine as an Infrastructure for Future-Event Forecasting](https://arxiv.org/abs/2606.21013v1). arXiv preprint. Abstract; offline/live correlation analysis.

[^37]: Philipp Schoenegger; Peter S. Park; Ezra Karger; Sean Trott; Philip E. Tetlock (2025). [AI-Augmented Predictions: LLM Assistants Improve Human Forecasting Accuracy](https://eprints.lse.ac.uk/127059/3/3707649.pdf). ACM Transactions on Interactive Intelligent Systems 15(1), Article 4. Abstract; §1; DOI 10.1145/3707649.

[^38]: Paul Schneider; Amalie Schramm (2025). [The Wisdom of Deliberating AI Crowds: Does Deliberation Improve LLM-Based Forecasting?](https://arxiv.org/abs/2512.22625v1). arXiv v1. Abstract.

[^39]: Felipe A. Csaszar; Aticus Peterson; Daniel Wilde (2026). [The Strategic Foresight of LLMs: Evidence from a Fully Prospective Venture Tournament](https://arxiv.org/abs/2602.01684v1). arXiv v1; SSRN working paper. Abstract; SSRN 6166986.
