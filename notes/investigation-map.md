# Investigation and evidence map

Author timestamps identify original checkpoints; committer timestamps identify curation.
A shared author timestamp for locality/kernel gates reflects their bundled source commit.
Artifact digests and explicit normalization are in [evidence-map.json](evidence-map.json).

| Gate | Decision | Original checkpoint | Source commits | Evidence |
|---|---|---|---|---|
| 1. Establish reproducible constrained-inference baseline | CONTINUE | 2026-11-14T18:28:38-06:00 | `43e1cee` | [baseline](../experiments/baseline/README.md) |
| 2. Adopt expert caching after the locality experiment | ADOPT | 2026-11-15T12:26:46-06:00 | `f5bd15b`, `1d92b68`, `c16e3e3`, `2075bb5`, `ac39a5b` | [expert-locality](../experiments/expert-locality/README.md) |
| 3. Stop kernel tuning after equivalent sustained decode | STOP | 2026-11-15T12:26:46-06:00 | `ac39a5b` | [kernel-stop](../experiments/kernel-stop/README.md) |

## Reading the arc

Movement one tests inference, locality, kernel limits, Tamil usefulness, model selection,
and context economics. The agent-completion gate deliberately pivots workloads.
Movement two tests completion and observability, externalizes document state, and ends
with performance-only adoption of Qwen3.6. No gate retroactively qualifies its quality.

Setup repairs and peripheral customization mechanics are compressed or excluded;
negative results and working-but-rejected choices remain first-class evidence.
