# Model pilot 01 results

Completed September 9, 2026: 80 model interviews, no remote execution exceptions. Server charge: $1.1346; sum of per-response costs: $1.134804. Costs include malformed answers. No model completions were rerun.

The clearest usable comparison is Gemini 3.1 Pro's complete 20-question pair. Its structured prompt scored better, but 37 of its 40 responses reported recognizing the outcome. These results exercise the forecasting pipeline and do not establish live forecasting skill.

## Registered strict analysis

| Model | Valid plain | Valid structured | Paired n | Plain Brier | Structured Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| gemini-2.5-flash | 5/20 | 19/20 | 5 | 0.1631 | 0.1107 |
| gemini-3.1-pro-preview | 20/20 | 20/20 | 20 | 0.1718 | 0.1281 |

Lower Brier is better. Each row uses its own common questions; compare conditions within a row. The six-way common cohort (four model/prompt arms plus two baselines) has only four cases under strict parsing; its full scores are retained in [evaluation.json](evaluation.json).

## Formatting diagnostic

The registered parser accepted 64/80 outputs. A separate, post-hoc rule accepting exactly one fenced JSON block recovered five additional Flash plain responses. It did not repair broken JSON, infer probabilities from prose, or generate replacement answers. The diagnostic accepts 69/80 and has eight six-way matched cases. See [posthoc_evaluation.json](posthoc_evaluation.json) and the original [results.ep](results.ep).

## Outcome recognition and costs

| Arm | Recognized / parsed (diagnostic) | Cost, all 20 calls |
| --- | ---: | ---: |
| gemini-2.5-flash:plain | 9/10 | $0.1357 |
| gemini-3.1-pro-preview:plain | 18/20 | $0.2622 |
| gemini-2.5-flash:structured | 18/19 | $0.1952 |
| gemini-3.1-pro-preview:structured | 19/20 | $0.5417 |

Recognition is a model self-report. Unparsed responses have unknown recognition status. Both conditions used the same output cap, but the structured prompts used more input and output tokens. One Flash plain response ended with MAX_TOKENS; the other 79 responses reported STOP.

## Sensitivity and review

Excluding the five cases without separate criteria, while retaining the original strict parsing:

- gemini-2.5-flash: n=3, plain 0.1722, structured 0.0644.
- gemini-3.1-pro-preview: n=15, plain 0.1595, structured 0.0994.

Review diagnostics use assessment and review probabilities from the same structured completion:

- gemini-2.5-flash: 1/19 probabilities changed; mean Brier change -0.0017.
- gemini-3.1-pro-preview: 1/20 probabilities changed; mean Brier change -0.0001.

This cannot isolate a causal effect of review. The [machine-readable summary](summary.json) preserves cohort membership, failures, costs, model versions, and input hashes.

Next experiment: audit original wording and criteria; assemble dated evidence; use cases and model versions with a defensible training-cutoff relationship or collect prospective predictions. Fix the response format contract before scaling. Keep this pilot unchanged as a recorded development experiment.
