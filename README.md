# Capability Under Constraints

**How much useful AI capability can I extract from a machine I already own?**

This is a curated engineering notebook from a November 14-16, 2026 investigation:
Ryzen 7 9700X, 64 GB DDR5, GTX 1660 Super 6 GB, native Windows.
It preserves the measurements, failed hypotheses, and stopping decisions.
The commit history follows decision gates, not the literal development sequence;
[provenance](PROVENANCE.md) explains the reconstruction and timestamps.

[Stage-by-stage reproduction audit](notes/reproduction-audit.md) records actual
commands, experiment counts, parameter changes, and explicit replay boundaries.


## Movement one: what can this machine actually do?

### 1. Establish a baseline

Separate build-host checks from target-machine evidence. Pin the runtime, record
placement and timing controls, and measure sustained generation rather than
mistaking successful compilation or a short burst for useful inference.
[Baseline protocol](experiments/baseline/README.md).


### 2. The performance win emerged progressively

The useful configuration did not come from simply moving more of the model onto
the GPU. An all-CPU baseline was already competitive with the first controlled
CPU/GPU placement, at 23.73 versus 24.16 tok/s.

The retained measurements show the optimization developing in steps
(medians of three runs):

| Configuration | Sustained decode |
|---|---:|
| All CPU | 23.73 tok/s |
| Original controlled placement | 24.16 tok/s |
| Controlled placement, matched runtime settings | 27.37 tok/s |
| Expert weights of six layers on GPU (42 expert layers on CPU) | 31.32 tok/s |
| 1 GiB expert cache | 39.10 tok/s |
| 2 GiB expert cache | **43.95 tok/s** |

"Controlled placement" decided where expert weights lived explicitly, rather than
treating GPU offload as a single knob that moves a count of whole layers (the
ordinary 4/6/8/9-layer splits). That made locality something to vary deliberately:
first how many layers' experts stayed on the CPU, then how much VRAM served as an
expert cache. "Matched" runs used the same thread-affinity, microbatch, loading,
and Flash Attention settings as the matched CPU and ordinary-split cases.

The final configuration was not "pin the experts to the GPU." It used **2 GiB of
VRAM as an expert cache**, configured so that, once the cache was full, 95% of
cache misses were computed by the CPU from host-resident experts. The CPU
remained an important execution tier. Statically placing six
layers' experts on the GPU was measurably slower.

That distinction matters. The result is evidence that **expert reuse and locality
can make a small amount of VRAM disproportionately useful**. It is not evidence
that the model, or even its full expert set, fit on the GPU. Placement mattered
more than the next kernel specialization. For reference, the repeated Ollama run
measured **32.28 tok/s**.

The investigation also planned ordinary 4/6/8/9-layer GPU splits, but the raw
measured rows for those earliest runs were not retained. I therefore don't
reconstruct performance numbers for them here.

**Decision: ADOPT the 2 GiB expert-cache configuration.**
[Original measurement rows and controls](experiments/expert-locality/README.md).


### 3. Stop kernel tuning

Three interleaved repetitions gave mean sustained decode of **44.17 / 44.11 /
44.32 tok/s** for stock SM75, forced MMQ, and Pascal PTX plus forced MMQ.
That was not a useful improvement. **STOP; retain stock SM75.**
[Null result](experiments/kernel-stop/README.md).


### 4. Fast tokens did not deliver the requested Tamil package

At roughly **49 tok/s**, Qwen still duplicated alternatives, omitted source
material, and weakly differentiated rewrites. That figure is the same selected
expert-cache runtime on a different workload (about 660-token conversation
prompts, 4K context, natural stopping up to 3,036 tokens), not a further
optimization; it is not directly comparable with the 43.95-tok/s locality
benchmark (84-token prompt, 1,024 fixed tokens, 2,048 context). Sampling improved
coverage without reliably producing three complete, distinct alternatives.
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


### 8. The agent had its own context budget

Once context became scarce, I started measuring what was actually consuming it.

In one controlled CLI experiment, the work request itself was only **48 tokens**.
The server reported a **4,557-token prompt**, exactly matching an independent
rendering and tokenization of the request.

| Prompt component | Tokens |
|---|---:|
| Controlled work request | 48 |
| Everything else in the rendered request | 4,509 |
| **Total prompt** | **4,557** |

The system message alone accounted for **2,925 tokens**. The remaining non-work
content included tool descriptions, framing, and ancillary messages.

The important result is not that an agent has a universal **4,509-token overhead**.
This was one measured configuration. A very small piece of actual work arrived
at the model surrounded by substantially more orchestration machinery.

That changed the question. Context was not merely capacity available to the
user's task. **The agent itself was competing for it.**

The later minimal harness was deliberately designed to make that cost visible
and controllable. In a separate historical measurement, its empty-history rendered
request with five tools used **958 tokens**. The two measurements are not a
controlled benchmark comparison, and neither describes current prompt costs.
They reinforce the reason for building the smaller instrument: once context
became a constrained resource, the machinery around the model could no longer
be treated as free.

**Decision: CONTINUE WITH AN OBSERVABLE HARNESS.**

The goal was not simply to minimize prompt size. It was to understand what each
instruction, tool, observation, and piece of workflow state was buying.

The small [standard-library harness](harness/README.md) exposes the model/tool
loop, context accounting, timing, streamed output, and explicit completion.
Its purpose is to make experiments inspectable, not to claim general autonomy.
[Measurement and decomposition](experiments/agent-completion/README.md#measured-system-and-tool-scaffolding).


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
[Curation audit](notes/curation-audit.md) records validation and publication boundaries.

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
