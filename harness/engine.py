import copy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import socket
import threading
import time
import uuid

from tools import DEFAULT_LIMITS, GUIDANCE, SCHEMAS, ToolError, bound_result, dumps, execute, local_path
from transport import Meter, ModelError, OutputLimitError, Transport, endpoint_parts
from documents import DocumentWorkflow, save_checkpoint


HERE = Path(__file__).resolve().parent


def defaults():
    return {
        "base_url": "http://127.0.0.1:8080/v1", "model": "local-model",
        "working_root": str(Path.cwd().resolve()),
        "system_prompt": (HERE / "system-prompt.txt").read_text(encoding="utf-8").rstrip(),
        "context": 16384, "max_input": 15360, "max_output": 1024,
        "tools": list(SCHEMAS), "explicit_completion": False, "completion_criteria": "",
        "max_iterations": 12, "max_seconds": 120, "repeat_limit": 3,
        "temperature": 0.6, "top_p": 0.95, "seed": None,
        "reduction": "truncate-oldest", "recent_groups": 2, "summary_tokens": 512,
        "read_bytes": 1048576, "scan_files": 20000, "scan_depth": 12,
        "limits": copy.deepcopy(DEFAULT_LIMITS),
        "capture": False, "capture_directory": str(HERE / "captures"),
        "workflow": "chat", "document_path": "", "document_chunk_bytes": 12288, "document_fan_in": 8,
        "checkpoint_directory": str(HERE / "checkpoints"),
        "server_progress": False,
    }


def configuration(value):
    base = defaults()
    if not isinstance(value, dict) or set(value) - set(base):
        raise ValueError("Unknown configuration fields.")
    base.update(copy.deepcopy(value))
    for key in ("base_url", "model", "working_root", "system_prompt", "completion_criteria", "capture_directory",
                "workflow", "document_path", "checkpoint_directory"):
        if not isinstance(base[key], str):
            raise ValueError(f"{key} must be a string.")
    endpoint_parts(base["base_url"])
    root = Path(base["working_root"])
    if not root.is_absolute() or str(root).startswith(("\\\\", "//")) or not root.is_dir():
        raise ValueError("working_root must be an existing absolute local directory.")
    base["working_root"] = str(root.resolve())
    if base["working_root"].startswith(("\\\\", "//")):
        raise ValueError("A working root resolving to a network share is not allowed.")
    if os.name == "nt":
        import ctypes
        if ctypes.windll.kernel32.GetDriveTypeW(str(root.anchor)) == 4:
            raise ValueError("Mapped network working roots are not allowed.")
    if not base["model"].strip():
        raise ValueError("A model identifier is required.")
    for key in ("context", "max_input", "max_output", "max_iterations", "max_seconds", "repeat_limit",
                "recent_groups", "summary_tokens", "read_bytes", "scan_files", "scan_depth",
                "document_chunk_bytes", "document_fan_in"):
        if type(base[key]) is not int or not 1 <= base[key] <= 10_000_000:
            raise ValueError(f"{key} must be a positive bounded integer.")
    if base["max_input"] + base["max_output"] > base["context"]:
        raise ValueError("max_input + max_output must not exceed the session context.")
    for key, maximum in (("temperature", 2), ("top_p", 1)):
        if type(base[key]) not in (int, float) or not math.isfinite(base[key]) or not 0 <= base[key] <= maximum:
            raise ValueError(f"Invalid {key}.")
    if base["seed"] is not None and type(base["seed"]) is not int:
        raise ValueError("seed must be an integer or null.")
    for key in ("capture", "explicit_completion", "server_progress"):
        if type(base[key]) is not bool:
            raise ValueError(f"{key} must be boolean.")
    if (not isinstance(base["tools"], list) or any(not isinstance(tool, str) or tool not in SCHEMAS
            for tool in base["tools"]) or len(set(base["tools"])) != len(base["tools"])):
        raise ValueError("tools must be a unique list of the five known tool names.")
    if base["explicit_completion"] and "task_complete" not in base["tools"]:
        raise ValueError("Explicit completion requires task_complete to be enabled.")
    if base["reduction"] not in {"truncate-oldest", "summarize-oldest"}:
        raise ValueError("Unknown history-reduction policy.")
    if base["workflow"] not in {"chat", "document"}:
        raise ValueError("Unknown workflow.")
    if not 2 <= base["document_fan_in"] <= 32:
        raise ValueError("Document fan-in must be between 2 and 32.")
    if base["workflow"] == "document" and (not base["document_path"].strip()
            or not {"view", "task_complete"} <= set(base["tools"])):
        raise ValueError("Document mode requires a document path, view and task_complete.")
    limits = copy.deepcopy(DEFAULT_LIMITS)
    if not isinstance(base["limits"], dict) or set(base["limits"]) - set(limits):
        raise ValueError("Unknown tool limits.")
    for name, changes in base["limits"].items():
        if not isinstance(changes, dict) or set(changes) - set(limits[name]):
            raise ValueError(f"Unknown limits for {name}.")
        limits[name].update(changes)
    for values in limits.values():
        for key, number in values.items():
            minimum = 256 if key == "max_bytes" else 64 if key == "max_tokens" else 1
            if type(number) is not int or not minimum <= number <= 1_000_000:
                raise ValueError(f"{key} must be between {minimum} and 1000000.")
    base["limits"] = limits
    directories = ["capture_directory"] if base["capture"] else []
    if base["workflow"] == "document":
        directories.append("checkpoint_directory")
    for directory in directories:
        capture_root = Path(base[directory])
        if not capture_root.is_absolute() or str(capture_root).startswith(("\\\\", "//")):
            raise ValueError(f"{directory} must be an absolute local path.")
        if os.name == "nt" and ctypes.windll.kernel32.GetDriveTypeW(str(capture_root.anchor)) == 4:
            raise ValueError(f"Mapped network capture/checkpoint directories are not allowed: {directory}.")
        base[directory] = str(capture_root.resolve())
        if str(base[directory]).startswith(("\\\\", "//")):
            raise ValueError(f"{directory} resolving to a network share is not allowed.")
        if os.name == "nt" and ctypes.windll.kernel32.GetDriveTypeW(str(Path(base[directory]).anchor)) == 4:
            raise ValueError(f"Mapped network capture/checkpoint directories are not allowed: {directory}.")
    return base


