# Stage-by-stage reproduction audit

November 18, 2026 editorial recovery, after the ten historical decisions.
This adds configuration evidence to the published notebook; it does not rewrite
the decision gates or report new experiments.

Command lines and experiment controls were mistakenly pruned during
publication-readiness preparation, so the distillation retained outcomes better
than executable controls. That was a real gap: wrapper parameter names did not
tell a reader what llama.cpp actually received. The recovered `commands.json`
files now retain argument order and non-path values from saved commands. Named
placeholders replace model/input/template paths; build labels identify the
corresponding executable. These are command records, not claims that excluded
inputs have become available.

For the central native performance result, start with the
[complete flag mapping, build command and selected invocation](../experiments/expert-locality/REPRODUCE.md).
The expert cache was stock functionality at the exact pinned revision:
`--moe-cache-mib 2048 --moe-cache-cpu-share 0.95`, not a private llama.cpp patch.

## What is captured at each gate

| Gate | Exact study identity and controls | Where to inspect / replay boundary |
|---|---|---|
| 1. Baseline protocol | Pinned upstream, target hardware, CPU / automatic split / controlled experts, repaired build/runtime boundaries. This gate establishes the protocol, not an already-successful target benchmark. | [Baseline](../experiments/baseline/README.md), [CPU configure/build recipe](../experiments/baseline/cpu-build-recipe.json), and [three captured CUDA build records](../experiments/kernel-stop/builds/stock-sm75.json). The CPU recipe is recovered from frozen build source, not a newly found build log. Earliest baseline raw directory remains unavailable. |
| 2. Expert locality | Six native exploration profiles x three repeats = 18; four native finalists x three = 12; three Ollama references. Native runs used 84 prompt tokens, 1,024 sampled output tokens, 1,023 decode runs, context 2,048, eight threads, batch 512. | [All ten native measured profiles plus placement check](../experiments/expert-locality/commands.json), [matrix/default mapping](../experiments/expert-locality/REPRODUCE.md), [Ollama API controls](../experiments/expert-locality/ollama-requests.json), and [exact synthetic input](../experiments/expert-locality/benchmark-input.json). Original repeat command files were compared, not inferred from the winning row. |
| 3. Kernel stopping point | Stock SM75, SM75 forced MMQ, Pascal PTX forced MMQ; that order within each of three repeats = nine runs. Same 2K/1,024-output cached profile. | [Shared saved commands](../experiments/kernel-stop/commands.json), three build JSONs, and [all nine rows](../experiments/kernel-stop/runs.csv). Native warmup/cache initialization contributes to lifetime counters; 0.95 is policy, not an exact observed lifetime CPU fraction. |
| 4. Tamil quality boundary | Preliminary three instruction variants, then three prompts x A/B/C = nine main responses. Native context 4,096, cap 3,036, natural EOS, thinking off. A: greedy; B: sampled; C: Ollama installed defaults, not B's sampling settings. | [Preliminary plan](../experiments/tamil-quality/preliminary-controls.json) and [three original rows](../experiments/tamil-quality/preliminary-results.csv); [native argument vectors](../experiments/tamil-quality/commands.json), [main controls](../experiments/tamil-quality/controls.json), [actual C requests](../experiments/tamil-quality/ollama-requests.json). Original source passages and external Qwen3 template are excluded, so full language-quality replay is not self-contained. |
| 5. Gemma branch | CPU and GPU16 qualification: 128-token fixed generation each. GPU24 failed during placement under the free-VRAM guard; no timed GPU24 result. Three GPU16 quality requests reuse Tamil prompts 1-3, cap 3,036, natural EOS. | [Actual CPU/GPU24/GPU16 and quality commands](../experiments/gemma-model-selection/commands.json), [qualification](../experiments/gemma-model-selection/qualification.csv), and [six comparison rows](../experiments/gemma-model-selection/performance.csv). Three of those six are reused Qwen B responses, not three additional Qwen measurements. Gemma's original template came from its GGUF; it is not vendored here. |
| 6. Context economics | Two separate fixed-order, single-repetition comparisons: fresh GPU4K vs CPU32K, then fresh GPU4K vs GPU8K. Each has two warmups plus two short measurements and one long measurement = five rows, not five replicates. | [All four saved server commands](../experiments/context-economics/commands.json), [exact request settings, plans and long-input construction](../experiments/context-economics/protocol.json), and both five-row CSVs. The short input/external template is excluded. Synthetic long-input recipe is retained. |
| 7. CLI completion boundary | Three read/edit context controls, four completion cases, then rejected policy variants. Fixed completion tests used provider 7,168 input / 1,024 output, autopilot continuation cap 1, and a 201-line exact-edit fixture. | [Controlled prompts, fixture recipe and cap](../experiments/agent-completion/experiment-controls.json), [four case outcomes](../experiments/agent-completion/completion.json), [context controls](../experiments/agent-completion/tool-context.json), [policy regressions](../experiments/agent-completion/policy-regressions.json). Private CLI system/plugin/policy context is not redistributed; the retained proof does not establish a CLI version for an exact independent replay. |
| 8. Observable harness | A retained executable source snapshot, bounded five-tool loop, transport/context accounting, explicit completion, synthetic regression cases. Historical 958-token cost applies to its documented configuration, not every later version. | `git show 54fa60a:harness/engine.py`; [historical literal defaults](../harness/historical-controls.json), [prompt-cost evidence](../experiments/agent-completion/minimal-harness-prompt-cost.json), and [harness instructions/tests](../harness/README.md). Code/tests are replayable; historical private session settings are not automatically the source defaults. |
| 9. Document state/recovery | Retained implementation for byte-cursor traversal, notes, merge lineage, pause/resume, and output-limit recovery. Live motivation: 108,640 bytes / 36 chunks, then repeated exhaustion of a 4,000-token output limit. | `git show d1a0f7f:harness/documents.py`; [workflow behavior](../document-workflow/README.md), historical defaults and synthetic tests. The private document/checkpoint and its complete per-run UI settings are excluded. This is a reproduced control/state failure in tests, not a replayable semantic-quality benchmark. |
| 10. Qwen3.6 adoption | Baseline then candidate; each 512 / 4,096 / 16,384 requested input tokens. AIPerf 0.13.0; concurrency 1; one warmup + three measured requests per case; 256 output; seeded synthetic input; streaming; no prompt reuse. Eighteen measured requests, not six. Both use 20,480 context/Q8 attention KV. | [Candidate server plus all six actual AIPerf commands](../experiments/qwen36-performance/commands.json), [selected original client package versions](../experiments/qwen36-performance/client-environment.json), [profiles and acceptance boundary](../experiments/qwen36-performance/README.md). Tokenizer repository names are preserved, but exact downloaded tokenizer revisions are not pinned by those command records. |

