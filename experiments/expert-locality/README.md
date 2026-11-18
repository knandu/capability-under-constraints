# Expert locality, not another kernel, changed the baseline

**Decision: ADOPT a 2,048 MiB expert cache, with 95% of cache misses on CPU.**
Source decision checkpoint: November 15, 2026, 12:26:46 -06:00 (`ac39a5b`).

| Record | Sustained decode |
|---|---:|
| Original controlled configuration, median of three | 24.16 tok/s |
| Finalist 2 GiB cache, microbatch 128, median of three | 43.95 tok/s |
| Repeated Ollama reference, median of three | 32.28 tok/s |

`exploration.csv` retains the initial matrix, including the original control.
`finalists.csv` retains all twelve finalist runs, including smaller-cache and
expert-count alternatives, not only the winner. `ollama.csv` retains all three
reference measurements. Only the machine-local evidence-path column is removed.
`summary.json` is derived from these rows.

The selected runtime used eight threads, batch 512, microbatch 128, 2,048 context,
Flash Attention auto, loading mode none, no strict CPU affinity, and
`--no-op-offload`. `controls.json` retains the original frozen plan's public
parameters and selected matrix. The model was Qwen3-30B-A3B Q4_K_M.

[Reproduce the selected command and map every wrapper parameter](REPRODUCE.md).
`commands.json` retains all ten measured native profiles, and
`ollama-requests.json` retains the reference API controls. The 24.16 -> 43.95
comparison includes other profile changes, not only the cache switch.

The mechanism is reuse/locality under a small VRAM budget, not evidence that the
whole model fits on the GPU. Sampled device VRAM is not process-specific peak
telemetry. Ollama used its native API/default placement and lacked equivalent
strict-affinity/ignore-EOS controls; preserve it as a reference, not a fully
identical backend experiment.

Repaired defaults, CRT linking, and host-memory classification established
measurement integrity. They are not separate performance wins.
