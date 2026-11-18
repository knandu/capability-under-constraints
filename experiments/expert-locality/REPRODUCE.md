# Reproducing the selected native profile

The original PowerShell wrapper is not required for the command below.
`controls.json` uses wrapper parameter names, not an alternative llama.cpp API.
This document maps every matrix parameter to the actual arguments and separates
build selection, placement, loading, affinity, and measurement behavior.

## The cache was an upstream feature

At the pinned **unmodified** llama.cpp revision
`cf9a9957dae4801dde95d174ec1ac1b4cac84bf8`, the selected settings were:

```text
--moe-cache-mib 2048 --moe-cache-cpu-share 0.95
```

These are real upstream options, not wrapper-implemented caching.
The [pinned argument parser](https://github.com/ggml-org/llama.cpp/blob/cf9a9957dae4801dde95d174ec1ac1b4cac84bf8/common/arg.cpp#L2747-L2768)
defines both; the [pinned cache documentation](https://github.com/ggml-org/llama.cpp/blob/cf9a9957dae4801dde95d174ec1ac1b4cac84bf8/docs/moe-cache.md)
and [implementation](https://github.com/ggml-org/llama.cpp/blob/cf9a9957dae4801dde95d174ec1ac1b4cac84bf8/src/llama-moe-cache.cpp#L812-L818)
explain their behavior.

`2048` is a MiB GPU expert-cache budget, not the size of all host experts.
The `0.95` requests CPU computation for that share of cache misses **after the
cache fills**. Hits execute on the GPU; other misses upload experts. Initial
misses fill the cache without that CPU split. This is not a cache-hit target,
a CPU-memory allocation fraction, or 95% of all inference work. The cache serves
small batches such as decode; large batches take the ordinary upload path.

## Build the recorded executable

Use a fresh llama.cpp checkout at the exact pin, not this notebook as its source.
The historical toolchain was Windows x64, Visual Studio 2022/MSVC
19.44.35230.0, CUDA, and shared libraries. Supply a compatible installed CUDA
toolkit; its version is not inferred from the SM75 architecture setting.
The complete configure arguments, including CPU ISA and runtime-library choices,
are retained in the [stock build record](../kernel-stop/builds/stock-sm75.json).

Run from the notebook root in a Visual Studio developer PowerShell:

```powershell
$Source = '<fresh-llama.cpp-checkout-at-the-pin>'
$Build = '<new-build-directory>'
$Cuda = '<installed-cuda-toolkit-directory>'
$record = Get-Content '.\experiments\kernel-stop\builds\stock-sm75.json' -Raw | ConvertFrom-Json
$configure = @($record.ConfigureArguments | ForEach-Object {
    $_.Replace('<llama.cpp-source-dir>', $Source).
       Replace('<build-dir>', $Build).
       Replace('<cuda-toolkit-dir>', $Cuda)
})
& cmake @configure
if ($LASTEXITCODE -ne 0) { throw 'CMake configuration failed.' }
& cmake --build $Build --config Release --target llama-completion
if ($LASTEXITCODE -ne 0) { throw 'Native build failed.' }
```

Keep the executable and its built runtime/backend DLLs together. The original
wrapper packaged them into one runtime directory. The kernel comparison selected
different built executables, not a special inference flag:

| Wrapper `CudaVariant` | Build record |
|---|---|
| `Default` | [stock SM75](../kernel-stop/builds/stock-sm75.json) |
| `SM75-MMQ` | [SM75 forced MMQ](../kernel-stop/builds/sm75-forced-mmq.json) |
| `Pascal-MMQ` | [Pascal PTX forced MMQ](../kernel-stop/builds/pascal-ptx-forced-mmq.json) |

Use separate build directories when configuring those records. The CPU-only case
used the separately recorded Zen 5 CPU build, not a CUDA kernel variant.

## Run the selected 2K-context completion

Prerequisites: the stock SM75 executable, a working CUDA device named `CUDA0`,
and the original Qwen3-30B-A3B Q4_K_M model. Its recorded SHA-256 is
`e9183b5c18a0cf736578c1e3d1cbd4b7e98e3ad3be6176b68c20f156d54a07ac`.
This is **not** the later Qwen3.6 model.

`benchmark-input.json` contains the short authored synthetic input used for this
measurement, including its original newline bytes and chat framing. It matches
the original recorded input hash. It is not a private CLI capture or the Tamil
evaluation corpus. It was submitted as raw completion text; do not apply another
chat template.

The following is the recovered selected measurement argument vector with only
paths made configurable. Run it from the notebook root. The example temporarily
clears runtime overrides and restores their previous values on exit.

```powershell
& {
    $Completion = '<runtime-directory>\llama-completion.exe'
    $Model = '<model-directory>\Qwen3-30B-A3B-Q4_K_M.gguf'
    $inputRecord = Get-Content '.\experiments\expert-locality\benchmark-input.json' -Raw | ConvertFrom-Json
    $Prompt = Join-Path $env:TEMP 'qwen3-locality-benchmark.txt'
    [IO.File]::WriteAllText($Prompt, $inputRecord.text, [Text.UTF8Encoding]::new($false))
    if ((Get-FileHash $Prompt -Algorithm SHA256).Hash -ne $inputRecord.sha256) {
        throw 'Benchmark input bytes differ.'
    }
    if ((Get-FileHash $Model -Algorithm SHA256).Hash -ne 'e9183b5c18a0cf736578c1e3d1cbd4b7e98e3ad3be6176b68c20f156d54a07ac') {
        throw 'Model differs from the measured checkpoint.'
    }
    $savedEnvironment = @{}
    try {
        foreach ($item in @(Get-ChildItem Env:)) {
            if ($item.Name -like 'LLAMA_ARG_*' -or
                $item.Name -in @('GGML_BACKEND_PATH', 'GGML_CUDA_FORCE_MMQ', 'GGML_CUDA_FORCE_CUBLAS')) {
                $savedEnvironment[$item.Name] = $item.Value
                Remove-Item "Env:$($item.Name)"
            }
        }
        $nativeArguments = @(
            '-m', $Model, '-f', $Prompt, '-c', '2048', '-n', '1024',
            '-b', '512', '-ub', '128', '-t', '8', '-tb', '8',
            '--seed', '1234', '--samplers', 'temperature', '--temp', '0',
            '--ignore-eos', '--no-conversation', '--simple-io',
            '--flash-attn', 'auto', '--fit', 'off', '--perf', '--offline',
            '--log-colors', 'off', '--load-mode', 'none', '--no-op-offload',
            '--moe-cache-mib', '2048', '--moe-cache-cpu-share', '0.95',
            '-ngl', '99', '--device', 'CUDA0', '--override-tensor', 'exps=CPU',
            '--warmup', '--log-verbosity', '4'
        )
        & $Completion @nativeArguments
        if ($LASTEXITCODE -ne 0) { throw 'Native completion failed.' }
    } finally {
        foreach ($name in $savedEnvironment.Keys) {
            Set-Item "Env:$name" $savedEnvironment[$name]
        }
    }
}
```

`commands.json` retains literal argument arrays recovered from the original
selected **measurement and placement** command files and original-control
measurement file, with executable/model/prompt paths replaced by named
placeholders. Argument order and all non-path values are unchanged. The arrays
are archived evidence, not newly executed benchmarks.

The wrapper first launched a separate placement check: the same arguments with
`-n 0`, `--no-warmup`, and `--log-verbosity 5`. It checked Qwen3 MoE Q4_K_M
metadata, expert-host overrides in all 48 layers, and a CUDA model buffer.
It then launched the measured command above, with native warmup and cache-access
logging. It required active cache hits/misses and performance timings, and checked
that 1,024 sampled tokens corresponded to 1,023 decode runs. Do not equate the
reported decode throughput with model-loading or total wall-clock throughput.

The original monitor required at least 2,048 MiB free device VRAM before starting
and stopped a hybrid run below 768 MiB free. It did not silently refit placement.
The displayed command does not reproduce that monitor or the placement assertions:
inspect those conditions yourself before timing. `--fit off` is retained.
The finalist plan ran its four named experiments in order within each of three
repeats; `Repeats` is not a llama.cpp argument. `Matrix` also catalogs exploratory
cases, not a claim that every listed case ran in the twelve-run finalist campaign.

## Complete `controls.json` mapping

The original wrapper defaults below matter when a case omits a field.
Placement rules are mutually exclusive.

| Field | Default / condition | Actual arguments or behavior |
|---|---|---|
| `Case` | `CPU` | `-ngl 0 --device none --no-kv-offload --no-op-offload`; selects CPU build. |
| `Case` | `Auto` | `-ngl <GpuLayers> --device CUDA0`. |
| `Case` | `Controlled`, `CpuExpertLayers=48` | `-ngl 99 --device CUDA0 --override-tensor exps=CPU`. The 48-layer special case belongs to this Qwen3 model. |
| `Case` | `Controlled`, fewer CPU expert layers | `-ngl 99 --device CUDA0 --n-cpu-moe <CpuExpertLayers>`; first N layers, not a cache-size setting. |
| `GpuLayers` | `4` | `-ngl <value>` only in `Auto`; ignored by the other placement modes. |
| `CpuExpertLayers` | `48` | Selects the `Controlled` rule above; a nondefault value in CPU/Auto mode is rejected. |
| `MoeCacheMiB` | `0` | If positive: `--moe-cache-mib <value>`; zero omits both cache options. Cache runs require Controlled host experts and a GPU; nonzero CPU share with zero cache is rejected. |
| `MoeCacheCpuShare` | `0` | `--moe-cache-cpu-share <value>` only with a positive cache; decimal point is culture-independent. |
| `MicroBatch` | `128` | `-ub <value>`; batch size remains `-b 512`. |
| `FlashAttention` | `off` | `--flash-attn off`, `on`, or `auto`. |
| `LoadMode` | `auto` | Omit `--load-mode`; otherwise `--load-mode mmap` or `--load-mode none`. `none` is an explicit upstream loading mode, not omission of loading. |
| `NoAffinity` | `false` | Detect local topology and add `--cpu-mask <mask> --cpu-mask-batch <mask> --cpu-strict 1 --cpu-strict-batch 1`. Eight threads used physical cores; sixteen used logical CPUs. |
| `NoAffinity` | `true` | Omit all four affinity arguments. There is no `--no-affinity` argument. |
| `NoHost` | `false` | If true, add `--no-host`. |
| `NoRepack` | `false` | If true, add `--no-repack`. |
| `NoOpOffload` | `false` | If true for non-CPU cases, add `--no-op-offload`; CPU placement already forces it regardless of this switch. |
| `CudaVariant` | `Default` | Select a built executable using the table above; does not add a runtime flag. A nondefault CUDA variant in CPU mode is rejected. |
| `Tokens` | finalist plan: `1024` | `-n 1024`; the general wrapper default was 256. |
| `Repeats` | finalist plan: `3` | Three wrapper invocations per named finalist, not a native flag. |
| `Experiments` | four finalist names | Select entries from `Matrix`, not native arguments. |
| `Matrix` | case-name/parameter objects | Supply per-case wrapper overrides using this table. |

Fixed finalist controls were `-c 2048 -t 8 -tb 8 -b 512`,
`--seed 1234 --samplers temperature --temp 0`, `--ignore-eos`,
`--no-conversation --simple-io --fit off --perf --offline --log-colors off`.
The shared wrapper also accepted other context/thread/output values; the finalist
driver fixed these values explicitly or through its frozen defaults.

The original control's recorded mask was `0x5555` on the measured machine.
Do not assume that mask describes physical cores on a different CPU/topology.
The winning profile omitted affinity flags entirely.

The 24.16 and 43.95 tok/s medians compare **profiles**, not a cache-only ablation.
Besides enabling the cache, the selected profile used Flash Attention `auto`
instead of `off`, explicit load mode `none`, no strict affinity, and
`--no-op-offload`. `exploration.csv` and the four interleaved finalists retain
the intermediate controls rather than attributing the entire difference to one
flag.

## Later context settings were different experiments

These are source-confirmed flag changes, not additional measurements:

| Runtime | Context/KV controls | Important distinction |
|---|---|---|
| Qwen3, 8K GPU KV | `-c 8192 -np 1 --flash-attn auto`; omit `--no-kv-offload` | The 768 MiB KV allocation was observed, not a `--kv-cache-mib 768` setting. |
| Qwen3, 32K CPU KV | `-c 32768 -np 1 --no-kv-offload` | The comparison cloned the then-current 4K server arguments, changed context/port, and added CPU KV; it was not the later adopted 8K server. |
| Qwen3.6, 20K Q8 KV | `-c 20480 -np 1 --cache-type-k q8_0 --cache-type-v q8_0 --flash-attn on --reasoning off` | The harness separately caps input/output at 16000/4000. Those are not native `-c` subdivisions. |

All three retained the 2,048 MiB expert cache and 0.95 CPU-miss share. KV cache
and expert cache are different allocations. Qwen3.6's separate FP32 recurrent
state was not converted to INT8 by the attention K/V flags.

These later servers used `llama-server`, not the completion command above.
Qwen3 used an external non-thinking chat template; Qwen3.6 used the model's
template with `--reasoning off`. This table does not reconstruct the excluded
Qwen3 template or imply that these rows alone reproduce the later end-to-end
workloads. Their original workload/quality limitations remain unchanged.

This reproduction follow-up recovered historical configuration evidence and
checked upstream source. No inference run, rebuild, or new performance claim was
made.
