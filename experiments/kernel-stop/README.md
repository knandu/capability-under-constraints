# Closing the kernel branch

**Decision: STOP kernel tuning; retain stock SM75.**
November 15, 2026, 12:26:46 -06:00 (`ac39a5b`), after the 12:06-12:12 run.

| Variant | Three-run mean decode tok/s |
|---|---:|
| Stock SM75 | 44.17 |
| SM75, forced MMQ | 44.11 |
| Pascal PTX, forced MMQ | 44.32 |

`runs.csv` retains all nine interleaved measurements and verified effective
controls. `summary.csv` retains the original aggregate calculation, including
contemporary and historical comparisons. Identical output hashes and matching
cache counters constrain interpretation; all nine effective-control checks passed.
`builds/` retains the three original build configurations, compiler/runtime
settings, build timestamps, and CMake arguments. Only source, build, and toolkit
directory arguments are replaced by explicit placeholders; variant flags remain
unchanged. These records were added at the final curation audit, not a new run.

The relevant comparison is sustained decode with the already-selected expert
cache, not an isolated microkernel or prefill speedup. The small differences did
not justify another tuning branch. This is a useful null result, not a hidden
successful optimization.

Runtime architecture reports distinguish a compiled architecture from execution
proof. Lifetime cache counters include warmup/prefill; they are not decode-only
locality measurements. VRAM numbers are sampled device totals.
