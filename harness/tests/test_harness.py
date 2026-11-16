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
from documents import DocumentWorkflow, align_chunk, validate_document


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
        if message.get("reasoning_content"):
            for character in message["reasoning_content"]:
                events.append({"choices": [{"delta": {"reasoning_content": character}}]})
        if payload.get("return_progress"):
            events.append({"choices": [], "prompt_progress": {"total": 100, "cache": 20, "processed": 80, "time_ms": 10}})
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
            output, errors = self.root / "browser-dom.html", self.root / "browser-errors.txt"
            # Browser children can inherit pipes after the main process exits.
            with output.open("wb") as stdout, errors.open("wb") as stderr:
                result = subprocess.run([str(edge), "--headless=new", "--disable-gpu",
                    "--no-first-run", "--no-default-browser-check", "--disable-background-networking",
                    f"--user-data-dir={self.root / 'browser-profile'}", "--virtual-time-budget=3000",
                    "--dump-dom", f"http://127.0.0.1:{server.server_port}/"],
                    stdout=stdout, stderr=stderr, timeout=30)
        dom = output.read_text(encoding="utf-8", errors="replace")
        self.assertEqual(result.returncode, 0, errors.read_text(encoding="utf-8", errors="replace"))
        self.assertIn('data-browser-check="passed"', dom, dom)

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
            self.assertEqual(session.status, "paused")
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
            self.assertEqual(session.status, "paused")
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

    def test_lossless_cursor_long_line_utf8_bounding_and_beyond_read_prefix(self):
        source = b"\xef\xbb\xbf" + (TAMIL * 80 + "\r\nend").encode("utf-8")
        (self.root / "long.txt").write_bytes(source)
        self.config["read_bytes"] = 137
        offset, parts = 0, []
        limit = {"max_bytes": 400, "max_tokens": 400}
        while offset < len(source):
            full = self.run_tool("view", {"path": "long.txt", "offset": offset})
            result, text = bound_result(full, limit, lambda value: len(value.encode("utf-8")))
            self.assertLessEqual(len(text.encode("utf-8")), 400)
            self.assertEqual(result["start_offset"], offset)
            self.assertGreater(result["next_offset"], offset)
            parts.append(result["text"].encode("utf-8"))
            offset = result["next_offset"]
            self.assertEqual(result["eof"], offset == len(source))
        self.assertEqual(b"".join(parts), source)
        self.assertGreater(offset, self.config["read_bytes"])
        self.assertTrue(self.run_tool("view", {"path": "long.txt", "offset": offset})["eof"])
        for args in ({"offset": 1, "start": 1}, {"offset": -1}, {"offset": len(source) + 1}):
            with self.assertRaises(ToolError):
                self.run_tool("view", {"path": "long.txt", **args})
        with self.assertRaises(ToolError):
            self.run_tool("view", {"path": "long.txt", "offset": 2})

    def document_session(self, model, **changes):
        return self.session(model, **{"workflow": "document", "document_path": "document.txt",
            "checkpoint_directory": str(self.root / "checkpoints"), "document_chunk_bytes": 64,
            "document_fan_in": 2, **changes})

    def test_document_coverage_hierarchy_persistence_and_no_raw_source_checkpoint(self):
        source = ("source-only-UNIQUE " + TAMIL * 3).encode("utf-8")
        (self.root / "document.txt").write_bytes(source)
        replies = [{"role": "assistant", "content": f"note {index}"} for index in range(30)]
        with serving(FakeModel(replies)) as model:
            session = self.document_session(model, max_iterations=50, summary_tokens=64)
            session.run("Summarize the whole document.")
            self.assertEqual(session.status, "completed")
            state = validate_document(session.document)
            self.assertEqual(state["offset"], len(source))
            self.assertGreater(state["chunks"], 2)
            self.assertEqual(len(state["frontier"]), 1)
            self.assertGreater(state["notes"][-1]["level"], 1)
            self.assertEqual(len(model.requests), state["chunks"] * 2)
            self.assertTrue(all(not payload.get("tools") for payload in model.requests))
            self.assertTrue(all(payload["max_tokens"] == 64 for payload in model.requests[:-1]))
            checkpoint = next((self.root / "checkpoints").glob("document-*.json")).read_text(encoding="utf-8")
            self.assertNotIn("source-only-UNIQUE", checkpoint)
            self.assertNotIn("model_request", checkpoint)
            self.assertEqual(json.loads(checkpoint)["document"]["result"], state["result"])
            self.assertEqual(len(session.history), 2)
            self.assertEqual(len([event for event in session.events if event["type"] == "task_complete"]), 1)
            broken = copy.deepcopy(state)
            broken["notes"][1]["start"] += 1
            with self.assertRaisesRegex(ValueError, "gap|overlap"):
                validate_document(broken)

    def test_document_chunks_prefer_complete_sentences_without_gaps(self):
        source = ("1901: Alder opened with two telescopes. " + "Background detail. " * 9 +
                  "1932: Birch opened with five rooms. " + "Background detail. " * 9 +
                  "1978: Cedar opened with seven galleries.").encode("utf-8")
        (self.root / "sentences.txt").write_bytes(source)
        self.config["read_bytes"] = 230
        offset, parts = 0, []
        while offset < len(source):
            chunk = align_chunk(self.run_tool("view", {"path": "sentences.txt", "offset": offset}))
            parts.append(chunk["text"])
            offset = chunk["next_offset"]
        self.assertEqual("".join(parts).encode("utf-8"), source)
        for year, name in (("1901", "Alder"), ("1932", "Birch"), ("1978", "Cedar")):
            self.assertTrue(any(year in part and name in part for part in parts))

    def test_document_budget_pause_http_checkpoint_import_and_resume_same_objective(self):
        (self.root / "document.txt").write_text("x" * 150, encoding="utf-8")
        with serving(FakeModel([{"role": "assistant", "content": "durable note"}] * 20)) as model:
            session = self.document_session(model, max_iterations=1)
            session.run("Read everything.")
            self.assertEqual(session.status, "paused")
            self.assertEqual(session.document["offset"], 64)
            checkpoint = json.loads(next((self.root / "checkpoints").glob("document-*.json")).read_text(encoding="utf-8"))
            with serving(HarnessServer(("127.0.0.1", 0))) as app:
                connection = http.client.HTTPConnection("127.0.0.1", app.server_port, timeout=10)
                connection.request("POST", "/api/import", dumps(checkpoint).encode("utf-8"),
                    {"Content-Type": "application/json"})
                response = connection.getresponse()
                imported = json.loads(response.read())
                self.assertEqual(response.status, 201)
                restored = app.sessions[imported["id"]]
                restored.update({"max_iterations": 20})
                previous = len(model.requests)
                connection.request("POST", f"/api/sessions/{restored.id}/resume", b"{}",
                    {"Content-Type": "application/json"})
                response = connection.getresponse()
                stream = response.read()
                self.assertIn(b"run_finished", stream)
                self.assertEqual(restored.status, "completed")
                self.assertEqual(restored.objective, "Read everything.")
                observations = json.loads(model.requests[previous]["messages"][-1]["content"])["observations"]
                self.assertEqual(observations["start_offset"], 64)
                self.assertEqual(len([item for item in restored.history if item["role"] == "user"]), 1)
                self.assertGreater(restored.document["iterations"], 1)
                connection.close()

    def test_document_interrupted_summary_retains_cursor_and_rejects_changed_source(self):
        path = self.root / "document.txt"
        path.write_text("original source " * 10, encoding="utf-8")
        with serving(FakeModel([{"role": "assistant", "content": "late note"}])) as model:
            model.delay = 2
            session = self.document_session(model, max_seconds=1)
            session.run("Summarize all.")
            self.assertEqual(session.status, "paused")
            self.assertEqual(session.document["offset"], 0)
            self.assertEqual(session.document["notes"], [])
            self.assertGreaterEqual(session.document["elapsed_seconds"], 1)
            path.write_text("different document", encoding="utf-8")
            session.update({"max_seconds": 30})
            session.run(resume=True)
            self.assertEqual(session.status, "error")
            self.assertTrue(any("changed since" in event["data"].get("message", "") for event in session.events))
            self.assertEqual(session.document["offset"], 0)

    def test_document_early_completion_and_overlong_summary_do_not_advance(self):
        (self.root / "document.txt").write_text("source" * 50, encoding="utf-8")
        for reply in (tool("task_complete", {"summary": "done"}),
                      {"role": "assistant", "content": "partial", "finish_reason": "length"}):
            with self.subTest(reply=reply), serving(FakeModel([reply, reply])) as model:
                session = self.document_session(model)
                session.run("Read all.")
                self.assertNotEqual(session.status, "completed")
                self.assertEqual(session.document["offset"], 0)
                self.assertFalse(any(event["type"] == "task_complete" for event in session.events))

    def test_document_merge_retries_compactly_before_growing_output_without_committing_partial_notes(self):
        (self.root / "document.txt").write_text("x" * 128, encoding="utf-8")
        replies = [{"role": "assistant", "content": f"leaf {index}"} for index in range(2)]
        replies += [{"role": "assistant", "content": "UNCOMMITTED partial", "finish_reason": "length"}] * 2
        replies += [{"role": "assistant", "content": "merged complete"}, {"role": "assistant", "content": "final complete"}]
        with serving(FakeModel(replies)) as model:
            session = self.document_session(model, max_iterations=30,
                summary_tokens=64, max_output=256)
            session.run("Read all.")
            self.assertEqual(session.status, "completed")
            self.assertEqual([payload["max_tokens"] for payload in model.requests[2:5]], [64, 64, 128])
            self.assertNotIn("COMPACT RETRY", model.requests[2]["messages"][0]["content"])
            self.assertIn("COMPACT RETRY", model.requests[3]["messages"][0]["content"])
            self.assertEqual(session.document["chunks"], 2)
            self.assertNotIn("UNCOMMITTED", dumps(session.document))
            self.assertEqual(len([event for event in session.events if event["type"] == "document_retry"]), 2)
            validate_document(session.document)

    def test_document_merge_learns_smaller_batch_and_preserves_it_across_checkpoint_import(self):
        (self.root / "document.txt").write_text("x" * 512, encoding="utf-8")

        def reply(payload):
            observations = json.loads(payload["messages"][-1]["content"])["observations"]
            return {"role": "assistant", "content": "too much" if isinstance(observations, list)
                    and len(observations) > 2 else "complete note",
                    "finish_reason": "length" if isinstance(observations, list) and len(observations) > 2 else "stop"}

        with serving(FakeModel([reply] * 20)) as model:
            session = self.document_session(model, document_fan_in=4, max_iterations=11,
                summary_tokens=64, max_output=256)
            session.run("Read all.")
            self.assertEqual(session.status, "paused")
            retries = [event["data"] for event in session.events if event["type"] == "document_retry"]
            self.assertEqual([(item["previous_batch_size"], item["next_batch_size"]) for item in retries],
                             [(4, 4), (4, 2)])
            self.assertEqual(session.document["merge_fan_in"], 2)
            checkpoint = json.loads(next((self.root / "checkpoints").glob("document-*.json")).read_text(encoding="utf-8"))
            with serving(HarnessServer(("127.0.0.1", 0))) as app:
                connection = http.client.HTTPConnection("127.0.0.1", app.server_port, timeout=10)
                connection.request("POST", "/api/import", dumps(checkpoint).encode("utf-8"),
                    {"Content-Type": "application/json"})
                response = connection.getresponse()
                imported = json.loads(response.read())
                self.assertEqual(response.status, 201)
                restored = app.sessions[imported["id"]]
                restored.update({"max_iterations": 40})
                previous = len(model.requests)
                restored.run(resume=True)
                self.assertEqual(restored.status, "completed")
                observations = [json.loads(payload["messages"][-1]["content"])["observations"]
                                for payload in model.requests[previous:]]
                self.assertTrue(all(isinstance(parts, list) and len(parts) <= 2 for parts in observations))
                self.assertEqual(restored.document["chunks"], 8)
                connection.close()
            legacy = copy.deepcopy(session.document)
            legacy.pop("merge_fan_in")
            validate_document(legacy)
            for invalid in (True, 1, 33, "2"):
                with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, "fan-in"):
                    validate_document({**legacy, "merge_fan_in": invalid})
            validate_document(session.document)

    def test_document_intermediate_targets_do_not_expand_with_final_budget(self):
        (self.root / "document.txt").write_text("source", encoding="utf-8")
        with serving(FakeModel([])) as model:
            session = self.document_session(model, context=20480, summary_tokens=4000, max_output=4000)
            workflow = DocumentWorkflow(session)
            for kind in ("document_chunk", "document_merge"):
                normal = workflow.payload(kind, [])
                compact = workflow.payload(kind, [], compact=True)
                self.assertIn("at most 256 words", normal["messages"][0]["content"])
                self.assertIn("at most 96 words", compact["messages"][0]["content"])
                self.assertEqual(normal["max_tokens"], compact["max_tokens"])
            final = workflow.payload("document_final", [])
            self.assertNotIn("at most 256 words", final["messages"][0]["content"])
            self.assertNotIn("compact intermediate note", final["messages"][0]["content"])

    def test_document_chunk_retries_compactly_without_duplicate_coverage(self):
        (self.root / "document.txt").write_text("source", encoding="utf-8")
        replies = [{"role": "assistant", "content": "UNCOMMITTED", "finish_reason": "length"},
                   {"role": "assistant", "content": "compact note"},
                   {"role": "assistant", "content": "final"}]
        with serving(FakeModel(replies)) as model:
            session = self.document_session(model)
            session.run("Read everything.")
            self.assertEqual(session.status, "completed")
            self.assertEqual(session.document["chunks"], 1)
            self.assertEqual(session.document["offset"], 6)
            self.assertNotIn("UNCOMMITTED", dumps(session.document))
            self.assertIn("COMPACT RETRY", model.requests[1]["messages"][0]["content"])

    def test_exhausted_two_note_merge_resumes_without_rereading_source(self):
        (self.root / "document.txt").write_text("x" * 128, encoding="utf-8")
        replies = [{"role": "assistant", "content": "leaf"}] * 2
        replies += [{"role": "assistant", "content": "partial", "finish_reason": "length"}] * 2
        replies += [{"role": "assistant", "content": "merged"}, {"role": "assistant", "content": "final"}]
        with serving(FakeModel(replies)) as model:
            session = self.document_session(model, summary_tokens=64, max_output=64)
            session.run("Read all.")
            self.assertEqual(session.status, "paused")
            self.assertEqual((session.document["offset"], len(session.document["frontier"])), (128, 2))
            first = len(model.requests)
            session.update({"max_output": 128})
            session.run(resume=True)
            self.assertEqual(session.status, "completed")
            for payload in model.requests[first:]:
                self.assertIsInstance(json.loads(payload["messages"][-1]["content"])["observations"], list)
            self.assertEqual(session.document["chunks"], 2)
            self.assertNotIn("partial", dumps(session.document))

    def test_document_final_retries_compactly_and_pauses_if_still_truncated(self):
        (self.root / "document.txt").write_text("x", encoding="utf-8")
        for twice in (False, True):
            replies = [{"role": "assistant", "content": "leaf"},
                {"role": "assistant", "content": "partial final", "finish_reason": "length"},
                {"role": "assistant", "content": "partial again" if twice else "complete final",
                 "finish_reason": "length" if twice else "stop"}]
            with self.subTest(twice=twice), serving(FakeModel(replies)) as model:
                session = self.document_session(model)
                session.run("Read all.")
                self.assertEqual(session.status, "paused" if twice else "completed")
                self.assertEqual(session.document["offset"], 1)
                self.assertNotIn("partial", dumps(session.document))
                self.assertIn("Finish comfortably below", model.requests[-1]["messages"][0]["content"])
                self.assertEqual(any(event["type"] == "task_complete" for event in session.events), not twice)

    def test_document_empty_file_and_checkpoint_write_failure(self):
        (self.root / "document.txt").write_bytes(b"")
        with serving(FakeModel([{"role": "assistant", "content": "The document is empty."}])) as model:
            session = self.document_session(model)
            session.run("Summarize all.")
            self.assertEqual(session.status, "completed")
            self.assertEqual(session.document["chunks"], 0)
            self.assertEqual(len(model.requests), 1)
            validate_document(session.document)
            blocked = self.root / "not-a-directory"
            blocked.write_text("unchanged", encoding="utf-8")
            session = self.session(model, workflow="document", document_path="document.txt",
                checkpoint_directory=str(blocked))
            session.run("Summarize all.")
            self.assertEqual(session.status, "error")
            self.assertEqual(blocked.read_text(encoding="utf-8"), "unchanged")
            self.assertFalse(any(event["type"] == "task_complete" for event in session.events))

    def test_resume_chat_does_not_add_another_user_prompt(self):
        with serving(FakeModel([{"role": "assistant", "content": "working"},
                                tool("task_complete", {"summary": "done"})])) as model:
            session = self.session(model, explicit_completion=True, max_iterations=1)
            session.run("Original objective")
            self.assertEqual(session.status, "paused")
            users = len([item for item in session.history if item["role"] == "user"])
            session.run(resume=True)
            self.assertEqual(session.status, "completed")
            self.assertEqual(users, len([item for item in session.history if item["role"] == "user"]))
            with self.assertRaisesRegex(ValueError, "new session"):
                session.update({"workflow": "document", "document_path": "x"})

    def test_reasoning_and_prompt_progress_are_observed_not_invented_or_added_to_history(self):
        secret = "secret-reasoning-key"
        for streaming in (True, False):
            with self.subTest(streaming=streaming), serving(FakeModel([
                    {"role": "assistant", "content": "answer", "reasoning_content": secret + TAMIL}],
                    streaming=streaming)) as model:
                session = Session({**self.config, "base_url": model.url, "server_progress": True, "capture": True}, secret)
                streamed = []
                session.run("hello", streamed.append)
                self.assertEqual(session.status, "answered")
                self.assertTrue(any(item["type"] == "reasoning_delta" for item in streamed))
                self.assertFalse(any(item["type"] == "reasoning_delta" for item in session.events))
                self.assertNotIn("reasoning_content", dumps(session.history))
                progress = [item["data"] for item in session.events if item["type"] == "model_progress"]
                if streaming:
                    self.assertTrue(any("prompt_progress" in item for item in progress))
                self.assertEqual(progress[-1]["reasoning_characters"], len(secret + TAMIL))
                self.assertNotIn(secret, dumps(session.snapshot()))
                for file in session.capture.path.iterdir():
                    self.assertNotIn(secret.encode("utf-8"), file.read_bytes())
                self.assertNotIn("reasoning_tokens", dumps(progress))

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
            restored = json.loads(body)
            self.assertEqual(restored["history"][-1]["content"], TAMIL)
            self.assertFalse(restored["config"]["capture"])
            self.assertEqual(restored["status"], "answered")
            status, _ = post(f"/api/sessions/{restored['id']}/resume", {})
            self.assertEqual(status, 400)
            connection.close()
            connection = http.client.HTTPConnection("127.0.0.1", app.server_port)
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