class RunStop(RuntimeError):
    pass


class RunPause(RunStop):
    pass


class Capture:
    def __init__(self, directory, session_id, secret=""):
        self.path = Path(directory) / (datetime.now().strftime("%Y%m%d-%H%M%S-") + session_id + "-" + uuid.uuid4().hex[:8])
        self.path.mkdir(parents=True, mode=0o700)
        (self.path / ".gitignore").write_text("*\n", encoding="utf-8")
        self.secret = secret.encode("utf-8")

    def save(self, name, data, redacted=False):
        if self.secret and self.secret in data:
            data = data.replace(self.secret, b"[REDACTED MODEL API KEY]")
            redacted = True
        if redacted:
            (self.path / "redaction-note.txt").write_text(
                "A known model API key was removed. Affected captured bytes are not exact.\n", encoding="utf-8")
        with (self.path / name).open("ab" if name.endswith(".jsonl") else "xb") as stream:
            stream.write(data)


def validate_history(history):
    if not isinstance(history, list):
        raise ValueError("Transcript history must be a list.")
    pending = set()
    for message in history:
        if not isinstance(message, dict) or message.get("role") not in {"user", "assistant", "tool"}:
            raise ValueError("Invalid history message role.")
        if set(message) - {"role", "content", "tool_calls", "tool_call_id", "name"}:
            raise ValueError("Unknown history message fields.")
        if message.get("content") is not None and not isinstance(message["content"], str):
            raise ValueError("Message content must be a string or null.")
        if message["role"] == "tool":
            if message.get("tool_call_id") not in pending:
                raise ValueError("Orphan tool result.")
            pending.remove(message["tool_call_id"])
        else:
            if pending:
                raise ValueError("Unanswered tool calls in history.")
            calls = message.get("tool_calls", [])
            if not isinstance(calls, list):
                raise ValueError("tool_calls must be a list.")
            for call in calls:
                if (not isinstance(call, dict) or not isinstance(call.get("id"), str) or not call["id"]
                        or not isinstance(call.get("function"), dict)
                        or not isinstance(call["function"].get("name"), str)
                        or not isinstance(call["function"].get("arguments"), str) or call["id"] in pending):
                    raise ValueError("Malformed model tool call.")
                pending.add(call["id"])
    if pending:
        raise ValueError("Unanswered tool calls in history.")


