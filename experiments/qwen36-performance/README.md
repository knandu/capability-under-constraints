# Qwen3.6: adopt for performance, leave quality unqualified

**Decision: ADOPT FOR PERFORMANCE; QUALITY UNQUALIFIED.**
November 16, 2026, 23:16:47 -06:00 (`0e3e590`, `40bb069`).

Compare Qwen3-30B-A3B Q4_K_M with Qwen3.6-35B-A3B UD-Q4_K_M on the same
machine/runtime, 20,480 context, Q8 K/V attention cache, 2,048 MiB expert cache,
95% CPU handling of expert-cache misses, eight threads, batch 512/microbatch 128,
thinking off. The candidate was text-only; no projector was loaded.

AIPerf 0.13.0 ran concurrency one, one warmup plus three measured requests per
length, seeded synthetic input, 256 output tokens, EOS ignored, temperature zero,
seed 1234, and prompt caching disabled. Equal requested token lengths use each
model's tokenizer; the texts and actual token counts are **not identical**.

| Requested input | Qwen3 decode | Qwen3.6 decode | Qwen3 TTFT | Qwen3.6 TTFT |
|---|---:|---:|---:|---:|
| 512 | 43.2881 tok/s | 43.1520 tok/s | 3.2435 s | 2.5463 s |
| 4,096 | 36.2380 | 42.1802 | 29.9201 | 20.5171 |
| 16,384 | 22.5836 | 36.5018 | 193.9547 | 98.6084 |

`profiles/*/profile_export_aiperf.json` preserves original aggregate metric
objects, completion/error/cache checks, actual input lengths, and version.
Operational client configuration, run identity, and telemetry metadata are
omitted. `performance-comparison.json` preserves the original derived table with
only candidate operational metadata removed.
`commands.json` restores all six actual AIPerf argument vectors and the saved
candidate server launch; only filesystem paths become placeholders.
`client-environment.json` retains selected original public package versions.
The [stage audit](../../notes/reproduction-audit.md) explicitly identifies the
unrecovered literal 20K-Q8 baseline launch vector and unpinned tokenizer revisions;
it does not relabel an older 4K launch as the matched benchmark runtime.
`candidate-ready.json` retains allocation lines and frozen runtime controls.
`model-provenance.json` pins the exact public model file, revision, size, and hash.

All eighteen measured requests succeeded with exactly 256 output tokens and no
reported prompt-cache reuse. Actual input length ranges were 524-525,
4,108-4,109, and 16,396-16,397 across the two tokenizers. These short generation
profiles are not interchangeable with earlier 1,024-token locality/kernel runs.

Q8 attention KV occupied 212.50 MiB; separate recurrent state was 62.81 MiB FP32.
The retained device-memory reading is a point-in-time device-total snapshot, not
peak telemetry or process-specific accounting. Do not describe all model state
as INT8 or infer a safe VRAM margin from one reading.

`adoption.json` preserves the final 20,480/16,000/4,000 startup budget and actual
switch timestamp, without machine service identifiers. The harness startup
options make that selected budget explicit; imported session settings remain
their own settings. The 480-token arithmetic remainder is not a separately
validated universal safety margin.

The older model/service was preserved in the original environment. A synthetic
view/completion smoke check established only bounded integration, not broad agent
reliability. Tamil, coding quality, broad autonomy, and semantic document fidelity
were **not** subsequently qualified for Qwen3.6.

Recheck aggregates offline with `python -B tools\validate_evidence.py` from the
repository root. This does not start AIPerf or send inference requests.
