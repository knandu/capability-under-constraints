"""Recompute retained aggregates offline; never send inference requests."""

import csv
import hashlib
import json
import math
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    return json.loads((ROOT / path).read_bytes())


def load_csv(path):
    with (ROOT / path).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def check(condition, message):
    if not condition:
        raise ValueError(message)


def equal(actual, expected, label):
    check(math.isclose(float(actual), float(expected), rel_tol=1e-10, abs_tol=1e-10),
          f"{label}: {actual} != {expected}")


def validate_prompt_costs(cli, harness):
    check(cli["rendered_matches_native"], "Original prompt/native agreement flag is false.")
    equal(cli["native_prompt_tokens"], cli["rendered_prompt_tokens"], "Rendered/native prompt agreement")
    equal(cli["rendered_prompt_tokens"] - cli["controlled_work_request_tokens"],
          cli["all_overhead_excluding_work_request_tokens"], "CLI non-work scaffolding")
    equal(cli["message_content_tokens_sum"] + cli["tools_and_chat_framing_residual_tokens"],
          cli["rendered_prompt_tokens"], "CLI content/framing decomposition")
    equal(cli["system_message_tokens"] + cli["other_message_content_excluding_work_request_tokens"]
          + cli["tools_and_chat_framing_residual_tokens"],
          cli["all_overhead_excluding_work_request_tokens"], "CLI scaffolding decomposition")
    equal(cli["rendered_prompt_tokens"] - cli["no_tools_rendered_tokens"],
          cli["tool_injection_marginal_tokens"], "Marginal tool injection")
    equal(cli["input_budget"] - cli["all_overhead_excluding_work_request_tokens"],
          cli["remaining_input_after_overhead"], "Remaining CLI work budget")
    equal(round(100 * cli["all_overhead_excluding_work_request_tokens"] / cli["input_budget"], 2),
          cli["overhead_percent_of_input_budget"], "CLI overhead percentage")
    equal(harness["system_and_guidance_tokens"] + harness["combined_schemas_tokens"]
          + harness["template_boundary_delta_tokens"],
          harness["empty_history_rendered_tokens"], "Historical minimal-harness decomposition")


