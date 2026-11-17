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


## Deliberate workload pivot

The Tamil workflow was largely single-shot. I deliberately changed the question
to multi-step tool and document work; this was not a natural evolution of the
same workload. Instructions, schemas, observations, history, and intermediate
work now competed with the user's material for the same context.
An affordance can cost both **tokens** and **another decision/action choice**.

## Movement two: what happens when this becomes an agent?

### 7. A successful tool call was not reliable completion

Adding the missing `task_complete` capability let a bounded read/edit task finish.
An identity question could still repeat until the continuation cap unless
explicitly directed to complete. Instruction-policy variants caused regressions,
including an undone edit. **STOP policy tweaking; preserve the boundary.**
[Focused protocol records](experiments/agent-completion/README.md).


### 8. Build an observable instrument, not an agent framework

The small [standard-library harness](harness/README.md) exposes the model/tool
loop, context accounting, timing, streamed output, and explicit completion.
Its purpose is to make experiments inspectable, not to claim general autonomy.


### 9. Durable document state belongs outside disposable chat context

The [document workflow](document-workflow/README.md) owns byte-cursor traversal,
bounded chunks, notes, merge/final stages, checkpoints, and pause/resume.
Incomplete output is detected; bounded recovery can change the next attempt
without committing a truncated note as success. Source notes survive a failed
merge. **Byte coverage is not semantic fidelity.**


### 10. A newer model shifted the performance boundary again

Matched Q4/Q8-attention-KV qualification, concurrency one, 256 output tokens:

| Requested input | Qwen3 decode tok/s | Qwen3.6 decode tok/s | TTFT old -> new |
|---|---:|---:|---:|
| 512 | 43.29 | 43.15 | 3.24 -> 2.55 s |
| 4,096 | 36.24 | 42.18 | 29.92 -> 20.52 s |
| 16,384 | 22.58 | 36.50 | 193.95 -> 98.61 s |

The final selected harness budget was **20,480 context / 16,000 input / 4,000
output**, with Q8 K/V attention cache. Separate recurrent state remained FP32;
this is not an all-INT8-state configuration.
**ADOPT Qwen3.6 for performance; quality unqualified.**
[Original AIPerf aggregate records, method, and model pin](experiments/qwen36-performance/README.md).

## Reading and reproducing the record

Start with the [decision/evidence map](notes/investigation-map.md), then the
experiment directories. [Limitations](notes/limitations.md) distinguish measured
results from untested questions. [Implementation notes](notes/implementation-notes.md)
compress repaired plumbing without treating it as experimental success.

From the repository root, offline checks need Python 3.11+:

```powershell
python -B tools\validate_evidence.py
python -B -m unittest discover -s harness\tests -p test_harness.py
```

These inspect records and exercise synthetic regression fixtures; they do not
run a new model benchmark. The harness requires an already-running compatible
local model endpoint. No weights, runtime binaries, private captures, or deployment
environment are distributed. See [third-party boundaries](THIRD_PARTY.md).

This is an engineering notebook, **not** a llama.cpp fork, production deployment
recommendation, comprehensive model ranking, optimal-configuration tutorial, or
general agent framework. Faster decode did not establish usefulness; checkpointed
work did not establish understanding; the last performance adoption did not
resolve the earlier quality failures.
