# Annotated bibliography

Source IDs match the numbered notes in the [review](REVIEW.md). Records were
assembled on September 8, 2026. Reading depth describes the material inspected,
not the amount of material available. Proposed package implications have not
been tested in Vorhersage. See the [search notes](SEARCH_LOG.md) for scope and
remaining work.

## 1. Strictly Proper Scoring Rules, Prediction, and Estimation

Tilmann Gneiting; Adrian E. Raftery (2007). Journal of the American Statistical Association 102(477):359–378.
[Source](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf). Locator: p. 359; DOI 10.1198/016214506000001437.

**Topic:** Foundations. **Design:** Mathematical theory.
**Reading depth:** Abstract and opening definitions.

**Finding:** Establishes proper scoring as a basis for eliciting and evaluating probability distributions.

**Limitation:** Expected-score incentives do not eliminate finite-sample uncertainty.

**Vorhersage implication:** Define score conventions and retain forecast distributions.

## 2. Psychological Strategies for Winning a Geopolitical Forecasting Tournament

Barbara Mellers et al. (2014). Psychological Science 25(5).
[Source](https://www.psychologicalscience.org/journals/psychological-science/0956797614524255/). Locator: Abstract; DOI 10.1177/0956797614524255.

**Topic:** Human foundations. **Design:** Human tournament interventions.
**Reading depth:** Publisher abstract.

**Finding:** Probability training, collaboration, and tracking improved human forecasting.

**Limitation:** Human intervention effects require separate validation for AI systems.

**Vorhersage implication:** Test training guidance, independent estimates, and collaboration.

## 3. Developing expert political judgment: The impact of training and practice on judgmental accuracy in geopolitical forecasting tournaments

Welton Chang; Eva Chen; Barbara Mellers; Philip Tetlock (2016). Judgment and Decision Making 11(5):509–526.
[Source](https://sjdm.org/~baron/journal/16/16511/jdm16511.html). Locator: Abstract.

**Topic:** Human foundations. **Design:** Human forecasting training.
**Reading depth:** Abstract and article overview.

**Finding:** Brief CHAMPS KNOW training improved human Brier scores by 6–11%.

**Limitation:** Does not estimate an LLM treatment effect.

**Vorhersage implication:** Use forecasting principles as testable interventions.

## 4. ForecastQA: A Question Answering Challenge for Event Forecasting with Temporal Text Data

Woojeong Jin et al. (2021). ACL-IJCNLP 2021.
[Source](https://aclanthology.org/2021.acl-long.357.pdf). Locator: p. 4636; arXiv first submission 2020.

**Topic:** Early benchmarks. **Design:** Retrospective temporal QA.
**Reading depth:** Published abstract and introduction.

**Finding:** Introduces 10,392 forecasting questions using time-restricted news.

**Limitation:** Multiple-choice accuracy differs from probabilistic event forecasting; versions report different baseline accuracy.

**Vorhersage implication:** Keep task type and publication version explicit.

## 5. Forecasting Future World Events with Neural Networks

Andy Zou et al. (2022). NeurIPS 2022 Datasets and Benchmarks.
[Source](https://arxiv.org/abs/2206.15474). Locator: Abstract; Autocast and IntervalQA.

**Topic:** Early benchmarks. **Design:** Historical questions and dated news.
**Reading depth:** Abstract and benchmark description.

**Finding:** Autocast links tournament questions to dated news; larger models and relevant retrieval improve results.

**Limitation:** A fixed historical test becomes vulnerable as model training windows advance.

**Vorhersage implication:** Import question, evidence-date, and numeric-target metadata.

## 6. AutoCast++: Enhancing World Event Prediction with Zero-shot Ranking-based Context Retrieval

Qi Yan; Raihan Seraj; Jiawei He; Lili Meng; Tristan Sylvain (2023). arXiv preprint.
[Source](https://arxiv.org/abs/2310.01880). Locator: Abstract.

**Topic:** Retrieval. **Design:** Retrospective Autocast evaluation.
**Reading depth:** Abstract.

**Finding:** Relevance ranking, recency, and summarization improve retrieval-based event prediction.

**Limitation:** Dataset-specific gains do not establish live generalization.

**Vorhersage implication:** Separate retrieval selection from probability synthesis.

## 7. Large Language Model Prediction Capabilities: Evidence from a Real-World Forecasting Tournament

Philipp Schoenegger; Peter S. Park (2023). arXiv preprint.
[Source](https://arxiv.org/abs/2310.13014). Locator: Abstract; July–October 2023 tournament.

**Topic:** Human comparisons. **Design:** Prospective tournament.
**Reading depth:** Abstract.

**Finding:** GPT-4 underperformed the human crowd and was not significantly different from a 50% baseline.

**Limitation:** Applies to the tested early model and protocol.

**Vorhersage implication:** Preserve a simple prospective baseline.

## 8. Approaching Human-Level Forecasting with Language Models

Danny Halawi; Fred Zhang; Yueh-Han Chen; Jacob Steinhardt (2024). NeurIPS 2024.
[Source](https://proceedings.neurips.cc/paper_files/paper/2024/file/5a5acfd0876c940d81619c1dc60e7748-Paper-Conference.pdf). Locator: Abstract; §3; Table 2.

**Topic:** Forecasting systems. **Design:** Retrospective; 914 test questions.
**Reading depth:** Selected full-text sections.

**Finding:** Retrieval, reasoning, and aggregation approach competitive human-crowd performance.

**Limitation:** Later methodological work identifies residual leakage risks; repeated forecast dates require careful weighting.

**Vorhersage implication:** Build modular research and aggregation baselines.

## 9. Wisdom of the Silicon Crowd: LLM Ensemble Prediction Capabilities Rival Human Crowd Accuracy

Philipp Schoenegger; Indre Tuminauskaite; Peter S. Park; Rafael Valdece Sousa Bastos; Philip E. Tetlock (2024). Science Advances 10(45):eadp1528, November 2024.
[Source](https://researchonline.lse.ac.uk/id/eprint/125626/1/sciadv.adp1528.pdf). Locator: Study 1 and Study 2 abstracts; published DOI 10.1126/sciadv.adp1528.

**Topic:** Aggregation. **Design:** Prospective; 31 binary questions; 12 LLMs.
**Reading depth:** Abstract and published conclusion.

**Finding:** A twelve-model ensemble was not statistically different from a human crowd; combining human and AI predictions was useful.

**Limitation:** Only 31 questions; failure to reject difference is not universal equivalence.

**Vorhersage implication:** Retain independent member forecasts and a simple aggregate.

## 10. Superhuman Automated Forecasting

Center for AI Safety; accompanying report by Long Phan et al. (2024). CAIS research announcement.
[Source](https://safe.ai/blog/forecasting). Locator: Evaluation and technical-report link.

**Topic:** Historical claims. **Design:** Retrospective Metaculus evaluation.
**Reading depth:** Primary announcement; report itself not retrieved.

**Finding:** Announces the FiveThirtyNine forecasting system and crowd-level performance claims.

**Limitation:** The announcement relies on cutoff and date-restricted search assumptions subsequently challenged.

**Vorhersage implication:** Retain as a historically influential claim, not decisive capability evidence.

## 11. ForecastBench: A Dynamic Benchmark of AI Forecasting Capabilities

Ezra Karger; Houtan Bastani; Yueh-Han Chen; Zachary Jacobs; Danny Halawi; Fred Zhang; Philip E. Tetlock (2025). arXiv v5; first submitted 2024.
[Source](https://arxiv.org/html/2409.19839v5). Locator: §5.2; Table 2 and its notes.

**Topic:** Live benchmarks. **Design:** Prospective; mixed dataset and market questions.
**Reading depth:** Selected full-text sections.

**Finding:** The original human comparison favors superforecasters; evaluation combines multiple horizons and source categories.

**Limitation:** Some unresolved market forecasts use crowd proxies; overall weighting differs from a pooled Brier mean.

**Vorhersage implication:** Store score target, horizon, and aggregation policy.

## 12. Consistency Checks for Language Model Forecasters

Daniel Paleka; Abhimanyu Pallavi Sudhir; Alejandro Alvarez; Vineeth Bhat; Adam Shen; Evan Wang; Florian Tramèr (2025). ICLR 2025; arXiv first submitted 2024.
[Source](https://arxiv.org/abs/2412.18544). Locator: Abstract; ICLR OpenReview r5IXBlTCGc.

**Topic:** Consistency. **Design:** Logical checks and outcome evaluation.
**Reading depth:** Abstract; full-text located.

**Finding:** Uses arbitrage on logically related forecasts as an immediate diagnostic and reports correlation with Brier performance.

**Limitation:** Coherence alone cannot establish accurate beliefs.

**Vorhersage implication:** Add complement, conjunction, conditional, and horizon checks.

## 13. Pitfalls in Evaluating Language Model Forecasters

Daniel Paleka; Shashwat Goel; Jonas Geiping; Florian Tramèr (2025). arXiv preprint.
[Source](https://arxiv.org/html/2506.00723v1). Locator: §§2–3.

**Topic:** Evaluation critique. **Design:** Methodological analysis with examples.
**Reading depth:** Selected full-text sections.

**Finding:** Identifies outcome-selection leakage, unreliable historical retrieval, cutoff uncertainty, copied crowd signals, and correlated tournament risk.

**Limitation:** Some examples illustrate possible mechanisms rather than quantify every system's bias.

**Vorhersage implication:** Maintain multiple temporal controls and explicit comparison conditions.

## 14. MIRAI: Evaluating LLM Agents for Event Forecasting

Chenchen Ye et al. (2024). arXiv paper.
[Source](https://arxiv.org/abs/2407.01231). Locator: Abstract; https://mirai-llm.github.io/.

**Topic:** Structured event benchmarks. **Design:** Historical relational prediction with GDELT and news tools.
**Reading depth:** Abstract and project API description.

**Finding:** Provides an agent environment combining structured international events and textual evidence.

**Limitation:** Relational prediction metrics are not interchangeable with tournament Brier scores.

**Vorhersage implication:** Support tools over structured event histories.

## 15. FOReCAst: The Future Outcome Reasoning and Confidence Assessment Benchmark

Zhangdie Yuan; Zifeng Ding; Andreas Vlachos (2025). arXiv v4.
[Source](https://arxiv.org/abs/2502.19676v4). Locator: Abstract.

**Topic:** Broader forecast targets. **Design:** Benchmark; protocol needs deeper extraction.
**Reading depth:** Abstract.

**Finding:** Covers Boolean outcomes, timeframes, and quantities with confidence assessment.

**Limitation:** No numerical superiority claim extracted at this reading depth.

**Vorhersage implication:** Plan schemas beyond binary events.

## 16. FutureX: An Advanced Live Benchmark for LLM Agents in Future Prediction

Zhiyuan Zeng et al. (2025). arXiv v3.
[Source](https://arxiv.org/abs/2508.11987v3). Locator: Abstract.

**Topic:** Live benchmarks. **Design:** Live questions with automated updates.
**Reading depth:** Abstract.

**Finding:** Introduces a live, frequently updated benchmark evaluating 25 LLM/agent systems.

**Limitation:** Inspect task-specific scoring and sampling before comparing ranks with other platforms.

**Vorhersage implication:** Maintain an adapter for prospective evaluation.

## 17. Bench to the Future: A Pastcasting Benchmark for Forecasting Agents

Jack Wildman; Nikos I. Bosse; Daniel Hnyk; Peter Mühlbacher; Finn Hambly; Jon Evans; Dan Schwarz; Lawrence Phillips (2025). arXiv preprint.
[Source](https://arxiv.org/abs/2506.21558). Locator: Abstract.

**Topic:** Frozen evidence benchmarks. **Design:** Offline pastcasting.
**Reading depth:** Abstract.

**Finding:** Pairs resolved questions with offline web corpora for repeatable agent evaluation.

**Limitation:** Training-cutoff validity changes with the model; availability is not equivalent to a fully open corpus.

**Vorhersage implication:** Version frozen evidence and model eligibility.

## 18. AIA Forecaster: Technical Report

Rohan Alur; Bradly C. Stadie; Daniel Kang et al. (2025). Bridgewater AIA Labs technical report.
[Source](https://arxiv.org/html/2511.07678v1). Locator: Tables 1, 2, 8; §§4–7.

**Topic:** Forecasting systems. **Design:** Retrospective benchmarks plus 64 resolved live markets.
**Reading depth:** Selected full-text sections.

**Finding:** Combines search, synthesis, and calibration; reports expert-comparable benchmark scores and complementarity with market forecasts.

**Limitation:** Live evidence is smaller; 1,750 open-market comparisons use market prices rather than resolved outcomes.

**Vorhersage implication:** Evaluate market-assisted and market-blind modes separately.

## 19. LLM-as-a-Prophet: Understanding Predictive Intelligence with Prophet Arena

Qingchuan Yang; Simon Mahns; Sida Li; Anri Gu; Jibang Wu; Haifeng Xu (2026). ICLR 2026; arXiv v1 dated 2025.
[Source](https://arxiv.org/html/2510.17638v1). Locator: §3.2; Tables 2, 10; Appendix C.6.1.

**Topic:** Live benchmarks and diagnosis. **Design:** Live Kalshi event forecasts.
**Reading depth:** Selected full-text sections.

**Finding:** Finds horizon-sensitive model/market comparisons and no significant gain from the tested reasoning scaffold.

**Limitation:** Market-level records share events; gross-return comparisons do not establish net profitability.

**Vorhersage implication:** Record lead times and test scaffolds behaviorally.

## 20. Automating Forecasting Question Generation and Resolution for AI Evaluation

Nikos I. Bosse; Peter Mühlbacher; Jack Wildman; Lawrence Phillips; Dan Schwarz (2026). ICLR 2026 workshop; arXiv v2.
[Source](https://arxiv.org/html/2601.22444v2). Locator: §§4–5; human verification.

**Topic:** Question generation and resolution. **Design:** Generated questions; human audits.
**Reading depth:** Selected full-text sections.

**Finding:** Creates 1,499 questions; a human audit finds four resolution errors in 100 cases.

**Limitation:** A low automated annulment rate is not proof of high resolution quality; §5.3 contains inconsistent counts.

**Vorhersage implication:** Treat resolution as an auditable process with disputes and corrections.

## 21. Evaluating Strategic Reasoning in Forecasting Agents

Tom Liptay; Dan Schwarz; Rafael Poyiadzi; Jack Wildman; Nikos I. Bosse (2026). arXiv v1; supplied PDF.
[Source](https://arxiv.org/abs/2604.26106v1). Locator: Supplied forcasting.pdf, pp. 2–9, Tables 3–7.

**Topic:** Strategic reasoning and frozen evidence. **Design:** BTF-2; 1,417 questions; common subset 1,367.
**Reading depth:** Full supplied PDF.

**Finding:** Combined system scores 0.119 versus 0.130 for Opus on a matched subset; rationale and case analyses identify potential reasoning gaps.

**Limitation:** Possible benchmark overfitting; rationale format confounding; research comparison changes supplied evidence.

**Vorhersage implication:** Test review interventions and preserve evidence-linked intermediate forecasts.

## 22. Agentic Forecasting using Sequential Bayesian Updating of Linguistic Beliefs

Kevin Murphy (2026). arXiv v1.
[Source](https://arxiv.org/html/2604.18576v1). Locator: §4 Table 3; §6; Appendix B.1.

**Topic:** Belief updating and calibration. **Design:** Retrospective ForecastBench; ablations.
**Reading depth:** Selected full-text sections.

**Finding:** Structured belief updates, aggregation, and calibration improve results; removing belief state costs 5.1 Brier Index points in an ablation.

**Limitation:** Retrospective and mostly one base model; headline cohort differs from expanded ablation cohort; some modes use market priors.

**Vorhersage implication:** Represent current belief, evidence, and open questions explicitly.

## 23. Outcome-based Reinforcement Learning to Predict the Future

Benjamin Turtel; Danny Franklin; Kris Skotheim; Luke Hewitt; Philipp Schoenegger (2025). Transactions on Machine Learning Research, November 2025.
[Source](https://openreview.net/pdf?id=bbhdeL8EUX). Locator: Published abstract; arXiv 2505.17989.

**Topic:** Training. **Design:** Outcome-based RL with held-out evaluation.
**Reading depth:** Published abstract and introduction.

**Finding:** Forecast-specific RL makes a compact model competitive with larger baselines while improving calibration.

**Limitation:** Synthetic questions and historical outcomes require leakage and generalization audits; versions differ.

**Vorhersage implication:** Export proper-score training data only after evaluation integrity exists.

## 24. Future-as-Label: Scalable Supervision from Real-World Outcomes

Benjamin Turtel; Paul Wilczewski; Danny Franklin; Kris Skothiem (2026). arXiv v1.
[Source](https://arxiv.org/html/2601.06336v1). Locator: Abstract; method.

**Topic:** Training. **Design:** Retrospective outcome supervision.
**Reading depth:** Abstract and method overview.

**Finding:** Uses temporally masked inputs and realized outcomes for forecasting supervision.

**Limitation:** Masking supplied text cannot remove model memorization or resolution error; an OpenReview version has different model details.

**Vorhersage implication:** Keep predictor inputs and resolver evidence separate.

## 25. Reaching the frontier of AI forecasting with reinforcement learning

Scott Jeen; Matthew Aitchison; Maximilian Anthony Hugh Clark; Toby Shevlane; Ben Day (2026). ICML 2026 forecasting workshop.
[Source](https://www.mantic.com/publications/153005). Locator: https://openreview.net/pdf?id=lbpDR9pj5F; July 2026 author page.

**Topic:** Training. **Design:** Forecast-specific RL; held-out Metaculus questions.
**Reading depth:** Paper abstract/introduction and author publication page.

**Finding:** RL on roughly 10,000 questions improves gpt-oss-120b to frontier-comparable performance in the reported test.

**Limitation:** Workshop evidence; full temporal and model-selection audits remain necessary.

**Vorhersage implication:** Compare training against cheaper calibration and sampling baselines.

## 26. Diversity is the Strength of the AI Crowd

Matthew Aitchison; Scott Jeen; Toby Shevlane; Ben Day (2026). arXiv preprint; ICML forecasting workshop.
[Source](https://arxiv.org/abs/2606.29661). Locator: OpenReview JAYM7AGe50; §7.

**Topic:** Aggregation. **Design:** Fixed sample-budget study; 113 binary questions.
**Reading depth:** Abstract, introduction, and limitations.

**Finding:** Model diversity changes marginal ensemble value; individual rank does not determine contribution.

**Limitation:** One tournament, up to three runs per model, and sample counts do not equal monetary cost.

**Vorhersage implication:** Track residual dependence and validate ensemble selection out of sample.

## 27. Aligning LLMs with Human Uncertainty: A Beta-Bernoulli Calibrator for LLM Forecasting

Hui Dai; Ryan Teehan; Parsa Torabian; Mengye Ren (2026). arXiv preprint.
[Source](https://arxiv.org/html/2605.27668v1). Locator: Abstract; Appendix A.

**Topic:** Calibration. **Design:** Learned calibration using outcomes and human forecasts.
**Reading depth:** Abstract and limitations.

**Finding:** Learns a distribution over event likelihood from initial estimates and human/outcome supervision.

**Limitation:** Depends on the human training signal and domain mix; does not model evidence updates.

**Vorhersage implication:** Preserve provenance for learned calibration and second-order uncertainty.

## 28. What LLM Forecasters Know but Don't Say: Probing Internal Representations for Calibration and Faithfulness

Raphaël Sarfati; Pratyush Ranjan Tiwari; Siddharth Boppana; Christopher J. Earls; Srikar Varadaraj; Eric Ho (2026). arXiv preprint.
[Source](https://arxiv.org/abs/2607.08046v1). Locator: Abstract.

**Topic:** Calibration and rationale faithfulness. **Design:** Activation probes and evidence interventions.
**Reading depth:** Abstract.

**Finding:** Probes improve calibration in tested models; evidence interventions can change forecasts without corresponding rationale changes.

**Limitation:** Recent model-specific evidence; activation access is needed for the probing method.

**Vorhersage implication:** Use input interventions to audit reasoning claims.

## 29. LLM-based Agents for Forecasting and Prediction: Methods, Training, Evaluation, and Applications

Xiaogang Xu et al. (2026). arXiv survey preprint.
[Source](https://arxiv.org/pdf/2608.23058). Locator: §§5–7; references.

**Topic:** Survey. **Design:** Literature synthesis.
**Reading depth:** Abstract and selected survey/reference sections.

**Finding:** Maps standalone, tool-augmented, and hybrid forecasting and emphasizes evaluation limitations.

**Limitation:** Secondary synthesis; template journal metadata does not establish journal publication.

**Vorhersage implication:** Use as a discovery map and verify claims in original papers.

## 30. Chronos: Learning the Language of Time Series

Abdul Fatir Ansari et al. (2024). Transactions on Machine Learning Research, October 2024.
[Source](https://arxiv.org/abs/2403.07815). Locator: Abstract; published OpenReview gerNCVqqtR.

**Topic:** Adjacent time series. **Design:** Pretrained probabilistic numerical forecasting.
**Reading depth:** Abstract.

**Finding:** Trains transformer architectures on tokenized numerical series for transferable forecasting.

**Limitation:** A numerical foundation model is distinct from a general text-reasoning agent.

**Vorhersage implication:** Treat specialist models as forecast providers and comparators.

## 31. Are Language Models Actually Useful for Time Series Forecasting?

Mingtian Tan; Mike A. Merrill; Vinayak Gupta; Tim Althoff; Thomas Hartvigsen (2024). NeurIPS 2024.
[Source](https://arxiv.org/abs/2406.16964). Locator: Abstract.

**Topic:** Adjacent negative evidence. **Design:** Ablations of three LLM-based methods.
**Reading depth:** Abstract.

**Finding:** Removing or simplifying the LLM component often preserves or improves results in tested systems.

**Limitation:** Does not refute all contextual or hybrid forecasting.

**Vorhersage implication:** Require a component-removal baseline for expensive designs.

## 32. Probabilistic weather forecasting with machine learning

Ilan Price et al. (2024). Nature; GenCast.
[Source](https://doi.org/10.1038/s41586-024-08252-9). Locator: Published article; arXiv 2312.15796.

**Topic:** Adjacent weather. **Design:** Specialized probabilistic weather evaluation.
**Reading depth:** Abstract and publisher summary.

**Finding:** Shows strong probabilistic weather performance from a specialized learned model.

**Limitation:** Domain-specific data and targets do not establish general geopolitical skill.

**Vorhersage implication:** Route suitable questions to specialist distributions.

## 33. Chronos-2: From Univariate to Universal Forecasting

Abdul Fatir Ansari et al. (2025). arXiv preprint.
[Source](https://arxiv.org/abs/2510.15821). Locator: Abstract.

**Topic:** Adjacent time series. **Design:** Multivariate and covariate-informed forecasting.
**Reading depth:** Abstract.

**Finding:** Extends pretrained forecasting to related series and covariates.

**Limitation:** Selected adjacent coverage, not an exhaustive time-series comparison.

**Vorhersage implication:** Allow covariate-aware numerical adapters.

## 34. Context is Key: A Benchmark for Forecasting with Essential Textual Information

Andrew R. Williams et al. (2025). ICML 2025; first submitted 2024.
[Source](https://proceedings.mlr.press/v267/williams25a.html). Locator: Abstract; PMLR 267.

**Topic:** Adjacent contextual forecasting. **Design:** Numerical series with essential textual context.
**Reading depth:** Published abstract and introduction.

**Finding:** Constructs tasks requiring text and numbers together; its prompting baseline outperforms tested alternatives.

**Limitation:** Purpose-built contextual tasks differ from ordinary univariate series.

**Vorhersage implication:** Test whether text adds information beyond the numeric baseline.

## 35. Hindcast: Replaying Prediction Markets to Evaluate LLM Forecasters

Xiao Ye; Jacob Dineen; Evan Zhu; Shijie Lu; Kevin Song; Ben Zhou (2026). arXiv preprint.
[Source](https://arxiv.org/html/2607.14051v1). Locator: Abstract; §§3.3–4.1.

**Topic:** Frozen evidence benchmarks. **Design:** Historical Polymarket and frozen Reddit.
**Reading depth:** Selected full-text sections.

**Finding:** Tests retrieval with dated social evidence and contemporaneous market baselines; benefit depends on coverage.

**Limitation:** Selection judges evidence against the resolved side, creating an outcome-conditioned sampling concern; archive controls do not certify model training cutoffs.

**Vorhersage implication:** Record evidence coverage and archive selection effects.

## 36. Agentic Time Machine as an Infrastructure for Future-Event Forecasting

Jingyi Chai; Bingyang Zheng; Xiangrui Liu; Hao Lu; Zihang Zhou; Tianchen Wang; Kemeng Zhang; Siheng Chen (2026). arXiv preprint.
[Source](https://arxiv.org/abs/2606.21013v1). Locator: Abstract; offline/live correlation analysis.

**Topic:** Replay and agent systems. **Design:** Filtered historical web replay plus live comparison.
**Reading depth:** Selected full-text sections.

**Finding:** Combines a replay filter with planner/solver/aggregator forecasting and reports alignment with live rankings.

**Limitation:** The 11 correlation points include repeated runs and related ensembles; filtered replay needs independent temporal and selection audits.

**Vorhersage implication:** Compare replay rankings with prospective performance.

## 37. AI-Augmented Predictions: LLM Assistants Improve Human Forecasting Accuracy

Philipp Schoenegger; Peter S. Park; Ezra Karger; Sean Trott; Philip E. Tetlock (2025). ACM Transactions on Interactive Intelligent Systems 15(1), Article 4.
[Source](https://eprints.lse.ac.uk/127059/3/3707649.pdf). Locator: Abstract; §1; DOI 10.1145/3707649.

**Topic:** Human–AI collaboration. **Design:** Preregistered prospective experiment; 991 participants; six questions.
**Reading depth:** Published abstract and introduction.

**Finding:** Both frontier-model assistants improve human accuracy relative to a weaker-model control.

**Limitation:** Few questions, outlier sensitivity, and a control differing in both model capability and forecasting support.

**Vorhersage implication:** Compare assisted forecasts against both human-only and model-only baselines.

## 38. The Wisdom of Deliberating AI Crowds: Does Deliberation Improve LLM-Based Forecasting?

Paul Schneider; Amalie Schramm (2025). arXiv v1.
[Source](https://arxiv.org/abs/2512.22625v1). Locator: Abstract.

**Topic:** Deliberation. **Design:** Historical evaluation; 202 binary questions; four conditions.
**Reading depth:** Abstract.

**Finding:** Diverse models with shared information improve log loss after deliberation; homogeneous groups do not benefit.

**Limitation:** Conditional result across several scenarios; full statistical and temporal audit remains pending.

**Vorhersage implication:** Distinguish deliberation from averaging and preserve estimates before discussion.

## 39. The Strategic Foresight of LLMs: Evidence from a Fully Prospective Venture Tournament

Felipe A. Csaszar; Aticus Peterson; Daniel Wilde (2026). arXiv v1; SSRN working paper.
[Source](https://arxiv.org/abs/2602.01684v1). Locator: Abstract; SSRN 6166986.

**Topic:** Domain-specific human comparisons. **Design:** Prospective ranking; 30 ventures; 870 pairwise comparisons.
**Reading depth:** Abstract.

**Finding:** Several LLMs outperform the studied human evaluators; ensembles and human–AI teams do not beat the best model.

**Limitation:** Ranking differs from probability accuracy; comparisons share 30 ventures and one domain.

**Vorhersage implication:** Test collaboration against the strongest constituent and retain event-level sample counts.
