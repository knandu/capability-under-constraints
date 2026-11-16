import http.client
import ipaddress
import io
import json
import math
import select
import time
from urllib.parse import urlsplit

from tools import dumps


class ModelError(RuntimeError):
    pass


class DeadlineReader(io.RawIOBase):
    def __init__(self, stream, deadline, check):
        self.stream, self.deadline, self.check = stream, deadline, check

    def readable(self):
        return True

    def readinto(self, buffer):
        while True:
            self.check()
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise ModelError("Elapsed-time limit reached.")
            if (getattr(self.stream, "pending", lambda: 0)() or
                    select.select([self.stream], [], [], min(.1, remaining))[0]):
                return self.stream.recv_into(buffer)

    def close(self):
        self.stream.close()
        super().close()


class ResponseSocket:
    def __init__(self, stream, deadline, check):
        self.stream, self.deadline, self.check = stream, deadline, check

    def makefile(self, mode):
        return io.BufferedReader(DeadlineReader(self.stream, self.deadline, self.check))


def endpoint_parts(base_url):
    try:
        url = urlsplit(base_url)
        port = url.port
    except ValueError as error:
        raise ModelError("Invalid model URL.") from error
    if (url.scheme not in {"http", "https"} or url.hostname not in {"localhost", "127.0.0.1", "::1"}
            or url.username or url.password or url.query or url.fragment):
        raise ModelError("Model URL must be loopback HTTP(S), without credentials, query, or fragment.")
    return url, port


class Transport:
    def __init__(self, base_url, api_key="", active_socket=None, check=lambda: None):
        self.url, self.port = endpoint_parts(base_url)
        self.api_key = api_key
        self.active_socket = active_socket or (lambda value: None)
        self.check = check
        self.base_path = self.url.path.rstrip("/") or "/v1"
        self.root_path = self.base_path[:-3] if self.base_path.endswith("/v1") else ""

    def request(self, path, payload=None, deadline=None, line_callback=None, raw_callback=None):
        deadline = deadline or time.monotonic() + 5
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ModelError("Elapsed-time limit reached.")
        connection_class = http.client.HTTPSConnection if self.url.scheme == "https" else http.client.HTTPConnection
        connection = connection_class(self.url.hostname, self.port, timeout=min(remaining, 5))
        body = dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json", "Content-Type": "application/json; charset=utf-8"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        raw = bytearray()
        owned = []
        response = None

        def response_class(stream, *args, **kwargs):
            reader_socket = stream
            # The response reader owns the socket, including Connection: close and TLS.
            connection.sock = None
            owned.append(reader_socket)
            self.active_socket(reader_socket)
            return http.client.HTTPResponse(ResponseSocket(reader_socket, deadline, self.check), *args, **kwargs)

        connection.response_class = response_class
        try:
            connection.connect()
            active = connection.sock
            if not ipaddress.ip_address(active.getpeername()[0]).is_loopback:
                raise ModelError("Model connection did not resolve to loopback.")
            self.active_socket(active)
            active.settimeout(max(0.01, deadline - time.monotonic()))
            connection.request("POST" if body is not None else "GET", path, body=body, headers=headers)
            response = connection.getresponse()
            streaming = line_callback and "text/event-stream" in response.getheader("Content-Type", "")
            while not response.isclosed():
                chunk = response.readline(4 * 1024 * 1024 + 1) if streaming else response.read1(65536)
                if not chunk:
                    break
                raw.extend(chunk)
                if len(raw) > 16 * 1024 * 1024:
                    raise ModelError("Model response exceeded the 16 MiB instrument limit.")
                if time.monotonic() > deadline:
                    raise ModelError("Elapsed-time limit reached.")
                if streaming:
                    line_callback(chunk)
            if response.status >= 300:
                raise ModelError(f"Model HTTP {response.status}: {raw[:1000].decode('utf-8', errors='replace')}")
            if streaming:
                return bytes(raw), None
            try:
                return bytes(raw), json.loads(raw)
            except (ValueError, UnicodeDecodeError) as error:
                raise ModelError("Model returned invalid UTF-8/JSON.") from error
        except (OSError, http.client.HTTPException) as error:
            raise ModelError(f"Model endpoint unavailable, interrupted, or timed out: {error}") from error
        finally:
            self.active_socket(None)
            connection.close()
            if response:
                response.close()
            for stream in owned:
                stream.close()
            if raw_callback:
                raw_callback(bytes(raw))

    def json(self, path, payload=None, deadline=None):
        return self.request(path, payload, deadline)[1]

    def chat(self, payload, deadline, delta, raw_response):
        content, calls, usage, timings = [], {}, None, None
        last_event, done = None, False
        self.finish_reason = None

        def consume(line):
            nonlocal usage, timings, last_event, done
            if not line.startswith(b"data:"):
                return
            data = line[5:].strip()
            if data == b"[DONE]":
                done = True
                return
            if not data:
                return
            try:
                event = json.loads(data)
            except (ValueError, UnicodeDecodeError) as error:
                raise ModelError("Malformed SSE JSON.") from error
            last_event = event
            if not isinstance(event, dict) or not isinstance(event.get("choices", []), list):
                raise ModelError("Malformed model stream envelope.")
            if "error" in event:
                raise ModelError("Model stream error: " + dumps(event["error"]))
            usage, timings = event.get("usage") or usage, event.get("timings") or timings
            for choice in event.get("choices", []):
                if not isinstance(choice, dict):
                    raise ModelError("Malformed model choice.")
                if choice.get("finish_reason"):
                    self.finish_reason = choice["finish_reason"]
                part = choice.get("delta", {})
                if not isinstance(part, dict) or not isinstance(part.get("tool_calls", []), list):
                    raise ModelError("Malformed streamed delta or tool-call list.")
                if part.get("content"):
                    if not isinstance(part["content"], str):
                        raise ModelError("Assistant content must be text.")
                    content.append(part["content"])
                    delta(part["content"])
                for fragment in part.get("tool_calls", []):
                    if not isinstance(fragment, dict) or type(fragment.get("index")) is not int:
                        raise ModelError("Tool-call stream omitted its index.")
                    call = calls.setdefault(fragment["index"], {"id": "", "type": "function",
                        "function": {"name": "", "arguments": ""}})
                    if fragment.get("id"):
                        call["id"] = fragment["id"]
                    function = fragment.get("function", {})
                    if not isinstance(function, dict):
                        raise ModelError("Malformed tool-call function.")
                    for field in ("name", "arguments"):
                        value = function.get(field, "")
                        if not isinstance(value, str):
                            raise ModelError("Streamed tool names and arguments must be strings.")
                        call["function"][field] += value

        raw, response = self.request(self.base_path + "/chat/completions", payload, deadline, consume,
            lambda data: raw_response(data, {"content": "".join(content), "tool_calls": list(calls.values())}))
        if response is not None:
            if (not isinstance(response, dict) or not isinstance(response.get("choices"), list)
                    or not response["choices"]):
                raise ModelError("Model response omitted choices.")
            choice = response["choices"][0]
            if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
                raise ModelError("Malformed assistant message.")
            message = choice["message"]
            self.finish_reason = choice.get("finish_reason")
            if not isinstance(message, dict) or (message.get("content") is not None and not isinstance(message["content"], str)):
                raise ModelError("Malformed assistant message.")
            if not message.get("content") and not message.get("tool_calls"):
                raise ModelError("Model returned no assistant content or tool calls.")
            if message.get("content"):
                delta(message["content"])
            return message, response.get("usage"), response.get("timings"), response
        if not done:
            raise ModelError("SSE ended without [DONE]; partial output was not committed to history.")
        message = {"role": "assistant", "content": "".join(content) or None}
        if calls:
            message["tool_calls"] = [calls[index] for index in sorted(calls)]
        if not content and not calls:
            raise ModelError("Model returned no assistant content or tool calls.")
        return message, usage, timings, last_event


