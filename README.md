# Capability Under Constraints

**How much useful AI capability can I extract from a machine I already own?**

This is a curated engineering notebook from a November 14-16, 2026 investigation:
Ryzen 7 9700X, 64 GB DDR5, GTX 1660 Super 6 GB, native Windows.
It preserves the measurements, failed hypotheses, and stopping decisions.
The commit history follows decision gates, not the literal development sequence;
[provenance](PROVENANCE.md) explains the reconstruction and timestamps.


## Movement one: what can this machine actually do?

### 1. Establish a baseline

Separate build-host checks from target-machine evidence. Pin the runtime, record
placement and timing controls, and measure sustained generation rather than
mistaking successful compilation or a short burst for useful inference.
[Baseline protocol](experiments/baseline/README.md).


### 2. Expert locality was the useful performance lever

The original controlled configuration decoded at **24.16 tok/s**. A 2 GiB expert
cache reached **43.95 tok/s**, versus **32.28 tok/s** for the repeated Ollama
reference. Placement mattered more than the next kernel specialization.
[Original measurement rows and controls](experiments/expert-locality/README.md).

