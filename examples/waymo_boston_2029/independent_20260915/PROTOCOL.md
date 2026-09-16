# Independent-context Waymo forecast

The user requested a new-context recalculation using the timeline model. A new
worker was launched with `fork_turns: "none"`. Its task was one independent
forecast, while the coordinator prepared artifact and arithmetic validation.

## Information supplied

- The exact question and resolution contract, copied as `question.json`.
- Generic package source, snapshotted in a clean temporary workspace.
- Instructions to build an unresolved structure before research, research its
  parameters, declare joint scenario weights, and issue a timeline forecast.
- Instructions to preserve evidence, source failures, assumptions, uncertainty,
  workflow history, and a reproducible build.

No earlier conversation, probability, source list, research finding, example
timeline, or preferred dependency was supplied. The coordinator did not provide
probability or substantive research guidance before the result was sealed. The
worker was instructed not to inspect the parent repository or deliberately seek
another forecast or market price, and to report any incidental numerical exposure.

The worker must seal its substantive files with SHA-256 hashes before reporting
the number to the coordinator. Subsequent validation checks arithmetic and
provenance and preserves the sealed result rather than silently replacing it.

## Limits

This is separation of supplied context, not removal of training knowledge. The
worker retains the system/developer instructions and available tools. Its clean
directory is not a separately enforced filesystem sandbox. Access exclusions
are instructions; input hashes establish what was supplied, not a proof about
every possible influence on an estimate. The coordinator has seen previous work.
Independent fresh retrievals also mean this is not a frozen-evidence method trial.

The platform's [subagent documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents)
was consulted using the [OpenAI Docs skill](/Users/johnhorton/.codex/skills/.system/openai-docs/SKILL.md).
The actual launch settings and file inventory are recorded in `launch.json` and
`input_manifest.json`.
