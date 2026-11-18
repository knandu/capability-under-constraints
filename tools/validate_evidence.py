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


def option(arguments, flag):
    check(arguments.count(flag) == 1, f"Expected exactly one {flag}.")
    index = arguments.index(flag) + 1
    check(index < len(arguments), f"Missing value for {flag}.")
    return arguments[index]


def validate_reproduction_controls():
    locality = "experiments/expert-locality/"
    catalog = load_json(locality + "commands.json")["commands"]
    measured = {item["id"]: item for item in catalog if item["stage"] == "measurement"}
    check(len(measured) == len(catalog) - 1, "Duplicate locality command identity.")
    rows = load_csv(locality + "exploration.csv") + load_csv(locality + "finalists.csv")
    check(set(measured) == {row["Experiment"] for row in rows},
          "Locality command catalog does not cover the measured campaigns.")
    matrix = load_json(locality + "controls.json")["Matrix"]
    for name, item in measured.items():
        matching = [row for row in rows if row["Experiment"] == name]
        check(sorted(int(row["Repeat"]) for row in matching) == item["repeats"],
              f"Repetition mismatch: {name}")
        argv, controls = item["arguments"], matrix[name]
        for flag, value in (("-c", 2048), ("-t", 8), ("-tb", 8), ("-b", 512),
                            ("-ub", controls.get("MicroBatch", 128))):
            equal(option(argv, flag), value, name + " " + flag)
        check(all(int(row["Tokens"]) == int(option(argv, "-n")) for row in matching),
              f"Output-cap mismatch: {name}")
        cache = controls.get("MoeCacheMiB", 0)
        check(("--moe-cache-mib" in argv) == (cache > 0), f"Cache enable mismatch: {name}")
        if cache:
            equal(option(argv, "--moe-cache-mib"), cache, name + " cache")
            equal(option(argv, "--moe-cache-cpu-share"), controls.get("MoeCacheCpuShare", 0),
                  name + " CPU miss share")
        for field, flag in (("NoAffinity", "--cpu-mask"), ("NoHost", "--no-host"),
                            ("NoRepack", "--no-repack")):
            expected = not controls.get(field, False) if field == "NoAffinity" else controls.get(field, False)
            check((flag in argv) == expected, f"{field} mismatch: {name}")
        expected = controls.get("NoOpOffload", False) or controls["Case"] == "CPU"
        check(("--no-op-offload" in argv) == expected, f"Operation offload mismatch: {name}")

    fixture = load_json(locality + "benchmark-input.json")
    data = fixture["text"].encode(fixture["encoding"])
    check(len(data) == fixture["bytes"] and hashlib.sha256(data).hexdigest() == fixture["sha256"],
          "Synthetic benchmark input bytes changed.")
    check(all(int(row["PromptTokens"]) == fixture["observed_prompt_tokens"] for row in rows),
          "Synthetic benchmark prompt count does not match the retained runs.")
    selected = measured["controlled-cache2048-share95-ub128"]["arguments"]
    kernel = load_json("experiments/kernel-stop/commands.json")["commands"]
    check(next(item["arguments"] for item in kernel if item["id"] == "measurement") == selected,
          "Kernel comparison no longer uses the selected measurement profile.")

    quality = "experiments/tamil-quality/"
    preliminary = load_csv(quality + "preliminary-results.csv")
    controls = load_json(quality + "controls.json")
    check(len(preliminary) == len(controls["Prompts"]), "Preliminary workload count changed.")
    for row, prompt in zip(preliminary, controls["Prompts"]):
        check(row["PromptSHA256"].lower() == prompt["SHA256"].lower(),
              "Preliminary/main workload identity differs.")
    commands = {item["id"]: item for item in load_json(quality + "commands.json")["commands"]}
    native = [row for row in load_csv(quality + "results.csv") if row["Arm"] in ("A", "B")]
    for row in native:
        id_ = f"{row['Arm']}-p{row['Prompt']}-measurement"
        argv = commands[id_]["arguments"]
        equal(option(argv, "-c"), controls["NativeRuntime"]["Context"], id_ + " context")
        equal(option(argv, "-n"), controls["NativeRuntime"]["Tokens"], id_ + " cap")
        equal(option(argv, "--temp"), controls["Arms"][row["Arm"]]["Temperature"], id_ + " temperature")
        check("--no-context-shift" in argv and "--ignore-eos" not in argv,
              "Natural-stop quality measurement became forced-length.")
    ollama = load_json(quality + "ollama-requests.json")["requests"]
    check(len(ollama) == len(controls["Prompts"]), "Missing Ollama quality request.")
    for request, prompt in zip(ollama, controls["Prompts"]):
        check(request["submitted_prompt_sha256"] == prompt["SHA256"].lower(),
              "Native/Ollama quality workload differs.")

    gemma = "experiments/gemma-model-selection/"
    commands = {item["id"]: item for item in load_json(gemma + "commands.json")["commands"]}
    for row in load_csv(gemma + "qualification.csv"):
        argv = commands[f"qualification-{row['Case']}-measurement"]["arguments"]
        for flag, field in (("-ngl", "GPULayers"), ("-t", "CPUThreads"), ("-c", "Context"),
                            ("-b", "Batch"), ("-ub", "Microbatch"), ("-n", "TokenCap")):
            equal(option(argv, flag), row[field], row["Case"] + " " + flag)
        check("--moe-cache-mib" not in argv, "Dense Gemma qualification gained an expert cache.")
    argv = commands["qualification-gpu24-placement-failed"]["arguments"]
    equal(option(argv, "-n"), 0, "Failed GPU24 attempt must remain a placement-only record")
    equal(option(argv, "-ngl"), 24, "Failed GPU24 placement")

    context = "experiments/context-economics/"
    protocol = load_json(context + "protocol.json")
    for item in load_json(context + "commands.json")["commands"]:
        argv = item["arguments"]
        equal(option(argv, "-c"), {"gpu-4k": 4096, "cpu-32k": 32768, "gpu-8k": 8192}[item["arm"]],
              item["id"] + " context")
        check(("--no-kv-offload" in argv) == (item["arm"] == "cpu-32k"),
              "Context-study KV placement changed.")
    check("ignore_eos" not in protocol["cpu-kv"]["short_request_fields_excluding_prompt"]
          and protocol["gpu-kv"]["short_request_fields_excluding_prompt"]["ignore_eos"] is True,
          "Distinct context-study EOS policies were lost.")

    performance = "experiments/qwen36-performance/"
    commands = {item["id"]: item for item in load_json(performance + "commands.json")["commands"]}
    comparison = load_json(performance + "performance-comparison.json")
    check(set(commands) == {"candidate-server"} | {
        f"{row['case']}-isl{row['requested_isl']}" for row in comparison["rows"]},
        "AIPerf command catalog does not match the six retained cases.")
    for row in comparison["rows"]:
        item = commands[f"{row['case']}-isl{row['requested_isl']}"]
        argv = item["arguments"]
        for flag, value in (("--isl", row["requested_isl"]), ("--osl", item["output_tokens"]),
                            ("--request-count", item["measured_requests"]),
                            ("--warmup-request-count", item["warmup_requests"]),
                            ("--concurrency", item["concurrency"])):
            equal(option(argv, flag), value, item["id"] + " " + flag)
        check(set(argv[argv.index("--extra-inputs") + 1:]) == {
            "ignore_eos:true", "temperature:0", "seed:1234", "cache_prompt:false"},
            "AIPerf request controls changed.")
    argv = commands["candidate-server"]["arguments"]
    budget = load_json(performance + "adoption.json")
    equal(option(argv, "-c"), budget["context"], "Candidate server/adoption context")
    check(option(argv, "--cache-type-k") == option(argv, "--cache-type-v") == "q8_0",
          "Candidate attention KV precision changed.")
    ready = load_json(performance + "candidate-ready.json")
    for flag, field in (("-t", "threads"), ("-b", "batch"), ("-ub", "microbatch"),
                        ("--moe-cache-mib", "expert_cache_mib"),
                        ("--moe-cache-cpu-share", "expert_cpu_miss_share")):
        equal(option(argv, flag), ready[field], "Candidate " + field)
    baseline = load_json(performance + "baseline-allocation.json")
    check(any("20480 cells" in line and "K (q8_0)" in line and "V (q8_0)" in line
              for line in baseline["allocation"]), "Missing actual baseline Q8/20K allocation evidence.")

    cli = load_json("experiments/agent-completion/experiment-controls.json")
    for case in load_json("experiments/agent-completion/completion.json"):
        equal(case["Budget"]["Input"], cli["provider_input_limit"], "Focused CLI input budget")
        equal(case["Budget"]["Output"], cli["provider_output_limit"], "Focused CLI output budget")


def main():
    validate_reproduction_controls()
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

    manifest = load_json("notes/evidence-map.json")
    origins = manifest["artifact_origins"]
    latest = {record["public_path"]: record for record in origins}
    for path, record in latest.items():
        actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        check(actual == record["public_sha256"], f"Normalized artifact changed: {path}")
    for followup in manifest.get("curation_followups", []):
        for record in followup.get("derived_artifacts", []):
            actual = hashlib.sha256((ROOT / record["public_path"]).read_bytes()).hexdigest()
            check(actual == record["public_sha256"], f"Derived artifact changed: {record['public_path']}")
    print("Retained aggregates, acceptance boundaries, AIPerf profiles, budgets, and artifact digests agree.")


if __name__ == "__main__":
    main()
