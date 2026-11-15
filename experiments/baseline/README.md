# Baseline: a trustworthy comparison starts before the first score

**Decision: CONTINUE with a pinned native-runtime experiment.**
Protocol checkpoint: November 14, 2026, 18:28:38 -06:00 (`43e1cee`).

The target was a Ryzen 7 9700X, 64 GB DDR5, GTX 1660 Super 6 GB on Windows.
The build host was not proof of target GPU execution. CPU capability inspection,
successful compilation, and successful target inference were distinct checks.
`upstream.lock` pins the unchanged llama.cpp source; this was not a kernel fork.

The experiment separates CPU-only, ordinary CPU/GPU splitting, and controlled
expert placement. Record context, generated-token count, batch/microbatch,
threads/affinity, loading, Flash Attention, placement, and cache policy alongside
timings. Use warmup and sustained generation; do not compare a short decode burst
with a long one as though they were equivalent.

This initial protocol is not retrospective proof that every build already worked.
PowerShell defaults, shared-CRT boundaries, and host-buffer validation needed
repair before trustworthy target results. Those repairs are compressed into the
next gate and [implementation notes](../../notes/implementation-notes.md).
The [locality record](../expert-locality/README.md) holds the target measurements.

## Reproducibility boundary

Build the pinned upstream with the recorded public toolchain and variant settings
in the later control records; supply your own compatible Windows/CUDA environment
and model file. Neither binaries nor downloaded dependencies are archived here.
This notebook preserves enough configuration to interpret and repeat the original
comparison, not a universal installer or a promise of identical timings.
