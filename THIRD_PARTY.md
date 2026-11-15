# Third-party and data boundaries

`LICENSE` covers the author's notebook text, analysis, and authored harness/code.
No third-party source tree, model weights, chat-template implementation, DLL,
downloaded Python environment, or benchmark package is vendored.

| Referenced component | Boundary |
|---|---|
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | MIT upstream; source revision is pinned in the baseline. This notebook is not a fork. |
| [AIPerf](https://github.com/ai-dynamo/aiperf) | Referenced measurement tool, not redistributed; the original qualification used 0.13.0. |
| [Qwen3](https://huggingface.co/Qwen/Qwen3-30B-A3B) | Referenced model; weights are not included. Consult the model repository's Apache-2.0 license. |
| [Qwen3.6 GGUF](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF) | Exact file/revision/digest are recorded. Weights and conversion environment are not included; consult the model repository's license. |
| [Gemma 3](https://ai.google.dev/gemma/terms) | Gemma terms apply to the model; no weights or model implementation are included. |
| Windows, MSVC, CUDA, Ollama, Edge | Public technical references and recorded tool/runtime names; none of their binaries are redistributed. |

The writing workload came from an existing personal Tamil workflow. Its full
corpus, full source passages, prompts, and third-party templates are deliberately
excluded: the notebook does not assert a redistribution license for that material.
Evaluation tables are the investigator's observations. Short model-generated
excerpts are labeled as experimental output, not human-authored Tamil exemplars;
MIT does not grant rights the author does not own in third-party material.

The public transliteration project supplies context and an established licensing
convention; it is not being vendored or relicensed here.