### Locality: do not confuse the matrix with the measured campaigns

The six exploration names are `cpu-baseline`, `controlled-baseline`,
`controlled-matched`, `controlled-matched-no-host-no-repack`,
`controlled-matched-no-op-offload`, and `controlled-pascal-mmq-no-op-offload`.
The four finalists are `controlled-experts6-ub128`,
`controlled-cache1024-share95`, `controlled-cache2048-share95`, and
`controlled-cache2048-share95-ub128`. Each has three retained measured rows.
`controls.json` also catalogs other possible wrapper cases; a catalog entry is
not evidence that it ran in either of these two campaigns.

The original controlled and selected profile differed in cache, Flash Attention,
loading, affinity and operation offload. The 24.16 -> 43.95 tok/s comparison is
therefore a **profile comparison**, not a one-flag cache ablation. The intermediate
profiles and cache/expert-count finalists remain visible.

The Ollama reference used `/api/generate`, raw input, 2,048 context, eight
threads, batch 512, temperature 0, seed 1234, top-k 1, top-p 1, min-p 0,
repeat penalty 1, an empty stop list and a 1,024-token cap. Its separate warmup
requested one token. Native placement/affinity/ignore-EOS controls were not
equivalent; do not turn this reference into a fully matched backend claim.

### Quality: three requests are not three repeated samples

The preliminary characterization and the A/B/C study are separate runs.
Each used three related instruction variants over the same source passage.
Each A/B/C prompt-arm combination ran once. The plan allowed a conditional
two-response frontend bridge; that allowance is not evidence of two more
measured responses in the retained nine-row main study.

Native A used `--samplers temperature --temp 0 --seed 1234`.
Native B used `--samplers penalties;top_k;top_p;min_p;temperature`,
temperature 0.5, top-k 20, top-p 0.8, min-p 0, repeat penalty 1,
repeat-last-n 64, zero presence/frequency penalties and seed 1234.
Both used the selected cache/placement profile without strict affinity and with
natural stopping, not the throughput experiment's `--ignore-eos`.
Arm C's actual request supplied context/output caps and `think=false`; its
effective temperature 0.6 / top-p 0.95 / seed -1 came from installed defaults.

Gemma used temperature 0.5, top-k 64, top-p 0.95, min-p 0, repeat penalty 1,
seed 1234, eight threads, batch 512/microbatch 128, context 4,096, load mode
none and Flash Attention auto. Its selected **16 dense GPU layers** are not the
Qwen expert-cache placement. There was no MoE cache for Gemma. GPU24's guard
failure is not an OOM and not a measured slow configuration.

Judgments remain investigator/model-assisted case observations, not a blinded
independent language benchmark or a standardized language score. Exact counts,
hashes, short excerpts and structural checks do not replace the excluded corpus
or establish broad model quality.

