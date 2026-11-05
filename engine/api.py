"""The Magic CAD engine API: a local HTTP server over engine.projects. Test seam 1 of the spec.

    .venv/bin/python magic.py serve [--port 8766]

    GET  /health                         engine identity
    POST /runs                           {"project": "/abs/folder", "samples"?, "timeout"?, "wait"?}
                                         202 with the queued run; with "wait": true, 200 once it is done
    GET  /runs                           every run since the engine started, newest first
    GET  /runs/<id>                      status (queued | running | done | error) and, when done, the verdict
    GET  /runs/<id>/events               Server-Sent Events: the whole history, then live events,
                                         then an "end" event. Honours Last-Event-ID.
    GET  /runs/<id>/artifacts/<path>     a file from the project's outputs folder (STL, STEP, PNG, report)

Bound to 127.0.0.1 and checks the Host header (refuses DNS rebinding). POST needs
Content-Type: application/json, which a web page cannot send cross-origin without a
preflight this server never answers. Runs execute one at a time, in order: the gates share
the CPU and the renderer, and a verdict must never depend on what else was running.
"""
import json
import queue
import re
import threading
import traceback
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .projects import ARTIFACT_TYPES, ProjectError, artifact_path, designs_of, run_project

HOST = "127.0.0.1"
PORT = 8766  # the plain-JS UI server keeps 8765
API_VERSION = 1
TERMINAL = ("done", "error")
RUN_PATH = re.compile(r"^/runs/([0-9a-f]{32})(/events|/artifacts/(.+))?$")


class Run:
    def __init__(self, project, samples, timeout):
        self.id = uuid.uuid4().hex
        self.project, self.samples, self.timeout = project, samples, timeout
        self.status, self.verdict, self.error = "queued", None, None
        self.created = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.events = []
        self.changed = threading.Condition()

    def emit(self, event):
        with self.changed:
            self.events.append({"id": len(self.events) + 1, **event})
            self.changed.notify_all()

    def set_status(self, status):
        with self.changed:
            self.status = status
            self.changed.notify_all()

    def summary(self):
        return {"id": self.id, "project": str(self.project), "status": self.status,
                "created": self.created, "events": len(self.events), "verdict": self.verdict,
                "error": self.error, "links": {"self": f"/runs/{self.id}",
                                               "events": f"/runs/{self.id}/events",
                                               "artifacts": f"/runs/{self.id}/artifacts/"}}


class Engine:
    """The run registry and its single worker thread."""

    def __init__(self):
        self.runs, self.pending = {}, queue.Queue()
        self.lock = threading.Lock()
        threading.Thread(target=self.work, name="engine-runs", daemon=True).start()

    def submit(self, project, samples=None, timeout=180):
        project = Path(project).expanduser().resolve()
        designs_of(project)  # refuse a non-project before it is queued
        run = Run(project, samples, timeout)
        with self.lock:
            self.runs[run.id] = run
        run.emit({"type": "queued", "project": str(project)})
        self.pending.put(run)
        return run

    def work(self):
        while True:
            run = self.pending.get()
            run.set_status("running")
            try:
                _, run.verdict = run_project(run.project, run.emit, run.samples, run.timeout)
                run.set_status("done")
            except Exception as err:  # the run fails; the engine keeps serving
                run.error = f"{type(err).__name__}: {err}"
                run.emit({"type": "error", "error": run.error, "traceback": traceback.format_exc()})
                run.set_status("error")

    def get(self, run_id):
        with self.lock:
            return self.runs.get(run_id)

    def all(self):
        with self.lock:
            return sorted(self.runs.values(), key=lambda r: r.created, reverse=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "MagicCADEngine/1"
    engine = None  # set by make_server

    def log_message(self, fmt, *args):  # quiet: the CLI prints its own lines
        pass

    def host_ok(self):
        port = self.server.server_address[1]
        if self.headers.get("Host") in {f"localhost:{port}", f"127.0.0.1:{port}"}:
            return True
        self.reply(HTTPStatus.FORBIDDEN, {"error": "unexpected Host header"})
        return False

    def reply(self, status, body):
        data = json.dumps(body, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.host_ok():
            return
        path = urlsplit(self.path).path
        if path == "/health":
            return self.reply(HTTPStatus.OK, {"engine": "magic-cad", "api": API_VERSION})
        if path == "/runs":
            return self.reply(HTTPStatus.OK, {"runs": [r.summary() for r in self.engine.all()]})
        match = RUN_PATH.match(path)
        run = self.engine.get(match.group(1)) if match else None
        if not run:
            return self.reply(HTTPStatus.NOT_FOUND, {"error": "no such run"})
        if match.group(2) == "/events":
            return self.stream(run)
        if match.group(3):
            return self.artifact(run, unquote(match.group(3)))
        return self.reply(HTTPStatus.OK, run.summary())

    def do_POST(self):
        if not self.host_ok():
            return
        if urlsplit(self.path).path != "/runs":
            return self.reply(HTTPStatus.NOT_FOUND, {"error": "no such endpoint"})
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            return self.reply(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "send application/json"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            samples, timeout = body.get("samples"), int(body.get("timeout", 180))
            if samples is not None:
                samples = int(samples)
            run = self.engine.submit(body["project"], samples, timeout)
        except (KeyError, TypeError, ValueError, AttributeError) as err:
            message = str(err) if isinstance(err, ProjectError) else f"bad request: {err!r}"
            return self.reply(HTTPStatus.BAD_REQUEST, {"error": message})
        if body.get("wait"):
            with run.changed:
                run.changed.wait_for(lambda: run.status in TERMINAL)
            return self.reply(HTTPStatus.OK, run.summary())
        return self.reply(HTTPStatus.ACCEPTED, run.summary())

    def stream(self, run):
        """SSE: replay from Last-Event-ID, then follow live until the run ends."""
        try:
            sent = int(self.headers.get("Last-Event-ID", 0))
        except ValueError:
            sent = 0
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            while True:
                with run.changed:
                    run.changed.wait_for(lambda: len(run.events) > sent or run.status in TERMINAL,
                                         timeout=15)
                    fresh, ended = run.events[sent:], run.status in TERMINAL
                for event in fresh:
                    self.wfile.write(f"id: {event['id']}\nevent: {event['type']}\n"
                                     f"data: {json.dumps(event)}\n\n".encode())
                sent += len(fresh)
                if ended and not fresh:
                    self.wfile.write(f"event: end\ndata: {json.dumps({'status': run.status})}\n\n".encode())
                    self.wfile.flush()
                    return
                if not fresh:
                    self.wfile.write(b": keep-alive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return  # the client went away; the run carries on

    def artifact(self, run, relative):
        target = artifact_path(run.project, relative)
        if not target:
            return self.reply(HTTPStatus.NOT_FOUND, {"error": "no such artifact"})
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ARTIFACT_TYPES[target.suffix])
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def make_server(port=PORT, engine=None):
    """A ready, not yet serving, engine server. port=0 picks a free port (tests)."""
    handler = type("EngineHandler", (Handler,), {"engine": engine or Engine()})
    server = ThreadingHTTPServer((HOST, port), handler)
    server.daemon_threads = True
    return server


def serve(port=PORT):
    server = make_server(port)
    print(f"Magic CAD engine API on http://{HOST}:{server.server_address[1]}  (Ctrl-C stops)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
