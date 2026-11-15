# Limitations and unresolved questions

The original stopping point is preserved; curation did not start new experiments.

- One personal machine, a short investigation, and small task-specific samples
  do not establish universal hardware, model, or inference-backend rankings.
- Contexts, output counts, prompt construction, tokenizers, stopping behavior,
  and timing sources differ across phases. The tables are labeled per experiment;
  they must not be flattened into one overall performance chart.
- The original controlled baseline is a recorded point, not a three-repeat
  baseline confidence interval. Finalist and closing-kernel repetitions do not
  retroactively create missing baseline repetitions.
- The earliest baseline-comparison raw directory was not available locally.
  The retained original control row comes from the subsequent locality exploration.
  No missing raw directory was recreated or called recovered.
- Ollama is a native-API/default-placement reference, not identical runtime
  controls. Device VRAM is sampled/device-total unless explicitly stated otherwise.
- Lifetime expert-cache counters are not decode-only counters. Small kernel
  differences do not imply a statistically established universal equivalence.
- Tamil evaluation preserves qualitative judgments and structural checks, not
  native-speaker certification. Faster generation, better coverage, and a useful
  isolated alternative do not establish a reliable complete package.
- The complete source corpus/prompts are not redistributed. Digests and short
  generated excerpts preserve traceability, not standalone reproduction of the
  entire language-quality campaign.
- Early-marker recall establishes that tested retrieval, not general 32K fidelity.
  The 8K threshold failure and later acceptance are both part of the record.
- Focused tool/completion controls are not broad agent evaluation. A reported
  completed task can still have an incorrect or reverted edit.
- Context overhead depends on instructions, schemas, tool observations, history,
  tokenizer, and harness version. No unsupported exact fixed footprint is claimed.
- Byte coverage and checkpoint integrity do not establish semantic fidelity.
  Summarization remains lossy; no broad factual-retention evaluation was performed.
- Qwen3.6 was adopted for measured performance, not qualified as superior for
  Tamil rewriting, coding, general agents, or faithful summarization.

There are no unresolved URL or license-selection placeholders. Quality and
generalization remain explicitly unqualified, not TODOs to fill by inventing
results. Publication of a bounded notebook does not require extending the study.
