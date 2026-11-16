# Investigation and evidence map

Author timestamps identify original checkpoints; committer timestamps identify curation.
A shared author timestamp for locality/kernel gates reflects their bundled source commit.
Artifact digests and explicit normalization are in [evidence-map.json](evidence-map.json).

| Gate | Decision | Original checkpoint | Source commits | Evidence |
|---|---|---|---|---|
| 1. Establish reproducible constrained-inference baseline | CONTINUE | 2026-11-14T18:28:38-06:00 | `43e1cee` | [baseline](../experiments/baseline/README.md) |
| 2. Adopt expert caching after the locality experiment | ADOPT | 2026-11-15T12:26:46-06:00 | `f5bd15b`, `1d92b68`, `c16e3e3`, `2075bb5`, `ac39a5b` | [expert-locality](../experiments/expert-locality/README.md) |
| 3. Stop kernel tuning after equivalent sustained decode | STOP | 2026-11-15T12:26:46-06:00 | `ac39a5b` | [kernel-stop](../experiments/kernel-stop/README.md) |
| 4. Close throughput tuning after Tamil quality evaluation | STOP | 2026-11-15T13:34:02-06:00 | `ac1ac9d`, `170988b` | [tamil-quality](../experiments/tamil-quality/README.md) |
| 5. Reject Gemma 3 12B for the end-to-end Tamil workload | REJECT | 2026-11-15T14:52:19-06:00 | `6aabf7f` | [gemma-model-selection](../experiments/gemma-model-selection/README.md) |
| 6. Adopt smaller GPU context after measuring the 32K tradeoff | WORKING BUT REJECTED (32K); ADOPT (8K) | 2026-11-15T18:32:17-06:00 | `b2bc3c0`, `fd94b24` | [context-economics](../experiments/context-economics/README.md) |
| 7. Establish agent-completion boundary and mark the workload pivot | CONTINUE bounded tools; STOP policy tuning | 2026-11-15T19:05:35-06:00 | `fd94b24`, `de521e0` | [agent-completion](../experiments/agent-completion/README.md) |
| 8. Introduce the minimal observable agent instrument | CONTINUE | 2026-11-16T00:29:57-06:00 | `35702cf`, `a78bd78`, `0b8cbcd`, `b5ca678`, `01b8a84`, `138fb1e` | [observable-harness](../harness/README.md) |
| 9. Externalize document-workflow state and bounded recovery | ADOPT | 2026-11-16T17:49:14-06:00 | `9de324f`, `58229fd`, `0024349`, `6f0b345`, `e602ddb` | [document-state](../document-workflow/README.md) |

## Reading the arc

Movement one tests inference, locality, kernel limits, Tamil usefulness, model selection,
and context economics. The agent-completion gate deliberately pivots workloads.
Movement two tests completion and observability, externalizes document state, and ends
with performance-only adoption of Qwen3.6. No gate retroactively qualifies its quality.

Setup repairs and peripheral customization mechanics are compressed or excluded;
negative results and working-but-rejected choices remain first-class evidence.