class Session:
    def __init__(self, config, api_key=""):
        self.id, self.config, self.api_key = uuid.uuid4().hex, configuration(config), api_key
        self.lock, self.cancel = threading.RLock(), threading.Event()
        self.running, self.active_socket, self.sink = False, None, None
        self.history, self.transcript, self.events = [], [], []
        self.objective, self.task_status, self.status = "", "Not started.", "idle"
        self.capture, self.request_number = None, 0
        self.deadline, self.physical_context = None, None
        self.document, self.document_started, self.document_elapsed = None, None, 0
        self.transport = Transport(self.config["base_url"], api_key, self.set_socket, self.check)
        self.meter = Meter(self.transport, self.emit, lambda: self.deadline)

    def clean(self, value):
        if isinstance(value, str):
            return value.replace(self.api_key, "[REDACTED MODEL API KEY]") if self.api_key else value
        if isinstance(value, list):
            return [self.clean(item) for item in value]
        if isinstance(value, dict):
            return {key: self.clean(item) for key, item in value.items()}
        return value

    def set_socket(self, value):
        with self.lock:
            self.active_socket = value
            if value and self.cancel.is_set():
                value.shutdown(socket.SHUT_RDWR)

    def check(self):
        if self.cancel.is_set():
            raise RunStop("Stopped by user or disconnected browser.")
        if self.deadline is not None and time.monotonic() >= self.deadline:
            self.pause("Elapsed-time budget exhausted; increase Seconds and Resume.")

    def pause(self, message):
        raise RunPause(message)

    def checkpoint_document(self):
        if self.document is not None:
            save_checkpoint(self)

    def stop(self):
        self.cancel.set()
        with self.lock:
            active = self.active_socket
        if active:
            try:
                active.shutdown(socket.SHUT_RDWR)
            except OSError as error:
                self.emit("stop_note", {"message": str(error)})

    def emit(self, kind, data):
        event = {"index": len(self.events), "time": datetime.now(timezone.utc).isoformat(),
                 "type": kind, "data": self.clean(data)}
        with self.lock:
            if kind not in {"assistant_delta", "reasoning_delta"}:
                self.events.append(event)
            if self.capture and kind not in {"assistant_delta", "reasoning_delta"}:
                self.capture.save("events.jsonl", (dumps(event) + "\n").encode("utf-8"))
        if self.sink:
            try:
                self.sink(event)
            except (BrokenPipeError, ConnectionResetError) as error:
                self.sink = None
                self.cancel.set()
                raise RunStop("Browser disconnected; run stopped.") from error
        return event

    def append(self, message):
        with self.lock:
            self.history.append(message)
            self.transcript.append(copy.deepcopy(message))

    def system(self):
        lines = [self.config["system_prompt"]]
        lines.extend(GUIDANCE[name] for name in self.config["tools"])
        if self.config["explicit_completion"]:
            lines.append("Explicit completion is enabled: finish by invoking task_complete.")
        if self.config["completion_criteria"]:
            lines.append("Completion criteria (preserve): " + self.config["completion_criteria"])
        return "\n\n".join(line for line in lines if line)

    def payload(self, messages=None, tools=True, output=None):
        payload = {"model": self.config["model"],
                   "messages": messages if messages is not None else [{"role": "system", "content": self.system()}] + self.history,
                   "max_tokens": output or self.config["max_output"],
                   "temperature": self.config["temperature"], "top_p": self.config["top_p"],
                   "stream": True, "stream_options": {"include_usage": True}}
        if self.config["seed"] is not None:
            payload["seed"] = self.config["seed"]
        if self.config["server_progress"]:
            payload["return_progress"] = True
        if tools and self.config["tools"]:
            payload["tools"] = [SCHEMAS[name] for name in self.config["tools"]]
        return payload

    def measure(self, payload):
        last_user = next((i for i in range(len(payload["messages"]) - 1, -1, -1)
                          if payload["messages"][i]["role"] == "user"), None)
        result = self.meter.measure(payload, last_user)
        result.update({"context": self.config["context"], "physical_context": self.physical_context,
                       "max_input": self.config["max_input"], "max_output": payload["max_tokens"],
                       "remaining": self.config["max_input"] - result["total"]})
        return result

    def inspect(self):
        payload = self.payload()
        measurement = self.measure(payload)
        return self.clean({"effective_system_prompt": self.system(), "request": payload, "accounting": measurement,
                "base_system_tokens": self.meter.count(self.config["system_prompt"]),
                "measurement_notices": [event for event in self.events
                                        if event["type"] in {"tokenizer_unavailable", "template_unavailable"}],
                "tool_schema_tokens": {name: self.meter.count(dumps(SCHEMAS[name])) for name in self.config["tools"]},
                "schema_count_note": "Standalone formal-schema counts; not marginal chat-template costs."})

    def snapshot(self):
        with self.lock:
            return self.clean(copy.deepcopy({"version": 1, "id": self.id, "config": self.config, "objective": self.objective,
                "history": self.history, "transcript": self.transcript, "events": self.events,
                "task_status": self.task_status, "status": self.status, "running": self.running,
                "document": self.document_snapshot(),
                "capture_path": str(self.capture.path) if self.capture else None}))

    def document_snapshot(self):
        value = copy.deepcopy(self.document)
        if value is not None and self.document_started is not None:
            value["elapsed_seconds"] = self.document_elapsed + time.monotonic() - self.document_started
        return value

    def update(self, changes):
        with self.lock:
            if self.running:
                raise ValueError("Configuration cannot change during a run.")
            previous = copy.deepcopy(self.config)
            updated = configuration({**self.config, **changes})
            if self.history and updated["workflow"] != previous["workflow"]:
                raise ValueError("Start a new session to change workflows after sending an objective.")
            if self.document is not None and any(updated[key] != previous[key]
                    for key in ("workflow", "document_path", "working_root")):
                raise ValueError("Start a new session to change a checkpointed document or working root.")
            self.config = updated
            if previous["base_url"] != self.config["base_url"]:
                self.transport = Transport(self.config["base_url"], self.api_key, self.set_socket, self.check)
                self.meter = Meter(self.transport, self.emit, lambda: self.deadline)
                self.physical_context = None
            self.capture = None
            self.emit("configuration_changed", {"before": previous, "after": self.config})

    def call_model(self, payload, kind="agent"):
        self.check()
        account = self.measure(payload)
        if account["remaining"] < 0:
            raise RunStop("Context limit cannot be satisfied for this model request.")
        self.request_number += 1
        number = self.request_number
        self.emit("model_request", {"number": number, "kind": kind, "request": payload, "accounting": account})
        if self.capture:
            self.capture.save(f"{number:04d}-{kind}-request.json", dumps(payload).encode("utf-8"))
        started = time.monotonic()

        def raw(data, assembled):
            redacted = bool(self.api_key and (self.api_key in dumps(assembled)
                or self.api_key.encode("utf-8") in data
                or json.dumps(self.api_key, ensure_ascii=True)[1:-1].encode("ascii") in data))
            if redacted:
                data = b"[REDACTED RESPONSE: streamed model API key]\n"
            if self.capture:
                self.capture.save(f"{number:04d}-{kind}-response.body", data, redacted=redacted)
            self.emit("raw_response", {"number": number, "kind": kind, "body": data.decode("utf-8")})

        message, usage, timings, response = self.transport.chat(
            payload, self.deadline, lambda text: (self.check(), self.emit("assistant_delta",
                {"number": number, "kind": kind, "text": text})), raw,
            progress=lambda data: self.emit("model_progress",
                {"number": number, "kind": kind, "elapsed_seconds": time.monotonic() - started, **data}),
            reasoning_delta=lambda text: (self.check(), self.emit("reasoning_delta",
                {"number": number, "kind": kind, "text": text})))
        self.check()
        if "reasoning_content" in message:
            message = {key: value for key, value in message.items() if key != "reasoning_content"}
        reported = usage.get("prompt_tokens") if isinstance(usage, dict) else None
        self.emit("model_response", {"number": number, "kind": kind, "message": message,
            "response": response, "usage": usage, "timings": timings,
            "finish_reason": self.transport.finish_reason,
            "elapsed_seconds": time.monotonic() - started,
            "input_discrepancy": reported - account["total"] if isinstance(reported, int) else None})
        if self.transport.finish_reason == "length":
            raise OutputLimitError("Model reached the output token limit; partial output is visible but not treated as completion.")
        if isinstance(reported, int) and reported > self.config["max_input"]:
            raise RunStop("Server-reported input exceeded the configured budget; inspect the estimation discrepancy.")
        return message

    def fit(self):
        for _ in range(self.config["max_iterations"] + 1):
            self.check()
            before = self.measure(self.payload())
            if before["remaining"] >= 0:
                return
            groups = []
            for index, message in enumerate(self.history):
                if message["role"] == "tool":
                    if not groups:
                        raise RunStop("Invalid tool-result history.")
                    groups[-1].append(index)
                else:
                    groups.append([index])
            latest_user = max(i for i, message in enumerate(self.history) if message["role"] == "user")
            candidates = [group for group in groups[:-self.config["recent_groups"]]
                          if 0 not in group and latest_user not in group]
            if not candidates:
                raise RunStop("Context cannot fit the pinned objective, current request, schemas and recent groups.")
            selected = candidates
            summary_payload = None
            if self.config["reduction"] == "summarize-oldest":
                selected = []
                for group in candidates:
                    trial = selected + [group]
                    source = [self.history[i] for item in trial for i in item]
                    messages = [
                        {"role": "system", "content": "Summarize supplied observations and unfinished work. Do not use tools."},
                        {"role": "user", "content": dumps({"objective": self.objective,
                            "completion_criteria": self.config["completion_criteria"],
                            "task_status": self.task_status, "observations": source})}]
                    trial_payload = self.payload(messages, tools=False,
                        output=min(self.config["summary_tokens"], self.config["max_output"]))
                    if self.measure(trial_payload)["remaining"] < 0:
                        break
                    selected, summary_payload = trial, trial_payload
                if not selected:
                    raise RunStop("Even one old group exceeds the summarizer budget; reduce tool limits or use truncate-oldest.")
            indices = {index for group in selected for index in group}
            removed = [copy.deepcopy(self.history[i]) for i in sorted(indices)]
            self.emit("reduction_input", {"policy": self.config["reduction"], "removed": removed,
                                         "task_status": self.task_status, "before": before})
            if summary_payload:
                response = self.call_model(summary_payload, "summary")
                if response.get("tool_calls") or not response.get("content"):
                    raise RunStop("Context summarization returned tools or no summary.")
                summary = response["content"]
            else:
                summary = f"Discarded {len(removed)} older messages (truncate-oldest baseline)."
            replacement = {"role": "assistant", "content": "[History reduction]\n" +
                           dumps({"task_status": self.task_status, "summary": summary})}
            first = min(indices)
            with self.lock:
                self.history = [message for i, message in enumerate(self.history) if i not in indices]
                self.history.insert(first, replacement)
            after = self.measure(self.payload())
            self.emit("context_reduction", {"policy": self.config["reduction"], "removed": removed,
                "replacement": replacement, "before": before, "after": after,
                "objective_preserved_verbatim": self.history[0]["content"] == self.objective})
            if after["total"] >= before["total"]:
                raise RunStop("History reduction made no token progress; run stopped without a hidden reset.")
        raise RunStop("History-reduction limit reached.")

    def run(self, prompt=None, sink=None, resume=False):
        if not resume and (not isinstance(prompt, str) or not prompt.strip()):
            raise ValueError("A nonempty user request is required.")
        with self.lock:
            if self.running:
                raise ValueError("Session already running.")
            if resume and (not self.history or self.status in {"answered", "completed"}):
                raise ValueError("No unfinished objective to resume.")
            if not resume and self.config["workflow"] == "document" and self.history:
                raise ValueError("Use Resume for this document or create a new session for another objective.")
            self.running, self.status, self.sink = True, "running", sink
        self.cancel.clear()
        self.document_elapsed = self.document["elapsed_seconds"] if self.document else 0
        self.document_started = time.monotonic() if self.config["workflow"] == "document" else None
        self.deadline = time.monotonic() + self.config["max_seconds"] - self.document_elapsed
        try:
            if self.config["capture"]:
                self.capture = Capture(self.config["capture_directory"], self.id, self.api_key)
            self.emit("run_started", {"config": self.config,
                "remaining_seconds": max(0, self.deadline - time.monotonic()), "resumed": resume,
                "capture_path": str(self.capture.path) if self.capture else None})
            self.check()
            try:
                slots = self.transport.json(self.transport.root_path + "/slots",
                                             deadline=min(self.deadline, time.monotonic() + 2))
                if not isinstance(slots, list) or not slots:
                    raise ValueError("No slot context metadata.")
                self.physical_context = slots[0]["n_ctx"]
                if type(self.physical_context) is not int:
                    raise ValueError("Invalid physical context metadata.")
            except (ModelError, KeyError, TypeError, ValueError) as error:
                self.emit("physical_context_unavailable", {"reason": str(error)})
            if self.physical_context and self.config["context"] > self.physical_context:
                raise RunStop("Configured session context exceeds observed physical server context.")
            if not resume:
                if not self.history:
                    self.objective = prompt
                self.append({"role": "user", "content": prompt})
                self.emit("user_message", {"text": prompt})
            if self.config["workflow"] == "document":
                DocumentWorkflow(self).run()
                return
            repeated = {}
            for iteration in range(self.config["max_iterations"]):
                self.check()
                self.fit()
                message = self.call_model(self.payload())
                message = {key: value for key, value in message.items()
                           if key in {"role", "content", "tool_calls"}}
                message["role"] = "assistant"
                calls = message.get("tool_calls", [])
                if calls:
                    results = [{"role": "tool", "tool_call_id": call.get("id"), "content": "{}"} for call in calls
                               if isinstance(call, dict)]
                    validate_history([message] + results)
                self.append(message)
                self.emit("assistant_message", message)
                if not calls:
                    if not self.config["explicit_completion"]:
                        self.status = "answered"
                        return
                    self.emit("completion_required", {"message": "Ordinary answer received; task_complete is required."})
                    self.append({"role": "user", "content": "Explicit completion remains enabled. Finish with task_complete when done."})
                    continue
                finished, blocked = False, False
                for call in calls:
                    started = time.monotonic()
                    name = call["function"]["name"]
                    args = None
                    try:
                        if finished or blocked:
                            raise ToolError("Not executed because this response already completed or stopped the task.")
                        self.check()
                        if name not in self.config["tools"]:
                            raise ToolError(f"Tool is disabled or unknown: {name}")
                        args = json.loads(call["function"]["arguments"])
                        identity = (name, dumps(args))
                        repeated[identity] = repeated.get(identity, 0) + 1
                        if repeated[identity] > self.config["repeat_limit"]:
                            blocked = True
                            raise ToolError("Repeated-identical-tool-call threshold reached.")
                        self.emit("tool_call", {"name": name, "arguments": args})
                        full = execute(name, args, self.config, self.check)
                        if self.capture:
                            self.capture.save(f"{self.request_number:04d}-tool-{uuid.uuid4().hex}.json",
                                              dumps(full).encode("utf-8"))
                        result, text = bound_result(full, self.config["limits"][name], self.meter.count)
                        if result.get("complete"):
                            finished = True
                    except (ToolError, ValueError, OSError) as error:
                        result, text = bound_result({"error": str(error)},
                            self.config["limits"].get(name, {"max_bytes": 512, "max_tokens": 128}),
                            self.meter.count)
                    self.append({"role": "tool", "tool_call_id": call["id"], "content": text})
                    self.task_status = dumps({"last_tool": name, "result": {key: result[key] for key in
                        ("error", "total", "returned", "truncated", "replacements", "complete") if key in result}})
                    self.emit("tool_result", {"name": name, "arguments": args, "result": result,
                        "tokens": self.meter.count(text), "tokenizer_exact": self.meter.tokenizer is True,
                        "elapsed_seconds": time.monotonic() - started})
                if finished:
                    self.status = "completed"
                    self.emit("task_complete", {"summary": next(json.loads(m["content"])["summary"]
                        for m in reversed(self.history) if m["role"] == "tool"
                        and json.loads(m["content"]).get("complete"))})
                    return
                if blocked:
                    raise RunStop("Repeated-identical-tool-call threshold reached.")
            self.pause("Agent iteration limit reached; Resume continues the same objective.")
        except (RunStop, ModelError, ValueError, OSError) as error:
            expired = self.deadline is not None and time.monotonic() >= self.deadline
            paused = isinstance(error, RunPause) or expired or (
                self.document is not None and self.cancel.is_set())
            self.status = "paused" if paused else (
                "stopped" if self.cancel.is_set() or isinstance(error, (RunStop, OutputLimitError)) else "error")
            if isinstance(error, OSError) and self.capture:
                self.capture = None
            self.emit("run_paused" if paused else "run_error",
                      {"message": str(error), "status": self.status, "resumable": bool(self.history)})
        finally:
            pending = {}
            for item in self.history:
                if item["role"] == "assistant":
                    pending.update({call["id"]: call for call in item.get("tool_calls", [])})
                elif item["role"] == "tool":
                    pending.pop(item["tool_call_id"], None)
            for identity in pending:
                self.append({"role": "tool", "tool_call_id": identity,
                             "content": dumps({"error": "Not executed: run stopped."})})
            if self.document is not None:
                if self.document_started is not None:
                    self.document["elapsed_seconds"] = self.document_elapsed + time.monotonic() - self.document_started
                self.document_started = None
                try:
                    self.checkpoint_document()
                except (ValueError, OSError) as error:
                    self.status = "error"
                    self.emit("run_error", {"message": f"Checkpoint save failed: {error}", "status": self.status})
            self.document_started = None
            self.running, self.deadline = False, None
            self.emit("run_finished", {"status": self.status, "task_status": self.task_status})
            self.sink = None