### Context: output length and stopping policy changed between studies

| Comparison | Per-arm warmup | Short output cap | Candidate long input / output cap | EOS policy |
|---|---|---|---|---|
| GPU4K vs CPU32K | 64 | 256 | 28,500 filler tokens -> 28,553 rendered prompt tokens / 128 | `ignore_eos` omitted; natural stopping remained possible. |
| GPU4K vs GPU8K | 64 | 1,024 | 7,000 filler tokens -> 7,053 rendered prompt tokens / 1,024 | Explicit `ignore_eos=true` for controlled output length. |

All native `/completion` request fields are in `protocol.json`: temperature 0.5,
top-k 20, top-p 0.8, min-p 0, repeat penalty 1, repeat-last-n 64, zero
presence/frequency penalties, seed 1234, `cache_prompt=false`, `stream=false`
and returned token IDs. Native timings, curl wall time and harness wall time
are separate retained fields. Model startup was outside those request timings.

Both use FP16 KV; only the 32K candidate adds `--no-kv-offload`.
GPU KV allocations of 384 MiB at 4K and 768 MiB at 8K are observed allocations,
not independent MiB knobs in the commands. The 8K plan explicitly used a
256-MiB minimum-free acceptance threshold, not the earlier completion wrapper's
768-MiB stop guard. Its failed 44-tok/s acceptance and subsequent explicit
adoption remain separate decisions.

### Harness: source defaults are not final deployment overrides

The retained source defaults at all three snapshots are **16,384 context /
15,360 input / 1,024 output**, temperature 0.6, top-p 0.95, no fixed seed,
12 iterations, 120 seconds and repeat limit 3. Context reduction is
`truncate-oldest`, keeping two recent groups with a 512-token summary target.
These are defaults, not proof of every historical UI session's settings.
The harness checks observed server context and does not make an oversized
configured context valid merely because it appears in the defaults.

The document gate adds default 12,288-byte chunks and fan-in 8. Those defaults
must **not** be substituted for the unknown complete configuration of the
private 36-chunk incident. Its 4,000-token output limit is a recorded observation.
Synthetic regression tests cover incomplete chunk/merge/final responses and
bounded recovery; they do not prove faithful summarization of the private text.

The final launch explicitly overrides only the selected model/endpoint and
20,480 / 16,000 / 4,000 budgets, as shown in the harness README.
It does not retroactively change earlier defaults, nor implicitly override saved
session settings. The 480-token arithmetic remainder is not a measured universal
safety margin.

### Qwen3.6: what the AIPerf commands establish

The six command records preserve endpoint type `chat`, per-model tokenizer
identifier, requested lengths, random seed 1234, server token counting,
900-second request timeout, streaming, and all extra request inputs:
`ignore_eos:true temperature:0 seed:1234 cache_prompt:false`.
These request controls override the candidate server's temperature-0.5 defaults.
Each case has one warmup plus three measured requests; warmups are not part of
the eighteen measured successes.

The candidate's complete saved server argument vector is recovered. A literal
historical **20K Q8 baseline server launch vector was not recovered**: the saved
older 4K launch is not relabeled as that later launch. The benchmark records fix
20,480/Q8 controls, and the runner asserted the observed 20,480-token slot before
requests. [Original baseline allocation lines](../experiments/qwen36-performance/baseline-allocation.json)
independently confirm 20,480 cells and Q8 K/V, rather than relying only on client
metadata. This remaining literal-launch boundary is explicit rather than filled
with a command guessed from the candidate.

Two baseline 128-input-token smoke attempts encountered remote-tokenizer and
local-path setup problems before the successful smoke. They are setup failures,
not failed measured requests among the eighteen. Offline tokenizer preparation
preceded the retained six main profiles. Equal requested token counts do not
mean equal generated texts or identical actual token counts across tokenizers.
The public GGUF weight revision/hash does not by itself pin the tokenizer.

## Recovery method and exclusions

Saved command files, frozen plans, request metadata, build source and retained
implementation snapshots were checked offline. The
[origin map](evidence-map.json) records original/public digests and explicit
projections. Command-path normalization is positional: no blind substitution of
private names or publication of operational launchers. The CPU build recipe and
historical source-default extraction are labeled as such.

The short native synthetic benchmark input, CLI work-request text/fixture recipe,
and inert context-filler construction are authored test material. They are the
explicit exception to exclusion of full private prompts/corpora. Private CLI
message streams, private system/plugin context, the Tamil source passage,
the real document/checkpoint, third-party model templates, weights and binaries
remain excluded. Quality and semantic-fidelity limitations remain unchanged.

`python -B tools\validate_evidence.py` checks the retained controls against their
case counts, artifacts and measurements without inference. This follow-up did
not rerun benchmarks, retune parameters or access the measurement machine.
