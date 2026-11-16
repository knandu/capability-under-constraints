import contextlib
import copy
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Capture, Session, configuration, defaults, validate_history
from harness import HarnessServer
from tools import SCHEMAS, ToolError, bound_result, dumps, execute
from transport import ModelError, Transport


TAMIL = "\u0ba4\u0bae\u0bbf\u0bb4\u0bcd \u0bae\u0bca\u0bb4\u0bbf: \u0bb5\u0ba3\u0b95\u0bcd\u0b95\u0bae\u0bcd!"


def rendered(payload):
    return dumps(payload.get("tools", [])) + "".join(
        "[" + message["role"] + "]" + dumps(message) for message in payload["messages"])


def tool(name, arguments, identity="call-1"):
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": identity, "type": "function", "function": {"name": name, "arguments": dumps(arguments)}}]}


class FakeModel(ThreadingHTTPServer):
    def __init__(self, replies, streaming=True, extras=True):
        super().__init__(("127.0.0.1", 0), FakeHandler)
        self.replies, self.streaming, self.extras = list(replies), streaming, extras
        self.requests, self.headers_seen = [], []
        self.url = f"http://127.0.0.1:{self.server_port}/v1"
        self.delay = 0


class FakeHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_json(self, value, status=200):
        data = dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.send_json([{"n_ctx": 32768}] if self.path == "/slots" and self.server.extras else {},
                       200 if self.server.extras else 404)

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        payload = json.loads(body)
        if self.path == "/tokenize":
            return self.send_json({"tokens": list(range(len(payload["content"].encode("utf-8"))))},
                                  200 if self.server.extras else 404)
        if self.path == "/apply-template":
            return self.send_json({"prompt": rendered(payload)}, 200 if self.server.extras else 404)
        self.server.requests.append(payload)
        self.server.headers_seen.append(self.headers.get("Authorization"))
        message = self.server.replies.pop(0) if self.server.replies else {"role": "assistant", "content": "done"}
        if callable(message):
            message = message(payload)
        usage = {"prompt_tokens": len(rendered(payload).encode("utf-8")), "completion_tokens": 10}
        if message == "malformed-envelope":
            return self.send_json({"choices": [{}]})
        if not self.server.streaming:
            return self.send_json({"choices": [{"message": message, "finish_reason": "stop"}], "usage": usage})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.end_headers()
        if self.server.delay:
            time.sleep(self.server.delay)
        if message == "malformed":
            self.wfile.write(b"data: not json\n\n")
            return
        if message == "incomplete":
            self.wfile.write(b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n')
            return
        if message == "malformed-function":
            self.wfile.write(b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":null}]}}]}\n\n')
            return
        events = []
        if message.get("content"):
            for character in message["content"]:
                events.append({"choices": [{"delta": {"content": character}}]})
        for index, call in enumerate(message.get("tool_calls", [])):
            events.append({"choices": [{"delta": {"tool_calls": [
                {"index": index, "id": call["id"], "type": "function",
                 "function": {"name": call["function"]["name"], "arguments": ""}}]}}]})
            arguments = call["function"]["arguments"]
            midpoint = len(arguments) // 2
            for part in (arguments[:midpoint], arguments[midpoint:]):
                events.append({"choices": [{"delta": {"tool_calls": [
                    {"index": index, "function": {"arguments": part}}]}}]})
        events.append({"choices": [{"delta": {}, "finish_reason": message.get("finish_reason", "stop")}],
                       "usage": usage, "timings": {"predicted_per_second": 12}})
        try:
            for event in events:
                data = ("data: " + dumps(event) + "\n\n").encode("utf-8")
                midpoint = len(data) // 2
                self.wfile.write(data[:midpoint])
                self.wfile.flush()
                self.wfile.write(data[midpoint:])
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


@contextlib.contextmanager
def serving(server):
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.config = defaults()
        self.config.update({"working_root": str(self.root), "capture_directory": str(self.root / "captures")})

    def tearDown(self):
        self.temporary.cleanup()

    def session(self, model, **changes):
        return Session({**self.config, "base_url": model.url, **changes})

    def run_tool(self, name, args):
        return execute(name, args, configuration(self.config), lambda: None)

    def test_browser_conversation_timestamps_durations_and_import(self):
        edge = Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        if not edge.is_file():
            self.skipTest("Microsoft Edge is unavailable for the optional DOM check.")
        static = Path(__file__).resolve().parents[1] / "static"
        page = (static / "index.html").read_bytes().replace(
            b'<script src="/app.js" defer></script>',
            b'<script src="/app.js" defer></script><script src="/browser-check.js" defer></script>')
        routes = {"/": page, "/app.js": (static / "app.js").read_bytes(),
                  "/style.css": (static / "style.css").read_bytes(),
                  "/api/defaults": dumps(self.config).encode("utf-8"),
                  "/browser-check.js": Path(__file__).with_name("browser_timing.js").read_bytes()}

        class BrowserHandler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                data = routes.get(self.path, b"")
                self.send_response(200 if self.path in routes else 404)
                self.send_header("Content-Length", str(len(data)))
                mime = "text/javascript" if self.path.endswith(".js") else "text/css" if self.path.endswith(".css") else "text/html"
                self.send_header("Content-Type", mime + "; charset=utf-8")
                self.end_headers()
                self.wfile.write(data)

        with serving(ThreadingHTTPServer(("127.0.0.1", 0), BrowserHandler)) as server:
            result = subprocess.run([str(edge), "--headless=new", "--disable-gpu",
                "--no-first-run", "--no-default-browser-check", "--disable-background-networking",
                f"--user-data-dir={self.root / 'browser-profile'}", "--virtual-time-budget=3000",
                "--dump-dom", f"http://127.0.0.1:{server.server_port}/"],
                capture_output=True, encoding="utf-8", errors="replace", timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('data-browser-check="passed"', result.stdout, result.stdout)

    def test_high_cardinality_glob_and_byte_token_limits(self):
        for number in range(656):
            (self.root / f"item-{number:04}.txt").write_text("needle " + TAMIL, encoding="utf-8")
        result = self.run_tool("glob", {"pattern": "*.txt"})
        self.assertEqual((result["total"], result["returned"], len(result["items"])), (656, 50, 50))
        self.assertTrue(result["truncated"])
        bounded, text = bound_result(result, {"max_bytes": 512, "max_tokens": 320}, lambda s: len(s))
        self.assertLessEqual(len(text.encode("utf-8")), 512)
        self.assertLessEqual(len(text), 320)
        self.assertEqual(bounded["total"], 656)
        self.assertLess(bounded["returned"], 50)
        grep = self.run_tool("grep", {"pattern": "needle", "file_glob": "*.txt"})
        self.assertEqual((grep["total"], grep["returned"]), (656, 50))

    def test_view_lines_directory_binary_and_utf8_boundary(self):
        path = self.root / "text.txt"
        path.write_text("first\n" + TAMIL + "\nthird\n", encoding="utf-8")
        result = self.run_tool("view", {"path": "text.txt", "start": 2, "end": 2})
        self.assertEqual(result["items"], [{"line": 2, "text": TAMIL}])
        self.assertEqual(self.run_tool("view", {"path": "."})["total"], 1)
        (self.root / "binary").write_bytes(b"abc\0xyz")
        with self.assertRaisesRegex(ToolError, "Binary"):
            self.run_tool("view", {"path": "binary"})
        self.config["read_bytes"] = 10
        result = self.run_tool("view", {"path": "text.txt"})
        self.assertTrue(result["truncated"])
        self.assertIsNone(result["total"])

    def test_exact_edit_preserves_bom_crlf_unicode_and_unrelated_bytes(self):
        path = self.root / "edit.txt"
        before = b"\xef\xbb\xbfheader\r\nvalue=old\r\n" + TAMIL.encode("utf-8") + b"\r\n"
        path.write_bytes(before)
        self.run_tool("edit", {"path": "edit.txt", "old": "value=old", "new": "value=new", "dry_run": True})
        self.assertEqual(path.read_bytes(), before)
        self.run_tool("edit", {"path": "edit.txt", "old": "value=old", "new": "value=new"})
        self.assertEqual(path.read_bytes(), before.replace(b"value=old", b"value=new"))
        with self.assertRaisesRegex(ToolError, "0 times"):
            self.run_tool("edit", {"path": "edit.txt", "old": "absent", "new": "x"})
        path.write_text("x x", encoding="utf-8")
        with self.assertRaisesRegex(ToolError, "2 times"):
            self.run_tool("edit", {"path": "edit.txt", "old": "x", "new": "y"})

    def test_traversal_absolute_escape_and_symlink_escape(self):
        for name in ("view", "glob", "grep", "edit"):
            args = {"path": "..", "pattern": "*", "old": "x", "new": "y"}
            args = {key: value for key, value in args.items()
                    if key in SCHEMAS[name]["function"]["parameters"]["properties"]}
            with self.assertRaisesRegex(ToolError, "outside"):
                self.run_tool(name, args)
        with self.assertRaises(ToolError):
            self.run_tool("view", {"path": "\\\\server\\share"})
        with tempfile.TemporaryDirectory() as outside:
            try:
                (self.root / "link").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("OS does not grant symlink creation permission.")
            with self.assertRaisesRegex(ToolError, "outside"):
                self.run_tool("view", {"path": "link"})

    def test_glob_depth_and_grep_literal_case(self):
        nested = self.root / "one" / "two"
        nested.mkdir(parents=True)
        (nested / "deep.txt").write_text("A+B\nAAB\n", encoding="utf-8")
        self.assertEqual(self.run_tool("glob", {"pattern": "**/*.txt", "max_depth": 1})["total"], 0)
        self.assertEqual(self.run_tool("glob", {"pattern": "**/*.txt", "max_depth": 3})["total"], 1)
        self.assertEqual(self.run_tool("grep", {"pattern": "a+b", "case_sensitive": False})["total"], 1)

    def test_streamed_unicode_normal_answer_and_raw_capture_off(self):
        with serving(FakeModel([{"role": "assistant", "content": TAMIL}])) as model:
            session = self.session(model)
            session.run(TAMIL)
            self.assertEqual(session.status, "answered")
            self.assertEqual(session.history[-1]["content"], TAMIL)
            self.assertEqual(model.requests[0]["messages"][-1]["content"], TAMIL)
            self.assertFalse((self.root / "captures").exists())
            response = next(event["data"] for event in session.events if event["type"] == "model_response")
            self.assertEqual(response["input_discrepancy"], 0)
            self.assertEqual(json.loads(dumps(session.snapshot()))["transcript"][-1]["content"], TAMIL)

    def test_json_response_and_exact_capture_auth_exclusion(self):
        with serving(FakeModel([{"role": "assistant", "content": TAMIL}], streaming=False)) as model:
            session = Session({**self.config, "base_url": model.url, "capture": True}, "private-model-test-key")
            session.run(TAMIL)
            self.assertEqual(model.headers_seen, ["Bearer private-model-test-key"])
            path = session.capture.path
            self.assertEqual((path / "0001-agent-request.json").read_bytes(),
                             dumps(model.requests[0]).encode("utf-8"))
            self.assertIn(TAMIL.encode("utf-8"), (path / "0001-agent-response.body").read_bytes())
            for file in path.iterdir():
                self.assertNotIn(b"private-model-test-key", file.read_bytes())
            self.assertEqual((path / ".gitignore").read_text(), "*\n")
            self.assertEqual(session.status, "answered")

    def test_fragmented_echoed_api_key_is_excluded_from_saved_data(self):
        secret = "private-model-test-key"
        with serving(FakeModel([{"role": "assistant", "content": secret + TAMIL}])) as model:
            session = Session({**self.config, "base_url": model.url, "capture": True}, secret)
            session.run("hello")
            self.assertEqual(session.status, "answered")
            self.assertNotIn(secret, dumps(session.snapshot()))
            self.assertFalse(any(event["type"] == "assistant_delta" for event in session.events))
            for file in session.capture.path.iterdir():
                self.assertNotIn(secret.encode("utf-8"), file.read_bytes())
            self.assertTrue((session.capture.path / "redaction-note.txt").is_file())

    def test_empty_json_and_streaming_answers_fail_explicitly(self):
        for streaming in (False, True):
            with self.subTest(streaming=streaming), serving(FakeModel([
                    {"role": "assistant", "content": None}], streaming=streaming)) as model:
                session = self.session(model)
                session.run("hello")
                self.assertEqual(session.status, "error")
                self.assertTrue(any(event["type"] == "run_error" for event in session.events))
                self.assertEqual(len(session.history), 1)

    def test_capture_network_directories_are_rejected(self):
        with self.assertRaises(ValueError):
            configuration({**self.config, "capture": True, "capture_directory": "\\\\server\\share"})
        if os.name == "nt":
            with patch("ctypes.windll.kernel32.GetDriveTypeW", side_effect=[3, 4]):
                with self.assertRaisesRegex(ValueError, "Mapped network capture"):
                    configuration({**self.config, "capture": True})

    def test_explicit_completion_stops_without_continuation_or_later_edit(self):
        (self.root / "x").write_text("old", encoding="utf-8")
        complete = tool("task_complete", {"summary": TAMIL})
        complete["tool_calls"] += tool("edit", {"path": "x", "old": "old", "new": "new"}, "call-2")["tool_calls"]
        with serving(FakeModel([complete])) as model:
            session = self.session(model, explicit_completion=True)
            session.run("finish")
            self.assertEqual(session.status, "completed")
            self.assertEqual(len(model.requests), 1)
            self.assertEqual((self.root / "x").read_text(), "old")
            validate_history(session.history)

    def test_tool_ablation_removes_schemas_guidance_and_cost_and_rejects_call(self):
        with serving(FakeModel([tool("glob", {"pattern": "*"}), {"role": "assistant", "content": "done"}])) as model:
            sizes = []
            for enabled in (["view"], ["view", "grep"], ["view", "grep", "glob"]):
                session = self.session(model, tools=enabled)
                inspection = session.inspect()
                sizes.append(inspection["accounting"]["total"])
                self.assertEqual(set(inspection["tool_schema_tokens"]), set(enabled))
                for disabled in set(SCHEMAS) - set(enabled):
                    self.assertNotIn(disabled + ":", inspection["effective_system_prompt"])
            self.assertTrue(sizes[0] < sizes[1] < sizes[2])
            session = self.session(model, tools=["view"])
            session.run("observe")
            results = [json.loads(message["content"]) for message in session.history if message["role"] == "tool"]
            self.assertIn("disabled", results[0]["error"])
            self.assertEqual([x["function"]["name"] for x in model.requests[0]["tools"]], ["view"])

    def test_repeat_and_iteration_limits(self):
        replies = [tool("view", {"path": "."}, f"call-{i}") for i in range(4)]
        with serving(FakeModel(replies)) as model:
            session = self.session(model, repeat_limit=2)
            session.run("observe")
            self.assertIn("Repeated", session.events[-2]["data"]["message"])
            self.assertEqual(len(model.requests), 3)
            validate_history(session.history)
        with serving(FakeModel([{"role": "assistant", "content": "not complete"}])) as model:
            session = self.session(model, explicit_completion=True, max_iterations=1)
            session.run("finish")
            self.assertEqual(session.status, "stopped")
            self.assertIn("iteration", session.events[-2]["data"]["message"])

    def history_fixture(self, session):
        session.objective = "Original objective " + TAMIL
        session.history = [{"role": "user", "content": session.objective}]
        for number in range(6):
            session.history.extend([
                {"role": "assistant", "content": f"observation-{number} " + "x" * 1700},
            ])
        session.task_status = "Known unfinished work."
        session.history.append({"role": "user", "content": "Continue original objective."})

    def test_artificial_8k_vs_16k_and_truncate_oldest(self):
        with serving(FakeModel([])) as model:
            small = self.session(model, context=8192, max_input=7168, max_output=1024, tools=[])
            large = self.session(model, context=16384, max_input=15360, max_output=1024, tools=[])
            for session in (small, large):
                self.history_fixture(session)
                session.fit()
                self.assertLessEqual(session.measure(session.payload())["total"], session.config["max_input"])
                self.assertEqual(session.history[0]["content"], session.objective)
            self.assertTrue(any(event["type"] == "context_reduction" for event in small.events))
            self.assertFalse(any(event["type"] == "context_reduction" for event in large.events))
            reduction = next(event["data"] for event in small.events if event["type"] == "context_reduction")
            self.assertIn("Known unfinished work.", reduction["replacement"]["content"])
            self.assertTrue(reduction["removed"])
            self.assertNotEqual(small.payload(), large.payload())

    def test_summary_is_visible_budgeted_and_preserves_original_objective(self):
        with serving(FakeModel([{"role": "assistant", "content": "Prior observations; more work remains."}])) as model:
            session = self.session(model, context=8192, max_input=7168, max_output=1024,
                                   tools=[], reduction="summarize-oldest")
            self.history_fixture(session)
            session.deadline = time.monotonic() + 10
            session.fit()
            self.assertTrue(any(event["type"] == "model_request" and event["data"]["kind"] == "summary"
                                for event in session.events))
            self.assertEqual(session.history[0]["content"], session.objective)
            self.assertTrue(all(not payload.get("tools") for payload in model.requests))
            self.assertLessEqual(session.measure(session.payload())["total"], 7168)

    def test_unreducible_context_malformed_and_truncated_stream(self):
        for response, text in (("malformed", "Malformed SSE"), ("incomplete", "without [DONE]"),
                               ("malformed-function", "Malformed tool-call function"),
                               ("malformed-envelope", "Malformed assistant message")):
            with serving(FakeModel([response])) as model:
                session = self.session(model)
                session.run("hello")
                self.assertEqual(session.status, "error")
                self.assertIn(text, next(event["data"]["message"] for event in session.events if event["type"] == "run_error"))
                self.assertEqual(len(session.history), 1)
        with serving(FakeModel([])) as model:
            session = self.session(model, tools=[], context=1000, max_input=900, max_output=100)
            session.run("objective " * 200)
            self.assertEqual(session.status, "stopped")
            self.assertFalse(model.requests)

    def test_elapsed_limit_and_cancellation(self):
        with serving(FakeModel([{"role": "assistant", "content": "late"}])) as model:
            model.delay = 2
            session = self.session(model, max_seconds=1)
            start = time.monotonic()
            session.run("hello")
            self.assertLess(time.monotonic() - start, 1.8)
            self.assertNotEqual(session.status, "answered")
        with serving(FakeModel([{"role": "assistant", "content": "late"}])) as model:
            model.delay = 2
            session = self.session(model)
            worker = threading.Thread(target=session.run, args=("hello",))
            worker.start()
            deadline = time.monotonic() + 3
            while not model.requests and time.monotonic() < deadline:
                time.sleep(.01)
            session.stop()
            worker.join(1)
            self.assertFalse(worker.is_alive())
            self.assertEqual(session.status, "stopped")

    def test_estimates_and_configuration_change_are_explicit(self):
        with serving(FakeModel([], extras=False)) as model:
            session = self.session(model)
            account = session.inspect()["accounting"]
            self.assertFalse(account["total_exact"])
            self.assertFalse(account["component_tokenizer_exact"])
            self.assertTrue(any(event["type"] == "tokenizer_unavailable" for event in session.events))
            session.update({"tools": ["view"]})
            self.assertEqual(session.events[-1]["type"], "configuration_changed")
        for bad in ({"context": 100}, {"max_seconds": True}, {"temperature": float("nan")},
                    {"tools": ["shell"]}, {"tools": ["view"], "explicit_completion": True},
                    {"base_url": "https://example.com/v1"}, {"base_url": "http://secret@localhost/v1"}):
            with self.assertRaises((ValueError, ModelError)):
                configuration({**self.config, **bad})

    def test_literature_request_has_no_content_filter(self):
        passage = "Public-domain study: Macbeth describes a murder. Analyze guilt, imagery and tragedy."
        with serving(FakeModel([{"role": "assistant", "content": "The scene connects guilt and ambition."}])) as model:
            session = self.session(model, tools=[])
            session.run(passage)
            self.assertEqual(model.requests[0]["messages"][-1]["content"], passage)
            self.assertEqual(session.status, "answered")

    def test_http_utf8_import_export_origin_and_static_page(self):
        with serving(FakeModel([{"role": "assistant", "content": TAMIL}])) as model, \
             serving(HarnessServer(("127.0.0.1", 0))) as app:
            connection = http.client.HTTPConnection("127.0.0.1", app.server_port, timeout=10)

            def post(path, value, origin=None):
                headers = {"Content-Type": "application/json"}
                if origin:
                    headers["Origin"] = origin
                connection.request("POST", path, dumps(value).encode("utf-8"), headers)
                response = connection.getresponse()
                return response.status, response.read()

            status, body = post("/api/sessions", {"config": {**self.config, "base_url": model.url}})
            self.assertEqual(status, 201)
            identity = json.loads(body)["id"]
            status, stream = post(f"/api/sessions/{identity}/run", {"prompt": TAMIL})
            self.assertEqual(status, 200)
            self.assertIn(TAMIL.encode("utf-8"), stream)
            connection.close()
            connection = http.client.HTTPConnection("127.0.0.1", app.server_port)
            connection.request("GET", f"/api/sessions/{identity}")
            snapshot = json.loads(connection.getresponse().read())
            self.assertEqual(snapshot["history"][0]["content"], TAMIL)
            status, body = post("/api/import", snapshot)
            self.assertEqual(status, 201)
            self.assertEqual(json.loads(body)["history"][-1]["content"], TAMIL)
            self.assertFalse(json.loads(body)["config"]["capture"])
            status, _ = post("/api/sessions", {"config": self.config}, "https://example.com")
            self.assertEqual(status, 400)
            connection.request("GET", "/")
            response = connection.getresponse()
            self.assertIn("charset=utf-8", response.getheader("Content-Type"))
            self.assertIn(b'<meta charset="utf-8">', response.read())
            connection.close()

    def test_startup_model_defaults_apply_to_ui_and_new_sessions(self):
        with serving(FakeModel([{"role": "assistant", "content": "ready"}])) as model, \
             serving(HarnessServer(("127.0.0.1", 0), default_overrides={
                 "base_url": model.url, "model": "deployment-model"})) as app:
            connection = http.client.HTTPConnection("127.0.0.1", app.server_port, timeout=10)
            connection.request("GET", "/api/defaults")
            value = json.loads(connection.getresponse().read())
            self.assertEqual(value["base_url"], model.url)
            self.assertEqual(value["model"], "deployment-model")
            connection.request("POST", "/api/sessions", dumps({"config": {
                "working_root": str(self.root), "tools": []}}).encode("utf-8"),
                {"Content-Type": "application/json"})
            created = json.loads(connection.getresponse().read())
            self.assertEqual(created["config"]["base_url"], model.url)
            self.assertEqual(created["config"]["model"], "deployment-model")
            connection.request("POST", f"/api/sessions/{created['id']}/run",
                dumps({"prompt": "hello"}).encode("utf-8"), {"Content-Type": "application/json"})
            stream = connection.getresponse().read()
            self.assertIn(b"run_finished", stream)
            self.assertEqual(model.requests[0]["model"], "deployment-model")
            connection.close()


if __name__ == "__main__":
    unittest.main()
