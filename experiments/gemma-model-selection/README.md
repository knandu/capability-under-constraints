# Gemma 3 12B: mixed candidates, rejected package

**Decision: REJECT Gemma 3 12B for this end-to-end Tamil workload.**
November 15, 2026, 14:52:19 -06:00 (`6aabf7f`).

| Model / tested policy | Mean response wall time |
|---|---:|
| Gemma 3 12B IT | 134.57 s |
| Sampled Qwen3-30B-A3B | 46.48 s |

`performance.csv` retains each measured response; `performance-summary.csv`
retains the original aggregates. The Qwen reference reuses the already-measured
sampled arm, not a new fully concurrent benchmark. Tokenizers and output lengths
differ: wall time is not a claim of equal-token decode efficiency.

`quality.csv` preserves the mixed outcome. Some Gemma alternatives had stronger
narrative differentiation or individually useful phrasing. Other responses used
English rather than Tamil, omitted facts, or padded the answer. Useful fragments
did not outweigh total latency and unreliable delivery of the requested package.
`excerpts.json` retains a short generated-output prefix, not an exemplar to adopt.

`qualification.csv` retains placement qualification. The 24-layer fallback
breached the free-VRAM guard; that was **not an OOM**. A 16-layer placement was
selected. Long placement logs and copied model templates are intentionally absent.

This closes one model-selection branch for a particular workload and machine.
It does not establish that Gemma is generally worse, nor that more kernel work
would repair the observed quality failures.
