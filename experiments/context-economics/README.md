# Working capacity versus a useful interactive default

**Decisions: WORKING BUT REJECTED (32K CPU-KV); ADOPT (8K GPU-KV).**
November 15, 2026, 18:32:17 -06:00 (`b2bc3c0`, `fd94b24`).

The canonical `cpu-kv.csv` records a 28,553-token prompt at 32K context,
525.79 seconds including generation, and 3.64 tok/s decode. `recall.json`
records successful early-marker retrieval. No long-context truncation was found.
32K therefore **worked**; its latency made it unsuitable as the interactive
default. One marker retrieval is not evidence of comprehensive long-document
understanding.

`cpu-summary.json` preserves the matched short-request comparison and the
termination-metadata correction: use canonical stop-type-derived EOS/token-cap
fields, not the initially queried absent legacy booleans.

`gpu-kv.csv` records the smaller-context comparison. Near-full 8K GPU-KV decoded
at 38.934 tok/s. `initial-acceptance.json` preserves failure of the original
44-tok/s requirement. `adoption.json` preserves the subsequent explicit acceptance,
including its original timestamp, while omitting machine-specific service details.
It would be misleading to present the first check as a pass.

The historical 8K choice used a 2,048 MiB expert cache and 768 MiB GPU KV.
It was a useful operating tradeoff, not a hardware limit or permanent universal
default. The later Qwen3.6 gate makes a separate 20K choice under a different
architecture/cache configuration.

`commands.json` retains the four actual server argument vectors; `protocol.json`
retains request controls, warmup/output budgets and the synthetic long-input
recipe. The 32K test omitted `ignore_eos`; the later 8K test explicitly enabled
it. Both comparisons ran once in fixed order, not as repeated statistical trials.
[Cross-stage audit and guard-threshold differences](../../notes/reproduction-audit.md).