class Meter:
    def __init__(self, transport, notice, deadline=lambda: None):
        self.transport, self.notice = transport, notice
        self.deadline = deadline
        self.tokenizer, self.template, self.cache = None, None, {}

    def count(self, text):
        if text in self.cache:
            return self.cache[text]
        if self.tokenizer is not False:
            try:
                data = self.transport.json(self.transport.root_path + "/tokenize",
                    {"content": text, "add_special": False, "parse_special": True}, self.deadline())
                value = len(data["tokens"])
                self.tokenizer = True
            except (ModelError, KeyError, TypeError) as error:
                self.tokenizer = False
                self.notice("tokenizer_unavailable", {"reason": str(error),
                    "fallback": "UTF-8 bytes / 3, rounded up; framing estimated"})
                value = math.ceil(len(text.encode("utf-8")) / 3)
        else:
            value = math.ceil(len(text.encode("utf-8")) / 3)
        if len(self.cache) >= 1024:
            self.cache.clear()
        self.cache[text] = value
        return value

    def measure(self, payload, current_user=None):
        parts = dict.fromkeys(("system", "user_history", "assistant_history", "tool_results",
                               "summaries", "current_request", "tool_schemas"), 0)
        for index, message in enumerate(payload["messages"]):
            content = message.get("content") or ""
            if message.get("tool_calls"):
                content += dumps(message["tool_calls"])
            if message["role"] == "system":
                key = "system"
            elif index == current_user:
                key = "current_request"
            elif message["role"] == "user":
                key = "user_history"
            elif message["role"] == "tool":
                key = "tool_results"
            elif content.startswith("[History reduction]"):
                key = "summaries"
            else:
                key = "assistant_history"
            parts[key] += self.count(content)
        parts["tool_schemas"] = self.count(dumps(payload["tools"])) if payload.get("tools") else 0
        total, exact = sum(parts.values()), False
        if self.tokenizer and self.template is not False:
            try:
                rendered = self.transport.json(self.transport.root_path + "/apply-template", payload, self.deadline())["prompt"]
                measured = self.count(rendered)
                if self.tokenizer:
                    total, exact, self.template = measured, True, True
            except (ModelError, KeyError, TypeError) as error:
                self.template = False
                self.notice("template_unavailable", {"reason": str(error)})
        if not exact:
            total += 64 + 16 * len(payload["messages"]) + 64 * len(payload.get("tools", []))
        return {"parts": parts, "total": total, "framing_and_boundary_delta": total - sum(parts.values()),
                "total_exact": exact, "component_tokenizer_exact": self.tokenizer is True,
                "note": "Standalone component counts are not additive template marginal costs."}
