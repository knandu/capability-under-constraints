# Tamil usefulness after throughput became adequate

**Decision: STOP further runtime tuning of the original checkpoint for this task.**
November 15, 2026, 13:34:02 -06:00 (`ac1ac9d`, `170988b`).

Three unchanged prompts requested three complete, meaning-preserving, distinct
Tamil rewrites. Arm A was greedy native Qwen; B sampled native Qwen; C was the
Ollama reference. Thinking was off. The native arms used 4K context, a 3,036-token
ceiling, natural stopping, and the same selected expert-cache runtime.
`controls.json` retains sampling parameters and original prompt/model digests.

`preliminary-controls.json` and `preliminary-results.csv` preserve the preceding
three-request characterization separately from the nine-response A/B/C study.
`commands.json` retains actual preliminary and A/B native argument vectors;
`ollama-requests.json` retains the C request fields with only prompt bodies
excluded. [Stage audit and replay boundaries](../../notes/reproduction-audit.md).

`results.csv` and `summary.csv` retain token counts and timing. `quality.csv`
retains case-level judgments rather than a fabricated single language score.
`structural-audit.csv` is a narrow background-marker check, not a fluency judge.
`excerpts.json` contains short, explicitly truncated original generated-output
prefixes with original file digests; full source passages are not redistributed.

Native output was roughly 49 tok/s. Sampling improved reviewed full-source
coverage from 3/9 to 6/9 alternatives, but not dependable end-to-end delivery.
Complete alternatives could still be duplicates; readable individual sentences
did not establish a complete, distinct three-rewrite package.

These are small, task-specific investigator/model-assisted observations, not
independent native-speaker certification or a universal Tamil/model ranking.
Preserve omissions, duplication, weak differentiation, and the natural-stop
failure boundary; do not count every missing fact as a context-window failure.
