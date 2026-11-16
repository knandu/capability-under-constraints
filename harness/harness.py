import argparse
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import traceback
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine import HERE, Session, configuration, validate_history
from tools import dumps
from transport import Meter, ModelError


class HarnessServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, api_key="", default_overrides=None):
        self.default_overrides = dict(default_overrides or {})
        configuration(self.default_overrides)
        super().__init__(address, Handler)
        self.sessions, self.api_key = {}, api_key


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        sys.stderr.write(f"{self.log_date_time_string()} HTTP request handled\n")

    def check_request(self):
        allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        host = self.headers.get("Host", "")
        if host not in allowed:
            raise ValueError("Invalid localhost Host header.")
        origin = self.headers.get("Origin")
        if origin is not None and origin != "http://" + host:
            raise ValueError("Cross-origin requests are not allowed.")
        if urlsplit(self.path).query:
            raise ValueError("Query parameters are not used by this instrument.")

    def respond(self, value, status=200):
        data = dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if status >= 400:
            self.close_connection = True
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        if self.headers.get_content_type() != "application/json":
            raise ValueError("Expected application/json.")
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size <= 4 * 1024 * 1024:
            raise ValueError("Request JSON must be between 1 byte and 4 MiB.")
        raw = self.rfile.read(size)
        if len(raw) != size:
            raise ValueError("Incomplete HTTP request.")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("Expected a JSON object.")
        return value

    def do_GET(self):
        try:
            self.check_request()
            if self.path == "/api/defaults":
                return self.respond(configuration(self.server.default_overrides))
            if self.path.startswith("/api/sessions/"):
                identity = self.path.rsplit("/", 1)[-1]
                session = self.server.sessions[identity]
                return self.respond(session.snapshot())
            static = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
                      "/style.css": ("style.css", "text/css")}
            if self.path not in static:
                return self.respond({"error": "Not found."}, 404)
            name, content_type = static[self.path]
            data = (HERE / "static" / name).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        except (ValueError, KeyError) as error:
            self.respond({"error": str(error)}, 400)

    def do_POST(self):
        streaming = False
        try:
            self.check_request()
            value = self.body()
            if self.path in {"/api/sessions", "/api/import"}:
                supplied = value.get("config", {})
                if not isinstance(supplied, dict):
                    raise ValueError("config must be an object.")
                config = {**self.server.default_overrides, **supplied}
                if self.path == "/api/import":
                    config = {**config, "capture": False}
                session = Session(config, self.server.api_key)
                if self.path == "/api/import":
                    if value.get("version") != 1:
                        raise ValueError("Unsupported transcript version.")
                    history = value.get("history", [])
                    validate_history(history)
                    if history and (history[0].get("role") != "user" or history[0].get("content") != value.get("objective")):
                        raise ValueError("Original objective does not match the first user message.")
                    session.history = copy.deepcopy(history)
                    session.transcript = copy.deepcopy(value.get("transcript", history))
                    validate_history(session.transcript)
                    session.objective = value.get("objective", "")
                    session.task_status = value.get("task_status", "Imported.")
                    session.events = copy.deepcopy(value.get("events", []))
                    if not isinstance(session.events, list):
                        raise ValueError("events must be a list.")
                    session.emit("transcript_imported", {"capture": False, "source_config": value.get("config")})
                self.server.sessions[session.id] = session
                return self.respond(session.snapshot(), 201)
            parts = self.path.strip("/").split("/")
            if len(parts) != 4 or parts[:2] != ["api", "sessions"]:
                return self.respond({"error": "Not found."}, 404)
            session = self.server.sessions[parts[2]]
            action = parts[3]
            if action == "stop":
                session.stop()
                return self.respond({"stop_requested": True})
            if action == "config":
                session.update(value)
                return self.respond(session.snapshot())
            if action == "inspect":
                if session.running:
                    raise ValueError("Use the live accounting while a run is active.")
                session.cancel.clear()
                session.meter = Meter(session.transport, session.emit, lambda: session.deadline)
                return self.respond(session.inspect())
            if action != "run":
                return self.respond({"error": "Not found."}, 404)
            if session.running or not isinstance(value.get("prompt"), str) or not value["prompt"].strip():
                raise ValueError("Session is busy or prompt is empty.")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            streaming, self.close_connection = True, True

            def send(event):
                self.wfile.write(("data: " + dumps(event) + "\n\n").encode("utf-8"))
                self.wfile.flush()

            session.run(value["prompt"], send)
        except (ValueError, KeyError, ModelError, OSError) as error:
            if streaming:
                try:
                    self.wfile.write(("data: " + dumps({"type": "http_error", "data": {"message": str(error)}}) + "\n\n").encode("utf-8"))
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    self.log_error("Client disconnected while reporting run failure.")
            else:
                self.respond({"error": str(error)}, 400)
        except Exception:
            traceback.print_exc()
            if not streaming:
                self.respond({"error": "Internal harness error; see server terminal."}, 500)
            else:
                self.close_connection = True


def main():
    parser = argparse.ArgumentParser(description="Minimal localhost model experiment harness.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--base-url", help="Default localhost model API base URL.")
    parser.add_argument("--model", help="Default model identifier.")
    parser.add_argument("--api-key-env", help="Optional environment variable containing the model API key; never exported.")
    args = parser.parse_args()
    key = os.environ[args.api_key_env] if args.api_key_env else ""
    overrides = {name: getattr(args, name) for name in ("base_url", "model") if getattr(args, name) is not None}
    with HarnessServer(("127.0.0.1", args.port), key, overrides) as server:
        print(f"Model harness: http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.", flush=True)


if __name__ == "__main__":
    main()
