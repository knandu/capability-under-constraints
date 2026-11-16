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


### 3. Stop kernel tuning

Three interleaved repetitions gave mean sustained decode of **44.17 / 44.11 /
44.32 tok/s** for stock SM75, forced MMQ, and Pascal PTX plus forced MMQ.
That was not a useful improvement. **STOP; retain stock SM75.**
[Null result](experiments/kernel-stop/README.md).


### 4. Fast tokens did not deliver the requested Tamil package

At roughly **49 tok/s**, Qwen still duplicated alternatives, omitted source
material, and weakly differentiated rewrites. Sampling improved coverage without
reliably producing three complete, distinct alternatives.
**STOP further runtime tuning of the original checkpoint for this workload.**
[Quality observations and selected output excerpts](experiments/tamil-quality/README.md).

This reused a practical writing workload from
[tamil-transliterator](https://github.com/knandu/tamil-transliterator), not a newly
invented benchmark. The earlier article,
[I Thought I Had a Model Problem. It Turned Out to Be a Latency Problem](https://www.linkedin.com/pulse/i-thought-had-model-problem-turned-out-latency-nandu-kirubanandan-2esbc/),
provides the preceding transliteration/writing context.


### 5. Gemma was a mixed result, not the answer

Gemma 3 12B supplied some promising individual candidates, but wrong-language
output, omissions, padding, and latency prevented a dependable end-to-end win.
Mean response wall time was **134.57 s**, versus **46.48 s** for sampled Qwen.
**REJECT for this workload**, not as a universal model judgment.
[Model-selection branch](experiments/gemma-model-selection/README.md).


### 6. Capacity and responsiveness were different constraints

32K CPU-KV **worked**: a 28,553-token prompt, successful early-marker recall,
**525.79 s** total, and **3.64 tok/s** decode. It was working but rejected as the
interactive default. Near-full 8K GPU-KV gave **38.93 tok/s**. That initially
failed the 44-tok/s acceptance target; the lower speed was then explicitly
accepted in return for useful context. **ADOPT the smaller GPU-resident context.**
[Both decisions and original rows](experiments/context-economics/README.md).