def main():
    locality = "experiments/expert-locality/"
    initial = load_csv(locality + "exploration.csv")
    finalists = load_csv(locality + "finalists.csv")
    ollama = load_csv(locality + "ollama.csv")
    summary = load_json(locality + "summary.json")
    controlled = [r for r in initial if r["Experiment"] == "controlled-baseline"]
    selected = [r for r in finalists if r["Experiment"] == summary["selected_case"]]
    check(len(controlled) == len(selected) == len(ollama) == 3,
          "Locality control/repetition counts changed.")
    equal(statistics.median(float(r["GenerationTokensPerSecond"]) for r in controlled),
          summary["original_controlled_decode_tok_s"], "Control median")
    equal(statistics.median(float(r["GenerationTokensPerSecond"]) for r in selected),
          summary["selected_finalist_decode_tok_s"], "Cache median")
    equal(statistics.median(float(r["GenerationTokensPerSecond"]) for r in ollama),
          summary["ollama_reference_decode_tok_s"], "Ollama median")
    check(all(r["Status"] == "PASS" for r in initial + finalists), "Failed locality row.")

    runs = load_csv("experiments/kernel-stop/runs.csv")
    check(len(runs) == 9, "Closing kernel run count changed.")
    for aggregate in load_csv("experiments/kernel-stop/summary.csv"):
        matching = [r for r in runs if r["Build"] == aggregate["Build"]]
        check(len(matching) == 3, "Missing kernel repetitions.")
        equal(statistics.mean(float(r["Decode"]) for r in matching),
              aggregate["MeanDecode"], aggregate["Build"])
    check(all(r["EffectiveControlsVerified"].lower() == "true" for r in runs),
          "Unverified kernel controls.")

    quality = load_csv("experiments/tamil-quality/quality.csv")
    for arm, expected in (("A", 3), ("B", 6)):
        equal(sum(int(r["BothSourceParagraphsInAlternatives"]) for r in quality if r["Arm"] == arm),
              expected, f"Tamil coverage arm {arm}")
    gemma = load_csv("experiments/gemma-model-selection/performance.csv")
    for aggregate in load_csv("experiments/gemma-model-selection/performance-summary.csv"):
        matching = [r for r in gemma if r["Model"] == aggregate["Model"]]
        check(len(matching) == 3, "Model-selection response count changed.")
        equal(statistics.mean(float(r["WallSeconds"]) for r in matching),
              aggregate["MeanWallSeconds"], aggregate["Model"])

    context = "experiments/context-economics/"
    long = [r for r in load_csv(context + "cpu-kv.csv") if int(r["PromptTokens"]) == 28553]
    check(len(long) == 1 and load_json(context + "recall.json")["ExactCodePresent"],
          "Missing successful long-context control.")
    equal(round(float(long[0]["WallSeconds"]), 2), 525.79, "32K wall time")
    equal(round(float(long[0]["DecodeTokSec"]), 2), 3.64, "32K decode")
    acceptance = load_json(context + "initial-acceptance.json")
    adoption = load_json(context + "adoption.json")
    check(not acceptance["Accepted"] and not adoption["Initial44TokSecCriterionPassed"],
          "Original failed 8K threshold was lost.")
    equal(acceptance["LongDecodeTokSec"], adoption["NearFullDecodeTokSec"], "8K adoption")

    validate_prompt_costs(
        load_json("experiments/agent-completion/prompt-overhead.json"),
        load_json("experiments/agent-completion/minimal-harness-prompt-cost.json"),
    )

    qwen = "experiments/qwen36-performance/"
    comparison = load_json(qwen + "performance-comparison.json")
    check(len(comparison["rows"]) == 6, "Missing matched performance cases.")
    for row in comparison["rows"]:
        profile = load_json(qwen + f"profiles/{row['case']}-isl{row['requested_isl']}/profile_export_aiperf.json")
        check(profile["is_complete"] and not profile["was_cancelled"], "Incomplete profile.")
        equal(profile["request_error_rate"]["avg"], 0, "Request errors")
        equal(profile["completed_request_count"]["avg"], 3, "Measured requests")
        equal(profile["output_sequence_length"]["min"], 256, "Minimum output")
        equal(profile["output_sequence_length"]["max"], 256, "Maximum output")
        equal(profile["overall_usage_prompt_cache_read_pct"]["avg"], 0, "Prompt cache")
        for field, metric, scale in (
            ("median_ttft_seconds", "time_to_first_token", 1000),
            ("median_prefill_tokens_per_second", "prefill_throughput_per_user", 1),
            ("median_decode_tokens_per_second", "output_token_throughput_per_user", 1),
            ("median_request_seconds", "request_latency", 1000),
        ):
            equal(row[field], profile[metric]["p50"] / scale, field)
        equal(row["actual_isl_min"], profile["input_sequence_length"]["min"], "Actual input minimum")
        equal(row["actual_isl_max"], profile["input_sequence_length"]["max"], "Actual input maximum")
    for ratio, baseline, candidate in zip(comparison["comparisons"], comparison["rows"][:3], comparison["rows"][3:]):
        for key, metric in (
            ("candidate_decode_ratio", "median_decode_tokens_per_second"),
            ("candidate_ttft_ratio", "median_ttft_seconds"),
            ("candidate_prefill_ratio", "median_prefill_tokens_per_second"),
        ):
            equal(ratio[key], candidate[metric] / baseline[metric], key)
    budget = load_json(qwen + "adoption.json")
    check(budget["max_input"] + budget["max_output"] <= budget["context"],
          "Selected startup budget exceeds context.")

    origins = load_json("notes/evidence-map.json")["artifact_origins"]
    latest = {record["public_path"]: record for record in origins}
    for path, record in latest.items():
        actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        check(actual == record["public_sha256"], f"Normalized artifact changed: {path}")
    print("Retained aggregates, acceptance boundaries, AIPerf profiles, budgets, and artifact digests agree.")


if __name__ == "__main__":
    main()
